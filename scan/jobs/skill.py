"""OCR-only skill popup scan job."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from PIL import Image

from scan.ocr import fix_ocr, is_available, ocr_image
from scan.ocr.parsers.skill import parse_skill_text

from ..types import Candidate, ScanResult

log = logging.getLogger(__name__)
DEFAULT_THRESHOLD = 0.0


def scan(
    capture: Image.Image,
    *,
    libs: Optional[Dict[str, Any]] = None,
    debug_dir: Optional[Path] = None,
    threshold: float = DEFAULT_THRESHOLD,
    force_slot: Optional[str] = None,
    force_age: Optional[int] = None,
) -> ScanResult:
    if capture is None:
        return ScanResult(matches=[], status="no_match", debug={"reason": "capture is None"})
    if not is_available():
        return ScanResult(matches=[], status="ocr_unavailable", debug={})
    try:
        raw = ocr_image(capture, debug_zone="skill")
        text = fix_ocr(raw, context="skill")
        slot = parse_skill_text(text)
    except Exception:
        log.exception("scan.jobs.skill: OCR parse failed")
        return ScanResult(matches=[], status="scan_error", debug={})

    missing = slot.pop("missing_fields", [])
    status = "low_confidence" if missing else "ok"
    candidate = Candidate(
        name=str(slot.get("__name__") or ""),
        score=1.0 if not missing else 0.5,
        rarity=str(slot.get("__rarity__") or ""),
        payload=dict(slot),
    )
    return ScanResult(
        matches=[candidate] if candidate.name else [],
        status=status if candidate.name else "no_match",
        debug={"slot_dict": slot, "raw_text": raw, "ocr_text": text, "missing_fields": missing},
    )


__all__ = ["scan"]

