"""
============================================================
  FORGE MASTER — Constantes partagées
  Tout ce qui est "paramètre de configuration" du backend
  est centralisé ici pour éviter la dispersion.
============================================================
"""

import os

# ── Chemins ──────────────────────────────────────────────────
_DIR = os.path.dirname(os.path.abspath(__file__))
PROFIL_FILE          = os.path.join(_DIR, "profil.txt")
SKILLS_FILE          = os.path.join(_DIR, "skills.txt")
PETS_FILE            = os.path.join(_DIR, "pets.txt")
MOUNT_FILE           = os.path.join(_DIR, "mount.txt")
PETS_LIBRARY_FILE    = os.path.join(_DIR, "pets_library.txt")
MOUNT_LIBRARY_FILE   = os.path.join(_DIR, "mount_library.txt")

# ── Paramètres de simulation ─────────────────────────────────
TICK                = 0.01
DEFAULT_DUREE_MAX   = 300.0   # secondes simulées par combat (profil vs adversaire)
COMPANION_DUREE_MAX = 60.0    # plus court pour "moi vs moi" (évite combats infinis)
VITESSE_BASE        = 0.5
AVANCE_DISTANCE     = 3.0
N_SIMULATIONS       = 1000    # nombre de combats par test

# ── Schémas de stats ─────────────────────────────────────────

STATS_KEYS = [
    "hp_total", "attaque_total",
    "hp_base", "attaque_base",
    "health_pct", "damage_pct", "melee_pct", "ranged_pct",
    "taux_crit", "degat_crit", "health_regen",
    "lifesteal", "double_chance", "vitesse_attaque",
    "skill_damage", "skill_cooldown", "chance_blocage",
]

# Pets et mount partagent exactement le même schéma
COMPANION_STATS_KEYS = [
    "hp_flat", "damage_flat", "health_pct", "damage_pct",
    "melee_pct", "ranged_pct", "taux_crit", "degat_crit",
    "health_regen", "lifesteal", "double_chance", "vitesse_attaque",
    "skill_damage", "skill_cooldown", "chance_blocage",
]

# Alias rétrocompatibles — pets et mount utilisaient leurs propres constantes
PETS_STATS_KEYS  = COMPANION_STATS_KEYS
MOUNT_STATS_KEYS = COMPANION_STATS_KEYS

# Stats "en pourcentage" communes à profil/équipement/companion
PERCENT_STATS_KEYS = [
    "taux_crit", "degat_crit", "health_regen", "lifesteal",
    "double_chance", "vitesse_attaque", "skill_damage",
    "skill_cooldown", "chance_blocage",
    "health_pct", "damage_pct", "melee_pct", "ranged_pct",
]
