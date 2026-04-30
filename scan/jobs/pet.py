"""
============================================================
  FORGE MASTER — Pet popup scan (Phase 3)

  Single-cell scan: identifies the pet shown in a Pets popup.
  Follows STRAT C from SCAN_REFACTOR.txt §3:

      1. OCR title  → ``[Rarity]`` balise + name + Lv.NN
      2. Fallback   → identify_rarity_from_color on the popup
                      border when the OCR balise is illegible
      3. Match      → autocrop_capture(crop) ↔ flat refs from
                      ``data/icons/pets/``
      4. Return     → ScanResult with one Candidate carrying
                      {id, name, rarity, level} ready to be
                      converted into ``IdentifiedPet`` by the
                      controller.

  No age, no slot, no force_* parameters consulted (kept in
  the signature for parity with the rest of scan.jobs.*).

  Public API:

      scan(capture, *, libs=None, debug_dir=None,
           threshold=DEFAULT_THRESHOLD,
           force_slot=None, force_age=None) -> ScanResult
============================================================
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from PIL import Image

from ..core import DEFAULT_THRESHOLD
from ..types import ScanResult

from ._flat import run_flat_scan


def scan(
    capture: Image.Image,
    *,
    libs:       Optional[Dict[str, Any]] = None,
    debug_dir:  Optional[Path]           = None,
    threshold:  float                    = DEFAULT_THRESHOLD,
    force_slot: Optional[str]            = None,
    force_age:  Optional[int]            = None,
) -> ScanResult:
    """Identify the pet shown in a Pets popup capture.

    The signature mirrors every other ``scan.jobs.*.scan(...)``
    so the controller can wire all jobs uniformly. ``force_slot``
    and ``force_age`` are accepted but ignored — pets have no
    age and no slot in the data model.
    """
    return run_flat_scan(
        capture,
        category="pets",
        kind="companion",
        threshold=threshold,
        debug_zone="pet",
        debug_dir=debug_dir,
        libs=libs,
    )


__all__ = ["scan"]
