"""
============================================================
  FORGE MASTER — Parsers
  Turn raw text copied from the game into stat dictionaries.
  Zero dependency on persistence or simulation.
============================================================
"""

import logging
import re
from typing import Dict, Iterable, Optional

from .constants import COMPANION_STATS_KEYS

log = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════
#  LOW-LEVEL UTILITIES
# ════════════════════════════════════════════════════════════

def parse_flat(val_str: str) -> float:
    """Convert '877k' / '2.3m' / '1.5b' / '42' to float."""
    val_str = str(val_str).strip().lower().replace(",", ".")
    try:
        if val_str.endswith("b"):
            return float(val_str[:-1]) * 1_000_000_000
        if val_str.endswith("m"):
            return float(val_str[:-1]) * 1_000_000
        if val_str.endswith("k"):
            return float(val_str[:-1]) * 1_000
        return float(val_str)
    except ValueError:
        log.debug("parse_flat: could not parse %r", val_str)
        return 0.0


def extract(text: str, patterns: Iterable[str]) -> float:
    """First percentage found in the text matching any of the given patterns."""
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            try:
                return float(m.group(1).replace(",", ".").replace(" ", "."))
            except ValueError:
                continue
    return 0.0


def extract_flat(text: str, patterns: Iterable[str]) -> float:
    """First flat value (k/m/b suffix allowed) matching any of the patterns."""
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return parse_flat(m.group(1))
    return 0.0


# ════════════════════════════════════════════════════════════
#  PLAYER PROFILE
# ════════════════════════════════════════════════════════════

def parse_profile_text(text: str) -> Dict[str, float]:
    """Parse the player stat block copied from the game."""
    hp_total     = extract_flat(text, [r"([\d.]+[km]?)\s*Total Health"])
    attack_total = extract_flat(text, [r"([\d.]+[km]?)\s*Total Damage"])
    health_pct   = extract(text, [r"\+([\d. ]+)%\s*Health(?!\s*Regen)"])
    damage_pct   = extract(text, [r"\+([\d. ]+)%\s*Damage(?!\s*%)"])
    melee_pct    = extract(text, [r"\+([\d. ]+)%\s*Melee Damage"])
    ranged_pct   = extract(text, [r"\+([\d. ]+)%\s*Ranged Damage"])

    hp_base = hp_total / (1 + health_pct / 100) if health_pct else hp_total

    return {
        "hp_total":       hp_total,
        "attack_total":   attack_total,
        "hp_base":        hp_base,
        "attack_base":    attack_total,
        "health_pct":     health_pct,
        "damage_pct":     damage_pct,
        "melee_pct":      melee_pct,
        "ranged_pct":     ranged_pct,
        "crit_chance":    extract(text, [r"\+([\d. ]+)%\s*Critical Chance"]),
        "crit_damage":    extract(text, [r"\+([\d. ]+)%\s*Critical Damage"]),
        "health_regen":   extract(text, [r"\+([\d. ]+)%\s*Health Regen"]),
        "lifesteal":      extract(text, [r"\+([\d. ]+)%\s*Lifesteal"]),
        "double_chance":  extract(text, [r"\+([\d. ]+)%\s*Double Chance"]),
        "attack_speed":   extract(text, [r"\+([\d. ]+)%\s*Attack Speed"]),
        "skill_damage":   extract(text, [r"\+([\d. ]+)%\s*Skill Damage"]),
        "skill_cooldown": extract(text, [r"([+-][\d. ]+)%\s*Skill Cooldown"]),
        "block_chance":   extract(text, [r"\+([\d. ]+)%\s*Block Chance"]),
    }


# ════════════════════════════════════════════════════════════
#  EQUIPMENT
# ════════════════════════════════════════════════════════════

def parse_equipment(text: str) -> Dict[str, Optional[float]]:
    """Parse an equipment stat block. attack_type optional."""
    # Cleanup: drop lone digits / single letters (UI artifacts)
    clean = re.sub(r'(?m)^\s*\d+\s*$',   '', text)
    clean = re.sub(r'(?m)^\s*[A-Z]\s*$', '', clean)
    clean = re.sub(r'\n(?![+\-\[\dA-Za-z\[])', ' ', clean)

    eq: Dict[str, Optional[float]] = {k: 0.0 for k in COMPANION_STATS_KEYS}
    eq["attack_type"] = None

    # Flat health: "877k Health" but not "Health Regen" or "Health %"
    m = re.search(r'([\d.]+[kmb]?)\s*Health(?!\s*Regen)(?!\s*%)', clean, re.IGNORECASE)
    if m:
        eq["hp_flat"] = parse_flat(m.group(1))

    # Flat damage: "12.3m Damage" optionally followed by (ranged)
    m = re.search(r'([\d.]+[kmb]?)\s*Damage(\s*\([^)]*\))?(?!\s*%)', clean, re.IGNORECASE)
    if m:
        eq["damage_flat"] = parse_flat(m.group(1))
        suffix = m.group(2) or ""
        if re.search(r'ranged', suffix, re.IGNORECASE):
            eq["attack_type"] = "ranged"

    eq["crit_chance"]    = extract(clean, [r'\+([\d. ]+)%\s*Critical\s*Chance'])
    eq["crit_damage"]    = extract(clean, [r'\+([\d. ]+)%\s*Critical\s*Damage'])
    eq["health_regen"]   = extract(clean, [r'\+([\d. ]+)%\s*Health\s*Regen'])
    eq["lifesteal"]      = extract(clean, [r'\+([\d. ]+)%\s*Lifesteal'])
    eq["double_chance"]  = extract(clean, [r'\+([\d. ]+)%\s*Double\s*Chance'])
    eq["attack_speed"]   = extract(clean, [r'\+([\d. ]+)%\s*Attack\s*Speed'])
    eq["skill_damage"]   = extract(clean, [r'\+([\d. ]+)%\s*Skill\s*Damage'])
    eq["skill_cooldown"] = extract(clean, [r'([+-][\d. ]+)%\s*Skill\s*Cooldown'])
    eq["block_chance"]   = extract(clean, [r'\+([\d. ]+)%\s*Block\s*Chance'])
    eq["health_pct"]     = extract(clean, [r'\+([\d. ]+)%\s*Health(?!\s*Regen)'])
    eq["damage_pct"]     = extract(clean, [r'\+([\d. ]+)%\s*Damage(?!\s*%)'])
    eq["melee_pct"]      = extract(clean, [r'\+([\d. ]+)%\s*Melee\s*Damage'])
    eq["ranged_pct"]     = extract(clean, [r'\+([\d. ]+)%\s*Ranged\s*Damage'])

    return eq


# ════════════════════════════════════════════════════════════
#  COMPANION (pet + mount)
# ════════════════════════════════════════════════════════════

def _empty_companion() -> Dict[str, float]:
    return {k: 0.0 for k in COMPANION_STATS_KEYS}


def parse_companion(text: str) -> Dict[str, float]:
    """Parse a pet or mount stat block — identical schema."""
    clean = re.sub(r'\n(?![+\-\[\d])', ' ', text)
    c = _empty_companion()

    m = re.search(r'([\d.]+[km]?)\s*Health(?!\s*Regen)(?!\s*%)', clean, re.IGNORECASE)
    if m:
        c["hp_flat"] = parse_flat(m.group(1))

    m = re.search(r'([\d.]+[km]?)\s*Damage(?!\s*%)', clean, re.IGNORECASE)
    if m:
        c["damage_flat"] = parse_flat(m.group(1))

    c["crit_chance"]    = extract(clean, [r"\+([\d. ]+)%\s*Critical Chance"])
    c["crit_damage"]    = extract(clean, [r"\+([\d. ]+)%\s*Critical Damage"])
    c["health_regen"]   = extract(clean, [r"\+([\d. ]+)%\s*Health Regen"])
    c["lifesteal"]      = extract(clean, [r"\+([\d. ]+)%\s*Lifesteal"])
    c["double_chance"]  = extract(clean, [r"\+([\d. ]+)%\s*Double Chance"])
    c["attack_speed"]   = extract(clean, [r"\+([\d. ]+)%\s*Attack Speed"])
    c["skill_damage"]   = extract(clean, [r"\+([\d. ]+)%\s*Skill Damage"])
    c["skill_cooldown"] = extract(clean, [r"([+-][\d. ]+)%\s*Skill Cooldown"])
    c["block_chance"]   = extract(clean, [r"\+([\d. ]+)%\s*Block Chance"])
    c["health_pct"]     = extract(clean, [r"\+([\d. ]+)%\s*Health(?!\s*Regen)"])
    c["damage_pct"]     = extract(clean, [r"\+([\d. ]+)%\s*Damage(?!\s*%)"])
    c["melee_pct"]      = extract(clean, [r"\+([\d. ]+)%\s*Melee Damage"])
    c["ranged_pct"]     = extract(clean, [r"\+([\d. ]+)%\s*Ranged Damage"])

    return c


# ════════════════════════════════════════════════════════════
#  COMPANION METADATA (name / rarity / level)
# ════════════════════════════════════════════════════════════

_RE_LEVEL       = re.compile(r'Lv\.?\s*(\d+)', re.IGNORECASE)
_RE_NAME_RARITY = re.compile(
    r'\[\s*([A-Za-z]+)\s*\]\s*([^\r\n\[\]]+?)\s*(?:\n|$)',
    re.IGNORECASE,
)


def parse_companion_meta(text: str) -> Dict:
    """
    Extract metadata from a pet/mount block:
      - name  : str or None
      - rarity: str (lowercase) or None
      - level : int or None
      - stats : full stat dict (result of parse_companion)
    """
    m_lv = _RE_LEVEL.search(text)
    level = int(m_lv.group(1)) if m_lv else None

    m_nr = _RE_NAME_RARITY.search(text)
    if m_nr:
        rarity = m_nr.group(1).strip().lower()
        name   = m_nr.group(2).strip()
        if not name:
            name = None
    else:
        rarity = None
        name   = None

    return {
        "name":   name,
        "rarity": rarity,
        "level":  level,
        "stats":  parse_companion(text),
    }


# Back-compat aliases
parse_pet   = parse_companion
parse_mount = parse_companion
