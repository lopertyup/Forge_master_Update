================================================================================
  FORGE MASTER - Dossier ui/
  Couche presentation Tk / customtkinter
================================================================================

`ui/` contient la presentation. Les vues affichent l'etat et declenchent des
actions via `GameController`; elles ne calculent pas les stats et ne
sauvegardent pas directement le profil joueur.

Etat actuel :

  - navigation principale : Dashboard, Simulator, Equipment, Skills, Mount,
    Pets, Optimizer, Zones ;
  - OCR generique via `GameController.scan(...)` ;
  - scans specialises via les methodes controller (`scan_equipment_slot`,
    `scan_player_equipment`, etc.) ;
  - persistance joueur via `backend/persistence/profile_store/`, jamais
    directement depuis une vue.


--------------------------------------------------------------------------------
1. REGLES
--------------------------------------------------------------------------------

P1. Une vue passe par `self.controller.<methode>`.
    Si une methode manque, elle se cree dans `game_controller.py`.

P2. Les longs traitements tournent cote controller dans des threads daemon.
    La vue pose un callback et le controller redispatche sur le thread Tk.

P3. Les widgets reutilisables vivent dans :

      ui/widgets.py
      ui/cards.py
      ui/dialogs.py
      ui/import_zone.py

P4. Les vues ne sauvegardent pas le profil joueur. Les mutations passent par
    le controller, puis par `profile_store`.

P5. Imports autorises dans les vues :

      - `ui.theme`
      - `ui.widgets`
      - `ui.cards`
      - constantes backend explicitement autorisees pour les vues swap-flow
        (`N_SIMULATIONS`, `EQUIPMENT_SLOTS`, `EQUIPMENT_SLOT_NAMES`)

P6. `ui/import_zone.py` est un helper UI partage. Il importe `scan.ocr.fix`
    pour normaliser le texte colle ou scanne avant affichage. Cette exception
    ne doit pas etre reproduite dans les vues.

P7. Les icones passent par `ui.theme`, pas par des chemins bricoles dans les
    vues.


--------------------------------------------------------------------------------
2. INVENTAIRE
--------------------------------------------------------------------------------

  ui/
    app.py
      `ForgeMasterApp`, side-nav, cache des vues, refresh courant.

    theme.py
      Palette, polices, labels de stats, tri de stats, helpers d'icones.

    widgets.py
      Header, lignes de stats, cards generiques, helpers import/scan.

    cards.py
      ItemCard, StatBlock, ResultDelta, SwapPanel, LibraryList.

    dialogs.py
      ConfirmDialog et helper `confirm(...)`.

    import_zone.py
      Zone de texte OCR reutilisable et normalisation `fix_ocr`.

    zone_picker.py
      Overlay de selection de bbox.

    views/
      dashboard.py
      simulator.py
      equipment.py
      skills_view.py
      mount_view.py
      pets_view.py
      optimizer_view.py
      zones_view.py


--------------------------------------------------------------------------------
3. CYCLE DE VIE D'UNE VUE
--------------------------------------------------------------------------------

Construction :

  ForgeMasterApp.show_view(view_id)
    -> cree la vue au premier affichage
    -> conserve l'instance en cache

Affichage :

  grid_remove() sur l'ancienne vue
  grid() sur la nouvelle

Refresh :

  refresh_current()
    -> invalide le cache
    -> controller.reload()
    -> reconstruit la vue active

`controller.reload()` recharge l'etat depuis la persistance actuelle :

  - profile_store pour le profil joueur canonique,
  - bibliotheques utilisateur pets/mount/skills,
  - zones,
  - window state si necessaire.


--------------------------------------------------------------------------------
4. SCAN ET OCR COTE UI
--------------------------------------------------------------------------------

Chemin OCR generique :

  self.controller.scan(zone_key, callback)

Callback :

  callback(text: str, status: str) -> None

Status possibles :

  ok
  empty
  zone_not_configured
  ocr_unavailable
  ocr_error

Scans specialises :

  controller.scan_player_equipment(callback)
  controller.scan_equipment_slot(slot, callback)

Les jobs de scan vivent dans `scan/jobs/`. Les vues n'appellent pas ces jobs
directement.


--------------------------------------------------------------------------------
5. VUES PRINCIPALES
--------------------------------------------------------------------------------

Dashboard
  Vue de synthese du profil joueur.

Simulator
  Compare le joueur courant avec le dernier adversaire scanne.

Equipment
  Build actuel, comparaison, bibliotheque. Peut declencher le scan d'un slot
  ou du panneau joueur.

Skills
  Slots equipes, comparaison et bibliotheque.

Mount
  Slot mount, comparaison et bibliotheque.

Pets
  Trois slots pet, comparaison et bibliotheque.

Optimizer
  Analyse marginale des stats.

Zones
  Calibration et test OCR des zones.


--------------------------------------------------------------------------------
6. ICONES
--------------------------------------------------------------------------------

Helpers a utiliser :

  load_skill_icon_by_name(name)
  load_pet_icon(name)
  load_mount_icon(name)
  load_equipment_icon(age, slot, sprite_name)

Les assets vivent dans `data/icons/`. La traduction des slots equipment
canoniques vers les dossiers d'assets est centralisee dans `ui.theme` et
`data.canonical`.


--------------------------------------------------------------------------------
7. AJOUTER UNE VUE
--------------------------------------------------------------------------------

1. Creer `ui/views/<nom>.py`.
2. La classe recoit `(parent, controller, app)`.
3. Utiliser les composants existants avant d'en ajouter.
4. Ajouter les appels metier au controller si necessaire.
5. Ajouter l'entree dans `ui/app.py` si la vue doit etre dans la navigation.
6. Verifier :

     python -m compileall ui
     rg -n "^(from|import) backend|^(from|import) scan" ui/views

Les imports backend autorises dans les vues doivent rester limites aux
constantes documentees en P5.

================================================================================
  Derniere mise a jour : apres refactor profile_store / scan.ocr
================================================================================
