================================================================================
  FORGE MASTER - Dossier data/
  Source runtime des donnees jeu, calibrations et icones
================================================================================

`data/` contient les donnees de jeu lues par le code au runtime :

  - bibliotheques JSON officielles ou derivees,
  - mappings nom <-> id,
  - calibrations de couleurs,
  - icones de reference.

Ce dossier n'est pas le seul dossier lu/ecrit par l'application : la
persistance utilisateur vit dans `backend/persistence/profile_store/`,
les zones dans `backend/zones.json` et l'etat de fenetre dans
`backend/window.json`.


--------------------------------------------------------------------------------
1. REGLES
--------------------------------------------------------------------------------

R1. Les JSON metier de `data/` ne sont pas des sorties de tests. Ne pas les
    modifier par accident.

R2. Les loaders runtime passent par :

      data.libraries.load_libs()
      data.libraries.get_lib(name)

R3. `data/colors.json` est la calibration runtime des couleurs HSV. Le fallback
    Python dans `scan/colors.py` sert seulement de resilience.

R4. Les noms visibles en jeu utilisent la convention display name :
    espaces entre les mots et majuscule initiale.

R5. `backend/data/` et `scan/data/` ne doivent pas revenir.


--------------------------------------------------------------------------------
2. FICHIERS PYTHON
--------------------------------------------------------------------------------

  __init__.py
    Package marker.

  canonical.py
    Source Python des noms canoniques partages :
      - slots equipment : Helmet, Body, Gloves, Necklace, Ring, Weapon, Shoe, Belt
      - slots skills : Skill_1, Skill_2, Skill_3
      - slots pets : Pet_1, Pet_2, Pet_3
      - mount : Mount
      - ages, rarities
      - aliases OCR de substats
      - mappings legacy -> canonique

  libraries.py
    Chargeur lazy + cache des JSON de `data/`.
    Charge uniquement les JSON runtime de `data/`. L'API publique reste
    `load_libs()` / `get_lib()`.

  library_ops.py
    Operations sur les bibliotheques utilisateur :
      - find_key
      - remove_entry
      - resolve_companion
      - lv1_version_of


--------------------------------------------------------------------------------
3. JSON RUNTIME
--------------------------------------------------------------------------------

A. Mappings nom -> identifiant

  AutoItemMapping.json
    Mapping equipements.
    Cle : "{Age}_{Type}_{Idx}".
    Valeur : Age, AgeName, Type, TypeName, Idx, ItemName, SpriteName, ...

  AutoPetMapping.json
    Mapping pets par rarity/id.

  AutoMountMapping.json
    Mapping mounts par rarity/id.

  AutoSkillMapping.json
    Mapping skills par display name.

B. Equipements et armes

  ItemBalancingLibrary.json
    Stats brutes par level pour les equipements.
    Les entrees arme portent aussi `weapon_meta` quand disponible.

  WeaponLibrary.json
    Physique des armes :
      AttackRange, WindupTime, AttackDuration, RealAttackDuration,
      IsRanged, IsAiming, ProjectileId, ...

    `RealAttackDuration` est prioritaire pour les timings. `AttackDuration`
    reste un fallback.

C. Pets, mounts, skills

  PetLibrary.json
  PetBalancingLibrary.json
  PetUpgradeLibrary.json

  MountLibrary.json
  MountUpgradeLibrary.json

  SkillLibrary.json
  SkillPassiveLibrary.json

D. Configuration globale

  StatConfigLibrary.json
  AscensionConfigsLibrary.json
  colors.json


--------------------------------------------------------------------------------
4. ICONES
--------------------------------------------------------------------------------

Etat actuel du dossier :

  data/icons/skills/*.png       18 fichiers
  data/icons/pets/*.png         25 fichiers
  data/icons/mount/*.png        15 fichiers
  data/icons/equipment/**/*.png 232 fichiers au total

Dans `equipment/`, 231 fichiers correspondent aux equipements. Un fichier
supplementaire existe actuellement :

  data/icons/equipment/mount/MountIcons.png

Structure equipment principale :

  data/icons/equipment/<Age>/<Slot>/<SpriteName>.png

Les dossiers `<Age>` actuellement presents :

  Primitive
  Medieval
  Early-Modern
  Modern
  Space
  Interstellar
  Multiverse
  Quantum
  Underworld
  Divine

Les dossiers `<Slot>` cote disque suivent les noms de dossiers d'assets :

  Headgear, Armor, Glove, Neck, Ring, Weapon, Foot, Belt

La traduction depuis les noms canoniques est geree par `ui.theme` et
`data.canonical`.


--------------------------------------------------------------------------------
5. ATTACK SPEED
--------------------------------------------------------------------------------

Le comportement runtime repose sur la formule dans :

  backend/calculator/attack_speed.py

Entrees principales :

  WeaponLibrary[key]["WindupTime"]
  WeaponLibrary[key]["RealAttackDuration"]
  WeaponLibrary[key]["AttackDuration"]       fallback

La formule reproduit le comportement officiel :

  speed_mult    = max(0.1, 1 + attack_speed_pct / 100)
  base_recovery = max(0, attack_duration - windup_time)
  sw            = floor(windup_time / speed_mult * 10) / 10
  sr            = floor(base_recovery / speed_mult * 10) / 10
  cycle         = max(0.4, sw + sr + 0.2)
  d             = min(double_damage_pct / 100, 1.0)
  sd            = floor(0.25 / speed_mult * 10) / 10
  double_cycle  = cycle + sd
  avg_cycle     = (1 - d) * cycle + d * double_cycle
  weighted_aps  = (1 + d) / avg_cycle

Les anciens fichiers de reference de breakpoints ne sont pas requis au runtime.
La source de verite du comportement est le code ci-dessus et les JSON runtime.


--------------------------------------------------------------------------------
6. SOUS-DOSSIERS NON RUNTIME DIRECT
--------------------------------------------------------------------------------

  _reference/
    Fichiers gardes pour analyse de futurs patches.


--------------------------------------------------------------------------------
7. AJOUTER OU METTRE A JOUR DES DONNEES
--------------------------------------------------------------------------------

1. Comparer le nouveau patch avec les JSON existants.
2. Mettre a jour les fichiers `data/*.json` concernes.
3. Si un nouveau type de JSON doit etre lu au runtime, l'ajouter dans
   `data/libraries.py`.
4. Si des icones changent, les placer sous `data/icons/...` avec le display
   name attendu par les mappings.
5. Relancer :

     python -m compileall data backend scan ui
     python -m pytest

================================================================================
  Derniere mise a jour : apres refactor data canonical / scan.ocr
================================================================================
