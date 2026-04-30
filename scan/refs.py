"""
============================================================
  FORGE MASTER — Reference image loader for scan/

  Loads PNG references from ``data/icons/`` once, pre-computes
  the grayscale + RGB arrays the matcher consumes, and caches
  the result so subsequent scans are zero-IO.

  Three loading modes covering every job in the unified
  pipeline (cf. SCAN_REFACTOR.txt §3):

      mode="exact"     — ``data/icons/equipment/<Age>/<Slot>/``
                         A single (age, slot) folder. Used by
                         STRAT A when the colour heuristic
                         confidently picks an age.

      mode="all_ages"  — ``data/icons/equipment/*/<Slot>/``
                         All 10 ages for a given slot. Used by
                         STRAT B when colour is ambiguous; each
                         Reference carries its source age so
                         the matcher can recover it from the
                         winning candidate.

      mode="flat"      — ``data/icons/<category>/`` where
                         category ∈ {pets, mount, skills}.
                         No age, no slot — the auto-mapping
                         JSON files supply the rest of the
                         metadata.

  All caches are module-level dicts keyed by the load
  parameters. Call ``reset_caches()`` if reference PNGs are
  renamed at runtime (e.g. an admin script that batch-edits
  ``data/icons/``) so subsequent scans pick up the new
  filenames.

  Public API:

      Reference                           — dataclass with
                                              stem / arrays /
                                              metadata
      load_references(category, ...)      — main entry point
      reset_caches()                      — drops every cache
      list_supported_categories()         — debugging helper
============================================================
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

from .core import autocrop_reference, to_gray_arr, to_rgb_arr

log = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────
#  Path constants — single source of truth
# ────────────────────────────────────────────────────────────
#
# scan/ lives at the project root (next to backend/), so two
# parents up is the project root and ``data/`` is the sibling
# of ``backend``. We keep our own copy of the path constants
# rather than importing them from backend.data.libraries to
# minimise coupling — the only reason to share that module is
# the AutoItemMapping dict, which we lazy-load via load_libs
# inside each loader so the import graph stays clean.

_ROOT      = Path(__file__).resolve().parent.parent
_DATA_DIR  = _ROOT / "data"
_ICONS_DIR = _DATA_DIR / "icons"


# Mirror of backend.data.libraries.AGE_INT_TO_FOLDER. Kept
# here so scan/ can be imported without pulling backend on
# headless test runs. Must stay in sync with the backend copy.
AGE_INT_TO_FOLDER: Dict[int, str] = {
    0: "Primitive",
    1: "Medieval",
    2: "Early-Modern",
    3: "Modern",
    4: "Space",
    5: "Interstellar",
    6: "Multiverse",
    7: "Quantum",
    8: "Underworld",
    9: "Divine",
}

# Mirror of backend.data.libraries.SLOT_TO_FOLDER.
SLOT_TO_FOLDER: Dict[str, str] = {
    "Helmet":   "Headgear",
    "Body":     "Armor",
    "Gloves":   "Glove",
    "Necklace": "Neck",
    "Ring":     "Ring",
    "Weapon":   "Weapon",
    "Shoe":     "Foot",
    "Belt":     "Belt",
}

# Slot type ids (mirrors AutoItemMapping.Type) — needed by
# equipment loaders to filter the auto-mapping JSON entries
# down to the right slot.
SLOT_TO_TYPE_ID: Dict[str, int] = {
    "Helmet":   0,
    "Body":     1,
    "Gloves":   2,
    "Necklace": 3,
    "Ring":     4,
    "Weapon":   5,
    "Shoe":     6,
    "Belt":     7,
}


# Categories accepted by load_references. Equipment lives in
# its own per-age/per-slot tree; the others are flat.
SUPPORTED_CATEGORIES: Tuple[str, ...] = ("equipment", "pets", "mount", "skills")
SUPPORTED_MODES:      Tuple[str, ...] = ("exact", "all_ages", "flat")


# ────────────────────────────────────────────────────────────
#  Reference dataclass
# ────────────────────────────────────────────────────────────


@dataclass
class Reference:
    """One pre-processed PNG reference, ready for the matcher.

    Fields:

        stem     — filename stem (e.g. "BlackBow", "Crab").
        gray     — 128×128 uint8 grayscale array.
        rgb      — 128×128 uint8 RGB array.
        age      — Age int when the reference came from an
                   age-aware folder (equipment); None for flat
                   categories.
        slot     — slot name when known; None for flat.
        category — "equipment" / "pets" / "mount" / "skills"
                   so callers can disambiguate mixed lists.
        payload  — auto-mapping metadata: ``{"idx", "name",
                   "rarity", ...}`` when the JSON had an entry
                   for this sprite. Empty dict otherwise.
    """

    stem: str
    gray: "Any"
    rgb:  "Any"
    age:      Optional[int] = None
    slot:     Optional[str] = None
    category: str = "equipment"
    payload:  Dict[str, Any] = field(default_factory=dict)


# ────────────────────────────────────────────────────────────
#  Caches
# ────────────────────────────────────────────────────────────
#
# We keep one cache per (category, mode, age, slot) tuple. The
# combined keyspace is small (10 ages × 8 slots × 3 modes plus
# 3 flat categories) so a plain dict is fine.

_cache: Dict[Tuple[str, str, Optional[int], Optional[str]],
             List[Reference]] = {}


def reset_caches() -> None:
    """Drop every cached reference list.

    Call if reference PNGs are renamed at runtime (e.g. an
    admin script that batch-edits ``data/icons/``) so
    subsequent scans pick up the new filenames. Cf.
    SCAN_REFACTOR.txt §8 V1.
    """
    _cache.clear()


def list_supported_categories() -> Tuple[str, ...]:
    """Debugging helper. Returns the tuple of category names
    accepted by ``load_references``."""
    return SUPPORTED_CATEGORIES


# ────────────────────────────────────────────────────────────
#  Auto-mapping access
# ────────────────────────────────────────────────────────────


def _load_libs() -> Dict[str, Any]:
    """Thin wrapper around ``backend.data.libraries.load_libs``.

    Lazy-imported so ``scan.refs`` can be exercised in tests
    that stub ``data/icons`` but do not provide a full backend
    package. Returns an empty dict when the import fails — the
    loaders treat absent metadata as "skip this png with a
    warning" exactly like the legacy implementation.
    """
    try:
        from backend.data.libraries import load_libs as _load
    except Exception:  # pragma: no cover - defensive
        log.exception("scan.refs: cannot import backend.data.libraries")
        return {}
    try:
        return _load() or {}
    except Exception:  # pragma: no cover - defensive
        log.exception("scan.refs: load_libs() raised")
        return {}


# ────────────────────────────────────────────────────────────
#  Internal builders — one per (category, mode)
# ────────────────────────────────────────────────────────────


def _open_rgba(path: Path) -> Optional[Image.Image]:
    try:
        return Image.open(path).convert("RGBA")
    except Exception:
        log.exception("scan.refs: cannot open %s", path)
        return None


def _build_reference(
    png_path: Path,
    *,
    age: Optional[int],
    slot: Optional[str],
    category: str,
    payload: Dict[str, Any],
) -> Optional[Reference]:
    """Open + autocrop + array-ise a single PNG into a
    Reference. Returns None on read errors so callers can skip."""
    img = _open_rgba(png_path)
    if img is None:
        return None
    cropped = autocrop_reference(img)
    return Reference(
        stem=png_path.stem,
        gray=to_gray_arr(cropped),
        rgb=to_rgb_arr(cropped),
        age=age,
        slot=slot,
        category=category,
        payload=payload,
    )


def _equipment_payloads_for(age: int, slot: str) -> Dict[str, Dict[str, Any]]:
    """Return ``{sprite_stem: {"idx", "name"}}`` for one
    (age, slot) cell, by filtering the AutoItemMapping JSON
    down to entries matching that slot's Type id and Age.
    Empty dict when AutoItemMapping is unavailable.
    """
    auto = _load_libs().get("auto_item_mapping", {}) or {}
    type_id = SLOT_TO_TYPE_ID.get(slot)
    if type_id is None:
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for entry in auto.values():
        if entry.get("Age") != age or entry.get("Type") != type_id:
            continue
        sprite = entry.get("SpriteName")
        if not sprite:
            continue
        out[sprite] = {
            "idx":  entry.get("Idx"),
            "name": entry.get("ItemName"),
            "type_id": type_id,
        }
    return out


def _flat_payloads(category: str) -> Dict[str, Dict[str, Any]]:
    """Return ``{sprite_stem: {...auto-mapping fields...}}``
    for the flat categories (pets / mount / skills). The keys
    of the returned payload follow the JSON's own naming so
    job code can read them as-is.
    """
    libs = _load_libs()
    if category == "pets":
        auto = libs.get("auto_pet_mapping", {}) or {}
        return {
            v["SpriteName"]: {
                "id":     v.get("Id"),
                "rarity": v.get("Rarity"),
                "name":   v.get("PetName"),
            }
            for v in auto.values()
            if v.get("SpriteName")
        }
    if category == "mount":
        auto = libs.get("auto_mount_mapping", {}) or {}
        return {
            v["SpriteName"]: {
                "id":     v.get("Id"),
                "rarity": v.get("Rarity"),
                "name":   v.get("MountName"),
            }
            for v in auto.values()
            if v.get("SpriteName")
        }
    if category == "skills":
        auto = libs.get("auto_skill_mapping", {}) or {}
        return {
            v["SpriteName"]: {
                "name":   v.get("Type"),
                "rarity": v.get("Rarity"),
            }
            for v in auto.values()
            if v.get("SpriteName")
        }
    return {}


def _load_equipment_exact(age: int, slot: str) -> List[Reference]:
    """``mode="exact"`` — single (age, slot) folder."""
    age_folder  = AGE_INT_TO_FOLDER.get(age)
    slot_folder = SLOT_TO_FOLDER.get(slot)
    if not age_folder or not slot_folder:
        log.warning("scan.refs: unknown age=%r slot=%r", age, slot)
        return []
    folder = _ICONS_DIR / "equipment" / age_folder / slot_folder
    if not folder.is_dir():
        log.warning("scan.refs: missing folder %s", folder)
        return []

    payloads = _equipment_payloads_for(age, slot)
    out: List[Reference] = []
    for png in sorted(folder.glob("*.png")):
        ref = _build_reference(
            png,
            age=age, slot=slot,
            category="equipment",
            payload=payloads.get(png.stem, {}),
        )
        if ref is not None:
            out.append(ref)
    return out


def _load_equipment_all_ages(slot: str) -> List[Reference]:
    """``mode="all_ages"`` — every age for one slot.

    Each Reference keeps its source age so the matcher's
    winning candidate carries it back to the caller.
    """
    out: List[Reference] = []
    for age_int in sorted(AGE_INT_TO_FOLDER):
        out.extend(_load_equipment_exact(age_int, slot))
    return out


def _load_flat(category: str) -> List[Reference]:
    """``mode="flat"`` — pets / mount / skills.

    The folder is the lower-cased category name (the legacy
    convention used in ``data/icons/``).
    """
    folder_name = {
        "pets":   "pets",
        "mount":  "mount",
        "skills": "skills",
    }.get(category)
    if folder_name is None:
        log.warning("scan.refs: unknown flat category %r", category)
        return []
    folder = _ICONS_DIR / folder_name
    if not folder.is_dir():
        log.warning("scan.refs: missing folder %s", folder)
        return []

    payloads = _flat_payloads(category)
    out: List[Reference] = []
    for png in sorted(folder.glob("*.png")):
        payload = payloads.get(png.stem)
        if payload is None:
            # Skip unreferenced PNGs but log them so devs
            # know to update the AutoXxxMapping JSON.
            log.warning("scan.refs: %s/%s.png has no auto-mapping entry",
                        folder_name, png.stem)
            continue
        ref = _build_reference(
            png,
            age=None, slot=None,
            category=category,
            payload=payload,
        )
        if ref is not None:
            out.append(ref)
    return out


# ────────────────────────────────────────────────────────────
#  Public dispatcher
# ────────────────────────────────────────────────────────────


def load_references(
    category: str,
    *,
    age:  Optional[int] = None,
    slot: Optional[str] = None,
    mode: str = "exact",
) -> List[Reference]:
    """Return a cached list of pre-processed references.

    Parameters
    ----------
    category : str
        One of ``"equipment"`` / ``"pets"`` / ``"mount"`` /
        ``"skills"``.
    age : int, optional
        Required when ``category == "equipment"`` and
        ``mode == "exact"``. Ignored otherwise.
    slot : str, optional
        Required when ``category == "equipment"`` (any mode).
        One of ``"Helmet"`` / ``"Body"`` / ``"Gloves"`` /
        ``"Necklace"`` / ``"Ring"`` / ``"Weapon"`` /
        ``"Shoe"`` / ``"Belt"``.
    mode : str
        ``"exact"`` (default) — equipment, single (age, slot).
        ``"all_ages"``         — equipment, every age for slot.
        ``"flat"``             — pets / mount / skills.

    Returns
    -------
    list[Reference]
        Cached list. The caller can mutate the returned
        ``Reference`` objects safely; only the list itself is
        shared. (Mutating ``payload`` will leak to subsequent
        callers — don't.)

    Raises
    ------
    ValueError
        Unknown category, unknown mode, or missing required
        argument for the chosen mode.
    """
    if category not in SUPPORTED_CATEGORIES:
        raise ValueError(
            f"scan.refs.load_references: unknown category {category!r}; "
            f"expected one of {SUPPORTED_CATEGORIES}")
    if mode not in SUPPORTED_MODES:
        raise ValueError(
            f"scan.refs.load_references: unknown mode {mode!r}; "
            f"expected one of {SUPPORTED_MODES}")

    # ---- Equipment validation
    if category == "equipment":
        if mode == "flat":
            raise ValueError(
                "scan.refs.load_references: mode='flat' is reserved for "
                "pets / mount / skills; use 'exact' or 'all_ages' for "
                "equipment.")
        if slot is None:
            raise ValueError(
                "scan.refs.load_references: equipment mode requires a "
                "slot argument.")
        if mode == "exact" and age is None:
            raise ValueError(
                "scan.refs.load_references: mode='exact' requires both "
                "age and slot for equipment.")

    # ---- Flat validation
    if category in ("pets", "mount", "skills") and mode != "flat":
        raise ValueError(
            f"scan.refs.load_references: category={category!r} only "
            f"supports mode='flat' (got {mode!r}).")

    # ---- Cache key
    key: Tuple[str, str, Optional[int], Optional[str]] = (
        category,
        mode,
        age if mode == "exact" else None,
        slot if category == "equipment" else None,
    )
    if key in _cache:
        return _cache[key]

    # ---- Build
    if category == "equipment":
        if mode == "exact":
            assert age is not None and slot is not None
            refs = _load_equipment_exact(age, slot)
        else:  # all_ages
            assert slot is not None
            refs = _load_equipment_all_ages(slot)
    else:
        # Flat category — mode is "flat" by construction here.
        refs = _load_flat(category)

    _cache[key] = refs
    return refs


# ────────────────────────────────────────────────────────────
#  Inspection helpers
# ────────────────────────────────────────────────────────────


def cache_size() -> int:
    """How many (category, mode, age, slot) cells are
    currently cached. Returned for diagnostics + tests."""
    return len(_cache)


def cached_keys() -> List[Tuple[str, str, Optional[int], Optional[str]]]:
    """Snapshot of the cache keyspace, sorted for stable
    output. Diagnostics only."""
    return sorted(_cache.keys(), key=lambda k: tuple(map(str, k)))


__all__ = [
    "AGE_INT_TO_FOLDER",
    "SLOT_TO_FOLDER",
    "SLOT_TO_TYPE_ID",
    "SUPPORTED_CATEGORIES",
    "SUPPORTED_MODES",
    "Reference",
    "load_references",
    "reset_caches",
    "list_supported_categories",
    "cache_size",
    "cached_keys",
]
