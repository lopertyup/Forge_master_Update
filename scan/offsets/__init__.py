"""
============================================================
  FORGE MASTER — Pixel-bbox layouts for scan/

  Two layouts, mirroring the two profile screens:

      scan.offsets.opponent — 5+3 equipment cells + mount +
                              skills + pets, used by the
                              opponent / Simulator scan path.

      scan.offsets.player   — 5+3 equipment cells (no mount,
                              no skills, no pets), used by
                              the player_equipment scan path.

  Both modules expose the same public surface:

      offsets_for_capture(width, height) -> dict
      write_overrides(payload) -> None
      overrides_path() -> Path

  Defaults are baked-in ratios calibrated on the chantier's
  reference captures. Per-user overrides live as JSON files
  under ``data/`` and are loaded transparently.

  Both modules are direct ports of the previous
  legacy offsets package — same numbers, same
  schema. Phase 7 of the refactor will delete the legacy copy.
============================================================
"""

from __future__ import annotations

from . import opponent, player  # noqa: F401  (re-export sub-modules)

__all__ = ["opponent", "player"]
