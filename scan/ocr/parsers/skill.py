"""OCR-only parser for skill popups."""

from __future__ import annotations

import re
from typing import Dict

from .common import _FLAT_RE, extract_level, extract_tag_name, first_flat, missing_fields, normalise_tag


def parse_skill_text(text: str) -> Dict[str, object]:
    tag, name = extract_tag_name(text)
    rarity, _age = normalise_tag(tag)
    passive_text = re.split(r"Passive\s*:", text or "", maxsplit=1, flags=re.IGNORECASE)
    active_text = passive_text[0] if passive_text else (text or "")
    damage_total = first_flat(active_text, (rf"(?:dealing|deals|deal)?\s*{_FLAT_RE}\s*Damage(?!\s*%)",))
    out: Dict[str, object] = {
        "__name__": name,
        "__level__": extract_level(text),
        "__rarity__": rarity or "",
        "hp_flat": first_flat(text, (rf"\+\s*{_FLAT_RE}\s*Base\s*Health",)),
        "damage_flat": first_flat(text, (rf"\+\s*{_FLAT_RE}\s*Base\s*Damage",)),
        "type": "damage" if damage_total else "buff",
        "substats": {},
    }
    if damage_total:
        out["damage"] = damage_total
        out["hits"] = 1.0
    out["missing_fields"] = missing_fields(out, ("__name__", "__level__", "__rarity__"))
    return out


def parse_skill_meta(text: str) -> Dict[str, object]:
    """Legacy parser for skill metadata."""
    tag, name = extract_tag_name(text or "")
    rarity, _age = normalise_tag(tag)
    passive_text = re.split(r"Passive\s*:", text or "", maxsplit=1, flags=re.IGNORECASE)
    cast_text = passive_text[0] if passive_text else (text or "")
    return {
        "name": name or None,
        "rarity": rarity.lower() if isinstance(rarity, str) else rarity,
        "level": extract_level(text or "") or None,
        "total_damage": first_flat(
            cast_text,
            (rf"(?:dealing|deals|deal)?\s*{_FLAT_RE}\s*Damage(?!\s*%)",),
        ),
        "passive_damage": first_flat(text or "", (rf"\+\s*{_FLAT_RE}\s*Base\s*Damage",)),
        "passive_hp": first_flat(text or "", (rf"\+\s*{_FLAT_RE}\s*Base\s*Health",)),
    }


__all__ = ["parse_skill_text", "parse_skill_meta"]
