================================================================================
  FORGE MASTER — Dossier data/
  Source de vérité runtime pour toutes les valeurs du jeu
================================================================================

Ce dossier contient TOUTES les données auxquelles le code Forge Master accède
au runtime. Aucune lecture de fichier n'a lieu en dehors de data/ (à part
icons_checker/ qui a été migré ici aussi sous data/icons/).

────────────────────────────────────────────────────────────────────────────────
1. RÈGLES D'OR
────────────────────────────────────────────────────────────────────────────────

  1. data/ est en LECTURE-SEULE pour le runtime SAUF pour l'outil de calibration
     icon_recognition (qui peut renommer des PNG dans data/icons/equipment/ et
     mettre à jour data/AutoItemMapping.json).

  2. Avant CHAQUE écriture dans data/, le code fait un backup horodaté dans
     _archive/ (ex: AutoItemMapping_YYYYMMDD_HHMMSS.json).

  3. Le dossier 2026_04_22/ à la racine du projet est un DUMP du patch officiel
     du 22/04/2026, gardé pour comparaison/extraction. Il N'EST PAS lu au
     runtime — seul data/ l'est.

  4. Les noms in-game (pets, mounts, skills, items) suivent la convention :
       - espace entre les mots
       - majuscule en première lettre de chaque mot
     Exemples : "Saber Tooth", "Cannon Barrage", "Brown Horse", "Higher Morale"

────────────────────────────────────────────────────────────────────────────────
2. INVENTAIRE DES FICHIERS
────────────────────────────────────────────────────────────────────────────────

A. MAPPINGS NOM ↔ ID
   Ces fichiers convertissent les noms reconnus par OCR (ou tapés à la main)
   vers les clés numériques utilisées par les libraries.

  AutoItemMapping.json     — items équipement
        clé:   "{Age}_{Type}_{Idx}"   (ex: "9_5_3" = Divine Weapon Idx 3)
        valeur: {Age, AgeName, Type, TypeName, Idx, ItemName, SpriteName, ...}
        232 entrées (10 ages × 8 slots × 1-8 items)

  AutoPetMapping.json      — 25 pets
        clé:   "{'Rarity': 'X', 'Id': N}"
        valeur: {Rarity, Id, PetName, SpriteName}

  AutoMountMapping.json    — 15 mounts
        clé:   "{'Rarity': 'X', 'Id': N}"
        valeur: {Rarity, Id, MountName, SpriteName}

  AutoSkillMapping.json    — 18 skills
        clé:   nom display avec espaces ("Cannon Barrage", "Higher Morale", …)
        valeur: {Type, Rarity, SpriteName}
        Note: la clé peut différer de SkillLibrary.json qui utilise CamelCase
              ("CannonBarrage"). Le code de lookup doit normaliser (strip
              espaces).

B. STATS DES ITEMS (équipement, armes)

  ItemBalancingLibrary.json — STATS BRUTES par level pour chaque item
        clé:   "{'Age': N, 'Type': 'Weapon'/'Helmet'/..., 'Idx': N}"
        valeur: {ItemId, EquipmentStats: [...], weapon_meta: {...}}
        232 entrées (le superset de tous les items du jeu).

        Champ weapon_meta (présent uniquement sur les armes) :
            {
              "is_ranged":         bool,    (depuis AttackRange > 1.0)
              "attack_range":      float,
              "windup_time":       float,   (cf. WeaponLibrary)
              "attack_duration":   float,   (RealAttackDuration de pref)
              "projectile_speed":  float|null
            }

  WeaponLibrary.json        — physique des armes
        clé:   "{'Age': N, 'Type': 'Weapon', 'Idx': N}"
        valeur: {ItemId, AttackRange, WindupTime, AttackDuration,
                 RealAttackDuration, IsRanged, IsAiming, ProjectileId, ...}
        75 armes (63 normales + 12 skins Age 999/1000).

        ⚠️ AttackDuration = 1.5 pour TOUTES les armes (placeholder du JSON).
           La VRAIE valeur est dans RealAttackDuration (1.10–1.20 par arme).
           Le code attack_speed_calculator lit RealAttackDuration en priorité.

C. STATS DES PETS / MOUNTS / SKILLS

  PetLibrary.json           — id ↔ Type (Balanced/Damage/Health) — 25 pets
  PetBalancingLibrary.json  — multipliers par Type (3 entrées) :
        Balanced: 1.0/1.0,  Damage: 1.5/0.5,  Health: 0.5/1.5
  PetUpgradeLibrary.json    — stats par level (6 raretés × 100 levels)

  MountLibrary.json         — id ↔ metadata (15 mounts)
  MountUpgradeLibrary.json  — stats par level (StatNature à ignorer, traiter flat)

  SkillLibrary.json         — 18 skills × 100 levels (Damage/HealthPerLevel)
  SkillPassiveLibrary.json  — passifs (rarity → list[level, base_dmg, base_hp])

D. CONFIG GLOBALE

  StatConfigLibrary.json    — defaults par stat (AttackSpeed mult=1.0,
                              CritChance=0.0, BlockChance=0.0, …)
  AscensionConfigsLibrary.json — paliers d'ascension par item

E. IMAGES

  icons/
    ├── equipment/{Age}/{Slot}/*.png   — 231 PNG, 10 ages × 8 slots
    ├── pets/*.png                     — 25 PNG
    ├── mount/*.png                    — 15 PNG
    └── skills/*.png                   — 18 PNG

  Les noms de fichiers utilisent la convention "Display Name.png" (espaces +
  majuscules), à part le dossier equipment/ qui garde temporairement le format
  IconAgeSlotName.png en attendant la calibration via icon_recognition.

F. SOUS-DOSSIERS

  _archive/                 — backups + fichiers obsolètes archivés.
                              À supprimer manuellement via Windows Explorer
                              (le mount FUSE Linux ne permet pas l'unlink).
  _reference/               — fichiers gardés pour analyse de futurs patches
                              (ex: ItemBalancingConfig.json, PvpBaseConfig.json).
                              NON LU au runtime.

────────────────────────────────────────────────────────────────────────────────
3. SOURCE DE VÉRITÉ PAR DOMAINE
────────────────────────────────────────────────────────────────────────────────

  Domaine                          | Fichier(s)
  ---------------------------------|-----------------------------------------
  Stats armes (windup, range)      | WeaponLibrary.json
  Stats items (HP/DMG par level)   | ItemBalancingLibrary.json
  Multipliers pet                  | PetBalancingLibrary.json (3 entrées)
                                   | + PetUpgradeLibrary.json (par level)
  Stats pet par level              | PetUpgradeLibrary.json
  Stats mount par level            | MountUpgradeLibrary.json (traité flat)
  Stats skills                     | SkillLibrary.json
  Passifs skills                   | SkillPassiveLibrary.json
  Defaults par stat                | StatConfigLibrary.json
  Mapping nom ↔ id                 | Auto{Item,Pet,Mount,Skill}Mapping.json
  Calcul attack speed              | backend/attack_speed_calculator.py
                                   | (formule, PAS de fichier de table)

────────────────────────────────────────────────────────────────────────────────
4. CONVENTIONS DES CLÉS
────────────────────────────────────────────────────────────────────────────────

  Items / armes :
        Format Python repr d'un dict :
            "{'Age': 9, 'Type': 'Weapon', 'Idx': 3}"
        Age range : 0..9 normaux + 10000 default + 999/1000 skins.

  Pets / mounts :
        Format Python repr :
            "{'Rarity': 'Common', 'Id': 0}"
        Rarities : Common, Rare, Epic, Legendary, Ultimate, Mythic.

  Skills (SkillLibrary) :
        Clé = nom CamelCase ("CannonBarrage", "RainOfArrows").
  Skills (AutoSkillMapping) :
        Clé = display name avec espaces ("Cannon Barrage", "Rain Of Arrows").

────────────────────────────────────────────────────────────────────────────────
5. AJOUTER UN NOUVEAU PATCH DE JEU
────────────────────────────────────────────────────────────────────────────────

Quand un nouveau patch sort, le workflow est :

  1. Décompresser le dump dans /<projet>/<date_patch>/  (ex: 2026_04_22/)
     pour comparaison côte-à-côte.
  2. Cross-checker entry-par-entry les libraries depuis ce dump vers data/.
     L'utilitaire `python -c "import json; ..."` suffit pour la plupart.
  3. Pour les armes : si de nouvelles entrées arrivent, ajouter
     `RealAttackDuration` (extraite via le wiki ou un nouveau WTL) dans
     WeaponLibrary.json.
  4. Pour les nouveaux items : compléter AutoItemMapping.json avec leurs
     ItemName + SpriteName. Si le sprite est déjà dans data/icons/, l'outil
     icon_recognition peut faire la calibration automatiquement.
  5. Ne pas écraser PetBalancingLibrary.json par la version brute du patch
     SAUF si tu as vérifié qu'elle est en format 3-entrées (Balanced/Damage/
     Health). Si le patch fournit la version 18-entrées Rarity_Type, c'est
     un faux multiplier — ignorer.

────────────────────────────────────────────────────────────────────────────────
6. ATTACK SPEED — IMPORTANT
────────────────────────────────────────────────────────────────────────────────

Aucun fichier de table de breakpoints n'existe dans data/. Tout est calculé à
la volée par backend/attack_speed_calculator.py à partir de :

  WeaponLibrary[key]["WindupTime"]            — par arme
  WeaponLibrary[key]["RealAttackDuration"]    — par arme (1.10–1.20)
                                                fallback "AttackDuration"=1.5

Le calculateur reproduit EXACTEMENT la formule de statEngine.ts +
BreakpointTables.tsx du jeu officiel :

  speed_mult     = max(0.1, 1 + attack_speed_pct / 100)
  base_recovery  = max(0, attack_duration - windup_time)
  sw = floor(windup_time / speed_mult * 10) / 10
  sr = floor(base_recovery / speed_mult * 10) / 10
  cycle = max(0.4, sw + sr + 0.2)
  d = min(double_damage_pct / 100, 1.0)
  sd = floor(0.25 / speed_mult * 10) / 10
  double_cycle = cycle + sd
  avg_cycle = (1 - d) * cycle + d * double_cycle
  weighted_aps = (1 + d) / avg_cycle

Validation : 1611/1611 breakpoints exacts contre le wiki sur les 62 armes
testées (toutes les ages × tous les slots).

────────────────────────────────────────────────────────────────────────────────
7. EN CAS DE DOUTE
────────────────────────────────────────────────────────────────────────────────

  - Vérifier INSTRUCTIONS_NOUVEAU_CHAT.txt à la racine du projet pour l'état
    général du chantier.
  - Les fichiers dans _reference/ et _archive/ contiennent l'historique des
    décisions et des versions précédentes.
  - Les TS sources du jeu (BattleEngine.ts, statEngine.ts, BreakpointTables.tsx)
    sont dans `attaque speed fonctionnement/` — c'est l'autorité ultime sur
    le comportement attendu.

================================================================================
  Dernière mise à jour : fin avril 2026
================================================================================
