"""
============================================================
  FORGE MASTER — Calculator subpackage (pure math, no I/O)

  Modules:
    stats         — applying equipment / companions, pvp_hp_total,
                    swing_time helpers (the math used during
                    simulation).
    combat        — recompute a profile's HP / Damage from the
                    raw identified gear (replaces enemy_stat_calculator).
    attack_speed  — formula-based attack-speed cycle and
                    breakpoint tables.
    optimizer     — marginal stat optimiser.
    item_keys     — stringly-typed JSON key helpers (item_key /
                    pet_key / stat_type / level_info_for).
============================================================
"""
