# Reference data

Files here are NOT loaded by the runtime. They contain values that
have been transferred into Python code (constants.py / simulation.py)
but are kept on disk so future game-balance patches can be diffed
quickly.

- ItemBalancingConfig.json — PlayerBaseDamage / PlayerBaseHealth /
  LevelScalingBase / PlayerMeleeDamageMultiplier / BaseCriticalDamage.
  Note: in-game level cap is dynamic (was 98 at one patch but can be
  raised); do NOT hardcode it.
- PvpBaseConfig.json — PvP balancing constants.
