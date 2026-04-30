================================================================================
  FORGE MASTER — Dossier ui/
  Couche présentation Tk / customtkinter, vit au-dessus du GameController
================================================================================

Ce dossier contient TOUTE la couche présentation de Forge Master. Les vues
n'écrivent jamais sur le disque, ne calculent aucune stat, et n'importent
JAMAIS depuis backend/* (sauf pour quelques constantes nommées — voir §5).
Tout passe par game_controller.py.

L'état de la refonte décrite dans ../UI_REFACTOR_PLAN.txt est : phases 1 → 5
livrées. Le menu de navigation expose 8 entrées (Dashboard, Simulator,
Equipment, Skills, Mount, Pets, Optimizer, Zones).

────────────────────────────────────────────────────────────────────────────────
1. RÈGLES D'OR
────────────────────────────────────────────────────────────────────────────────

  P1  Une vue n'importe JAMAIS depuis backend/*. Tout passe par
      `self.controller.<methode>` (cf. game_controller.py). Si une
      méthode n'existe pas, on l'ajoute au controller — pas dans la vue.

  P2  Les longs traitements (simulate_batch, OCR scan, optimizer) tournent
      dans des threads daemon côté controller. La vue ne fait que poser
      un callback ; le controller dispatche le retour sur le thread Tk
      via _dispatch().

  P3  Les widgets réutilisables (StatRow, CardFrame, ItemCard, …) vivent
      dans ui/widgets.py ou ui/cards.py. Une vue ne ré-écrit JAMAIS un
      composant déjà disponible.

  P4  Pas de logique métier dans les vues. Parsing texte, calcul de stats,
      résolution librairie → controller. La vue orchestre les callbacks
      et le rendu ; rien d'autre.

  P5  Hiérarchie d'une vue :
          Header  (titre + actions principales — utiliser build_header)
          Body    (panneau gauche état actuel / panneau droit édition,
                   ou onglets CTkTabview pour les vues swap-flow)
          Footer  (status bar facultative pour les longues opérations)

  P6  Les sections « swap-simulation » (Equipment / Skills / Mount / Pets)
      partagent toutes la même mécanique :
          1. Afficher l'item équipé (carte gauche).
          2. L'utilisateur sélectionne un candidat (librairie ou « coller texte »).
          3. Bouton « Comparer » → controller.compare_X / test_X.
          4. Affichage du Δ via ResultDelta (win-rate + ΔHP + ΔDMG).
          5. Bouton « Appliquer » qui persiste via le controller.

  P7  Toutes les icônes passent par les helpers de ui.theme :
          load_skill_icon_by_name(name) → data/icons/skills/<name>.png
          load_pet_icon(name)           → data/icons/pets/<name>.png
          load_mount_icon(name)         → data/icons/mount/<name>.png
          load_equipment_icon(age, slot, sprite_name)
                                        → data/icons/equipment/<Age>/<Slot>/<Sprite>.png
      Pas de Path() bricolé dans une vue. Le `name` passé est exactement
      la valeur SpriteName lue dans data/Auto{Skill,Pet,Mount,Item}Mapping.json
      (display name avec espaces, ex. « Saber Tooth », « Cannon Barrage »,
      « Brown Horse », « Kevlar Helmet »). Aucune normalisation côté vue.

────────────────────────────────────────────────────────────────────────────────
2. INVENTAIRE DES FICHIERS
────────────────────────────────────────────────────────────────────────────────

  ui/
  ├── __init__.py              package marker
  ├── app.py                   ForgeMasterApp (CTk root) + side-nav (8 entrées)
  │                            Cache de vues : show_view() construit la vue
  │                            au premier passage puis la masque/affiche
  │                            via grid_remove/grid pour un switch instant.
  │                            refresh_current() invalide tout le cache pour
  │                            forcer un rebuild après mutation des données.
  │
  ├── theme.py                 Palette (C[…]), polices (FONT_*), labels de
  │                            stats (STAT_LABELS, STAT_DISPLAY_ORDER), ordre
  │                            de tri canonique (stat_sort_key, sorted_stats)
  │                            et tous les helpers d'icônes (cf. P7).
  │                            Aucun import depuis backend/*.
  │
  ├── widgets.py               Composants génériques :
  │                              build_header        — bandeau supérieur
  │                              stat_row            — ligne stat zébrée
  │                              build_wld_bars      — barres W/L/D
  │                              stats_card          — card totaux + substats
  │                              companion_slot_card — card slot équipé
  │                              skill_icon_grid     — grille de skills
  │                            Re-exporte aussi confirm/ConfirmDialog
  │                            (depuis dialogs.py) et build_import_zone /
  │                            attach_scan_button (depuis import_zone.py).
  │
  ├── cards.py                 Composants partagés extraits Phase 2 :
  │                              ItemCard       — alias companion_slot_card
  │                              StatBlock      — alias stats_card
  │                              ResultDelta    — barres W/L/D + verdict
  │                                              + boutons Apply/Discard
  │                              SwapPanel      — gauche/droite + bouton
  │                                              Compare + slot résultat
  │                              LibraryList    — filtre + scrollable + boutons
  │                                              Compare/Delete/icône par ligne
  │                            Tous testables en isolation avec un mock
  │                            controller.
  │
  ├── dialogs.py               ConfirmDialog (modale Toplevel) + helper
  │                            confirm(parent, title, message, ok_label,
  │                            cancel_label, danger=True) → bool.
  │
  ├── import_zone.py           Boîte « coller le texte OCR » réutilisée
  │                            partout (build_import_zone) +
  │                            attach_scan_button(parent, textbox, status_lbl,
  │                            scan_key, scan_fn, captures_fn) qui pilote la
  │                            FSM Scan → multi-step → display.
  │                            Cf. W6 du plan : ne JAMAIS dupliquer cette boîte.
  │
  ├── zone_picker.py           Overlay plein-écran drag-to-bbox (CTkToplevel
  │                            avec attributes('-alpha'…)). Utilisé par
  │                            zones_view.py pour calibrer un bbox OCR.
  │
  └── views/
      ├── __init__.py
      ├── dashboard.py          Vue 1-colonne, 5 cards (header [Scan / Update
      │                         / Reset] + Main stats + Substats + Skills +
      │                         Companions + Equipment 4×2 cliquable).
      │                         ZÉRO import depuis backend/*.
      │
      ├── simulator.py          Vue 2-panneaux read-only (joueur / ennemi).
      │                         L'ennemi est lu via get_last_enemy_stats()
      │                         (peek). Bouton Run désactivé si !has_profile()
      │                         OR !get_last_enemy_stats(). Affichage du Δ
      │                         via ResultDelta. ZÉRO import backend/*.
      │
      ├── equipment.py          3 onglets : [Build actuel] [Comparer]
      │                         [Librairie]. Comparer auto-simule sur
      │                         debounce 600 ms ; Librairie est browsable
      │                         depuis data/AutoItemMapping.json (filtres
      │                         Age + Slot). Importe seulement
      │                         backend.constants (EQUIPMENT_SLOTS,
      │                         EQUIPMENT_SLOT_NAMES, N_SIMULATIONS).
      │
      ├── skills_view.py        3 onglets : [Équipés] [Comparer] [Librairie].
      │                         Comparer teste un candidat contre les 3
      │                         slots → 3 cartes résultat + reco du meilleur
      │                         slot. EditSkillDialog conservé pour le
      │                         chemin save direct. Importe seulement
      │                         backend.constants.N_SIMULATIONS.
      │
      ├── mount_view.py         3 onglets : [Équipée] [Comparer] [Librairie].
      │                         Le plus simple des swap-flow (1 slot).
      │                         Importe seulement N_SIMULATIONS.
      │
      ├── pets_view.py          3 onglets : [Équipés] [Comparer] [Librairie].
      │                         Même structure que skills_view. Importe
      │                         seulement N_SIMULATIONS.
      │
      ├── optimizer_view.py     Layout 2-colonnes (résultats / config).
      │                         Verdicts colorés (KEEP / INCREASE /
      │                         DECREASE / NEUTRAL) + boutons « ⤓ CSV »
      │                         et « 📋 Copy » (TSV). ZÉRO import backend/*.
      │
      ├── zones_view.py         Sidebar (liste des zones, chip
      │                         configured / pending par ligne) + carte de
      │                         détail (bboxes + Capture + Test scan +
      │                         Reset). Test scan dump l'OCR brut dans
      │                         un textbox. ZÉRO import backend/*.
      │
      (wiki_calibration.py supprimée en Phase 7 du SCAN_REFACTOR : le
       pipeline scan/ s'auto-calibre par tile, plus besoin d'outil admin
       pour renommer les PNG.)

────────────────────────────────────────────────────────────────────────────────
3. CYCLE DE VIE D'UNE VUE
────────────────────────────────────────────────────────────────────────────────

A. Construction
   ForgeMasterApp.show_view(view_id) cherche la vue dans son cache.
   Au premier appel : `view = ViewClass(self.content_frame, controller, app)`.
   Une vue reçoit :
      parent     = content_frame de l'app (ctk.CTkFrame)
      controller = GameController unique partagé entre toutes les vues
      app        = ForgeMasterApp pour show_view() inter-vues + refresh_current()

B. Affichage
   show_view() appelle grid_remove() sur la vue précédente puis grid()
   sur la nouvelle. Pas de destroy : le widget reste en mémoire et la
   navigation suivante est instantanée.

C. Rafraîchissement
   refresh_current() invalide tout le cache, recharge le controller
   (controller.reload() lit les .txt du dossier backend/) puis re-affiche
   la vue active reconstruite. Appelé après tout import / set_profile /
   set_pets / set_equipment / set_skill / etc.

D. Threading
   Toute opération qui dépasse ~50 ms passe par le controller, qui
   spawne un thread daemon et renvoie le résultat via _dispatch (which
   re-entre sur le thread Tk via after()). Une vue ne crée JAMAIS un
   threading.Thread elle-même.

────────────────────────────────────────────────────────────────────────────────
4. PIPELINE OCR / SCAN
────────────────────────────────────────────────────────────────────────────────

Une scan utilisateur a toujours la même forme :

   self.controller.scan(zone_key, callback)

avec callback signature `(text: str, status: str) -> None`. Le status
peut être :

   "ok"                  — texte OCR récupéré
   "empty"               — moteur OK mais aucun texte (bbox trop serré)
   "zone_not_configured" — bboxes inexistants ou tous à zéro
   "ocr_unavailable"     — Pillow ou backend PaddleOCR manquant
   "ocr_error"           — moteur a planté (loggé côté controller)

La vue Zones (zones_view.py) expose un bouton « Test scan » par zone qui
appelle ce même chemin et dump le résultat dans un textbox — c'est le
diagnostic visuel quand le pipeline d'une autre vue ne renvoie rien.

Pour les zones multi-captures (profile, opponent — 2 grabs successifs),
la mécanique « Capture all » de zones_view chaîne automatiquement les
ZonePicker overlays avec un bouton « Continue » entre deux captures pour
laisser l'utilisateur scroller dans le jeu.

────────────────────────────────────────────────────────────────────────────────
5. DÉCOUPAGE BACKEND / UI
────────────────────────────────────────────────────────────────────────────────

Le critère de sortie E3 du plan exige : ZÉRO `from backend` ou
`import backend` dans dashboard.py / simulator.py / optimizer_view.py /
zones_view.py.

Les 4 vues swap-flow (Mount / Pet / Skills / Equipment) sont autorisées
à importer UNIQUEMENT des constantes nommées :
   N_SIMULATIONS              (nombre de combats / simulation)
   EQUIPMENT_SLOTS            (clés canoniques 8 slots)
   EQUIPMENT_SLOT_NAMES       (labels d'affichage des 8 slots)

Toute autre dépendance backend doit passer par une méthode du
GameController. Exemples ajoutés au fil des phases :

   simulate_vs_last_enemy(callback)         — Simulator (Phase 4)
   run_optimizer(n_points, n_sims, ...)     — Optimizer (Phase 4)
   preview_stats(profile=None) -> dict      — Equipment swap (Phase 5,
                                              remplace l'import direct
                                              de combat_stats)

(Aucune vue ne déroge à la règle « zéro import backend/scan » depuis
la Phase 7 — wiki_calibration.py, qui était l'unique exception, a été
supprimée.)

────────────────────────────────────────────────────────────────────────────────
6. ICÔNES — DATA/ICONS/
────────────────────────────────────────────────────────────────────────────────

Cf. data/README-DATA.txt §2.E. Toutes les icônes vivent sous :

   data/icons/skills/<SpriteName>.png     (18 fichiers)
   data/icons/pets/<SpriteName>.png       (25 fichiers)
   data/icons/mount/<SpriteName>.png      (15 fichiers)
   data/icons/equipment/<Age>/<Slot>/<SpriteName>.png  (231 fichiers)

Les <Age> et <Slot> côté disque NE sont PAS strictement les mêmes que
les TypeName de AutoItemMapping.json :

   AutoItemMapping TypeName  →  Folder
   ───────────────────────────────────
   Helmet                    →  Headgear
   Armour                    →  Armor
   Gloves                    →  Glove
   Necklace                  →  Neck
   Ring                      →  Ring
   Weapon                    →  Weapon
   Shoes                     →  Foot
   Belt                      →  Belt

ui/theme.py.load_equipment_icon() gère la traduction. Il accepte aussi
les clés canoniques utilisées par backend.constants.EQUIPMENT_SLOTS
(Helmet / Body / Gloves / Necklace / Ring / Weapon / Shoe / Belt) — donc
les vues peuvent indifféremment passer un slot frontend ou un TypeName.

Validation : le smoke test phase 5 résout 18 + 25 + 15 + 231 icônes
contre les 4 fichiers AutoXxxMapping.json sans manquant.

────────────────────────────────────────────────────────────────────────────────
7. AJOUTER UNE NOUVELLE VUE
────────────────────────────────────────────────────────────────────────────────

   1. Créer ui/views/<nom>.py avec une classe `NomView(ctk.CTkFrame)`
      dont __init__(self, parent, controller, app) installe la grille.
      Suivre P5 (header + body + footer) ou choisir un CTkTabview
      pour une vue swap-flow.

   2. Importer :
        - les constantes UI depuis ui.theme (couleurs, polices, helpers
          d'icônes, stat_sort_key, sorted_stats…)
        - les composants depuis ui.widgets / ui.cards
        - JAMAIS depuis backend/* (sauf exceptions §5)

   3. Toute donnée se lit via self.controller.get_*() ; toute mutation
      via self.controller.set_*() ou self.controller.import_*_text(...).
      Si la méthode n'existe pas, l'ajouter au controller AVANT de
      câbler la vue.

   4. Ajouter l'entrée dans ui/app.py:_NAV_ITEMS si la vue doit
      apparaître dans le menu latéral. Sinon, l'ouvrir comme
      CTkToplevel depuis une autre vue.

   5. Smoke tests minimum :
        - python3 -m compileall ui/<nom>.py
        - grep "^(from|import) backend" ui/views/<nom>.py
          → vide si la vue est dans le nav (sauf swap-flow autorisés)
        - vérifier que tout self.controller.<x>(...) référence une
          méthode existante de GameController.

────────────────────────────────────────────────────────────────────────────────
8. EN CAS DE DOUTE
────────────────────────────────────────────────────────────────────────────────

  - UI_REFACTOR_PLAN.txt à la racine du projet : plan complet en 5
    phases, critères de sortie chiffrés (D1..D5 phase 4, E1..E5 phase 5),
    points de vigilance W1..W7.
  - data/README-DATA.txt : structure data/, conventions de noms, mapping
    nom ↔ id (Auto{Skill,Pet,Mount,Item}Mapping.json).
  - backend/README-BACKEND.txt : invariants du moteur de simulation,
    formules attack speed, persistence des .txt utilisateur.
  - game_controller.py : la liste exhaustive des méthodes publiques
    accessibles aux vues (~58 méthodes après phase 5).

================================================================================
  Dernière mise à jour : fin avril 2026 (Phase 5 livrée)
================================================================================
