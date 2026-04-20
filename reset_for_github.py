"""
============================================================
  FORGE MASTER — reset_for_github.py
  Remet profil.txt et pets.txt à zéro avant un git push.
  skills.txt est conservé intact.

  Lancer depuis la racine du projet :
    python reset_for_github.py
  Puis :
    git add .
    git commit -m "votre message"
    git push
============================================================
"""

import os

_DIR = os.path.dirname(os.path.abspath(__file__))

PROFIL_FILE = os.path.join(_DIR, "backend", "profil.txt")
PETS_FILE   = os.path.join(_DIR, "backend", "pets.txt")


# ════════════════════════════════════════════════════════════
#  PROFIL VIDE
# ════════════════════════════════════════════════════════════

PROFIL_VIDE = """\
# ============================================================
# FORGE MASTER — Profil joueur (modifiable a la main)
# ============================================================

[JOUEUR]
hp_total             = 0.0
attaque_total        = 0.0
hp_base              = 0.0
attaque_base         = 0.0
health_pct           = 0.0
damage_pct           = 0.0
melee_pct            = 0.0
ranged_pct           = 0.0
taux_crit            = 0.0
degat_crit           = 0.0
health_regen         = 0.0
lifesteal            = 0.0
double_chance        = 0.0
vitesse_attaque      = 0.0
skill_damage         = 0.0
skill_cooldown       = 0.0
chance_blocage       = 0.0
type_attaque         = corps_a_corps
skills               =
"""

# ════════════════════════════════════════════════════════════
#  PETS VIDES
# ════════════════════════════════════════════════════════════

PETS_VIDE = """\
# ============================================================
# FORGE MASTER — Pets actifs (modifiable a la main)
# ============================================================

[PET1]
hp_flat              = 0.0
damage_flat          = 0.0
health_pct           = 0.0
damage_pct           = 0.0
melee_pct            = 0.0
ranged_pct           = 0.0
taux_crit            = 0.0
degat_crit           = 0.0
health_regen         = 0.0
lifesteal            = 0.0
double_chance        = 0.0
vitesse_attaque      = 0.0
skill_damage         = 0.0
skill_cooldown       = 0.0
chance_blocage       = 0.0

[PET2]
hp_flat              = 0.0
damage_flat          = 0.0
health_pct           = 0.0
damage_pct           = 0.0
melee_pct            = 0.0
ranged_pct           = 0.0
taux_crit            = 0.0
degat_crit           = 0.0
health_regen         = 0.0
lifesteal            = 0.0
double_chance        = 0.0
vitesse_attaque      = 0.0
skill_damage         = 0.0
skill_cooldown       = 0.0
chance_blocage       = 0.0

[PET3]
hp_flat              = 0.0
damage_flat          = 0.0
health_pct           = 0.0
damage_pct           = 0.0
melee_pct            = 0.0
ranged_pct           = 0.0
taux_crit            = 0.0
degat_crit           = 0.0
health_regen         = 0.0
lifesteal            = 0.0
double_chance        = 0.0
vitesse_attaque      = 0.0
skill_damage         = 0.0
skill_cooldown       = 0.0
chance_blocage       = 0.0
"""


# ════════════════════════════════════════════════════════════
#  RESET
# ════════════════════════════════════════════════════════════

def reset():
    print("=" * 50)
    print("  FORGE MASTER — Reset pour GitHub")
    print("=" * 50)

    for path, contenu, nom in [
        (PROFIL_FILE, PROFIL_VIDE, "profil.txt"),
        (PETS_FILE,   PETS_VIDE,   "pets.txt"),
    ]:
        with open(path, "w", encoding="utf-8") as f:
            f.write(contenu)
        print(f"  ✅ {nom} remis à zéro")

    print("\n  skills.txt conservé intact.")
    print("\n  Tu peux maintenant faire :")
    print('    git add .')
    print('    git commit -m "ton message"')
    print('    git push')
    print("=" * 50)


if __name__ == "__main__":
    # Demander confirmation avant d'écraser
    print("⚠  Ceci va effacer tes stats de profil.txt et pets.txt.")
    rep = input("   Continuer ? (oui/non) : ").strip().lower()
    if rep in ("oui", "o", "yes", "y"):
        reset()
    else:
        print("  Annulé.")
