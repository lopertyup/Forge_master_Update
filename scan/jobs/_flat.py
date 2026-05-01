"""
============================================================
  FORGE MASTER — STRAT C orchestrator (flat-refs jobs)

  Interdit aux jobs joueur. Usage adversaire ou legacy/debug uniquement.

  Pet, mount, and skill popups all walk the same pipeline
  (cf. PLAN_REFACTO_SCAN.txt STRAT C):

      1. OCR the popup title → ``[<Rarity>]`` + name + Lv.
      2. If the bracket is missing, fall back to the colour
         heuristic on the popup border.
      3. ``autocrop_capture`` the popup down to the icon sprite.
      4. ``match(crop, refs, ocr_name=name)`` against the FLAT
         category folder (data/icons/{pets,mount,skills}/).
      5. Assemble a Candidate that carries the rarity (from OCR
         balise, with colour as filet de sécurité), the ref
         payload (id / name / rarity from the AutoXxxMapping
         JSON), and the popup-derived level.

  This module factors that pipeline once so pet.py / mount.py /
  skill.py stay tiny and identical in shape — the only thing
  that changes between them is the category name and the
  ``parse_*_meta`` flavour.

  Public API:

      run_flat_scan(capture, *, category, kind,
                    threshold, debug_zone, debug_dir,
                    libs=None) -> ScanResult

  No public dataclasses are exposed: callers consume the
  ``ScanResult`` returned by this function.
============================================================
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from PIL import Image

from ..colors import (
    RARITY_NAMES,
    identify_rarity_from_color_with_distance,
)
from ..core import (
    DEFAULT_THRESHOLD,
    autocrop_capture,
    is_cell_filled,
    match as core_match,
)
from ..refs import load_references
from ..types import Candidate, ScanResult

from . import _lv
from . import _title

log = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────
#  Internal helpers
# ────────────────────────────────────────────────────────────


def _canonicalise_rarity(tag: Optional[str]) -> Optional[str]:
    """Map an OCR'd bracket tag to the canonical rarity name.

    Accepts the parser's lower-case output and the title-cased
    form returned by ``_title.parse_popup_metadata``. Returns
    ``None`` when the tag does not match any known rarity (the
    job will then ignore the OCR balise and rely on colour).
    """
    if not tag:
        return None
    canonical = tag.strip().title()
    return canonical if canonical in RARITY_NAMES else None


def _border_crop(capture: Image.Image) -> Image.Image:
    """Sample a 6 %-wide strip around the popup border.

    Used by ``identify_rarity_from_color_with_distance`` as the
    colour fallback when the OCR bracket is unreadable. The
    border in single-cell popups is the rarity-coloured frame
    around the icon; sampling the outer strip of the whole
    popup captures it cleanly without picking up the icon
    sprite itself.
    """
    w, h = capture.size
    margin_w = max(1, int(w * 0.06))
    margin_h = max(1, int(h * 0.06))
    # Take the top strip — borders are uniform colour all the
    # way around so any single side works and the top one is
    # least likely to be obscured by Lv.NN cartouches.
    return capture.crop((0, 0, w, margin_h)) if h > 2 * margin_h else capture


# ────────────────────────────────────────────────────────────
#  Main orchestrator
# ────────────────────────────────────────────────────────────


def run_flat_scan(
    capture: Image.Image,
    *,
    category: str,
    kind: str = "companion",
    threshold: float = DEFAULT_THRESHOLD,
    debug_zone: Optional[str] = None,
    debug_dir: Optional[Path] = None,
    libs: Optional[Dict[str, Any]] = None,
) -> ScanResult:
    """STRAT C scan: flat-refs match for a single popup.

    Parameters
    ----------
    capture : PIL.Image.Image
        Full popup capture.
    category : str
        ``"pets"`` / ``"mount"`` / ``"skills"`` — passed straight
        to ``scan.refs.load_references(category, mode="flat")``.
    kind : str
        ``"skill"`` to apply the skill-flavoured text parser,
        anything else uses the companion (pet/mount) flavour.
    threshold : float
        Minimum hybrid score for the result to be flagged
        ``status="ok"``. Below this the result is still returned
        but with ``status="low_confidence"`` so the UI can show
        it greyed-out.
    debug_zone : Optional[str]
        Forwarded to the OCR layer for the project-wide debug
        dump infrastructure (``debug_scan.save_image``).
    debug_dir, libs : reserved
        Reserved for parity with future jobs (Phase 4+). The
        flat scan does not need either, but the controller will
        wire them through uniformly.

    Returns
    -------
    ScanResult
        ``matches`` holds at most one Candidate; if the icon is
        empty (``is_cell_filled == False``) the list is empty
        and status is ``"no_match"``. The Candidate's
        ``payload`` is a copy of the matched reference's payload
        plus a ``"level"`` key (when extracted) and a
        ``"rarity_source"`` key (``"ocr"`` or ``"color"``).
    """
    # Empty / blank popup short-circuit. The variance heuristic
    # is calibrated for icon tiles, so we restrict it to an
    # autocropped sprite — a popup full of text would otherwise
    # always pass the variance bar.
    sprite = autocrop_capture(capture)
    if not is_cell_filled(sprite):
        return ScanResult(matches=[], status="no_match",
                          debug={"reason": "is_cell_filled=False"})

    # ---- Step 1: title OCR (balise + name + level) ----------
    meta = _title.parse_popup_metadata(
        capture,
        kind=kind,
        debug_zone=debug_zone,
    )
    rarity_ocr = _canonicalise_rarity(meta.get("tag"))
    name_ocr   = meta.get("name") or ""
    level_ocr  = meta.get("level")
    raw_text   = meta.get("raw") or ""

    rarity_source = "ocr" if rarity_ocr else None

    # ---- Step 2: colour fallback ----------------------------
    rarity_color: Optional[str] = None
    rarity_color_distance: float = float("inf")
    rarity_color_gap:      float = 0.0
    if rarity_ocr is None:
        try:
            border = _border_crop(capture)
            rarity_color, rarity_color_distance, rarity_color_gap = (
                identify_rarity_from_color_with_distance(border)
            )
            rarity_source = "color"
        except Exception:  # pragma: no cover - defensive
            log.exception("scan.jobs._flat: colour fallback failed")

    rarity_final = rarity_ocr or rarity_color  # may be None when both fail

    # ---- Step 3: Lv.NN cartouche fallback -------------------
    if level_ocr is None:
        try:
            level_ocr = _lv.extract_popup_level(
                capture,
                debug_zone=debug_zone,
            )
        except Exception:  # pragma: no cover - defensive
            log.exception("scan.jobs._flat: cartouche Lv extraction failed")

    # ---- Step 4: load refs + match --------------------------
    refs = load_references(category, mode="flat")
    if not refs:
        return ScanResult(
            matches=[],
            status="no_match",
            debug={
                "reason": f"no flat refs for category={category!r}",
                "raw_text": raw_text,
            },
        )

    candidates = core_match(
        sprite,
        refs,
        ocr_name=name_ocr,
        autocrop=False,   # already autocropped above
    )
    if not candidates:
        return ScanResult(
            matches=[],
            status="no_match",
            debug={
                "reason": "matcher returned no candidates",
                "raw_text": raw_text,
            },
        )

    best = candidates[0]
    runner_up = candidates[1] if len(candidates) > 1 else None

    # ---- Step 5: assemble result ----------------------------
    enriched_payload: Dict[str, Any] = dict(best.payload)
    if level_ocr is not None:
        enriched_payload["level"] = int(level_ocr)
    if rarity_source is not None:
        enriched_payload["rarity_source"] = rarity_source
    enriched = Candidate(
        name=best.name,
        score=best.score,
        age=best.age,
        slot=best.slot,
        rarity=rarity_final,
        idx=best.idx,
        payload=enriched_payload,
    )

    status = "ok" if best.score >= threshold else "low_confidence"
    debug: Dict[str, Any] = {
        "category": category,
        "kind": kind,
        "ocr_name": name_ocr,
        "rarity_ocr": rarity_ocr,
        "rarity_color": rarity_color,
        "rarity_source": rarity_source,
        "rarity_color_distance": rarity_color_distance,
        "rarity_color_gap": rarity_color_gap,
        "level": level_ocr,
        "raw_text": raw_text,
        "top1_score": best.score,
        "top2_score": runner_up.score if runner_up else None,
        "n_refs": len(refs),
    }

    return ScanResult(matches=[enriched], status=status, debug=debug)


__all__ = [
    "run_flat_scan",
]
