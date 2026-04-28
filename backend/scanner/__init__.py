"""
============================================================
  FORGE MASTER — Scanner subpackage (image + OCR + parsing)

  Modules:
    ocr               — RapidOCR engine wrapper.
    fix_ocr           — colour normalisation + post-OCR text fixes.
    debug_scan        — debug dumps of every scan step.
    icon_recognition  — wiki-grid calibration tool (admin only).
    icon_matcher      — SAD 32×32 icon → game id mapper (was
                        enemy_icon_identifier).
    ocr_types         — dataclasses for the 3-layer OCR pipeline.
    ocr_parser        — text → EnemyIdentifiedProfile.
    text_parser       — generic text parsers (profile / equipment /
                        companion / skill blocks). Replaces the old
                        backend/parser.py.
    panel             — shared equipment-panel identification
                        (was equipment_pipeline).
    player_equipment  — player-side equipment scanner.
    weapon            — player-side weapon scanner.
    offsets/opponent  — opponent capture sub-zone offsets.
    offsets/player    — player capture sub-zone offsets.
============================================================
"""
