================================================================================
  FORGE MASTER — Documentation runtime du package `scan/`
  Version : post-Phase 7 du SCAN_REFACTOR (cleanup terminé).
  Public visé : nouveau dev qui débarque sur le projet et veut comprendre
  comment fonctionne tout ce qui touche à l'identification visuelle dans
  Forge Master, en dix minutes.
================================================================================


────────────────────────────────────────────────────────────────────────────────
0. EN UNE PHRASE
────────────────────────────────────────────────────────────────────────────────

`scan/` est le package qui transforme une CAPTURE D'ÉCRAN du jeu (équipement
joueur, popup d'item, opponent profile, pet, mount, skill) en STRUCTURED DATA
que le controller persiste et que le simulateur consomme.

Le moteur est un MATCHER HYBRIDE (NCC gris + NCC Sobel + histogramme couleur
+ similarité de texte OCR + auto-crop) appliqué sur des CROPS D'ICÔNES
préalablement extraits. Aucun job ne demande à l'utilisateur de pré-sélec-
tionner âge ou rareté : tout est déduit du visuel et/ou du texte de la
popup.


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
  │
  ├── core.py                  matcher hybride : ensemble_score, autocrop,
  │                            greedy_assignment, match(), is_cell_filled,
  │                            constantes de seuil (DEFAULT_THRESHOLD).
  │
  ├── colors.py                heuristiques HSV : identify_age_from_color /
  │                            identify_rarity_from_color (+ leurs variantes
  │                            *_with_distance), AGE_NAME_TO_INT,
  │                            HSV_AMBIGUITY_THRESHOLD / HSV_AMBIGUITY_GAP,
  │                            reload_calibration() pour relire le JSON.
  │
  ├── refs.py                  chargement et cache des images de référence.
  │                            Trois modes :
  │                              "exact"     → data/icons/equipment/<Age>/<Slot>/
  │                              "all_ages"  → toutes les ages d'un slot
  │                              "flat"      → pets / mount / skills
  │                            Cache invalidé via reset_caches().
  │
  ├── types.py                 Candidate / ScanResult, plus re-export des
  │                            dataclasses OCR partagées (IdentifiedItem,
  │                            IdentifiedPet, IdentifiedMount, IdentifiedSkill).
  │
  ├── offsets/
  │   ├── opponent.py          ratios pixel→bbox pour le panel adverse
  │   │                        (8 équipements + 3 pets + 1 mount + 3 skills),
  │   │                        avec override possible via
  │   │                        data/opponent_offsets.json.
  │   └── player.py            mêmes ratios pour le panel joueur (8 tiles).
  │
  └── jobs/                    un fichier par zone_key actif, signature
                               commune (cf. §3) :
       ├── _title.py            helper OCR du titre des popups
                                (extrait [<Age>] / [<Rarity>] + nom + Lv.).
       ├── _lv.py               helper OCR du cartouche bas-gauche (Lv.NN).
       ├── _flat.py             orchestrateur STRAT C (pet/mount/skill).
       ├── _panel.py            orchestrateur 4×2 (player_equipment/opponent).
       ├── _weapon_enrich.py    enrichissement WeaponLibrary du slot Weapon
                                (windup, recovery, range, projectile_*,
                                attack_type) — appelé après identification.
       │
       ├── pet.py               pet popup → IdentifiedPet
       ├── mount.py             mount popup → IdentifiedMount
       ├── skill.py             skill popup → IdentifiedSkill
       ├── player_equipment.py  panneau 4×2 joueur → 8 slot_dicts complets
       │                        (avec enrichissement Weapon inline)
       ├── equipment_popup.py   popup détail item → 1 slot_dict complet
       │                        (force_slot fourni par le contexte UI)
       └── opponent.py          opponent profile → (EnemyComputedStats,
                                EnemyIdentifiedProfile, raw_text)


────────────────────────────────────────────────────────────────────────────────
2. PRINCIPE DIRECTEUR — « PAS DE PRÉ-SÉLECTION »
────────────────────────────────────────────────────────────────────────────────

Aucun scan ne demande à l'utilisateur l'âge ou la rareté avant de tourner.
Trois stratégies couvrent tous les cas :

STRAT A — popups single-cell équipement (la balise OCR donne l'âge)
  1. OCR du titre → balise `[<Age>]` + nom + Lv.NN.
  2. Si la balise est lisible → âge déterministe via AGE_NAME_TO_INT.
     Sinon → identify_age_from_color sur le centre de l'icône.
  3. Charger les refs (age, slot) en mode="exact" → match() → top-1.
  4. Bascule automatique vers STRAT B si :
       a) hsv_dist_top1 > HSV_AMBIGUITY_THRESHOLD  (couleur trop loin)
       b) hsv_dist_top1 - hsv_dist_top2 < HSV_AMBIGUITY_GAP  (ambiguïté)
       c) score_hybride_top1 < threshold  (score visuel trop faible)
     ⚠ hsv_dist (0=parfait, ↑=pire) et score_hybride (↑=meilleur) ont
       des échelles INVERSES. Ne jamais les comparer entre elles.

STRAT B — fallback all-ages
  1. Refs (slot) sur les 10 ages, mode="all_ages".
  2. match() global → le ref gagnant porte (age, idx).

STRAT C — flat (pet/mount/skill)
  1. Pas d'âge, pas de slot. Un seul dossier de refs (mode="flat").
  2. OCR du titre → balise `[<Rarity>]` + nom (rareté déterministe).
     Fallback identify_rarity_from_color si la balise est illisible.
  3. match() top-1.

Choix par job :

  Job                       | Stratégie    | Source du slot
  --------------------------|--------------|-------------------------
  pet / mount / skill       | STRAT C      | (pas de slot)
  equipment_popup           | STRAT A → B  | force_slot (UI context)
  player_equipment (8 tiles)| STRAT A → B  | position 0..7 (grid)
  opponent (8 + 3 + 1 + 3)  | STRAT A → B  | position pour les 8 ;
                                            companions = flat refs


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
  libs        backend.data.libraries.load_libs() — pré-chargé en option pour
              les tests ou pour mutualiser entre plusieurs slots.
  debug_dir   si fourni, chaque crop intermédiaire est dumpé.
  threshold   seuil minimal du score hybride (différent par job).
  force_slot  utilisé UNIQUEMENT par equipment_popup (mandatory) — la vue
              Build sait quel tile l'utilisateur scrute. Ignoré par les
              jobs de panneau (qui déduisent le slot de la position) et par
              pet/mount/skill (pas de slot du tout).
  force_age   ignoré en pratique — la balise OCR ou la couleur tranche.

Sortie : `ScanResult(matches: List[Candidate], status: str, debug: dict)`.

  status ∈ {
    "ok"               score ≥ threshold partout
    "low_confidence"   meilleure hypothèse fournie mais score < threshold
    "no_match"         aucune référence n'a passé _is_cell_filled
    "ocr_unavailable"  RapidOCR manquant ou pas démarré
    "scan_error"       exception attrapée (loggée)
  }

Aucune fonction `scan(...)` ne demande, retourne ou propage un « besoin de
précision » à l'UI. Toute incertitude est résolue dans le job.

`debug["slot_dict"]` (player_equipment / equipment_popup) est le format
canonique consommé par le controller : Dict[section_name, slot_dict] où
le slot_dict contient :

    {
      "__age__":   int,
      "__idx__":   int,
      "__rarity__": str,
      "__name__":  str,
      "__level__": int,
      "hp_flat":   float,
      "damage_flat": float,
      # pour le slot Weapon uniquement :
      "attack_type":            "melee" | "ranged",
      "weapon_attack_range":    float,
      "weapon_windup":          float,
      "weapon_recovery":        float,
      "projectile_speed":       float,
      "projectile_travel_time": float,
    }


────────────────────────────────────────────────────────────────────────────────
4. RÉACTIVITÉ POST-SCAN — UN SEUL ÉTAT, UN SEUL ÉVÉNEMENT
────────────────────────────────────────────────────────────────────────────────

Source de vérité unique :
    GameController._equipment : Dict[slot_name, slot_dict]

Pipeline post-scan (atomique) :

  1. Le job retourne un ScanResult ; le controller MERGE
     `result.debug["slot_dict"]` dans `_equipment` (8 slots ou 1
     selon le job).
  2. Le controller persiste via `save_equipment(_equipment)`.
  3. Le controller émet UN SEUL événement equipment_changed via
     `_notify_equipment_changed()` (Tk-safe : passe par
     `tk_root.after(0, fn)`).
  4. Tous les abonnés se redessinent à partir du nouvel état :
       - vue Build courant
       - Dashboard (HP, DPS, defense, mitigations, totaux)
       - Equipment Comparator « Build actuel »
       - Simulator (la prochaine simulation utilisera les nouveaux
         windup / range / projectile_*)

S'abonner depuis une vue :

    self._unsub = self.controller.subscribe_equipment_changed(
        self._on_equipment_changed
    )

Invariants à tenir :

  R1  Aucune vue ne mémorise une copie de `_equipment` plus longtemps qu'un
      repaint. Lecture systématique via `controller.get_equipment()` ou
      `controller.get_equipment_slot(slot)`.
  R2  Aucune stat dérivée n'est cachée côté vue.
  R3  Un swap manuel (Equipment Comparator > Apply) passe par le MÊME
      chemin que le scan : merge → recalc → notify. Pas de shortcut.
  R4  Le scan d'UN SEUL slot (equipment_popup) déclenche le recalc de
      TOUS les totaux player.
  R5  Le scan opponent NE TOUCHE PAS `_equipment` ; il alimente
      `_last_enemy_stats` / `_last_enemy_profile` (cf. simulate_vs_last_enemy).


────────────────────────────────────────────────────────────────────────────────
5. POINT D'ENTRÉE CONTROLLER — CE QUE LES VUES APPELLENT
────────────────────────────────────────────────────────────────────────────────

Méthodes publiques du `GameController` adossées à `scan/` :

  scan(zone_key, callback, step=None)
      Scan OCR text-only d'une zone configurée (profile / pet / mount /
      skill / equipment / opponent). Pour `zone_key="opponent"`, lance
      ADDITIONNELLEMENT scan.jobs.opponent.recompute_from_capture sur
      la même capture pour alimenter le cache enemy.

  scan_player_equipment(callback)
      → scan/jobs/player_equipment.scan() sur la zone "player_equipment".
      Merge les 8 slots dans `_equipment`, persiste, broadcast.

  scan_equipment_slot(slot, callback)
      → scan/jobs/equipment_popup.scan(force_slot=slot) sur la zone
      "equipment_popup". Merge UN slot, persiste, broadcast.

  scan_pet / scan_mount / scan_skill — non câblées au controller en tant
  que méthode dédiée (les vues Pets / Mount / Skill appellent
  controller.scan(zone_key=...) qui passe par l'OCR text + parsers).
  Les jobs scan/jobs/{pet,mount,skill}.scan(...) restent disponibles pour
  un câblage direct si besoin (par exemple un mode « Smart scan » qui
  combinerait OCR + matcher visuel).

  simulate_vs_last_enemy(callback)
      Réutilise `_last_enemy_stats` posé par scan(zone_key="opponent").
      Aucun auto-rescan-avant-fight (cf. §6.bis V9 du SCAN_REFACTOR).

Ne PAS exister :

  ✗ scan_player_weapon            (le slot Weapon est rempli par
                                   player_equipment + _weapon_enrich,
                                   ou par equipment_popup + idem)
  ✗ scan_wiki_grid                (béquille de migration supprimée Phase 7)
  ✗ apply_wiki_results            (idem)


────────────────────────────────────────────────────────────────────────────────
6. CALIBRATION COULEURS (V8)
────────────────────────────────────────────────────────────────────────────────

Toutes les tables HSV et les seuils vivent dans `scan/data/colors.json` :

    {
      "rarity_colors_hsv": { "Common": [...], "Rare": [...], ... },
      "age_colors_hsv":    { "0": [...], "1": [...], ... },
      "hsv_ambiguity_threshold": 0.08,
      "hsv_ambiguity_gap":       0.02,
      "match_confidence_threshold": 0.35
    }

Au boot, `scan.colors` lit ce JSON. Si le fichier est absent ou corrompu,
les constantes Python embarquées dans `colors.py` servent de fallback
(warning loggé, dégradation transparente).

Recharger après modification du JSON sans redémarrer :

    from scan.colors import reload_calibration
    reload_calibration()              # relit scan/data/colors.json
    reload_calibration("/tmp/test.json")  # relit un fichier de test

Tests / debug : pointer reload_calibration() sur une copie du JSON,
modifier les seuils, valider les résultats sur un dataset connu, puis
revenir au fichier canonique.


────────────────────────────────────────────────────────────────────────────────
7. AJOUTER UN NOUVEAU JOB
────────────────────────────────────────────────────────────────────────────────

Cas typique : on veut scanner un nouveau type d'élément (par exemple un
buff actif ou un objet de raid). Les étapes :

  1. Décider la stratégie :
       - icône isolée avec popup → STRAT C → utiliser `_flat.run_flat_scan`
       - panneau multi-icônes → STRAT A/B → modeler sur `_panel.identify_panel`
       - une seule pièce + force_slot UI → modeler sur `equipment_popup.scan`

  2. Créer `scan/jobs/<nouveau>.py` avec la signature commune (§3).
     Réutiliser `core.match`, `refs.load_references`, `colors.identify_*`.

  3. Ajouter une méthode publique `scan_<nouveau>(callback)` au
     GameController qui :
        a) récupère la bbox via `_zones[<zone_key>]`
        b) appelle `ocr.capture_region(bbox)` puis `<nouveau>.scan(img, ...)`
        c) merge le résultat dans l'état persistant pertinent
        d) émet l'événement de propagation correspondant

  4. Si l'objet est représenté visuellement par un dossier d'icônes,
     ajouter le dossier sous `data/icons/<categorie>/` ET un mapping
     dans `data/Auto<Categorie>Mapping.json`.

  5. Tests minimum :
        - `python -m compileall scan/jobs/<nouveau>.py`
        - import smoke (`from scan.jobs import <nouveau>`)
        - test sur capture synthétique : niveau / nom / rareté attendus
          retrouvés, status="ok", debug["slot_dict"] cohérent.


────────────────────────────────────────────────────────────────────────────────
8. PARCOURS UTILISATEUR — SMOKE TEST (S7)
────────────────────────────────────────────────────────────────────────────────

À dérouler avant chaque release :

  1.  Dashboard → « Scan profil »                   → texte OCR'é sans erreur.
  2.  Simulator → « Scan opponent » → « Run sim »   → win-rate plausible
                                                       (> 0 % et < 100 %)
                                                       pour un build de test.
  3.  Equipment > Build > « Scan tout »             → la grille 4×2 se
                                                       remplit avec 8 pièces ;
                                                       le slot Weapon a un
                                                       projectile_travel_time
                                                       non nul si ranged.
  4.  Equipment > Build > tile Helmet > « 📷 »
      (popup détail in-game ouvert)                 → seul le slot Helmet
                                                       est mis à jour ;
                                                       Dashboard et
                                                       Comparator se
                                                       rafraîchissent dans
                                                       la même transaction.
  5.  Equipment > Compare > swap → Apply            → même cascade que (4),
                                                       chemin atomique
                                                       (R3 §4).
  6.  Pets > Scan slot N  → Compare → Apply         → IdentifiedPet correct,
                                                       rareté = balise OCR
                                                       (et non couleur).
  7.  Mount > Scan        → Compare → Apply         → idem pour le mount.
  8.  Skills > Scan slot N → Compare → Apply        → idem pour le skill.

Aucune popup ne doit demander Age, Slot ou Rareté à l'utilisateur. Aucun
bouton « Calibrate icons → wiki » ne doit être visible.


────────────────────────────────────────────────────────────────────────────────
9. CHANGELOG D'INFRASTRUCTURE — POINTS DE REPÈRE
────────────────────────────────────────────────────────────────────────────────

Phase 1   squelette du package (core, refs, types, colors, offsets, data/).
Phase 2   wiki_grid transitoire (a été supprimé en Phase 7).
Phase 3   pet / mount / skill — STRAT C.
Phase 4   FOLDÉE dans Phase 5 (rev.4) — pas de job player_weapon dédié.
Phase 5   player_equipment (8 tiles + Weapon enrich) + equipment_popup
          per-slot + bus equipment_changed.
Phase 6   opponent — port complet de l'ancien backend/pipeline.py.
Phase 7   cleanup :
          - backend/pipeline.py supprimé
          - backend/scanner/{icon_matcher, icon_recognition, panel,
            player_equipment, weapon}.py supprimés
          - backend/scanner/offsets/ supprimé
          - ui/views/wiki_calibration.py supprimé
          - controller.scan_wiki_grid / apply_wiki_results supprimés
          - bouton « 🔍 Calibrate icons → wiki » retiré de Equipment
          - zone "wiki_grid" retirée de ZONE_DEFAULTS et zones.json
          - tools/ pointent vers scan.offsets

Le détail jour-par-jour vit dans `SCAN_REFACTOR.txt §12 (CHANGELOG)`.


────────────────────────────────────────────────────────────────────────────────
10. PIÈGES CONNUS (V1..V9)
────────────────────────────────────────────────────────────────────────────────

V1  Cache de refs : si quelqu'un renomme un PNG de `data/icons/`, appeler
    `scan.refs.reset_caches()` avant le prochain scan.

V2  Threading : tous les scans tournent dans un thread daemon. Les jobs
    eux-mêmes sont passifs (pas de Tk, pas de ImageGrab). Le matcher
    est CPU-bound mais sub-seconde sur une icône. Pas de scan en
    parallèle sur la même région.

V3  Auto-detect en zone sombre : sur les builds très bas niveau, la
    couleur de fond peut hésiter entre Primitive et Medieval. La bascule
    STRAT A → STRAT B utilise les seuils HSV_AMBIGUITY_THRESHOLD
    (distance) et HSV_AMBIGUITY_GAP (écart top-1/top-2).

V4  Rareté Common : si identify_rarity_from_color hésite, mieux vaut
    renvoyer Common que d'inventer une autre rareté — les multipliers
    Common sont neutres et l'utilisateur voit visuellement le doute.

V5  OpenCV optionnel : `core.py` marche dégradé sans cv2 (NCC Sobel et
    histogramme couleur tombent sur le NCC pur). Cette propriété DOIT
    être préservée pour qu'un dev sans `opencv-python` puisse booter
    l'app.

V6  Tests : si un test pytest pointe vers `backend.scanner.*` pour
    l'identification visuelle, le réorienter vers `scan.jobs.*`
    (les modules legacy ont disparu en Phase 7).

V8  Calibration couleurs persistée : éditer `scan/data/colors.json`,
    pas les constantes Python. Le JSON gagne au runtime ; le Python
    n'est qu'un fallback. Distribuer `colors.json` dans tout
    binaire / installer.

V9  Plus d'auto-rescan-avant-simulation. La sim lit directement
    `_equipment["Weapon"]` pour windup / range / projectile_*. Si
    l'utilisateur a changé d'arme en jeu sans scanner, la sim
    utilisera les anciens timings — c'est ASSUMÉ : le bouton « 📷 »
    par tile est le chemin pour rattraper rapidement.


────────────────────────────────────────────────────────────────────────────────
11. INDEX RAPIDE — « JE CHERCHE … »
────────────────────────────────────────────────────────────────────────────────

  La fonction de score visuel              → scan/core.py    `match()`
  Le seuil par défaut                      → scan/core.py    `DEFAULT_THRESHOLD`
  La table HSV âge → couleur               → scan/data/colors.json
                                              (fallback : scan/colors.py)
  La conversion balise OCR → âge int       → scan/colors.py  `AGE_NAME_TO_INT`
  La détection rareté par couleur          → scan/colors.py  `identify_rarity_from_color`
  La détection âge par couleur             → scan/colors.py  `identify_age_from_color`
  Le chargement des refs equipment         → scan/refs.py    `load_references`
  Le re-cache après rename de PNG          → scan/refs.py    `reset_caches`
  Les bbox du panneau adverse              → scan/offsets/opponent.py
  Les bbox du panneau joueur               → scan/offsets/player.py
  L'OCR du titre des popups                → scan/jobs/_title.py
  L'OCR du Lv.NN cartouche                 → scan/jobs/_lv.py
  L'enrichissement Weapon (windup, etc.)   → scan/jobs/_weapon_enrich.py
  Le matcher 4×2 (panel)                   → scan/jobs/_panel.py
  L'orchestrateur STRAT C (flat)           → scan/jobs/_flat.py
  Le scan d'un opponent complet            → scan/jobs/opponent.py
                                              (recompute_from_capture)
  Le scan du build joueur (8 tiles)        → scan/jobs/player_equipment.py
  Le scan d'un slot via popup détail       → scan/jobs/equipment_popup.py


================================================================================
  Fin du document
================================================================================
