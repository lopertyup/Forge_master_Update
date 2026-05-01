"""OCR-only single equipment popup scan job."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from PIL import Image

from data.canonical import EQUIPMENT_SLOTS, LEGACY_EQUIPMENT_SLOT_MAP, canonical_equipment_slot
from scan.ocr import fix_ocr, is_available, ocr_image
from scan.ocr.parsers.equipment import parse_equipment_popup_text

from ..types import Candidate, ScanResult
from ._weapon_enrich import enrich_weapon_slot

log = logging.getLogger(__name__)
DEFAULT_THRESHOLD = 0.0
_CANONICAL_TO_LEGACY = {value: key for key, value in LEGACY_EQUIPMENT_SLOT_MAP.items()}


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
    slot = canonical_equipment_slot(force_slot or "")
    if slot not in EQUIPMENT_SLOTS:
        return ScanResult(matches=[], status="scan_error", debug={"reason": f"force_slot is required, got {force_slot!r}"})
    if not is_available():
        return ScanResult(matches=[], status="ocr_unavailable", debug={})

    try:
        raw = ocr_image(capture, debug_zone="equipment_popup")
        text = fix_ocr(raw, context="equipment_popup")
        slot_dict = parse_equipment_popup_text(text, slot=slot)
        if force_age is not None and not slot_dict.get("__age__"):
            slot_dict["__age__"] = int(force_age)
        if slot == "Weapon":
            enrich_weapon_slot(slot_dict, libs=libs)
    except Exception:
        log.exception("scan.jobs.equipment_popup: OCR parse failed")
        return ScanResult(matches=[], status="scan_error", debug={})

    missing = slot_dict.pop("missing_fields", [])
    status = "low_confidence" if missing else "ok"
    candidate = Candidate(
        name=str(slot_dict.get("__name__") or ""),
        score=1.0 if not missing else 0.5,
        age=int(slot_dict.get("__age__", 0) or 0),
        slot=slot,
        rarity=str(slot_dict.get("__rarity__") or ""),
        idx=int(slot_dict.get("__idx__", 0) or 0),
        payload=dict(slot_dict),
    )
    legacy_key = _CANONICAL_TO_LEGACY.get(slot, slot)
    return ScanResult(
        matches=[candidate] if candidate.name else [],
        status=status if candidate.name else "no_match",
        debug={
            "slot_dict": {legacy_key: slot_dict},
            "profile_slot_dict": {slot: slot_dict},
            "force_slot": slot,
            "raw_text": raw,
            "ocr_text": text,
            "missing_fields": missing,
        },
    )


__all__ = ["scan"]

