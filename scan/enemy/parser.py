"""
============================================================
  FORGE MASTER — Enemy OCR text parser

  First leg of the enemy-recompute pipeline: convert raw OCR
  output (the same kind of text that ``scan.ocr.parsers`` already
  understands) into structured ``EnemyOcrRaw`` /
  ``EnemyIdentifiedProfile`` objects.

  This module deliberately splits responsibilities:

    - ``parse_substats(text)``      → list[OcrSubstat]
        Pure text parsing of "+50.1% Critical Chance" / "+28.9%
        Damage" lines. Maps free-text labels onto canonical ids
        consumed by the calculator.

    - ``parse_displayed_totals(text)`` → (damage, health, level)
        Reuses the same regexes as ``parser.parse_profile_text``
        for HP/Dmg totals and Forge level.

    - ``parse_enemy_text(text)``    → EnemyIdentifiedProfile
        Convenience wrapper that pre-fills the profile with
        EVERYTHING the OCR text alone can give us. The caller is
        expected to fill in items/pets/mount/skills via the icon
        identifier (Phase 2) — until then the calculator can run
        on hand-built profiles for testing.
============================================================
"""

from __future__ import annotations

import re
from typing import List, Tuple

from .types import (
    EnemyIdentifiedProfile,
    OcrSubstat,
)
from scan.ocr.parsers.common import parse_flat


# ────────────────────────────────────────────────────────────
#  Substat label → canonical id
# ────────────────────────────────────────────────────────────
#
# The keys are matched case-insensitively. The internal ids match
# what ``statEngine.ts`` uses (and what the calculator expects).
#
# Game-side labels:
#     "Critical Chance"  / "Critical Damage"
#     "Lifesteal"        / "Health Regen" / "Block Chance"
#     "Double Chance"    / "Attack Speed"
#     "Damage"           / "Health"             (global multipliers)
#     "Melee Damage"     / "Ranged Damage"      (specific multipliers)
#     "Skill Damage"     / "Skill Cooldown"
#
# Two pre-existing OCR aliases from backend/fix_ocr.py also match:
# "Lifesteal" sometimes lands as "Life Steal", "Cooldown" as "CD".

_SUBSTAT_LABELS: List[Tuple[str, str]] = [
    ("Critical Chance",  "CriticalChance"),
    ("Critical Damage",  "CriticalDamage"),
    ("Crit Chance",      "CriticalChance"),
    ("Crit Damage",      "CriticalDamage"),

    ("Block Chance",     "BlockChance"),
    ("Health Regen",     "HealthRegen"),

    ("Lifesteal",        "LifeSteal"),
    ("Life Steal",       "LifeSteal"),

    ("Double Chance",    "DoubleDamageChance"),
    ("Double Damage",    "DoubleDamageChance"),
    ("Attack Speed",     "AttackSpeed"),

    ("Skill Damage",     "SkillDamageMulti"),
    ("Skill Cooldown",   "SkillCooldownMulti"),
    ("Skill CD",         "SkillCooldownMulti"),

    ("Move Speed",       "MoveSpeed"),

    # Specific damage multipliers — must come BEFORE the generic
    # "Damage" / "Health" entries so the more specific labels win.
    ("Melee Damage",     "MeleeDamageMulti"),
    ("Ranged Damage",    "RangedDamageMulti"),

    ("Damage",           "DamageMulti"),
    ("Health",           "HealthMulti"),
]

# Pre-compile a single regex that captures EVERY known label.
# The label group captures the longest match thanks to Python's
# left-to-right alternation and our manual ordering above.
_SUBSTAT_REGEX = re.compile(
    r"([+-]?\s*\d[\d. ,]*)\s*%\s*("
    + "|".join(re.escape(lbl) for lbl, _id in _SUBSTAT_LABELS)
    + r")\b",
    re.IGNORECASE,
)

# Lookup table: lower-cased label → canonical id.
_LABEL_TO_ID = {lbl.lower(): canon for lbl, canon in _SUBSTAT_LABELS}


def _normalise_value(raw: str) -> float:
    """Convert ``"+50.1"`` / ``" 28,9 "`` / ``"-3.5"`` to ``float``.

    The OCR sometimes inserts spaces inside numbers (decimal point
    confused with a space) or uses the European comma separator.
    """
    cleaned = raw.replace(",", ".").replace(" ", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def parse_substats(text: str) -> List[OcrSubstat]:
    """Extract every recognisable ``+X% StatName`` from the OCR text.

    Values are returned as PERCENTAGE POINTS (50.1 for "+50.1%").
    Multiple occurrences of the same stat are summed — useful when
    the OCR doubles a value because of a re-scan.
    """
    out: dict[str, float] = {}
    for m in _SUBSTAT_REGEX.finditer(text):
        value = _normalise_value(m.group(1))
        label = m.group(2).strip().lower()
        canon = _LABEL_TO_ID.get(label)
        if canon is None:
            continue
        out[canon] = out.get(canon, 0.0) + value
    return [OcrSubstat(stat_id=sid, value=v) for sid, v in out.items()]


# ────────────────────────────────────────────────────────────
#  Displayed totals (HP / Damage / Forge level)
# ────────────────────────────────────────────────────────────

_RE_TOTAL_HEALTH = re.compile(
    r"([\d.]+\s*[kmb]?)\s*Total\s*Health", re.IGNORECASE,
)
_RE_TOTAL_DAMAGE = re.compile(
    r"([\d.]+\s*[kmb]?)\s*Total\s*Damage", re.IGNORECASE,
)
_RE_FORGE_LEVEL = re.compile(r"Lv\.?\s*(\d+)", re.IGNORECASE)


def parse_displayed_totals(text: str) -> Tuple[float, float, int]:
    """Returns ``(damage, health, forge_level)`` parsed from the OCR text.

    Any field not found is returned as 0.
    """
    m_dmg = _RE_TOTAL_DAMAGE.search(text)
    m_hp  = _RE_TOTAL_HEALTH.search(text)
    m_lv  = _RE_FORGE_LEVEL.search(text)

    damage = parse_flat(m_dmg.group(1)) if m_dmg else 0.0
    health = parse_flat(m_hp.group(1))  if m_hp  else 0.0
    level  = int(m_lv.group(1))         if m_lv  else 0
    return damage, health, level


# ────────────────────────────────────────────────────────────
#  Convenience wrapper
# ────────────────────────────────────────────────────────────


def parse_enemy_text(text: str) -> EnemyIdentifiedProfile:
    """Pre-fill an EnemyIdentifiedProfile with everything we can read
    from the OCR text alone.

    Item / pet / mount / skill identifiers stay empty: those require
    the visual identification step that lives in Phase 2 of the
    chantier. The calculator can run on the result regardless — it
    will simply contribute nothing for unidentified slots.
    """
    damage, health, forge_level = parse_displayed_totals(text)
    return EnemyIdentifiedProfile(
        forge_level=forge_level,
        total_damage_displayed=damage,
        total_health_displayed=health,
        substats=parse_substats(text),
    )
