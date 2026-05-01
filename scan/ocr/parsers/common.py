"""Shared parsing helpers for OCR text."""

from __future__ import annotations

import re
from typing import Dict, Iterable, Optional

from data.canonical import (
    AGE_NAME_TO_INT,
    RARITIES,
    SUBSTAT_KEYS,
    canonical_age_int,
    canonical_rarity,
    canonical_substat_key,
)

_LEVEL_RE = re.compile(r"\bLv\.?\s*(\d+)", re.IGNORECASE)
_TAG_NAME_RE = re.compile(r"\[\s*([A-Za-z][A-Za-z -]*)\s*\]\s*([^\r\n\[\]]+)")
_FLAT_RE = r"([+-]?\s*\d+(?:[.,]\d+)?\s*[kmbKMB]?)"
_PCT_RE = r"([+-]?\s*\d+(?:[.,]\d+)?)\s*%"


def parse_flat(value: object) -> float:
    text = str(value or "").strip().lower().replace(" ", "").replace(",", ".")
    sign = -1.0 if text.startswith("-") else 1.0
    text = text.lstrip("+-")
    mult = 1.0
    if text.endswith("b"):
        mult = 1_000_000_000.0
        text = text[:-1]
    elif text.endswith("m"):
        mult = 1_000_000.0
        text = text[:-1]
    elif text.endswith("k"):
        mult = 1_000.0
        text = text[:-1]
    try:
        return sign * float(text) * mult
    except ValueError:
        return 0.0


def parse_percent(value: object) -> float:
    text = str(value or "").strip().replace(" ", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return 0.0


def extract(text: str, patterns: Iterable[str]) -> float:
    """Return the first signed percentage matched by any pattern."""
    for pattern in patterns:
        match = re.search(pattern, text or "", re.IGNORECASE)
        if match:
            return parse_percent(match.group(1))
    return 0.0


def extract_flat(text: str, patterns: Iterable[str]) -> float:
    """Return the first flat k/m/b value matched by any pattern."""
    for pattern in patterns:
        match = re.search(pattern, text or "", re.IGNORECASE)
        if match:
            return parse_flat(match.group(1))
    return 0.0


def extract_level(text: str) -> int:
    match = _LEVEL_RE.search(text or "")
    return int(match.group(1)) if match else 0


def extract_tag_name(text: str) -> tuple[Optional[str], str]:
    match = _TAG_NAME_RE.search(text or "")
    if not match:
        return None, ""
    return match.group(1).strip(), match.group(2).strip()


def normalise_tag(tag: Optional[str]) -> tuple[Optional[str], Optional[int]]:
    if not tag:
        return None, None
    rarity = canonical_rarity(tag)
    age = canonical_age_int(tag)
    return rarity, age


def first_flat(text: str, patterns: Iterable[str]) -> float:
    for pattern in patterns:
        match = re.search(pattern, text or "", re.IGNORECASE)
        if match:
            return parse_flat(match.group(1))
    return 0.0


def extract_substats(text: str) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for label, patterns in _SUBSTAT_PATTERNS.items():
        canonical = canonical_substat_key(label) or label
        for pattern in patterns:
            match = re.search(pattern, text or "", re.IGNORECASE)
            if match:
                out[canonical] = parse_percent(match.group(1))
                break
    return out


def missing_fields(slot: Dict[str, object], required: Iterable[str]) -> list[str]:
    missing: list[str] = []
    for key in required:
        value = slot.get(key)
        if value in (None, "", 0, 0.0, {}):
            missing.append(key)
    return missing


def empty_substats() -> Dict[str, float]:
    return {key: 0.0 for key in SUBSTAT_KEYS}


_SUBSTAT_PATTERNS: Dict[str, tuple[str, ...]] = {
    "Crit Chance": (rf"\+?\s*{_PCT_RE}\s*(?:Critical|Crit)\s*Chance",),
    "Crit Damage": (rf"\+?\s*{_PCT_RE}\s*(?:Critical|Crit)\s*Damage",),
    "Block Chance": (rf"\+?\s*{_PCT_RE}\s*Block\s*Chance",),
    "Health Regen": (rf"\+?\s*{_PCT_RE}\s*Health\s*Regen",),
    "Lifesteal": (rf"\+?\s*{_PCT_RE}\s*Life\s*Steal", rf"\+?\s*{_PCT_RE}\s*Lifesteal"),
    "Double Chance": (rf"\+?\s*{_PCT_RE}\s*Double\s*Chance",),
    "Damage%": (rf"\+?\s*{_PCT_RE}\s*Damage(?!\s*\(|\s*Base|\s*[a-z]*\s*Damage)",),
    "Melee%": (rf"\+?\s*{_PCT_RE}\s*Melee\s*Damage",),
    "Ranged%": (rf"\+?\s*{_PCT_RE}\s*Ranged\s*Damage",),
    "Attack Speed": (rf"\+?\s*{_PCT_RE}\s*Attack\s*Speed",),
    "Skill Damage": (rf"\+?\s*{_PCT_RE}\s*Skill\s*Damage",),
    "Skill Cooldown": (rf"{_PCT_RE}\s*Skill\s*Cooldown",),
    "Health%": (rf"\+?\s*{_PCT_RE}\s*Health(?!\s*Regen)",),
}

__all__ = [
    "AGE_NAME_TO_INT",
    "RARITIES",
    "parse_flat",
    "parse_percent",
    "extract",
    "extract_flat",
    "extract_level",
    "extract_tag_name",
    "normalise_tag",
    "first_flat",
    "extract_substats",
    "missing_fields",
]
