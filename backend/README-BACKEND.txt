================================================================================
  FORGE MASTER - Dossier backend/
  Logique metier, persistance joueur, calculs et simulation
================================================================================

`backend/` ne contient pas d'UI et n'importe jamais depuis `ui/`.
L'interface passe par `game_controller.py`, qui orchestre ensuite les modules
backend, `scan/` et `data/`.

Etat post-refactor scan/persistence :

  - `backend/scanner/` a ete supprime.
  - L'OCR texte vit dans `scan/ocr/`.
  - Les types et parsers adversaire vivent dans `scan/enemy/`.
  - Le pipeline adversaire vit dans `scan/jobs/opponent.py`.
  - La persistance joueur canonique vit dans
    `backend/persistence/profile_store/`.


--------------------------------------------------------------------------------
1. ARCHITECTURE ACTUELLE
--------------------------------------------------------------------------------

  backend/
    constants.py                 Constantes backend et zones OCR.
    zone_store.py                Chargement, validation et sauvegarde zones.

    calculator/
      stats.py                   Stats PvP joueur, apply_* et combat_stats.
      combat.py                  Recalcule les stats adversaire depuis un
                                 EnemyIdentifiedProfile + libs JSON.
      attack_speed.py            Formule attack speed officielle.
      optimizer.py               Analyse marginale des stats.
      item_keys.py               API publique pour les cles JSON.

    simulation/
      engine.py                  Moteur PvP tick-by-tick.

    weapon/
      projectiles.py             Vitesse et travel time des projectiles.
      breakpoints.py             Helpers derives de la formule attack speed.

    persistence/
      profile_store/             Store canonique schema v2 du profil joueur.
      _migrate_profile.py         Migration legacy vers profile_store.
      profile.py                 Shim temporaire vers profile_store.
      equipment.py               Shim temporaire vers profile_store.
      companions.py              Shim temporaire vers profile_store.
      skills.py                  Shim temporaire vers profile_store.
      libraries.py               Bibliotheques utilisateur pets/mount/skills.
      zones.py                   I/O zones.json.
      window.py                  I/O window.json.

Regle pratique :
  - Calcul pur -> `backend/calculator/`
  - Combat -> `backend/simulation/`
  - Donnees jeu JSON/icones -> `data/`
  - OCR et scan -> `scan/`
  - Persistance joueur -> `backend/persistence/profile_store/`
  - Orchestration UI -> `game_controller.py`


--------------------------------------------------------------------------------
2. PERSISTANCE JOUEUR
--------------------------------------------------------------------------------

Source de verite locale :

  backend/persistence/profile_store/profile.txt

Ce fichier est un etat utilisateur genere par l'application. Il est ignore par
Git pour eviter de publier un profil personnel; s'il est absent,
`profile_store` recree un profil vide.

API canonique :

  from backend.persistence.profile_store import store

  store.load_profile() -> dict
  store.save_profile(profile: dict) -> None
  store.empty_profile() -> dict
  store.set_equipment_slot(profile, slot, value) -> dict
  store.set_pet_slot(profile, slot, value) -> dict
  store.set_mount(profile, value) -> dict
  store.set_skill_slot(profile, slot, value) -> dict
  store.compute_substats_total(profile) -> dict[str, float]

Schema logique :

  profile = {
      "equipment": {"Helmet": {...}, ...},
      "skills": {"Skill_1": {...}, ...},
      "pets": {"Pet_1": {...}, ...},
      "mount": {"Mount": {...}},
      "substats_total": {...},
      "base_profile": {...},
  }

Les anciens fichiers `backend/profile.txt`, `equipment.txt`, `pets.txt`,
`mount.txt` et `skills.txt` sont legacy. La migration est portee par
`backend/persistence/_migrate_profile.py`. Les modules `profile.py`,
`equipment.py`, `companions.py` et `skills.py` restent des shims de
compatibilite vers `profile_store`, mais le nouveau code ne doit plus les
utiliser comme API principale.


--------------------------------------------------------------------------------
3. SCAN ET ADVERSAIRE
--------------------------------------------------------------------------------

Le backend ne contient plus de scanner.

Pipeline adversaire actuel :

  scan.ocr.ocr_image(capture)              -> texte OCR
  scan.offsets.opponent.offsets_for_capture
  scan.jobs._panel.identify_panel          -> 8 equipements + mount
  scan.refs / scan.core / scan.colors      -> identification visuelle
  scan.enemy.parser.parse_enemy_text       -> totals + substats OCR
  backend.calculator.combat.calculate_enemy_stats

Point d'entree public :

  scan.jobs.opponent.recompute_from_capture(capture, ocr_text=None)

Les scans joueur OCR purs sont dans :

  scan/jobs/equipment_popup.py
  scan/jobs/player_equipment.py
  scan/jobs/pet.py
  scan/jobs/mount.py
  scan/jobs/skill.py


--------------------------------------------------------------------------------
4. DONNEES JEU
--------------------------------------------------------------------------------

Les JSON et icones runtime sont dans `data/`.

APIs principales :

  data.libraries.load_libs()
  data.libraries.get_lib(name)
  data.library_ops.resolve_companion(...)
  data.library_ops.lv1_version_of(...)

`backend/data/` n'existe plus et ne doit pas revenir.


--------------------------------------------------------------------------------
5. INVARIANTS
--------------------------------------------------------------------------------

V1. Les vues UI ne sauvegardent pas directement. Elles appellent le controller.

V2. Toute sauvegarde joueur passe par `profile_store` via le controller.

V3. `Skill Cooldown` est un float signe. Ne jamais appliquer `abs()`.

V4. Pet et Mount gardent toujours `hp_flat` et `damage_flat`.

V5. Les skills ne contribuent pas a `substats_total`; equipment, pets et mount
    y contribuent.

V6. Le scan joueur est OCR pur. Seul le scan adversaire utilise core/colors/refs.

V7. OpenCV reste optionnel pour `scan.core`.

V8. Les constantes PvP restent dans `backend/constants.py`.

V9. `backend/zones.json`, `backend/window.json`, `logs/`, `__pycache__/` et
    les fichiers `.legacy.bak` sont des artefacts locaux non destines au depot
    GitHub.


--------------------------------------------------------------------------------
6. SMOKE TESTS
--------------------------------------------------------------------------------

Apres modification backend importante :

  python -m compileall backend scan ui data game_controller.py main.py
  python -c "import game_controller; print('import ok')"
  python -m pytest

================================================================================
  Derniere mise a jour : apres refactor scan/persistence
================================================================================
