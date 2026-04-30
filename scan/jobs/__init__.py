"""
============================================================
  FORGE MASTER — scan jobs (Phase 3+)

  One module per zone_key. Every public job exposes the same
  signature::

      def scan(
          capture:    PIL.Image.Image,
          *,
          libs:       Optional[Dict] = None,
          debug_dir:  Optional[Path] = None,
          threshold:  float = DEFAULT_THRESHOLD,
          force_slot: Optional[str]  = None,
          force_age:  Optional[int]  = None,
      ) -> ScanResult: ...

  ⚠ No job ever asks the UI for an age, slot, or rarity.
  Any uncertainty is resolved internally (STRAT A → STRAT B
  fallback for equipment, OCR balise → colour fallback for
  pets/mount/skills).

  Production jobs (post Phase 7):

      pet.py               — single-pet popup, refs flat, STRAT C
      mount.py             — single-mount popup, refs flat, STRAT C
      skill.py             — single-skill popup, refs flat, STRAT C
      player_equipment.py  — 8-tile player panel (incl. Weapon
                             enrichment via _weapon_enrich)
      equipment_popup.py   — single-slot via the in-game item
                             detail popup (force_slot from UI)
      opponent.py          — opponent profile (8 tiles + 3 pets +
                             1 mount + 3 skills + text substats)

  Internal helpers:

      _title.py         — OCR the popup text + extract
                          [<Rarity>] / [<Age>] balise + name + Lv.
      _lv.py            — focused crop of the cartouche bas-gauche
                          de l\'icône for popup Lv. extraction.
      _flat.py          — STRAT C orchestrator shared by pet /
                          mount / skill.
      _panel.py         — 4×2 grid identifier shared by
                          player_equipment / opponent.
      _weapon_enrich.py — WeaponLibrary lookup applied after
                          identification of the Weapon slot.
============================================================
"""

from __future__ import annotations

# Nothing is re-exported at the package level on purpose: every
# caller imports the specific job they need (``from scan.jobs.pet
# import scan as scan_pet``), which keeps grep-ability sharp and
# avoids loading every job module on first import of scan.jobs.

__all__: list = []
