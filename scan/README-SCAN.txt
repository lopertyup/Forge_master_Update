================================================================================
  FORGE MASTER — Documentation runtime du package `scan/`
  Source de vérité : Instructions — Alignement du système de scan.
  Public visé : nouveau dev qui débarque sur le projet et veut comprendre
  comment fonctionne le système de scan de Forge Master en dix minutes.
================================================================================


────────────────────────────────────────────────────────────────────────────────
0. EN UNE PHRASE
────────────────────────────────────────────────────────────────────────────────

`scan/` transforme une capture d'écran du jeu en données structurées,
persistées dans profile.txt et consommées par le simulateur.

Deux familles de scan coexistent :

  — Scan joueur (equipment, pet, mount, skill) :
    toutes les stats sont lues DIRECTEMENT par OCR sur la popup.
    Aucun calcul, aucune librairie, aucune identification visuelle requise.
    Nom et Level servent uniquement à l'affichage UI et à la résolution
    d'icônes (nom → data/icons/). Exception : pour les skills, Nom + Level
    permettent aussi de retrouver les instances de dégâts, type (buff/damage)
    etc. via la librairie — mais les valeurs passives restent lues par OCR.

  — Scan adversaire (opponent.py uniquement) :
    les substats sont lues par OCR ; HP et Damage sont DÉDUITS via icône
    + level + librairie + formule. C'est le seul contexte où
    l'identification visuelle des icônes est nécessaire.


────────────────────────────────────────────────────────────────────────────────
1. ARBORESCENCE
────────────────────────────────────────────────────────────────────────────────

  scan/
  ├── __init__.py
  ├── README-SCAN.txt          ce document
  ├── SCAN_REFACTOR.txt        plan de la refonte (historique + décisions)
  │
  ├── data/
  │   └── colors.json          source de vérité des HSV (rarity_colors_hsv,
  │                            age_colors_hsv, thresholds). Édition canonique
  │                            côté JSON ; scan/colors.py embarque les mêmes
  │                            valeurs en fallback Python pour résilience.
  │                            Utilisé UNIQUEMENT par opponent.py.
  │
  ├── core.py                  matcher hybride : ensemble_score, autocrop,
  │                            greedy_assignment, match(), is_cell_filled,
  │                            constantes de seuil (DEFAULT_THRESHOLD).
  │                            Utilisé UNIQUEMENT par opponent.py.
  │
  ├── colors.py                heuristiques HSV : identify_age_from_color /
  │                            identify_rarity_from_color (+ leurs variantes
  │                            *_with_distance), AGE_NAME_TO_INT,
  │                            HSV_AMBIGUITY_THRESHOLD / HSV_AMBIGUITY_GAP,
  │                            reload_calibration() pour relire le JSON.
  │                            Utilisé UNIQUEMENT par opponent.py.
  │
  ├── refs.py                  chargement et cache des images de référence.
  │                            Trois modes :
  │                              "exact"    → data/icons/equipment/<Age>/<Slot>/
  │                              "all_ages" → toutes les ages d'un slot
  │                              "flat"     → pets / skills (adversaire)
  │                            Cache invalidé via reset_caches().
  │                            Utilisé UNIQUEMENT par opponent.py.
  │
  ├── types.py                 Candidate / ScanResult, plus re-export des
  │                            dataclasses OCR partagées (IdentifiedItem,
  │                            IdentifiedPet, IdentifiedMount, IdentifiedSkill).
  │
  ├── offsets/
  │   ├── opponent.py          ratios pixel→bbox pour le panel adverse
  │   │                        (8 équipements + 1 mount + 3 skills + 3 pets),
  │   │                        avec override possible via
  │   │                        data/opponent_offsets.json.
  │   └── player.py            mêmes ratios pour le panel joueur (8 tiles).
  │
  └── jobs/
       ├── _title.py            helper OCR : extrait [Age/Rarity] + nom + Lv.
       │                        depuis le titre des popups joueur.
       ├── _lv.py               helper OCR : cartouche Lv.NN bas-gauche.
       ├── _flat.py             orchestrateur STRAT C — adversaire uniquement
       │                        (pets + skills du panel adverse).
       ├── _panel.py            orchestrateur STRAT A/B — adversaire uniquement
       │                        (équipements + mount du panel adverse).
       ├── _weapon_enrich.py    enrichissement WeaponLibrary du slot Weapon
       │                        (windup, recovery, range, projectile_*,
       │                        attack_type) — appelé après scan OCR.
       │
       ├── equipment_popup.py   popup détail équipement → slot_dict (OCR pur)
       ├── player_equipment.py  panneau 4×2 joueur → 8 slot_dicts (OCR pur,
       │                        enrichissement Weapon inline)
       ├── pet.py               popup pet → slot_dict (OCR pur)
       ├── mount.py             popup mount → slot_dict (OCR pur)
       ├── skill.py             popup skill → slot_dict (OCR pur)
       └── opponent.py          profil adverse → (EnemyComputedStats,
                                EnemyIdentifiedProfile, raw_text)
                                Seul job qui utilise core / colors / refs.


────────────────────────────────────────────────────────────────────────────────
2. CE QUE LE PARSER LIT SUR CHAQUE POPUP (OCR EXCLUSIF — SCAN JOUEUR)
────────────────────────────────────────────────────────────────────────────────

RÈGLE FONDAMENTALE : toutes les stats viennent du texte OCR de la popup.
Pas de calcul, pas d'identification visuelle pour le profil joueur.

Substats reconnues (liste exhaustive) :
  Crit Chance | Crit Damage | Block Chance | Health Regen | Lifesteal
  | Double Chance | Damage% | Melee% | Ranged% | Attack Speed
  | Skill Damage | Skill Cooldown | Health%

⚠ Skill Cooldown est un SIGNED FLOAT. "-X%" = réduction du cooldown.
  Jamais de abs() dans le parser ou le loader sur ce champ.

Raretés reconnues : Common | Rare | Epic | Legendary | Ultimate | Mythic
Âges reconnus     : Primitive | Medieval | Early-Modern | Modern | Space
                    | Interstellar | Multiverse | Quantum | Underworld | Divine

─── parse_equipment_popup — equipment_popup.py ────────────────────────────────

  Ligne 1 : [Age] Nom                      → Name
  Ligne 2 : Lv. X                          → Level
  Ligne 3 : X / Xk / Xm / Xb HP           → HP
              (Helmet | Body | Shoe | Belt | Weapon dans de rares cas)
            X / Xk / Xm / Xb Damage       → Damage
              (Gloves | Necklace | Ring | Weapon)
  Lignes + : +X% Nom_Substat               → substats (0 à N lignes)

─── parse_companion_meta — pet.py / mount.py ──────────────────────────────────

  Ligne 1 : [Rarity] Nom                   → Name, Rarity
  Ligne 2 : Lv. X                          → Level
  Ligne 3 : X / Xk / Xm / Xb Damage       → Damage
  Ligne 4 : X / Xk / Xm / Xb Health       → HP
  Lignes + : +X% Nom_Substat               → substats (0 à N lignes)

  ⚠ Pet ET Mount ont les deux stats. Le parser ne s'arrête pas à la
    première stat principale — il lit Damage ET HP.

─── parse_skill — skill.py ────────────────────────────────────────────────────

  Ligne 1 : [Rarity] Nom                   → Name, Rarity
  Ligne 2 : Lv. X                          → Level
  Passive : +X / Xk / Xm Base Damage      → Damage (passif)
            +X / Xk / Xm Base Health      → HP (passif)

  Les valeurs passives sont sauvegardées dans profile.txt (OCR direct).
  Nom + Level servent en plus à retrouver via la librairie les instances
  de dégâts actifs, type (buff/damage), cooldown etc. — pas de substats
  pour les skills, le format de slot est distinct (cf. §3.1).


────────────────────────────────────────────────────────────────────────────────
3. SIGNATURE COMMUNE D'UN JOB
────────────────────────────────────────────────────────────────────────────────

Tous les modules de `scan/jobs/*.py` exposent UNE seule fonction publique
`scan(...)` :

    def scan(
        capture:    PIL.Image.Image,
        *,
        libs:       Optional[Dict] = None,
        debug_dir:  Optional[Path] = None,
        threshold:  float = DEFAULT_THRESHOLD,
        force_slot: Optional[str]  = None,
        force_age:  Optional[int]  = None,
    ) -> ScanResult:

Détails :

  capture     PIL.Image fournie par le controller (jamais ImageGrab côté job).
  libs        backend.data.libraries.load_libs() — pré-chargé en option.
              Obligatoire pour opponent.py (librairie de formules).
              Ignoré par les jobs OCR pur (equipment, pet, mount, skill).
  debug_dir   si fourni, chaque crop intermédiaire est dumpé (adversaire).
  threshold   seuil minimal du score hybride — opponent.py uniquement.
  force_slot  utilisé UNIQUEMENT par equipment_popup (mandatory) — la vue
              Build sait sur quel tile l'utilisateur a cliqué.
  force_age   ignoré en pratique.

Sortie : `ScanResult(matches, status, debug)`.

  status ∈ {
    "ok"               résultat fiable
    "low_confidence"   meilleure hypothèse fournie mais score < threshold
    "no_match"         aucune référence n'a passé is_cell_filled
    "ocr_unavailable"  RapidOCR manquant
    "scan_error"       exception attrapée (loggée)
  }

`debug["slot_dict"]` est le format canonique consommé par le controller :

    {
      "__name__":    str,
      "__level__":   int,
      "hp_flat":     float,     # 0.0 si non applicable
      "damage_flat": float,     # 0.0 si non applicable
      "substats": {             # dict {nom_substat: valeur_float}
          "Crit Chance":  float,
          "Attack Speed": float,
          ...
      }
      # Pour le slot Weapon uniquement (via _weapon_enrich) :
      "attack_type":            "melee" | "ranged",
      "weapon_attack_range":    float,
      "weapon_windup":          float,
      "weapon_recovery":        float,
      "projectile_speed":       float,
      "projectile_travel_time": float,
      # Pour equipment : "__age__", "__rarity__", "__idx__"
      # Pour pet/mount : "__rarity__"
      # Pour skill     : "__rarity__", "type" (buff/damage)
    }


────────────────────────────────────────────────────────────────────────────────
4. PERSISTENCE — PROFILE.TXT
────────────────────────────────────────────────────────────────────────────────

profile.txt est le fichier unique de persistance du profil joueur.
Il fusionne ce qui était auparavant 4 fichiers séparés (equipment.txt,
pets.txt, skills.txt, mount.txt). Mis à jour à chaque scan validé.

  [EQUIPMENT]       8 slots : Helmet | Body | Gloves | Necklace |
                              Ring | Weapon | Shoe | Belt
  [SKILL]           3 slots : Skill_1 | Skill_2 | Skill_3
  [PETS]            3 slots : Pet_1 | Pet_2 | Pet_3
  [MOUNT]           1 slot  : Mount
  [SUBSTATS_TOTAL]  somme automatique (voir §4.2)

─── 4.1 Format de chaque slot ─────────────────────────────────────────────────

  Équipement, Pet, Mount :
    Name                   = [Age ou Rarity] Nom_Item
    Level                  = Lv. X
    HP                     = X          (ligne absente si non applicable)
    Damage                 = X          (ligne absente si non applicable)
    Substat (Crit Chance)  = +11.5%
    Substat (Attack Speed) = +20.7%
    ...                                 (0 à N lignes, nombre variable)

  Skill (format distinct — pas de substats) :
    Name                   = [Rarity] Nom_Skill
    Level                  = Lv. X
    HP                     = X          (passif Base Health)
    Damage                 = X          (passif Base Damage)
    Type                   = buff | damage

  Ne jamais supposer un nombre fixe de substats par type d'item.

─── 4.2 [SUBSTATS_TOTAL] ──────────────────────────────────────────────────────

  Recalculé à chaque écriture de profile.txt.
  Somme de [EQUIPMENT] + [PETS] + [MOUNT] uniquement.
  Les skills ne contribuent PAS aux substats totales.
  Toutes les substats reconnues apparaissent ; valeur 0 ou None si absente.

  Crit Chance     = X%
  Crit Damage     = X%
  Block Chance    = X%
  Health Regen    = X%
  Lifesteal       = X%
  Double Chance   = X%
  Damage%         = X%
  Melee%          = X%
  Ranged%         = X%
  Attack Speed    = X%
  Skill Damage    = X%
  Skill Cooldown  = X%    (signé, peut être négatif)
  Health%         = X%

─── 4.3 Icônes ────────────────────────────────────────────────────────────────

  Le nom scanné est passé par fix_ocr puis tel quel aux helpers de ui/theme.py.
  Aucune normalisation côté vue ni côté parser.
  Le SpriteName dans AutoXxxMapping.json fait foi.

    load_equipment_icon(age, slot, sprite_name)
    load_skill_icon_by_name(name)
    load_pet_icon(name)
    load_mount_icon(name)

─── 4.4 Loader — invariants (persistence/profile.py) ─────────────────────────

  — Les 4 sections [EQUIPMENT], [SKILL], [PETS], [MOUNT] existent et sont
    séparées dans un seul profile.txt (fusion des anciens fichiers séparés).
  — Skill Cooldown est lu comme signed float (jamais abs() ni cast positif).
  — [SUBSTATS_TOTAL] est recalculé à chaque save, pas seulement à l'init.


────────────────────────────────────────────────────────────────────────────────
5. CAS D'USAGE — LOGIQUE DE DÉCISION POST-SCAN (game_controller.py)
────────────────────────────────────────────────────────────────────────────────

─── CAS 1 : Interface double — changement d'équipement ────────────────────────

  Interface : "Equipped" (haut) vs "New" (bas).

  1. Scan OCR des deux équipements (nom, level, HP/Damage, substats).
  2. Simulation 1000 combats PvP : build actuel vs build avec le nouvel item
     (tous les changements de stats impliqués sont pris en compte).
  3. Affichage des résultats → le joueur choisit de sauvegarder ou non.
  4. Si oui → réécriture du slot dans profile.txt + recalc [SUBSTATS_TOTAL].

─── CAS 2 : Scan simple — mise à jour directe ─────────────────────────────────

  Interface : fiche unique. La distinction avec le Cas 3 est faite au niveau
  de l'UI par le bouton cliqué (pas par le scanner).

  1. Scan OCR : nom, level, HP + Damage (si applicable), substats.
  2. Écrase directement le slot dans profile.txt.
  3. Recalc [SUBSTATS_TOTAL]. Pas de simulation.

─── CAS 3 : Interface simple — changement Pet / Mount / Skill ─────────────────

  Interface : fiche unique. La distinction avec le Cas 2 est faite au niveau
  de l'UI par le bouton cliqué (pas par le scanner).

  1. Scan OCR : nom, level, HP + Damage, substats.
  2. Simulation 1000 combats PvP :
       — Pet et Skill : tester les 3 slots (3 simulations, une par slot).
       — Mount : 1 seul slot, comparaison directe.
  3. Affichage des résultats → le joueur choisit de sauvegarder ou non.
  4. Si oui → écriture du slot retenu dans profile.txt.


────────────────────────────────────────────────────────────────────────────────
6. RÉACTIVITÉ POST-SCAN
────────────────────────────────────────────────────────────────────────────────

Pipeline post-scan (atomique) :

  1. Merge du slot_dict scanné dans _equipment.
  2. Persistence via save_equipment() → profile.txt mis à jour.
  3. Émission d'un unique événement equipment_changed
     (Tk-safe via tk_root.after(0, fn)).
  4. Toutes les vues abonnées se redessinent :
       Dashboard, Build, Comparator, Simulator.

Invariants :

  R1  Aucune vue ne mémorise une copie de _equipment plus longtemps
      qu'un repaint. Lecture via controller.get_equipment() uniquement.
  R2  Un swap manuel (Comparator > Apply) passe par le même chemin
      que le scan : merge → recalc → notify.
  R3  Le scan adversaire ne touche pas _equipment — il alimente
      uniquement _last_enemy_stats / _last_enemy_profile.
  R4  Le scan d'UN SEUL slot (equipment_popup) déclenche le recalc
      de TOUS les totaux joueur.
  R5  Pas d'auto-rescan avant simulation. La sim lit directement
      _equipment["Weapon"] pour windup / range / projectile_*.
      Si l'utilisateur change d'arme en jeu sans scanner, les anciens
      timings sont utilisés — assumé. Le bouton 📷 par tile est le
      chemin pour rattraper.


────────────────────────────────────────────────────────────────────────────────
7. SCAN ADVERSAIRE — scan/jobs/opponent.py
────────────────────────────────────────────────────────────────────────────────

C'est le SEUL contexte où l'identification visuelle des icônes est utilisée.

Interface : page profil adverse. Deux captures si scroll nécessaire
(ZONE_DEFAULTS "opponent" captures=2).

─── Ce qui est scanné directement (OCR) ───────────────────────────────────────

  Substats uniquement.
  Merge des 2 captures, dédoublonnage sur le nom de substat.

─── Ce qui est déduit via icône + level + librairie ───────────────────────────

  Equipment (8 slots) → HP et Damage par slot via level affiché.
  Mount (1)           → HP et Damage via level affiché.
  Skills (3 slots)    → dégâts et passives via level affiché.
  Pets (3 slots)      → HP et Damage par slot via level affiché.

─── Formules (calculator/stats.py) ────────────────────────────────────────────

  HP_réel  = ( HP_equip  × PVP_HP_BASE_MULTIPLIER   (1.0)
             + HP_pets   × PVP_HP_PET_MULTIPLIER    (0.5)
             + HP_skills × PVP_HP_SKILL_MULTIPLIER  (0.5)
             + HP_mount  × PVP_HP_MOUNT_MULTIPLIER  (2.0)
             ) × (1 + Health%)

  ATK_réel = (ATK_equip + ATK_pets + ATK_mount + ATK_skill)
             × (1 + Damage% + Melee% / Ranged%)

  Les coefficients viennent de backend/constants.py — jamais hardcodés
  ailleurs (invariant V1).

─── Identification visuelle — trois stratégies ────────────────────────────────

  Contexte : sur le profil adversaire, aucune popup n'est ouverte.
  On dispose uniquement de l'icône dans sa cellule et du Lv.NN affiché
  dessous. Pas de titre, pas de balise [Age] ou [Rarity] lisible par OCR.

  Layout du panel adverse :
    Rangée 1 (5 carrés)  : Helmet | Body | Gloves | Necklace | Ring
    Rangée 2 (4 éléments): Weapon | Shoe | Belt | Mount (rectangle)
    Ligne du bas — 3 ronds  : Skill_1 | Skill_2 | Skill_3
    Ligne du bas — 3 carrés : Pet_1   | Pet_2   | Pet_3

  STRAT A — équipements + mount (rangées 1 et 2)
    1. Lecture du Lv.NN affiché sous la cellule.
    2. identify_age_from_color sur le centre de l'icône → âge déduit.
    3. Refs (age, slot) mode="exact" → match() → top-1.
    4. Bascule vers STRAT B si :
         a) hsv_dist_top1 > HSV_AMBIGUITY_THRESHOLD  (couleur trop loin)
         b) hsv_dist_top1 - hsv_dist_top2 < HSV_AMBIGUITY_GAP  (ambiguïté)
         c) score_hybride_top1 < threshold  (score visuel trop faible)
    HP et Damage déduits via librairie + Lv.NN.

  STRAT B — fallback all-ages (équipements + mount uniquement)
    1. Refs (slot) sur les 10 âges, mode="all_ages".
    2. match() global → le ref gagnant porte (age, idx).
    3. HP et Damage déduits via librairie + Lv.NN.

  STRAT C — skills + pets (ligne du bas)
    3 ronds  = Skills (positions 1-2-3)
    3 carrés = Pets   (positions 4-5-6)
    1. Lecture du Lv.NN affiché sous la cellule.
    2. identify_rarity_from_color sur l'icône → rareté déduite.
       En cas de doute → Common (multipliers neutres).
    3. Refs mode="flat" → match() → top-1.
    4. HP et Damage déduits via librairie + Lv.NN.

  ⚠ hsv_dist (0=parfait, ↑=pire) et score_hybride (↑=meilleur) ont
    des échelles INVERSES. Ne jamais les comparer entre elles.


────────────────────────────────────────────────────────────────────────────────
8. AJOUTER UN NOUVEAU JOB
────────────────────────────────────────────────────────────────────────────────

  1. Décider la famille :
       - popup joueur (OCR pur) → modeler sur equipment_popup ou pet
       - panel multi-icônes adversaire → utiliser _panel / _flat

  2. Créer `scan/jobs/<nouveau>.py` avec la signature commune (§3).
     Pour un job OCR pur : réutiliser _title.py et _lv.py.
     Pour un job adversaire : réutiliser core.match, refs.load_references,
     colors.identify_*.

  3. Ajouter une méthode publique `scan_<nouveau>(callback)` au
     GameController qui :
        a) récupère la bbox via `_zones[<zone_key>]`
        b) appelle `ocr.capture_region(bbox)` puis `<nouveau>.scan(img, ...)`
        c) merge le résultat dans l'état persistant pertinent
        d) émet l'événement de propagation correspondant

  4. Si l'objet a des icônes, ajouter le dossier sous `data/icons/<cat>/`
     ET un mapping dans `data/Auto<Cat>Mapping.json`.

  5. Tests minimum :
       - `python -m compileall scan/jobs/<nouveau>.py`
       - import smoke : `from scan.jobs import <nouveau>`
       - test sur capture synthétique : status="ok", slot_dict cohérent.


────────────────────────────────────────────────────────────────────────────────
9. PARCOURS UTILISATEUR — SMOKE TEST
────────────────────────────────────────────────────────────────────────────────

À dérouler avant chaque release :

  1.  Simulator → « Scan opponent » → « Run sim »
        → win-rate plausible (> 0 % et < 100 %) pour un build de test.

  2.  Equipment > Build > « Scan tout »
        → la grille 4×2 se remplit avec 8 pièces ;
          le slot Weapon a un projectile_travel_time non nul si ranged.

  3.  Equipment > Build > tile Helmet > « 📷 »
      (popup détail in-game ouvert)
        → seul le slot Helmet est mis à jour ;
          Dashboard et Comparator se rafraîchissent dans la même transaction.

  4.  Equipment > Compare > double popup → Simuler
        → win-rate affiché ;
        → Apply → slot mis à jour si joueur confirme.

  5.  Pets > Scan → bouton "Comparer"
        → 3 slots testés, résultats affichés, joueur confirme avant save.

  6.  Mount > Scan → bouton "Comparer"
        → 1 slot testé, résultats affichés, joueur confirme avant save.

  7.  Skills > Scan → bouton "Comparer"
        → 3 slots testés, résultats affichés, joueur confirme avant save.

  Aucune popup ne doit demander Age, Slot ou Rareté à l'utilisateur.


────────────────────────────────────────────────────────────────────────────────
10. PIÈGES CONNUS
────────────────────────────────────────────────────────────────────────────────

V1   Skill Cooldown négatif : signed float obligatoire. Jamais abs() ni
     cast positif dans le parser ou le loader. Le moteur applique
     (1 + skill_cooldown_pct / 100) directement.

V2   Pet / Mount — deux stats principales : le parser lit Damage ET HP.
     Ne pas s'arrêter à la première stat rencontrée.

V3   Substats — nombre variable : 0 à N lignes selon l'item. Ne jamais
     supposer un nombre fixe de substats par type. Lecture jusqu'au
     prochain header [].

V4   Simulation — confirmation utilisateur : les Cas 1 et 3 affichent
     le résultat et attendent la confirmation avant toute écriture dans
     profile.txt. La simulation ne sauvegarde rien automatiquement.

V5   Identification visuelle = scan adversaire uniquement. Ne jamais
     appeler core / colors / refs depuis equipment_popup, pet, mount
     ou skill.

V6   Threading : tous les scans tournent dans un thread daemon. Les jobs
     sont passifs (pas de Tk, pas de ImageGrab). Pas de scan en parallèle
     sur la même région.

V7   Zone sombre / ambiguïté HSV : sur les builds très bas niveau, la
     couleur de fond peut hésiter entre Primitive et Medieval. La bascule
     STRAT A → STRAT B utilise HSV_AMBIGUITY_THRESHOLD (distance) et
     HSV_AMBIGUITY_GAP (écart top-1/top-2).

V8   Rareté Common : si identify_rarity_from_color hésite, toujours
     renvoyer Common — multipliers neutres, l'utilisateur voit le doute.

V9   Cache de refs : après renommage d'un PNG dans data/icons/, appeler
     scan.refs.reset_caches() avant le prochain scan adversaire.

V10  Calibration couleurs : éditer scan/data/colors.json, pas les
     constantes Python. Le JSON gagne au runtime ; le Python n'est qu'un
     fallback. Distribuer colors.json dans tout binaire / installer.

V11  OpenCV optionnel : core.py fonctionne sans cv2 (NCC Sobel et
     histogramme couleur tombent sur NCC pur). Cette propriété doit
     être préservée pour qu'un dev sans opencv-python puisse booter l'app.

V12  Tests legacy : si un test pytest pointe vers backend.scanner.* pour
     l'identification visuelle, le réorienter vers scan.jobs.*
     (les modules legacy ont disparu en Phase 7).

V13  Coefficients PvP : toujours lus depuis backend/constants.py.
     Jamais hardcodés dans calculator/stats.py ou ailleurs.

V14  [SUBSTATS_TOTAL] : recalculé à chaque écriture, pas seulement
     à l'initialisation. Les skills n'y contribuent pas.


────────────────────────────────────────────────────────────────────────────────
11. INDEX RAPIDE
────────────────────────────────────────────────────────────────────────────────

  OCR popup équipement             → scan/jobs/equipment_popup.py
  OCR popup pet                    → scan/jobs/pet.py
  OCR popup mount                  → scan/jobs/mount.py
  OCR popup skill                  → scan/jobs/skill.py
  Scan panneau joueur 4×2          → scan/jobs/player_equipment.py
  Scan profil adversaire           → scan/jobs/opponent.py
  Matcher visuel (adversaire only) → scan/core.py         match()
  Seuil par défaut                 → scan/core.py         DEFAULT_THRESHOLD
  Tables HSV couleurs              → scan/data/colors.json
                                     (fallback : scan/colors.py)
  Conversion balise → âge int      → scan/colors.py        AGE_NAME_TO_INT
  Détection rareté par couleur     → scan/colors.py        identify_rarity_from_color
  Détection âge par couleur        → scan/colors.py        identify_age_from_color
  Chargement refs icônes           → scan/refs.py           load_references
  Cache refs icônes                → scan/refs.py           reset_caches()
  Orchestrateur STRAT A/B panel    → scan/jobs/_panel.py
  Orchestrateur STRAT C flat       → scan/jobs/_flat.py
  Bbox panel adverse               → scan/offsets/opponent.py
  Bbox panel joueur                → scan/offsets/player.py
  Enrichissement Weapon            → scan/jobs/_weapon_enrich.py
  Persistence profil               → backend/persistence/profile.py
  Coefficients PvP                 → backend/constants.py
                                     PVP_HP_BASE/PET/SKILL/MOUNT_MULTIPLIER
  Formules HP/ATK adversaire       → backend/calculator/stats.py
  Résolution icône → fichier       → ui/theme.py
  Logique décision scan            → game_controller.py


================================================================================
  Fin du document
================================================================================
