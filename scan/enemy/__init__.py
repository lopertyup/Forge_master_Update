"""Enemy OCR types and parser."""

from .types import (
    SLOT_ORDER,
    SLOT_TO_JSON_TYPE,
    EnemyComputedStats,
    EnemyIdentifiedProfile,
    EnemyOcrRaw,
    IdentifiedItem,
    IdentifiedMount,
    IdentifiedPet,
    IdentifiedSkill,
    OcrEquipmentSlot,
    OcrMount,
    OcrPet,
    OcrSkill,
    OcrSubstat,
)
from .parser import parse_displayed_totals, parse_enemy_text, parse_substats

__all__ = [
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
    "parse_substats",
    "parse_displayed_totals",
    "parse_enemy_text",
]
