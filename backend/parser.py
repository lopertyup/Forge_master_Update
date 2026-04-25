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
 
# Frontière entre deux items : une ligne "[Rarity] Name".
_RE_ITEM_BOUNDARY = re.compile(r'(?=^\[)', re.MULTILINE)
 
 
def _parse_single_equipment(text: str) -> Dict[str, Optional[float]]:
    """Parse UN seul bloc équipement (déjà isolé, sans autre item dedans)."""
    eq: Dict[str, Optional[float]] = {k: 0.0 for k in COMPANION_STATS_KEYS}
    eq["attack_type"] = None
 
    # Flat health: "877k Health" mais pas "Health Regen" ni "Health %"
    m = re.search(r'([\d.]+[kmb]?)\s*Health(?!\s*Regen)(?!\s*%)', text, re.IGNORECASE)
    if m:
        eq["hp_flat"] = parse_flat(m.group(1))
 
    # Flat damage: "12.3m Damage" optionnellement suivi de (ranged) ou (melee).
    # Tout équipement portant du "damage flat" est une ARME, et possède donc
    # un type d'attaque. On considère « melee » par défaut (les armes melee
    # ne portent pas de qualifier en jeu) et on bascule à « ranged » lorsque
    # le qualifier est présent.
    m = re.search(r'([\d.]+[kmb]?)\s*Damage(\s*\([^)]*\))?(?!\s*%)', text, re.IGNORECASE)
    if m:
        eq["damage_flat"] = parse_flat(m.group(1))
        suffix = m.group(2) or ""
        if re.search(r'ranged', suffix, re.IGNORECASE):
            eq["attack_type"] = "ranged"
        else:
            eq["attack_type"] = "melee"
 
    eq["crit_chance"]    = extract(text, [r'\+([\d. ]+)%\s*Critical\s*Chance'])
    eq["crit_damage"]    = extract(text, [r'\+([\d. ]+)%\s*Critical\s*Damage'])
    eq["health_regen"]   = extract(text, [r'\+([\d. ]+)%\s*Health\s*Regen'])
    eq["lifesteal"]      = extract(text, [r'\+([\d. ]+)%\s*Lifesteal'])
    eq["double_chance"]  = extract(text, [r'\+([\d. ]+)%\s*Double\s*Chance'])
    eq["attack_speed"]   = extract(text, [r'\+([\d. ]+)%\s*Attack\s*Speed'])
    eq["skill_damage"]   = extract(text, [r'\+([\d. ]+)%\s*Skill\s*Damage'])
    eq["skill_cooldown"] = extract(text, [r'([+-][\d. ]+)%\s*Skill\s*Cooldown'])
    eq["block_chance"]   = extract(text, [r'\+([\d. ]+)%\s*Block\s*Chance'])
    eq["health_pct"]     = extract(text, [r'\+([\d. ]+)%\s*Health(?!\s*Regen)'])
    eq["damage_pct"]     = extract(text, [r'\+([\d. ]+)%\s*Damage(?!\s*%)'])
    eq["melee_pct"]      = extract(text, [r'\+([\d. ]+)%\s*Melee\s*Damage'])
    eq["ranged_pct"]     = extract(text, [r'\+([\d. ]+)%\s*Ranged\s*Damage'])
 
    # Nom et rareté depuis la ligne "[Rarity] Name"
    m_nr = re.match(r'^\[\s*([A-Za-z]+)\s*\]\s*(.+?)\s*$',
                    text.strip().splitlines()[0] if text.strip() else "",
                    re.IGNORECASE)
    if m_nr:
        eq["rarity"] = m_nr.group(1).strip().lower()
        eq["name"]   = m_nr.group(2).strip()
 
    return eq
 
 
def parse_equipment(text: str) -> Dict[str, Optional[float]]:
    """Parse un bloc équipement.
 
    Si le texte contient deux items (séparés par une ligne '[Rarity] Name'),
    retourne un dict avec les clés 'equipped' et 'candidate' pointant chacun
    vers un dict de stats.  Si un seul item est présent, retourne directement
    le dict de stats (comportement rétrocompatible).
    """
    # Séparer sur chaque ligne commençant par '[' (frontière d'item).
    blocks = [b.strip() for b in _RE_ITEM_BOUNDARY.split(text) if b.strip()]
 
    if len(blocks) == 1:
        # Un seul item — comportement identique à l'ancienne version.
        return _parse_single_equipment(blocks[0])
 
    if len(blocks) >= 2:
        # Deux items : premier = équipé, second = candidat.
        return {
            "equipped":  _parse_single_equipment(blocks[0]),
            "candidate": _parse_single_equipment(blocks[1]),
        }
 
    # Texte vide ou sans rarity bracket.
    eq: Dict[str, Optional[float]] = {k: 0.0 for k in COMPANION_STATS_KEYS}
    eq["attack_type"] = None
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

    m = re.search(r'([\d.]+[kmb]?)\s*Health(?!\s*Regen)(?!\s*%)', clean, re.IGNORECASE)
    if m:
        c["hp_flat"] = parse_flat(m.group(1))

    m = re.search(r'([\d.]+[kmb]?)\s*Damage(?!\s*%)', clean, re.IGNORECASE)
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


# ════════════════════════════════════════════════════════════
#  SKILL (in-game text)
# ════════════════════════════════════════════════════════════
#
#  Sample input the user copies from the game:
#
#      Equipped
#      Lv.3
#      0/2
#      [Ultimate] Stampede
#      Call on a Bull stampede, each
#      dealing 2.77m Damage
#      Passive:
#      +43.4k Base Damage +347k Base Health
#
#  Note: the "dealing X Damage" line gives the TOTAL damage of one
#  cast (sum across hits). To match the simulator's "damage per hit"
#  convention we divide by `hits` from the library entry.
# ════════════════════════════════════════════════════════════

_RE_SKILL_NAME_RARITY = re.compile(
    r'\[\s*([A-Za-z]+)\s*\]\s*([^\r\n\[\]]+?)\s*(?:\n|$)',
    re.IGNORECASE,
)
# Tolerate "dealing 2.77m Damage" / "deals 600k Damage" / "1.2m Damage"
_RE_SKILL_DAMAGE = re.compile(
    r'(?:dealing|deals|deal)?\s*([\d.]+\s*[kmb]?)\s*Damage(?!\s*%)',
    re.IGNORECASE,
)
_RE_SKILL_PASS_DMG = re.compile(
    r'\+\s*([\d.]+\s*[kmb]?)\s*Base\s*Damage', re.IGNORECASE)
_RE_SKILL_PASS_HP  = re.compile(
    r'\+\s*([\d.]+\s*[kmb]?)\s*Base\s*Health', re.IGNORECASE)


def parse_skill_meta(text: str) -> Dict:
    """
    Extract skill metadata from a pasted in-game block:
      - name           : str or None
      - rarity         : str (lowercase) or None
      - level          : int or None
      - total_damage   : float (sum across hits, as printed in game) or 0
      - passive_damage : float or 0
      - passive_hp     : float or 0
    """
    m_lv = _RE_LEVEL.search(text)
    level = int(m_lv.group(1)) if m_lv else None

    m_nr = _RE_SKILL_NAME_RARITY.search(text)
    if m_nr:
        rarity = m_nr.group(1).strip().lower()
        name   = m_nr.group(2).strip() or None
    else:
        rarity = None
        name   = None

    # total damage — first occurrence of "X Damage" outside the passive line.
    # Strip the passive section (everything after "Passive:") so a stray
    # "+10 Damage" in passives can't be picked up as the cast damage.
    cast_text = re.split(r'Passive\s*:', text, maxsplit=1, flags=re.IGNORECASE)[0]
    m_dmg = _RE_SKILL_DAMAGE.search(cast_text)
    total_damage = parse_flat(m_dmg.group(1).replace(" ", "")) if m_dmg else 0.0

    m_pd = _RE_SKILL_PASS_DMG.search(text)
    passive_damage = parse_flat(m_pd.group(1).replace(" ", "")) if m_pd else 0.0

    m_ph = _RE_SKILL_PASS_HP.search(text)
    passive_hp = parse_flat(m_ph.group(1).replace(" ", "")) if m_ph else 0.0

    return {
        "name":           name,
        "rarity":         rarity,
        "level":          level,
        "total_damage":   total_damage,
        "passive_damage": passive_damage,
        "passive_hp":     passive_hp,
    }
