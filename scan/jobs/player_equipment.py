"""OCR-only player equipment-panel scan job."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image

from data.canonical import LEGACY_EQUIPMENT_SLOT_MAP
from scan.ocr import fix_ocr, is_available, ocr_image
from scan.ocr.parsers.equipment import parse_equipment_popup_text

from ..offsets import player as _offsets
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
    skip_per_slot_ocr: bool = False,
) -> ScanResult:
    if capture is None:
        return ScanResult(matches=[], status="no_match", debug={"reason": "capture is None"})
    if not is_available():
        return ScanResult(matches=[], status="ocr_unavailable", debug={})

    width, height = capture.size
    layout = _offsets.offsets_for_capture(width, height)
    slot_order = list(layout["slot_order"])
    slot_dict: Dict[str, Dict[str, object]] = {}
    profile_slot_dict: Dict[str, Dict[str, object]] = {}
    matches: List[Candidate] = []
    missing_by_slot: Dict[str, list[str]] = {}
    raw_by_slot: Dict[str, str] = {}
    text_by_slot: Dict[str, str] = {}

    try:
        for slot, box in zip(slot_order, layout["equipment"]):
            crop = capture.crop(tuple(box))
            raw = ocr_image(crop, debug_zone="player_equipment")
            text = fix_ocr(raw, context="equipment_popup")
            parsed = parse_equipment_popup_text(text, slot=slot)
            if slot == "Weapon":
                enrich_weapon_slot(parsed, libs=libs)
            missing = parsed.pop("missing_fields", [])
            legacy_key = _CANONICAL_TO_LEGACY.get(slot, slot)
            slot_dict[legacy_key] = parsed
            profile_slot_dict[slot] = parsed
            missing_by_slot[slot] = missing
            raw_by_slot[slot] = raw
            text_by_slot[slot] = text
            matches.append(Candidate(
                name=str(parsed.get("__name__") or ""),
                score=1.0 if not missing else 0.5,
                age=int(parsed.get("__age__", 0) or 0),
                slot=slot,
                rarity=str(parsed.get("__rarity__") or ""),
                idx=int(parsed.get("__idx__", 0) or 0),
                payload=dict(parsed),
            ))
    except Exception:
        log.exception("scan.jobs.player_equipment: OCR panel parse failed")
        return ScanResult(matches=[], status="scan_error", debug={})

    filled = [m for m in matches if m.name]
    if not filled:
        status = "no_match"
    elif any(missing_by_slot.values()):
        status = "low_confidence"
    else:
        status = "ok"

    return ScanResult(
        matches=matches,
        status=status,
        debug={
            "slot_dict": slot_dict,
            "profile_slot_dict": profile_slot_dict,
            "slot_order": slot_order,
            "missing_fields": missing_by_slot,
            "raw_text": raw_by_slot,
            "ocr_text": text_by_slot,
            "n_filled": len(filled),
        },
    )


__all__ = ["scan"]

