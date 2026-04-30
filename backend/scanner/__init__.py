"""
============================================================
  FORGE MASTER — Scanner subpackage (text-OCR utilities only)

  Post Phase-7, ``backend.scanner`` is intentionally narrowed
  to the text-OCR side of the pipeline. Every visual / icon
  identification module migrated to the unified ``scan/``
  package at the project root (cf. SCAN_REFACTOR.txt §7).

  Modules:
    ocr               — RapidOCR engine wrapper.
    fix_ocr           — colour normalisation + post-OCR text fixes.
    debug_scan        — debug dumps of every scan step.
    ocr_types         — dataclasses for the 3-layer OCR pipeline.
    ocr_parser        — text → EnemyIdentifiedProfile.
    text_parser       — generic text parsers (profile / equipment /
                        companion / skill blocks). Replaces the old
                        backend/parser.py.

  Removed in Phase 7 (now under ``scan/``):
    icon_recognition  → scan/core.py
    icon_matcher      → scan/colors.py + scan/core.py
    panel             → scan/jobs/_panel.py
    player_equipment  → scan/jobs/player_equipment.py
    weapon            → scan/jobs/_weapon_enrich.py (slot-level
                        enrichment, not a standalone job anymore)
    offsets/{opponent,player}  → scan/offsets/{opponent,player}.py
============================================================
"""
