================================================================================
  FORGE MASTER - Dossier scan/
  OCR, parsers de scan, identification visuelle adversaire
================================================================================

`scan/` transforme des captures d'ecran en donnees structurees.

Deux familles coexistent :

  1. Scans joueur OCR purs :
       equipment_popup, player_equipment, pet, mount, skill.
     Ils lisent le texte OCR, normalisent, parsers, puis retournent un
     `ScanResult`. Ils ne sauvegardent rien directement.

  2. Scan adversaire :
       opponent.py.
     Il combine OCR + identification visuelle, car le profil adverse ne donne
     pas toutes les informations par texte.


--------------------------------------------------------------------------------
1. ARBORESCENCE ACTUELLE
--------------------------------------------------------------------------------

  scan/
    __init__.py
    PLAN_REFACTO_SCAN.txt        Plan historique de refactor.
    README-SCAN.txt              Ce document.

    ocr/
      engine.py                  RapidOCR lazy, capture_region, ocr_image.
      fix.py                     Recoloriage UI + normalisation texte OCR.
      debug.py                   Dumps debug_scan/.
      parsers/
        common.py                Helpers texte et nombres.
        profile.py               Parser profil texte legacy-compatible.
        equipment.py             Parser OCR equipement.
        companion.py             Parser OCR pet/mount.
        skill.py                 Parser OCR skill.

    enemy/
      types.py                   EnemyOcrRaw, EnemyIdentifiedProfile,
                                 EnemyComputedStats, Identified*.
      parser.py                  Texte OCR adversaire -> profile partiel.

    core.py                      Matching visuel, OpenCV optionnel.
    colors.py                    Detection HSV age/rarity, lit data/colors.json.
    refs.py                      Chargement refs depuis data/icons/.
    types.py                     Candidate, ScanResult + re-export enemy types.

    offsets/
      opponent.py                Layout profil adversaire.
      player.py                  Layout panneau joueur.

    jobs/
      equipment_popup.py         Popup equipement joueur -> slot_dict.
      player_equipment.py        Panneau joueur 4x2 -> 8 slot_dicts.
      pet.py                     Popup pet -> slot_dict.
      mount.py                   Popup mount -> slot_dict.
      skill.py                   Popup skill -> slot_dict.
      opponent.py                Profil adversaire -> stats/profile/raw_text.
      _title.py                  Helper OCR titre popup.
      _lv.py                     Helper OCR level.
      _weapon_enrich.py          Enrichissement WeaponLibrary.
      _panel.py                  Adversaire ou legacy/debug uniquement.
      _flat.py                   Adversaire ou legacy/debug uniquement.


--------------------------------------------------------------------------------
2. OCR JOUEUR
--------------------------------------------------------------------------------

Regle fondamentale :
  Les jobs joueur ne font pas d'identification visuelle. Ils ne doivent pas
  importer `scan.core`, `scan.colors`, `scan.refs`, `_panel` ou `_flat`.

Parsers cibles :

  scan.ocr.parsers.equipment.parse_equipment_popup_text(text, slot=...)
  scan.ocr.parsers.companion.parse_companion_text(text)
  scan.ocr.parsers.skill.parse_skill_text(text)

Format commun dans `debug["slot_dict"]` :

  {
      "__name__": str,
      "__level__": int,
      "__rarity__": str,
      "hp_flat": float,
      "damage_flat": float,
      "substats": dict[str, float],
  }

Equipment ajoute :

  "__age__", "__idx__", "attack_type",
  "weapon_attack_range", "weapon_windup", "weapon_recovery",
  "projectile_speed", "projectile_travel_time"

Skill ajoute :

  "type": "buff" | "damage"

Invariant :
  `Skill Cooldown` est signe. `-8.0%` reste `-8.0`.


--------------------------------------------------------------------------------
3. ADVERSAIRE
--------------------------------------------------------------------------------

Point d'entree :

  scan.jobs.opponent.recompute_from_capture(capture, ocr_text=None)

Flux :

  capture PIL
    -> scan.ocr.ocr_image(capture)
    -> scan.enemy.parser.parse_enemy_text(raw_text)
    -> scan.offsets.opponent.offsets_for_capture(W, H)
    -> scan.jobs._panel.identify_panel(...)
    -> scan.refs.load_references(...)
    -> scan.core.match(...)
    -> scan.colors.identify_*_from_color(...)
    -> backend.calculator.combat.calculate_enemy_stats(...)

Seul le scan adversaire peut utiliser :

  scan.core
  scan.colors
  scan.refs


--------------------------------------------------------------------------------
4. PERSISTANCE
--------------------------------------------------------------------------------

Les jobs `scan/` ne sauvegardent jamais.

Ils retournent un `ScanResult`; le controller decide ensuite :

  - sauvegarde immediate pour une action explicite sur un slot,
  - simulation sans sauvegarde pour une comparaison,
  - sauvegarde apres confirmation utilisateur pour pet/mount/skill compare.

La persistance canonique est :

  backend.persistence.profile_store.store

Fichier runtime principal :

  backend/persistence/profile_store/profile.txt


--------------------------------------------------------------------------------
5. DATA UTILISEE PAR SCAN
--------------------------------------------------------------------------------

  data/colors.json
    Calibration HSV. `scan.colors` embarque un fallback Python, mais le JSON
    gagne au runtime s'il existe.

  data/icons/
    References visuelles pour le scan adversaire et resolution d'icones UI.

  data/WeaponLibrary.json
    Enrichissement des armes scannees par OCR.

  data/canonical.py
    Slots, ages, rarities et aliases de substats.


--------------------------------------------------------------------------------
6. API DES JOBS
--------------------------------------------------------------------------------

Tous les jobs exposent :

  def scan(
      capture,
      *,
      libs=None,
      debug_dir=None,
      threshold=DEFAULT_THRESHOLD,
      force_slot=None,
      force_age=None,
  ) -> ScanResult

Status possibles :

  ok
  low_confidence
  no_match
  ocr_unavailable
  scan_error


--------------------------------------------------------------------------------
7. TESTS ET VERIFICATIONS
--------------------------------------------------------------------------------

Verification jobs joueur OCR purs :

  rg -n "from \\.\\.core|from \\.\\.colors|from \\.\\.refs|_flat|_panel" `
    scan/jobs/equipment_popup.py scan/jobs/player_equipment.py `
    scan/jobs/pet.py scan/jobs/mount.py scan/jobs/skill.py

Verification globale :

  python -m compileall backend scan ui data game_controller.py main.py
  python -c "import game_controller; print('import ok')"
  python -m pytest

================================================================================
  Derniere mise a jour : apres migration scan.ocr / scan.enemy
================================================================================
