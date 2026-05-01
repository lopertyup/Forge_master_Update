"""
============================================================
  FORGE MASTER — Unified scan package

  Refactored scan pipeline. See ``PLAN_REFACTO_SCAN.txt`` for
  the historical design document.

  All non-OCR scans (icons / panels) follow the hybrid
  matcher pattern from the wiki-grid scanner:
  NCC grayscale + NCC Sobel edges + colour histogram
  + OCR text similarity + auto-crop + greedy assignment.

  Public sub-modules:

      scan.core      — the hybrid matcher (ensemble_score,
                       match, greedy_assignment, autocrop_*).
      scan.refs      — reference image loader with cache and
                       three modes (exact / all_ages / flat).
      scan.colors    — HSV-based heuristics for age and rarity
                       detection (background colour → age,
                       border colour → rarity).
      scan.types     — dataclasses (Candidate, ScanResult)
                       plus re-exports of the enemy OCR types from
                       scan.enemy.types.
      scan.offsets   — pixel-bbox layouts for the opponent
                       and player equipment panels.
      scan.jobs      — (added in later phases) one file per
                       zone_key (opponent, player_equipment,
                       player_weapon, pet, mount, skill).

  Phase 1 of the refactor (this checkpoint) only ships the
  matcher + helpers. Jobs and controller wiring follow.

  The OCR pipeline lives in scan.ocr. Enemy OCR types/parser live
  in scan.enemy and are re-exported through scan.types where needed.
============================================================
"""

from __future__ import annotations

# Versioned to make it easy to grep "which scan refactor phase
# is this build on?" once the migration is in flight.
__version__ = "0.1.0-phase1"

__all__ = ["__version__"]
