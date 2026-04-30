"""
============================================================
  FORGE MASTER — Opponent recompute pipeline (Phase 6)

  Replaces ``backend.pipeline`` (orchestrator) +
  ``backend.scanner.icon_matcher.identify_all`` (visual
  identification) with a thin wrapper around the unified
  ``scan/`` building blocks. The capture flow is identical
  to the legacy pipeline:

      capture (PIL)
        → backend.scanner.ocr.ocr_image(full_capture)   (text)
        → scan.offsets.opponent.offsets_for_capture()   (sub-zones)
        → scan.jobs._panel.identify_panel               (8 items)
        → scan.core.match against pets/mount/skill refs (companions —
                                                         no popup title
                                                         on the panel,
                                                         hence not run
                                                         through the
                                                         standalone
                                                         pet/mount/skill
                                                         jobs)
        → backend.scanner.ocr_parser.parse_enemy_text   (substats)
        → backend.calculator.combat.calculate_enemy_stats
                                                        (final stats)

  Public API (binary-compatible with ``backend.pipeline`` so
  callers / tests do not need to change anything besides the
  import line):

      recompute_from_capture(capture, ocr_text=None,
                             *, skip_per_slot_ocr=False)
          -> (EnemyComputedStats, EnemyIdentifiedProfile, raw_text)

      capture_and_recompute(bbox, *, skip_per_slot_ocr=False)
          -> (stats, profile, raw_text, image) | None

  ⚠ The OCR layer (``backend.scanner.ocr``) and the text
  parsers (``ocr_parser`` / ``text_parser``) are KEPT — Phase 6
  only migrates the visual identification. The legacy
  ``backend.scanner.icon_matcher`` is no longer imported here
  (it remains on disk until Phase 7 cleans it up).
============================================================
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

# OCR + text parsers are kept untouched — these still live in backend/.
from backend.scanner import ocr as _ocr
from backend.scanner.ocr_parser import parse_enemy_text
from backend.scanner.ocr_types import (
    EnemyComputedStats,
    EnemyIdentifiedProfile,
    IdentifiedItem,
    IdentifiedMount,
    IdentifiedPet,
    IdentifiedSkill,
)
from backend.calculator.combat import calculate_enemy_stats
from backend.data.libraries import load_libs

# Visual identification — unified scan/ layer.
from ..colors import identify_rarity_from_color
from ..core import (
    DEFAULT_THRESHOLD,
    autocrop_capture,
    is_cell_filled,
    match as core_match,
)
from ..offsets import opponent as _offsets
from ..refs import load_references
from ..types import ScanResult

from . import _panel

log = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────
#  Companion identification (pets / mount / skills)
# ────────────────────────────────────────────────────────────
#
# The opponent panel embeds 3 pets + 1 mount + 3 skills in the
# same screenshot as the 8-tile equipment grid. Each one is a
# tiny crop, no popup title around it — so we cannot rely on
# the OCR balise and run STRAT C with a colour-only rarity
# inference. The unified ``run_flat_scan`` helper does too much
# (it tries to OCR a popup title which doesn't exist for
# bare icons) so we drive the matcher directly here.
#
# That means we still go through ``scan.refs.load_references``
# (mode="flat") and ``scan.core.match`` — same matcher as the
# popup jobs, just without the title-OCR step.


def _identify_companion(
    crop: Image.Image,
    *,
    category: str,
) -> Optional[Dict[str, Any]]:
    """Match one bare icon against the flat refs of ``category``.

    ``category`` is one of ``"pets"`` / ``"mount"`` / ``"skills"``.
    Returns a dict with the auto-mapping payload (id / name /
    rarity for pets and mounts, name / rarity for skills) plus
    a ``rarity_color`` field derived from the icon border —
    used to overwrite ``rarity`` since the auto-mapping payload
    only carries the canonical reference rarity, not the in-game
    instance rarity. Returns ``None`` when the icon is empty
    (matches legacy ``identify_*`` semantics).
    """
    if crop is None:
        return None
    sprite = autocrop_capture(crop)
    if not is_cell_filled(sprite):
        return None
    refs = load_references(category, mode="flat")
    if not refs:
        return None
    candidates = core_match(sprite, refs, autocrop=False)
    if not candidates:
        return None
    best = candidates[0]
    out: Dict[str, Any] = dict(best.payload)
    # Border colour → rarity. The mapping payload's rarity is the
    # ref's canonical one; in-game rarity is derived from the
    # coloured border just like equipment.
    try:
        rarity_color = identify_rarity_from_color(crop)
    except Exception:  # pragma: no cover - defensive
        log.exception("opponent: identify_rarity_from_color failed (%s)",
                      category)
        rarity_color = None
    if rarity_color:
        out["rarity"] = rarity_color
    return out


# ────────────────────────────────────────────────────────────
#  Profile assembly (visual side)
# ────────────────────────────────────────────────────────────


def _build_profile(
    capture: Image.Image,
    raw_text: str,
    *,
    skip_per_slot_ocr: bool = False,
) -> EnemyIdentifiedProfile:
    """Glue OCR text + visual identification into a single profile.

    Mirrors ``backend.pipeline._build_profile`` 1:1 but uses
    the unified scan/ layer for the visual step. The text-side
    profile (forge_level / displayed totals / substats) is
    untouched because it still flows through
    ``parse_enemy_text``.
    """
    profile = parse_enemy_text(raw_text)

    W, H = capture.size
    layout = _offsets.offsets_for_capture(W, H)
    slot_order = list(layout["slot_order"])

    # ---- Equipment (8-tile panel) — shared with the player-side flow.
    panel_dicts = _panel.identify_panel(
        capture,
        layout,
        skip_per_slot_ocr=skip_per_slot_ocr,
    )
    items: List[IdentifiedItem] = []
    for slot, sd in zip(slot_order, panel_dicts):
        items.append(IdentifiedItem(
            slot=slot,
            age=int(sd.get("__age__", 0)),
            idx=int(sd.get("__idx__", 0) or 0),
            rarity=str(sd.get("__rarity__") or "Common"),
            level=int(sd.get("__level__", 1) or 1),
        ))
    profile.items = items

    # ---- Pets (3 cells)
    pets: List[IdentifiedPet] = []
    for ofs in layout["pets"]:
        match = _identify_companion(capture.crop(ofs), category="pets")
        if not match:
            continue
        level = (0 if skip_per_slot_ocr
                 else _panel.extract_level(capture, ofs))
        pets.append(IdentifiedPet(
            id=int(match.get("id") or 0),
            rarity=str(match.get("rarity") or "Common"),
            level=max(1, level),
        ))
    profile.pets = pets

    # ---- Mount (single cell, optional)
    mount_offsets = layout.get("mount") or []
    if mount_offsets:
        ofs = mount_offsets[0]
        match = _identify_companion(capture.crop(ofs), category="mount")
        if match:
            level = (0 if skip_per_slot_ocr
                     else _panel.extract_level(capture, ofs))
            profile.mount = IdentifiedMount(
                id=int(match.get("id") or 0),
                rarity=str(match.get("rarity") or "Common"),
                level=max(1, level),
            )

    # ---- Skills (3 cells)
    skills: List[IdentifiedSkill] = []
    for ofs in layout["skills"]:
        match = _identify_companion(capture.crop(ofs), category="skills")
        if not match:
            continue
        level = (0 if skip_per_slot_ocr
                 else _panel.extract_level(capture, ofs))
        skills.append(IdentifiedSkill(
            id=str(match.get("name") or ""),
            rarity=str(match.get("rarity") or "Common"),
            level=max(1, level),
        ))
    profile.skills = skills

    return profile


# ────────────────────────────────────────────────────────────
#  Public entry points (binary-compatible with backend.pipeline)
# ────────────────────────────────────────────────────────────


def recompute_from_capture(
    capture: Image.Image,
    ocr_text: Optional[str] = None,
    *,
    skip_per_slot_ocr: bool = False,
) -> Tuple[EnemyComputedStats, EnemyIdentifiedProfile, str]:
    """Run the full opponent pipeline on an already-captured image.

    Returns the same triple as ``backend.pipeline.recompute_from_capture``:
    ``(EnemyComputedStats, EnemyIdentifiedProfile, raw_text)``.

    ``skip_per_slot_ocr`` short-circuits every Lv.NN OCR (returns
    ``level=1`` for every slot) — useful for headless tests on
    synthetic captures where the OCR backend is unavailable.
    """
    if ocr_text is None:
        try:
            ocr_text = (
                _ocr.ocr_image(capture) if _ocr.is_available() else ""
            )
        except Exception:
            log.exception("recompute_from_capture: OCR pass failed")
            ocr_text = ""

    profile = _build_profile(
        capture, ocr_text or "",
        skip_per_slot_ocr=skip_per_slot_ocr,
    )
    stats = calculate_enemy_stats(profile, load_libs())
    return stats, profile, ocr_text or ""


def capture_and_recompute(
    bbox,
    *,
    skip_per_slot_ocr: bool = False,
):
    """Take a screen bbox → return (stats, profile, raw_text, image).

    Convenience wrapper used by the controller's wiki-grid /
    opponent-zone scan paths. Returns ``None`` when the capture
    failed entirely (camera offline, zone misconfigured, etc.).
    """
    img, text = _ocr.capture_and_ocr(bbox)
    if img is None:
        return None
    stats, profile, raw_text = recompute_from_capture(
        img, text,
        skip_per_slot_ocr=skip_per_slot_ocr,
    )
    return stats, profile, raw_text, img


# ────────────────────────────────────────────────────────────
#  scan() — uniform job signature
# ────────────────────────────────────────────────────────────
#
# Provided for parity with the rest of ``scan.jobs.*``. The
# controller's existing zone "opponent" branch keeps calling
# ``recompute_from_capture`` directly because it needs the
# triple (stats, profile, raw_text) in one go; this thin
# wrapper exists for callers that want a uniform ScanResult.


def scan(
    capture: Image.Image,
    *,
    libs:       Optional[Dict[str, Any]] = None,
    debug_dir: "Optional[Any]"           = None,
    threshold: float                     = DEFAULT_THRESHOLD,
    force_slot: Optional[str]            = None,
    force_age:  Optional[int]            = None,
    ocr_text:   Optional[str]            = None,
    skip_per_slot_ocr: bool              = False,
) -> ScanResult:
    """Identify a full opponent capture and return a ScanResult.

    ``force_slot`` / ``force_age`` are accepted for parity
    with the other jobs but ignored — opponent panels carry
    8 slots whose age varies independently per tile, and the
    flow has no notion of "force" that would make sense.

    The returned ScanResult carries:

      - ``matches``: empty (the per-tile Candidates are not
        exposed at this level — callers wanting them call the
        underlying ``_panel.identify_panel`` directly).
      - ``debug["stats"]``:    EnemyComputedStats
        ``debug["profile"]``:  EnemyIdentifiedProfile
        ``debug["raw_text"]``: original OCR text
      - ``status``: ``"ok"`` when the panel returned at least
        one filled slot, otherwise ``"no_match"``.
    """
    if capture is None:
        return ScanResult(matches=[], status="no_match",
                          debug={"reason": "capture is None"})

    try:
        stats, profile, raw_text = recompute_from_capture(
            capture, ocr_text=ocr_text,
            skip_per_slot_ocr=skip_per_slot_ocr,
        )
    except Exception:
        log.exception("scan.jobs.opponent: recompute_from_capture crashed")
        return ScanResult(matches=[], status="scan_error",
                          debug={"reason": "recompute_from_capture raised"})

    n_filled = sum(1 for it in profile.items if it.idx)
    status = "ok" if n_filled > 0 else "no_match"

    return ScanResult(
        matches=[],
        status=status,
        debug={
            "stats":    stats,
            "profile":  profile,
            "raw_text": raw_text,
            "n_filled": n_filled,
        },
    )


__all__ = [
    "recompute_from_capture",
    "capture_and_recompute",
    "scan",
]
