"""
============================================================
  FORGE MASTER — Skill popup scan (Phase 3)

  Single-cell scan: identifies the skill shown in a Skill
  popup. Same shape as ``scan.jobs.pet`` / ``scan.jobs.mount``
  but uses the skill-flavoured text parser
  (``parse_skill_meta``) which knows about the passive block
  ``Passive: +43.4k Base Damage +347k Base Health`` and the
  cast-damage line.

  STRAT C (cf. SCAN_REFACTOR.txt §3):

      1. OCR title  → ``[Rarity]`` balise + name + Lv.NN
      2. Fallback   → identify_rarity_from_color on the popup
                      border when the OCR balise is illegible
      3. Match      → autocrop_capture(crop) ↔ flat refs from
                      ``data/icons/skills/``
      4. Return     → ScanResult with one Candidate carrying
                      {name, rarity, level} ready to be
                      converted into ``IdentifiedSkill`` by
                      the controller.

  Skills also carry a ``Lv.X/Y`` capacity badge on top of the
  icon (cf. SCAN_REFACTOR.txt §11.D). The matcher's
  auto-crop tolerates it; the badge is NOT used as a level
  source — the cartouche bottom-left is the canonical Lv.NN
  field, exactly like pets and mounts.

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
    """Identify the skill shown in a Skill popup capture.

    ``force_slot`` and ``force_age`` are accepted but ignored —
    skills have no slot and no age. Kept in the signature for
    parity with the rest of ``scan.jobs.*``.
    """
    return run_flat_scan(
        capture,
        category="skills",
        kind="skill",
        threshold=threshold,
        debug_zone="skill",
        debug_dir=debug_dir,
        libs=libs,
    )


__all__ = ["scan"]
