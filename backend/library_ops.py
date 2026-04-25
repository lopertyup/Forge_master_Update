"""
============================================================
  FORGE MASTER — Library operations

  Pure functions over the pet / mount / skill libraries. They
  used to live as `@staticmethod` / private methods on
  `GameController`; pulling them out makes the controller
  shorter and lets the smoke tests cover them directly without
  spinning up a controller (and its file I/O on import).

  None of these functions hold state; the library dict is
  always passed in. `remove_entry` takes a `save_fn` so
  callers can pick whichever persistence module fits the
  library type (pets / mount / skills).
============================================================
"""

from __future__ import annotations

from typing import Callable, Dict, Optional, Tuple

from .parser import parse_companion_meta


def find_key(library: Dict[str, Dict], name: str) -> Optional[str]:
    """Look up `name` in the library case-insensitively.

    Returns the exact key as stored in the dict (preserving the
    library's original casing) or None if the name is unknown.
    """
    name_lc = name.lower()
    for key in library:
        if key.lower() == name_lc:
            return key
    return None


def lv1_version_of(companion: Dict, library: Dict[str, Dict]) -> Dict:
    """Return a Lv.1-equivalent of an equipped pet/mount.

    Used for swap comparisons: % stats (lifesteal, attack_speed, etc.)
    are kept as-is — only the FLAT stats (hp_flat / damage_flat) are
    pulled from the library so the comparison stays at "equal level".

    If the companion isn't in the library (no `__name__`, or unknown
    name), the input is returned unchanged (best effort).
    """
    if not companion:
        return companion
    name = companion.get("__name__")
    if not name:
        return dict(companion)
    key = find_key(library, name)
    if key is None:
        return dict(companion)
    ref = library[key]
    out = dict(companion)
    out["hp_flat"]     = float(ref.get("hp_flat", 0.0))
    out["damage_flat"] = float(ref.get("damage_flat", 0.0))
    return out


def resolve_companion(
    text: str,
    library: Dict[str, Dict],
) -> Tuple[Optional[Dict], str, Optional[Dict]]:
    """
    Common pet/mount resolution logic:
      1. parse text → meta (name/rarity/level) + stats
      2. if name unknown → reject (status "unknown")
      3. if name known  → status "ok", hp_flat / damage_flat kept from
         the scan (current level); Lv.1 reference values stay in the
         library for swap simulations (see `lv1_version_of`).

    The library is treated as read-only: no auto-add, no placeholder
    fill-in. Unknown names are always surfaced back to the user.

    The returned dict is a COMPLETE companion (same keys as parse_pet),
    ready to be passed to apply_pet / apply_mount.

    status ∈ {"ok", "unknown", "no_name"}
      - "ok"      : name found in library
      - "unknown" : name not in library → companion = None
      - "no_name" : couldn't extract a name from the text → None
    """
    meta  = parse_companion_meta(text)
    name  = meta.get("name")
    level = meta.get("level")
    stats = dict(meta.get("stats") or {})

    if not name:
        return None, "no_name", meta

    key = find_key(library, name)
    if key is None:
        return None, "unknown", meta

    # Keep the ACTUAL scanned hp_flat / damage_flat (current level).
    # The Lv.1 reference values stay in the library and are looked up
    # only when running swap simulations (see lv1_version_of).
    ref = library[key]

    # Annotate the resolved companion with its identity + level (used
    # by the UI to show name + icon + level of the equipped slot).
    stats["__name__"]   = key
    stats["__rarity__"] = str(ref.get("rarity", "common")).lower()
    if level is not None:
        stats["__level__"] = int(level)
    return stats, "ok", meta


def remove_entry(
    name: str,
    library: Dict[str, Dict],
    save_fn: Callable[[Dict[str, Dict]], None],
) -> bool:
    """Delete `name` from `library` (case-insensitive) and persist.

    Returns True on success, False if the name was not found.
    """
    key = find_key(library, name)
    if key is None:
        return False
    del library[key]
    save_fn(library)
    return True
