"""
============================================================
  FORGE MASTER — Shared dataclasses for the scan package

  Two responsibilities:

    1. Re-export the OCR layer's dataclasses from
       ``scan.enemy.types`` so callers in scan.jobs.*
       only ever import from one place. The OCR types are
       NOT touched by this refactor — only relocated.

    2. Define the new dataclasses that every scan job exposes
       in its return value:

           Candidate   — a single ranked guess for "what is
                         this icon", including the metadata
                         (age, slot, rarity, idx) that the
                         downstream calculators need.

           ScanResult  — the wrapper a job returns. Holds the
                         list of candidates, a status code,
                         and a debug dict for diagnostics.

  Status vocabulary (used as ScanResult.status):

      "ok"               — confidence above threshold
      "low_confidence"   — best guess provided but below
                           threshold; UI may grey it out
      "no_match"         — no reference passed _is_cell_filled
      "ocr_unavailable"  — OCR backend missing (informational)
      "scan_error"       — exception caught and logged
============================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ────────────────────────────────────────────────────────────
#  Re-exports from scan.enemy.types
# ────────────────────────────────────────────────────────────
#
# The enemy OCR pipeline lives in scan.enemy.types.
# We re-export the dataclasses so scan/jobs/*.py can do:
#
#     from scan.types import IdentifiedItem, ScanResult, ...
#
# without ever needing to know the OCR layer's import path.
from scan.enemy.types import (  # noqa: F401  (re-export)
    SLOT_ORDER,
    SLOT_TO_JSON_TYPE,
    OcrEquipmentSlot,
    OcrPet,
    OcrMount,
    OcrSkill,
    OcrSubstat,
    EnemyOcrRaw,
    IdentifiedItem,
    IdentifiedPet,
    IdentifiedMount,
    IdentifiedSkill,
    EnemyIdentifiedProfile,
    EnemyComputedStats,
)


# ────────────────────────────────────────────────────────────
#  New dataclasses introduced by the unified scan pipeline
# ────────────────────────────────────────────────────────────


# Status codes that callers (controller, vues) may rely on.
# Defined as a frozen tuple so tests can iterate them.
SCAN_STATUSES: tuple = (
    "ok",
    "low_confidence",
    "no_match",
    "ocr_unavailable",
    "scan_error",
)


@dataclass
class Candidate:
    """One ranked guess for "what is this icon".

    Fields:

        name      — canonical reference filename stem
                    (e.g. "BlackBow", "Crab", "Stampede").
        score     — hybrid ensemble score, in [0, 1] where
                    1 is a perfect match. ↑ = better.
        age       — Age int (0..9) when known. Equipment jobs
                    always populate it; pet/mount/skill leave
                    it None (no age concept).
        slot      — slot name (Helmet, Body, …) for equipment;
                    None for the flat categories.
        rarity    — rarity name (Common/Rare/Epic/…) when
                    known. Filled by the colour heuristic on
                    the border crop (see scan.colors), or from
                    the OCR'd ``[<Rarity>]`` tag in popups.
        idx       — game-side numeric id (when the auto-mapping
                    was looked up). None for raw reference-only
                    matches.
        payload   — free-form dict; jobs may stuff hp_flat,
                    damage_flat, weapon params, etc.
    """

    name: str
    score: float
    age: Optional[int] = None
    slot: Optional[str] = None
    rarity: Optional[str] = None
    idx: Optional[int] = None
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScanResult:
    """Wrapper every ``scan.jobs.<job>.scan(capture, ...)`` returns.

    Fields:

        matches  — ordered list of Candidate objects, best
                   first. For panel jobs (8 tiles) the list
                   contains one Candidate per tile in slot
                   order; for single-cell jobs there is
                   typically one Candidate (or zero if the
                   icon was empty).
        status   — one of SCAN_STATUSES. Tells the controller
                   whether to act on the result, surface a
                   warning, or fall back.
        debug    — free-form dict reserved for diagnostics:
                   per-tile crops, OCR text fragments, hsv
                   distances, etc. Vues NEVER read it; only
                   the debug-dump path or tests do.
    """

    matches: List[Candidate] = field(default_factory=list)
    status: str = "ok"
    debug: Dict[str, Any] = field(default_factory=dict)

    @property
    def best(self) -> Optional[Candidate]:
        """Top-scoring candidate, or None when matches is empty."""
        return self.matches[0] if self.matches else None


__all__ = [
    # OCR re-exports
    "SLOT_ORDER",
    "SLOT_TO_JSON_TYPE",
    "OcrEquipmentSlot",
    "OcrPet",
    "OcrMount",
    "OcrSkill",
    "OcrSubstat",
    "EnemyOcrRaw",
    "IdentifiedItem",
    "IdentifiedPet",
    "IdentifiedMount",
    "IdentifiedSkill",
    "EnemyIdentifiedProfile",
    "EnemyComputedStats",
    # new
    "SCAN_STATUSES",
    "Candidate",
    "ScanResult",
]
