"""
============================================================
  FORGE MASTER — Mount popup scan (Phase 3)

  Single-cell scan: identifies the mount shown in a Mount
  popup. Same shape as ``scan.jobs.pet`` — different category
  folder (``data/icons/mount/``) and different downstream
  dataclass (``IdentifiedMount``); the matcher pipeline is
  identical.

  STRAT C (cf. SCAN_REFACTOR.txt §3):

      1. OCR title  → ``[Rarity]`` balise + name + Lv.NN
      2. Fallback   → identify_rarity_from_color on the popup
                      border when the OCR balise is illegible
      3. Match      → autocrop_capture(crop) ↔ flat refs from
                      ``data/icons/mount/``
      4. Return     → ScanResult with one Candidate carrying
                      {id, name, rarity, level} ready to be
                      converted into ``IdentifiedMount`` by
                      the controller.

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
    """Identify the mount shown in a Mount popup capture.

    ``force_slot`` and ``force_age`` are accepted but ignored —
    mounts have neither concept. Kept in the signature for
    parity with the rest of ``scan.jobs.*``.
    """
    return run_flat_scan(
        capture,
        category="mount",
        kind="companion",
        threshold=threshold,
        debug_zone="mount",
        debug_dir=debug_dir,
        libs=libs,
    )


__all__ = ["scan"]
