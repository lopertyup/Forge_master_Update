================================================================================
  FORGE MASTER — Dossier backend/
  Toute la logique métier de l'application (zéro UI, zéro Tk)
================================================================================

Ce dossier contient le code Python qui transforme les captures d'écran et les
fichiers utilisateur en simulations PvP. Aucun import depuis ui/ ; tout passe
par GameController (à la racine du projet) qui sert de pont entre l'interface
et le backend.

────────────────────────────────────────────────────────────────────────────────
1. ARCHITECTURE EN COUCHES (de bas en haut)
────────────────────────────────────────────────────────────────────────────────

  ┌─────────────────────────────────────────────────────────────────────────┐
  │  pipeline.py                — orchestrateur opponent → stats           │
  ├─────────────────────────────────────────────────────────────────────────┤
  │  simulation/                — moteur de combat tick-by-tick            │
  │  calculator/                — math pure (stats, optimizer, item_keys)  │
  │  scanner/                   — image + OCR + parsers texte              │
  │  weapon/                    — physique des armes (projectiles, BP)     │
  │  data/                      — chargeur unique des JSON sous data/      │
  │  persistence/               — I/O des .txt utilisateur                 │
  │  constants.py               — constantes partagées                     │
  │  zone_store.py              — logique métier des zones OCR             │
  └─────────────────────────────────────────────────────────────────────────┘

Règle de dépendance (à respecter à chaque modification) :
    constants ← data ← weapon ← scanner ← calculator ← simulation ← pipeline
    persistence et zone_store sont à part : ils ne dépendent que de constants.

Tout import à l'intérieur de backend/ est RELATIF ("from .X" / "from ..Y").
Aucune ligne `from backend.X` dans les modules internes — sinon le moindre
renommage de dossier casse tout. Cette règle est vérifiée par le smoke test.

────────────────────────────────────────────────────────────────────────────────
2. INVENTAIRE DES MODULES
────────────────────────────────────────────────────────────────────────────────

  RACINE backend/
  ┌─────────────────────────────────────┬──────────────────────────────────────┐
  │ Fichier                             │ Rôle                                 │
  ├─────────────────────────────────────┼──────────────────────────────────────┤
  │ constants.py                        │ Constantes partagées (PvP multis,    │
  │                                     │ chemins .txt utilisateur, zones).    │
  │ pipeline.py                         │ Orchestrateur opponent (~170 lignes).│
  │                                     │ scanner → calculator pour produire   │
  │                                     │ EnemyComputedStats à partir d'une    │
  │                                     │ capture PIL.Image.                   │
  │ zone_store.py                       │ Logique métier des zones OCR         │
  │                                     │ (charger / valider / sauver bboxes). │
  └─────────────────────────────────────┴──────────────────────────────────────┘

  data/
  ┌─────────────────────────────────────┬──────────────────────────────────────┐
  │ libraries.py                        │ Chargeur lazy + cache thread-safe    │
  │                                     │ pour les JSON sous <root>/data/.     │
  │                                     │ Centralise aussi les breakpoints     │
  │                                     │ d'attaque (helper/weapon atq speed). │
  │                                     │ V2 : SEUL chargeur JSON du backend.  │
  │ library_ops.py                      │ Opérations sur les libs utilisateur  │
  │                                     │ pets/mount/skill (find_key,          │
  │                                     │ resolve_companion, lv1_version_of).  │
  └─────────────────────────────────────┴──────────────────────────────────────┘

  weapon/
  ┌─────────────────────────────────────┬──────────────────────────────────────┐
  │ projectiles.py                      │ Vitesse + travel time des armes      │
  │                                     │ ranged (fallback table + JSON).      │
  │ breakpoints.py                      │ Helpers autour des breakpoints       │
  │                                     │ pré-calculés. Délègue le chargement  │
  │                                     │ à data.libraries (V2).               │
  └─────────────────────────────────────┴──────────────────────────────────────┘

  calculator/  (calcul pur, zéro I/O)
  ┌─────────────────────────────────────┬──────────────────────────────────────┐
  │ stats.py                            │ apply_change / pvp_hp_total /        │
  │                                     │ swing_time. Math du combat PvP.      │
  │ combat.py                           │ Recompute opponent depuis identifié  │
  │                                     │ + libs JSON → EnemyComputedStats.    │
  │ attack_speed.py                     │ Formule attack-speed + tables de     │
  │                                     │ breakpoints (1611/1611 validés).     │
  │ optimizer.py                        │ Analyse marginale : pour chaque stat │
  │                                     │ teste +Δ vs −Δ et donne KEEP /       │
  │                                     │ INCREASE / DECREASE.                 │
  │ item_keys.py                        │ API publique des clés JSON           │
  │                                     │ (item_key, pet_key, stat_type,       │
  │                                     │ level_info_for). Évite que le        │
  │                                     │ scanner accède aux _privées de       │
  │                                     │ combat.py.                           │
  └─────────────────────────────────────┴──────────────────────────────────────┘

  scanner/  (image + OCR + parsing texte)
  ┌─────────────────────────────────────┬──────────────────────────────────────┐
  │ ocr.py                              │ Wrapper RapidOCR avec colour fix     │
  │                                     │ + capture_region (PIL).              │
  │ fix_ocr.py                          │ Recoloriage UI + corrections post-OCR│
  │                                     │ (937 lignes très spécialisées).      │
  │ debug_scan.py                       │ Dumps debug_scan/ horodatés.         │
  │ icon_recognition.py                 │ Outil admin de calibration ORB       │
  │                                     │ (wiki grid).                         │
  │ icon_matcher.py                     │ Template matching SAD 32×32 pour    │
  │                                     │ items / pets / mount / skills.       │
  │ ocr_types.py                        │ Dataclasses des 3 couches OCR        │
  │                                     │ (Raw / Identified / Computed).       │
  │ ocr_parser.py                       │ Substats + displayed_totals depuis   │
  │                                     │ texte OCR opponent.                  │
  │ text_parser.py                      │ Parsers texte génériques (profil,    │
  │                                     │ équipement, companion, skill).       │
  │ panel.py                            │ identify_equipment_panel partagé     │
  │                                     │ entre opponent et joueur (8 slots).  │
  │ player_equipment.py                 │ Scanner panel équipement joueur.     │
  │ weapon.py                           │ Scanner d'icône d'arme joueur seule. │
  │ offsets/opponent.py                 │ Sub-zones de la capture opponent     │
  │                                     │ (8 items + 3 pets + mount + 3 skills)│
  │ offsets/player.py                   │ Sub-zones du panel équipement joueur │
  │                                     │ (8 items uniquement).                │
  └─────────────────────────────────────┴──────────────────────────────────────┘

  simulation/
  ┌─────────────────────────────────────┬──────────────────────────────────────┐
  │ engine.py                           │ Fighter, SkillInstance, simulate,    │
  │                                     │ simulate_batch. Le moteur PvP        │
  │                                     │ tick-by-tick.                        │
  └─────────────────────────────────────┴──────────────────────────────────────┘

  persistence/  (intouché par le refactor d'avril 2026)
  ┌─────────────────────────────────────┬──────────────────────────────────────┐
  │ _io.py                              │ Helpers bas niveau, _LIBRARY_KEYS.   │
  │ profile.py                          │ profile.txt I/O.                     │
  │ skills.py                           │ skills.txt I/O (3 slots).            │
  │ companions.py                       │ pets.txt + mount.txt I/O.            │
  │ equipment.py                        │ equipment.txt I/O (8 slots).         │
  │ libraries.py                        │ pets_library / mount_library /       │
  │                                     │ skills_library (collections user).   │
  │ zones.py                            │ zones.json I/O.                      │
  │ window.py                           │ window.json I/O (geometry Tk).       │
  └─────────────────────────────────────┴──────────────────────────────────────┘

────────────────────────────────────────────────────────────────────────────────
3. POINTS D'ENTRÉE PUBLICS (par rôle)
────────────────────────────────────────────────────────────────────────────────

  Tu veux…                                  | Appelle…
  ------------------------------------------|--------------------------------------
  Lire le profil joueur depuis disque       | persistence.load_profile()
  Sauver le profil joueur                   | persistence.save_profile(p)
  Parser un bloc texte profil OCR'é         | scanner.text_parser.parse_profile_text
  Parser un pet/mount OCR'é                 | scanner.text_parser.parse_companion_meta
  Charger les libs JSON du jeu              | data.libraries.load_libs()
  Stats finales d'un profil prêt à fight    | calculator.stats.combat_stats(p)
  HP PvP pondéré (V1 invariant)             | calculator.stats.pvp_hp_total(p)
  Simuler N combats joueur vs ennemi        | simulation.engine.simulate_batch
  Recalculer un opponent depuis capture     | scan.jobs.opponent.recompute_from_capture (cf. scan/)
  Identifier les 8 pièces du joueur         | scan.jobs.player_equipment.scan (cf. scan/)
  Scanner UNE pièce via popup détail        | scan.jobs.equipment_popup.scan(force_slot=…)
  Optimiser un profil (stat par stat)       | calculator.optimizer.analyze_profile
  Breakpoints d'attack speed                | calculator.attack_speed.compute_breakpoint_tables
  Charger / valider une zone OCR            | zone_store.load / is_zone_configured

────────────────────────────────────────────────────────────────────────────────
4. INVARIANTS À NE JAMAIS CASSER
────────────────────────────────────────────────────────────────────────────────

  V1  PvP HP. Toute simulation utilise pvp_hp_total(profile), JAMAIS hp_total
      brut. Les multiplicateurs PvP par source (équipement 1.0, pet 0.5,
      skill 0.5, mount 2.0) sont définis dans constants.py.

  V2  Chargeur JSON unique. Tout fichier sous data/*.json se lit via
      data.libraries.load_libs() ou get_lib(name). Les caches isolés sont
      interdits — ils ré-ouvrent les mêmes fichiers et divergent.

  V3  Imports relatifs. Aucun "from backend.X" dans backend/. Les modules
      utilisent "from .X" (même sous-dossier) ou "from ..Y" (un niveau plus
      haut).

  V4  Précision OCR > approximations. Le calculator ne tolère pas un fallback
      du genre "AttackDuration = 1.5 par défaut" : il lit RealAttackDuration
      en priorité (validé wiki, 1.10-1.20 par arme).

  V5  skill_cooldown négatif. Une valeur "+X% Skill Cooldown" lue avec un
      signe NÉGATIF signifie une RÉDUCTION du cooldown. Le moteur traite
      donc skill_cooldown comme un signed float et l'applique
      multiplicativement : (1 + skill_cooldown_pct/100).

  V6  Pas de shim de compat. Le module forge_master.py a été supprimé. Si tu
      vois un nouveau "from backend.forge_master import …" apparaître dans
      un PR, c'est une régression — pointer vers le module direct.

  V7  Stats utilisateur ≠ stats jeu. Les .txt utilisateur (profile.txt,
      pets.txt, …) restent au format texte simple — ils sont versionnés à
      part dans persistence/. Aucun nouveau champ n'y est ajouté sans
      mise à jour du loader correspondant.

────────────────────────────────────────────────────────────────────────────────
5. PIPELINES TYPE
────────────────────────────────────────────────────────────────────────────────

  A.  L'utilisateur change un pet. La vue compare actuel vs candidat.
      ──────────────────────────────────────────────────────────────────────
      ui                                                       | game_controller
      ───────────────────────────────────────────────────────────────────────
      [user clique "remplacer Whirly Bull par Saber Tooth"]    |
      → controller.swap_pet(slot, candidate_text)              |
        → scanner.text_parser.parse_companion_meta(text)       |
        → data.library_ops.resolve_companion(meta, pets_lib)   |
        → data.library_ops.lv1_version_of(actuel)              |
        → calculator.stats.apply_pet(profile, candidat)        |
        → simulation.engine.simulate_batch(profile_actuel,     |
                                            profile_candidat)  |
        → renvoyer win_rate à la vue                           |

  B.  L'utilisateur scanne un opponent (zone "opponent").
      ──────────────────────────────────────────────────────────────────────
      → controller.scan_zone("opponent", callback)
        → scanner.ocr.capture_region(bbox)
        → scanner.ocr.ocr_image(img)              # texte
        → pipeline.recompute_from_capture(img, ocr_text=...)
            → scanner.offsets.opponent.offsets_for_capture(W, H)
            → scanner.panel.identify_equipment_panel(img, offsets)
            → scanner.icon_matcher.identify_all(...)  # pets/mount/skills
            → scanner.ocr_parser.parse_enemy_text(ocr_text)
            → calculator.combat.calculate_enemy_stats(profile, libs)
        → controller stocke EnemyComputedStats pour la prochaine simulation

  C.  L'utilisateur lance le simulator avec son profil joueur sauvegardé.
      ──────────────────────────────────────────────────────────────────────
      → controller.simulate(player_profile, enemy_profile)
        → calculator.stats.combat_stats(player) / combat_stats(enemy)
        → simulation.engine.simulate_batch(player_cs, enemy_cs, n=1000)
        → renvoyer (wins, losses, draws, win_rate, mean_duration, ...)

────────────────────────────────────────────────────────────────────────────────
6. AJOUTER UNE NOUVELLE FONCTIONNALITÉ — CHECKLIST
────────────────────────────────────────────────────────────────────────────────

  1. Trouver la BONNE COUCHE :
     - Calcul pur (formule) → calculator/
     - Lecture/écriture des .txt user → persistence/
     - Lecture des JSON jeu → passer par data.libraries
     - Image / OCR / parsing texte → scanner/
     - Combat tick-by-tick → simulation/engine.py
     - Orchestration multi-couche → pipeline.py (rester fin)

  2. Imports relatifs uniquement (cf. V3).

  3. Si la fonctionnalité a besoin d'une lib JSON nouvelle :
     - L'ajouter dans data/libraries.py (_LIB_FILES) — ne PAS créer
       un loader privé ailleurs.
     - Mettre à jour data/README.txt.

  4. Tests : les tests/ référencent les modules par chemin complet
     (ex: backend.scanner.text_parser). Vérifier qu'aucun ancien chemin
     ne traîne.

  5. UI : si la fonctionnalité doit apparaître dans une vue, c'est
     game_controller.py qui expose la méthode publique. Les vues n'importent
     JAMAIS directement depuis backend/* — toujours via le controller.

────────────────────────────────────────────────────────────────────────────────
7. HISTORIQUE
────────────────────────────────────────────────────────────────────────────────

  Avril 2026 — refactor architectural majeur :
    - Préfixe "enemy_*" supprimé (modules génériques renommés).
    - Couplage privé→privé éliminé via calculator/item_keys.py.
    - Chargeur JSON centralisé dans data/libraries.py.
    - parser.py scindé : utilitaires bas-niveau gardés dans
      scanner/text_parser.py, qui remplace l'ancien.
    - forge_master.py (shim de compat) supprimé.
    - Tous les imports externes mis à jour (game_controller, ui,
      tools, tests).
    Voir ARCHITECTURE_PLAN.txt pour le détail de la migration.

================================================================================
  Dernière mise à jour : fin avril 2026
================================================================================
