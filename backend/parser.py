"""
============================================================
  FORGE MASTER — Parsers
  Transforme du texte brut copié depuis le jeu en dictionnaires
  de stats. Zéro dépendance sur persistance ou simulation.
============================================================
"""

import logging
import re
from typing import Dict, Iterable, Optional

from .constants import COMPANION_STATS_KEYS

log = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════
#  UTILITAIRES BAS-NIVEAU
# ════════════════════════════════════════════════════════════

def parse_flat(val_str: str) -> float:
    """Convertit '877k' / '2.3m' / '1.5b' / '42' en float."""
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
        log.debug("parse_flat: impossible de parser %r", val_str)
        return 0.0


def extraire(texte: str, motifs: Iterable[str]) -> float:
    """Premier pourcentage trouvé dans le texte pour un des motifs donnés."""
    for motif in motifs:
        m = re.search(motif, texte, re.IGNORECASE)
        if m:
            try:
                return float(m.group(1).replace(",", ".").replace(" ", "."))
            except ValueError:
                continue
    return 0.0


def extraire_flat(texte: str, motifs: Iterable[str]) -> float:
    """Première valeur plate (avec suffixe k/m/b possible) pour un des motifs."""
    for motif in motifs:
        m = re.search(motif, texte, re.IGNORECASE)
        if m:
            return parse_flat(m.group(1))
    return 0.0


# ════════════════════════════════════════════════════════════
#  PROFIL JOUEUR
# ════════════════════════════════════════════════════════════

def parser_texte(texte: str) -> Dict[str, float]:
    """Parse le bloc de stats joueur copié depuis le jeu."""
    hp_total      = extraire_flat(texte, [r"([\d.]+[km]?)\s*Total Health"])
    attaque_total = extraire_flat(texte, [r"([\d.]+[km]?)\s*Total Damage"])
    health_pct    = extraire(texte, [r"\+([\d. ]+)%\s*Health(?!\s*Regen)"])
    damage_pct    = extraire(texte, [r"\+([\d. ]+)%\s*Damage(?!\s*%)"])
    melee_pct     = extraire(texte, [r"\+([\d. ]+)%\s*Melee Damage"])
    ranged_pct    = extraire(texte, [r"\+([\d. ]+)%\s*Ranged Damage"])

    hp_base = hp_total / (1 + health_pct / 100) if health_pct else hp_total

    return {
        "hp_total":        hp_total,
        "attaque_total":   attaque_total,
        "hp_base":         hp_base,
        "attaque_base":    attaque_total,
        "health_pct":      health_pct,
        "damage_pct":      damage_pct,
        "melee_pct":       melee_pct,
        "ranged_pct":      ranged_pct,
        "taux_crit":       extraire(texte, [r"\+([\d. ]+)%\s*Critical Chance"]),
        "degat_crit":      extraire(texte, [r"\+([\d. ]+)%\s*Critical Damage"]),
        "health_regen":    extraire(texte, [r"\+([\d. ]+)%\s*Health Regen"]),
        "lifesteal":       extraire(texte, [r"\+([\d. ]+)%\s*Lifesteal"]),
        "double_chance":   extraire(texte, [r"\+([\d. ]+)%\s*Double Chance"]),
        "vitesse_attaque": extraire(texte, [r"\+([\d. ]+)%\s*Attack Speed"]),
        "skill_damage":    extraire(texte, [r"\+([\d. ]+)%\s*Skill Damage"]),
        "skill_cooldown":  extraire(texte, [r"([+-][\d. ]+)%\s*Skill Cooldown"]),
        "chance_blocage":  extraire(texte, [r"\+([\d. ]+)%\s*Block Chance"]),
    }


# ════════════════════════════════════════════════════════════
#  ÉQUIPEMENT
# ════════════════════════════════════════════════════════════

def parser_equipement(texte: str) -> Dict[str, Optional[float]]:
    """Parse un bloc de stats d'équipement. type_attaque optionnel."""
    # Nettoyage : supprimer chiffres/lettres isolés (artefacts UI)
    texte_net = re.sub(r'(?m)^\s*\d+\s*$',   '', texte)
    texte_net = re.sub(r'(?m)^\s*[A-Z]\s*$', '', texte_net)
    texte_net = re.sub(r'\n(?![+\-\[\dA-Za-z\[])', ' ', texte_net)

    eq: Dict[str, Optional[float]] = {k: 0.0 for k in COMPANION_STATS_KEYS}
    eq["type_attaque"] = None

    # Health flat : "877k Health" mais pas "Health Regen" ni "Health %"
    m = re.search(r'([\d.]+[kmb]?)\s*Health(?!\s*Regen)(?!\s*%)', texte_net, re.IGNORECASE)
    if m:
        eq["hp_flat"] = parse_flat(m.group(1))

    # Damage flat : "12.3m Damage" optionnellement suivi de (ranged)
    m = re.search(r'([\d.]+[kmb]?)\s*Damage(\s*\([^)]*\))?(?!\s*%)', texte_net, re.IGNORECASE)
    if m:
        eq["damage_flat"] = parse_flat(m.group(1))
        suffix = m.group(2) or ""
        if re.search(r'ranged', suffix, re.IGNORECASE):
            eq["type_attaque"] = "distance"

    eq["taux_crit"]       = extraire(texte_net, [r'\+([\d. ]+)%\s*Critical\s*Chance'])
    eq["degat_crit"]      = extraire(texte_net, [r'\+([\d. ]+)%\s*Critical\s*Damage'])
    eq["health_regen"]    = extraire(texte_net, [r'\+([\d. ]+)%\s*Health\s*Regen'])
    eq["lifesteal"]       = extraire(texte_net, [r'\+([\d. ]+)%\s*Lifesteal'])
    eq["double_chance"]   = extraire(texte_net, [r'\+([\d. ]+)%\s*Double\s*Chance'])
    eq["vitesse_attaque"] = extraire(texte_net, [r'\+([\d. ]+)%\s*Attack\s*Speed'])
    eq["skill_damage"]    = extraire(texte_net, [r'\+([\d. ]+)%\s*Skill\s*Damage'])
    eq["skill_cooldown"]  = extraire(texte_net, [r'([+-][\d. ]+)%\s*Skill\s*Cooldown'])
    eq["chance_blocage"]  = extraire(texte_net, [r'\+([\d. ]+)%\s*Block\s*Chance'])
    eq["health_pct"]      = extraire(texte_net, [r'\+([\d. ]+)%\s*Health(?!\s*Regen)'])
    eq["damage_pct"]      = extraire(texte_net, [r'\+([\d. ]+)%\s*Damage(?!\s*%)'])
    eq["melee_pct"]       = extraire(texte_net, [r'\+([\d. ]+)%\s*Melee\s*Damage'])
    eq["ranged_pct"]      = extraire(texte_net, [r'\+([\d. ]+)%\s*Ranged\s*Damage'])

    return eq


# ════════════════════════════════════════════════════════════
#  COMPANION (pet + mount)
# ════════════════════════════════════════════════════════════

def _companion_vide() -> Dict[str, float]:
    return {k: 0.0 for k in COMPANION_STATS_KEYS}


def parser_companion(texte: str) -> Dict[str, float]:
    """Parse un bloc de stats de pet ou de mount — schéma identique."""
    texte_net = re.sub(r'\n(?![+\-\[\d])', ' ', texte)
    c = _companion_vide()

    m = re.search(r'([\d.]+[km]?)\s*Health(?!\s*Regen)(?!\s*%)', texte_net, re.IGNORECASE)
    if m:
        c["hp_flat"] = parse_flat(m.group(1))

    m = re.search(r'([\d.]+[km]?)\s*Damage(?!\s*%)', texte_net, re.IGNORECASE)
    if m:
        c["damage_flat"] = parse_flat(m.group(1))

    c["taux_crit"]       = extraire(texte_net, [r"\+([\d. ]+)%\s*Critical Chance"])
    c["degat_crit"]      = extraire(texte_net, [r"\+([\d. ]+)%\s*Critical Damage"])
    c["health_regen"]    = extraire(texte_net, [r"\+([\d. ]+)%\s*Health Regen"])
    c["lifesteal"]       = extraire(texte_net, [r"\+([\d. ]+)%\s*Lifesteal"])
    c["double_chance"]   = extraire(texte_net, [r"\+([\d. ]+)%\s*Double Chance"])
    c["vitesse_attaque"] = extraire(texte_net, [r"\+([\d. ]+)%\s*Attack Speed"])
    c["skill_damage"]    = extraire(texte_net, [r"\+([\d. ]+)%\s*Skill Damage"])
    c["skill_cooldown"]  = extraire(texte_net, [r"([+-][\d. ]+)%\s*Skill Cooldown"])
    c["chance_blocage"]  = extraire(texte_net, [r"\+([\d. ]+)%\s*Block Chance"])
    c["health_pct"]      = extraire(texte_net, [r"\+([\d. ]+)%\s*Health(?!\s*Regen)"])
    c["damage_pct"]      = extraire(texte_net, [r"\+([\d. ]+)%\s*Damage(?!\s*%)"])
    c["melee_pct"]       = extraire(texte_net, [r"\+([\d. ]+)%\s*Melee Damage"])
    c["ranged_pct"]      = extraire(texte_net, [r"\+([\d. ]+)%\s*Ranged Damage"])

    return c


# ════════════════════════════════════════════════════════════
#  MÉTADONNÉES COMPANION (nom / rareté / level)
# ════════════════════════════════════════════════════════════

_RE_LEVEL       = re.compile(r'Lv\.?\s*(\d+)', re.IGNORECASE)
_RE_NAME_RARITY = re.compile(
    r'\[\s*([A-Za-z]+)\s*\]\s*([^\r\n\[\]]+?)\s*(?:\n|$)',
    re.IGNORECASE,
)


def parser_companion_meta(texte: str) -> Dict:
    """
    Extrait les métadonnées d'un bloc pet/mount :
      - name  : str ou None
      - rarity: str (lowercase) ou None
      - level : int ou None
      - stats : dict complet (résultat de parser_companion)
    """
    m_lv = _RE_LEVEL.search(texte)
    level = int(m_lv.group(1)) if m_lv else None

    m_nr = _RE_NAME_RARITY.search(texte)
    if m_nr:
        rarity = m_nr.group(1).strip().lower()
        name   = m_nr.group(2).strip()
        # Rejeter les captures "vides" ou qui ressemblent à des mots-clés parasites
        if not name:
            name = None
    else:
        rarity = None
        name   = None

    return {
        "name":   name,
        "rarity": rarity,
        "level":  level,
        "stats":  parser_companion(texte),
    }


# Alias rétrocompatibles
parser_pet   = parser_companion
parser_mount = parser_companion
