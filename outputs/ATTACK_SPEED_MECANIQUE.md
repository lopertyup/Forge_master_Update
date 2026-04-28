# Forge Master — Mécanique de l'Attack Speed

**Source** : code TypeScript du jeu (`BattleEngine.ts`, `statEngine.ts`, `BattleHelper.ts`, `constants.ts` — patch du 22/04/2026).

Le but de ce doc est de figer la formule exacte que doit reproduire `backend/simulation.py` côté Forge Master.

---

## 1. Formule réelle (telle qu'elle tourne dans le jeu)

### 1.1 Entrées par arme

Lues dans `WeaponLibrary.json`, **par clé `{Age, Type:'Weapon', Idx}`** :

| Champ | Source | Variable |
|---|---|---|
| `WindupTime` | par arme | varie (0.32 – 1.08 s) |
| `AttackDuration` | par arme | **toujours 1.5 s** dans toutes les armes vérifiées |
| `AttackRange` | par arme | 0.3 (melee) ou 7.0 (ranged) |
| `IsRanged` | par arme | **bug d'export : toujours 0** dans le JSON. Détermination réelle = `AttackRange > 1.0`. Le code TS lit pourtant `IsRanged` directement (ils ont peut-être patché les data binaires côté serveur, le JSON exporté n'est plus à jour). |
| `ProjectileId` | par arme ranged | id dans `ProjectilesLibrary.json` |

### 1.2 Entrées par joueur

| Champ | Calcul |
|---|---|
| `attackSpeedMultiplier` | `1 + ΣAttackSpeed_substats + bonus_tree + bonus_ascension` (les substats `+X% Attack Speed` sont additives, le total est appliqué comme multiplier) |
| `doubleDamageChance` | somme additive des `+X% Double Chance`, capée à 1.0 |
| `criticalChance` | idem, capée à 1.0 |
| `criticalDamage` | `1.2 + Σ(+X% Critical Damage)` (base 1.2, pas 1.0) |

### 1.3 Le coeur du système — discrétisation 0.1 s

Code authoritatif : `statEngine.ts` lignes 1680–1707.

```python
# entrées
speed_mult     = attack_speed_multiplier            # ex. 1.737 pour +73.7%
base_duration  = weapon.AttackDuration              # ≈ 1.5
base_windup    = weapon.WindupTime                  # ex. 0.717
base_recovery  = max(0, base_duration - base_windup)

# discrétisation par phase (clé du système de breakpoint)
stepped_windup    = floor(base_windup    / speed_mult * 10) / 10
stepped_recovery  = floor(base_recovery  / speed_mult * 10) / 10
stepped_cycle     = max(0.4, stepped_windup + stepped_recovery + 0.2)
                    #         ↑                                    ↑
                    #         minimum cycle                        +0.2 s overhead fixe
                    #         absolu                               (transition entre attaques)

# Double Attack
base_double_delay     = 0.25                                       # constante in-game
stepped_double_delay  = floor(0.25 / speed_mult * 10) / 10
double_hit_cycle      = stepped_cycle + stepped_double_delay

# APS pondéré (combine cycle normal + cycle double)
d_chance              = min(double_damage_chance, 1.0)
average_real_cycle    = (1 - d_chance) * stepped_cycle + d_chance * double_hit_cycle
weighted_aps          = (1 + d_chance) / average_real_cycle

# DPS
crit_mult             = 1 + min(crit_chance, 1) * (crit_damage - 1)
real_weapon_dps       = total_damage * weighted_aps * crit_mult
real_total_dps        = real_weapon_dps + skill_dps + skill_buff_dps
```

### 1.4 Conséquences "métier" du `floor(... × 10) / 10`

- Tu ne gagnes **rien** en DPS d'arme tant que ton attack speed n'a pas poussé `windup/speed` ou `recovery/speed` dans le bracket 0.1 s suivant.
- Les 3 tables wiki (`primary_weapon_cycle`, `rhythmic_windup_steps`, `double_attack_cycle`) sont les **listes pré-calculées** des `req_speed` (en %) au-dessus duquel on tombe d'un cran de 0.1 s pour chaque arme.
- C'est exactement ce qu'on a stocké dans `data/WindupTimeLibrary.json`.

### 1.5 Côté simulation (BattleEngine, par tick)

```
phase IDLE      → CHARGING       (init: windupTimer = effective_windup)
phase CHARGING  → décrémenter windupTimer; quand ≤ 0 → frappe, transition RECOVERING
phase RECOVERING → décrémenter recoveryTimer; quand ≤ 0 → IDLE

effective_windup    = base_windup    / speed_mult
effective_recovery  = (base_duration - base_windup) / speed_mult
```

**À noter** : la simulation tick ne fait PAS le `floor` 0.1 s — elle tourne sur l'horloge continue. Les breakpoints ne sont donc valables que pour le **résumé statistique** (DPS théorique du UI). En combat réel les phases sont continues.

Pour Forge Master ça veut dire deux modes :
- **Mode rapide / résumé / optimizer** : utiliser la formule discrétisée (rapide, stable, équivalent à ce que le jeu affiche dans ses panneaux UI).
- **Mode simulation tick** : utiliser les durées continues `effective_windup` / `effective_recovery`.

---

## 2. Constantes globales (extraites des sources)

| Constante | Valeur | Source | Notes |
|---|---|---|---|
| Tick rate de la sim | 1/60 s ≈ 0.0167 s | `BattleEngine.ts:164` | "matches game frame rate" |
| Discrétisation des breakpoints | 0.1 s | `statEngine.ts:1686` | `floor(... × 10)/10` |
| Cycle minimum | 0.4 s | `statEngine.ts:1688` | hard cap |
| Overhead de cycle | +0.2 s | `statEngine.ts:1688` | ajouté à chaque cycle |
| Délai Double Attack base | 0.25 s | `statEngine.ts:1691` |  |
| Cycle min après floor du speed | 0.1 s | implicit | speed_mult clamp à 0.1 |
| `PlayerBaseDamage` | 10.0 | `ItemBalancingConfig.json` |  |
| `PlayerBaseHealth` | 80.0 | `ItemBalancingConfig.json` |  |
| `PlayerMeleeDamageMultiplier` | 1.6 | `ItemBalancingConfig.json` | melee = ×1.6 du base damage |
| `PlayerBaseCritDamage` | 0.20 | `ItemBalancingConfig.json` | **base = +20%, pas 0** ; le total crit dmg final = `1.2 + Σbonus` |
| `LevelScalingBase` | 1.01 | `ItemBalancingConfig.json` | scaling par niveau |
| `ItemBaseMaxLevel` | 98 | `ItemBalancingConfig.json` | augmente via TechTree |

---

## 3. Cross-check des libraries (data/ vs 2026_04_22/)

### 3.1 PetBalancingLibrary — **erreur dans nos data**

Le vrai `PetBalancingLibrary.json` du jeu (patch 22/04/2026) contient **3 entrées seulement** :

```json
{
  "Balanced": {"Type": "Balanced", "DamageMultiplier": 1.0, "HealthMultiplier": 1.0},
  "Damage":   {"Type": "Damage",   "DamageMultiplier": 1.5, "HealthMultiplier": 0.5},
  "Health":   {"Type": "Health",   "DamageMultiplier": 0.5, "HealthMultiplier": 1.5}
}
```

**Pas de combos `Rarity_Type`** comme on l'avait dans `INSTRUCTIONS_NOUVEAU_CHAT.txt`. Les multipliers Epic/Legendary/Mythic (2.8, 12.0, 5.12 etc.) que j'avais mis dans notre `PetBalancingLibrary.json` étaient **incorrects** — ils représentaient le scaling de rarity qui en réalité est **déjà encodé dans `PetUpgradeLibrary.LevelInfo[]`** (les valeurs Lv1 d'un pet Mythic incluent déjà le scaling de la rarity).

➜ **Action requise** : remplacer notre `data/PetBalancingLibrary.json` par la version officielle (3 entrées). Mettre à jour `enemy_stat_calculator._aggregate_pets()` pour ne plus utiliser la clé `f"{rarity}_{type}"` mais juste `pet_type`.

### 3.2 WeaponLibrary — 12 nouvelles armes ajoutées

| | data/_archive/ | 2026_04_22/ |
|---|---|---|
| Total | 63 armes | **75 armes** |
| `AttackDuration` | toutes 1.5 | toutes 1.5 (cohérent) |
| `WindupTime` | 1 diff (rounding) | identique à 0.01 près |
| `IsRanged` | toujours 0 (bug d'export) | toujours 0 (idem, ils ont pas patché) |

**Nouvelles armes (Age 999 et 1000)** : ce sont les armes "Skin" récemment ajoutées au jeu (les versions cosmétiques).
- Age 999 = "Skin" melee (range 0.3, 6 nouvelles armes)
- Age 1000 = "Skin" ranged (range 7.0, 6 nouvelles armes)

➜ **Action requise** : décider si on supporte les skins. Si oui, copier la version 2026_04_22 de `WeaponLibrary.json`. Sinon les ignorer (l'optimizer ne pourrait de toute façon pas suggérer de skin sans connaître quels skins le joueur possède via `SkinsLibrary.json`).

### 3.3 Autres libraries

| Library | data/ | 2026_04_22/ | Cohérent ? |
|---|---|---|---|
| AutoItemMapping | 232 | (nouveau patch dans uploads/, à comparer) | à vérifier |
| ItemBalancingLibrary | 232 entrées + weapon_meta | version brute du patch | nos `weapon_meta` sont à régénérer |
| MountLibrary | 15 (notre simplifié) | 15 (full physics) | OK, on garde la version simplifiée |
| MountUpgradeLibrary | 504 KB | identique | OK |
| PetLibrary | 25 | 25 | OK |
| PetUpgradeLibrary | 488 KB | identique | OK |
| SkillLibrary | 100 KB | identique | OK |
| **SkillPassiveLibrary** | **177 KB (rewritten)** | **format brut** | **notre version est plus lisible mais à jour** |
| ProjectilesLibrary | (archived) | présente | merged dans IB côté nous |
| **PetBalancingLibrary** | **18 entrées (FAUX)** | **3 entrées (CORRECT)** | **À corriger** |
| StatConfigLibrary | absent | présent | à importer (defaults par stat) |
| BaseConfig | absent | présent | utile (MaxAge=9 etc.) |
| ItemBalancingConfig | _reference/ | identique | OK (déjà archivé) |

### 3.4 Nouvelles libraries pertinentes du patch

- `StatConfigLibrary.json` : valeurs par défaut de chaque stat (`AttackSpeed`: 1.0 multiplier, `CriticalDamage`: 1.0 multiplier, `CriticalChance`: 0.0, etc.). Source de vérité pour les "valeurs neutres" quand un stat est absent du profil.
- `SkinsLibrary.json` : tous les skins disponibles (lié aux Age 999/1000 ci-dessus).
- `SetsLibrary.json` : sets d'équipement (bonus 2-pieces, 4-pieces).
- `TechTreeLibrary.json` + `TechTreeUpgradeLibrary.json` : skill tree qui peut booster `attackSpeedMultiplier`. Gros morceau, **important pour le simulateur** car explique pourquoi nos calculs HP/DMG ont jusqu'à 15% d'écart avec ce que le jeu affiche.

---

## 4. Implications pour Forge Master

### 4.1 Ce qu'on a déjà bien fait

✅ `data/WindupTimeLibrary.json` — les 3 tables breakpoints par arme, format propre keyé sur `{Age, Type, Idx}`. Directement utilisable par le simulateur.

✅ `data/ItemBalancingLibrary.json.weapon_meta` — `is_ranged`, `attack_range`, `projectile_speed` par arme. Parfait pour l'instant.

✅ `data/SkillPassiveLibrary.json` reformaté en `{rarity: {levels: [{level, base_damage, base_health}]}}` — plus lisible que la version brute du patch.

### 4.2 Ce qu'il faut corriger / ajouter

🔧 **`PetBalancingLibrary.json`** — réduire à 3 entrées (Balanced/Damage/Health). Updater `enemy_stat_calculator.py`.

🔧 **Créer `backend/attack_speed_calculator.py`** qui implémente la formule discrétisée :
```python
def compute_real_aps_and_cycle(weapon_age, weapon_idx, attack_speed_pct,
                                double_damage_pct):
    """Retourne (real_aps, cycle_normal_s, cycle_double_s, weighted_dps_factor)."""
    weapon = item_balancing_library[f"{{'Age': {weapon_age}, 'Type': 'Weapon', 'Idx': {weapon_idx}}}"]
    base_windup = weapon["weapon_meta_extended"]["windup_time"]   # à rajouter dans IB
    base_dur = 1.5  # constante de fait
    speed_mult = 1 + attack_speed_pct / 100
    stepped_windup = floor(base_windup / speed_mult * 10) / 10
    stepped_recovery = floor((base_dur - base_windup) / speed_mult * 10) / 10
    stepped_cycle = max(0.4, stepped_windup + stepped_recovery + 0.2)
    stepped_double = floor(0.25 / speed_mult * 10) / 10
    double_cycle = stepped_cycle + stepped_double
    d = min(double_damage_pct / 100, 1.0)
    avg_cycle = (1 - d) * stepped_cycle + d * double_cycle
    weighted_aps = (1 + d) / avg_cycle
    return (weighted_aps, stepped_cycle, double_cycle, weighted_aps * (1 + d))
```

🔧 **Brancher dans `simulation.py`** : remplacer le cycle d'attaque actuel (`ATTACK_INTERVAL = 0.25` constant) par `compute_real_aps_and_cycle(...)` qui prend en compte l'arme du joueur.

🔧 **Importer `StatConfigLibrary.json`** depuis le patch — utile pour normaliser les valeurs neutres (ex: `attackSpeedMultiplier` part à 1.0, pas 0).

🔧 **`weapon_meta` dans ItemBalancingLibrary** — ajouter `windup_time` et `attack_duration` (qu'on avait retirés). C'est nécessaire pour le calcul. **Correction de mes pretendues "info inutiles" de la passe précédente** : `windup_time` EST utilisé en input pour le calcul des breakpoints — il n'est juste pas la VALEUR finale (le code la transforme via le `floor`).

### 4.3 Ordre suggéré

1. Corriger `PetBalancingLibrary.json` → 3 entrées
2. Re-réinjecter `windup_time` + `attack_duration` dans `weapon_meta` de `ItemBalancingLibrary`
3. Créer `backend/attack_speed_calculator.py` + tests qui reproduisent la formule TS
4. Brancher dans `simulation.py`
5. Vérifier sur tes captures du panneau profil que `Real DPS` simulé = `Real DPS` affiché in-game

---

## 5. Récap : pourquoi nos calculs HP/DMG ont un écart in-game

Sources d'écart connues :
- TechTree non implémenté (peut donner +10–30% à certains stats)
- Sets bonuses (2-pieces, 4-pieces) non implémentés
- Skins (Age 999/1000) potentiellement actifs
- Substats secondaires (rolls aléatoires) — partiellement géré

L'attack speed via les **breakpoints** est l'autre source — sans le `floor` 0.1 s, les chiffres affichés en jeu ne matchent jamais.

---

*Dernière mise à jour : analyse du patch du 22/04/2026, sources TS reçues le 27/04/2026.*
