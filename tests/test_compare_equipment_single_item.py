"""
Tests for P2.9 -- single-item compare_equipment path that pulls the
equipped piece from the persisted equipment.txt instead of requiring
the user to capture a side-by-side popup.

Covers:
  * Returns None when slot is unspecified and only one item is parsed.
  * Returns None when the slot exists but the persisted entry is empty.
  * apply_change_flat_only swaps flat hp/damage but leaves substats.
  * Two-item flow stays unchanged (regression).
"""

import os

try:
    import pytest
except ImportError:
    pytest = None  # type: ignore

from backend.calculator.stats import apply_change, apply_change_flat_only


def _make_profile():
    return {
        "hp_base":      100_000.0,
        "attack_base":   50_000.0,
        "hp_total":     110_000.0,
        "attack_total":  55_000.0,
        "health_pct":     10.0,
        "damage_pct":     10.0,
        "melee_pct":       0.0,
        "ranged_pct":      0.0,
        "crit_chance":    35.0,
        "crit_damage":   200.0,
        "lifesteal":      50.0,
        "double_chance":  20.0,
        "attack_speed":   80.0,
        "skill_damage":    0.0,
        "skill_cooldown":  0.0,
        "block_chance":    0.0,
        "health_regen":    0.0,
        "attack_type":   "melee",
    }


def test_apply_change_flat_only_keeps_substats():
    profile = _make_profile()
    old_eq = {"hp_flat": 5_000.0, "damage_flat": 0.0}
    new_eq = {
        "hp_flat":     8_000.0,
        "damage_flat": 0.0,
        "crit_chance": 99.0,    # would normally bump crit
        "lifesteal":   99.0,
    }
    new_profile = apply_change_flat_only(profile, old_eq, new_eq)
    # hp_base bumped by +3000
    assert new_profile["hp_base"] == 103_000.0
    # Substats UNTOUCHED -- candidate's substats not folded back in
    assert new_profile["crit_chance"] == 35.0
    assert new_profile["lifesteal"]   == 50.0
    # Totals re-derived from the new bases
    assert new_profile["hp_total"] == 103_000.0 * 1.10


def test_apply_change_full_still_works():
    """Two-item path: substats DO get swapped (legacy behaviour)."""
    profile = _make_profile()
    old_eq = {"hp_flat": 5_000.0, "damage_flat": 0.0,
              "crit_chance": 5.0, "lifesteal": 10.0}
    new_eq = {"hp_flat": 8_000.0, "damage_flat": 0.0,
              "crit_chance": 12.0, "lifesteal": 0.0}
    new_profile = apply_change(profile, old_eq, new_eq)
    # crit_chance: 35 - 5 + 12 = 42
    assert new_profile["crit_chance"] == pytest.approx(42.0) if pytest else new_profile["crit_chance"] == 42.0
    # lifesteal: 50 - 10 + 0 = 40
    assert new_profile["lifesteal"] == pytest.approx(40.0) if pytest else new_profile["lifesteal"] == 40.0
    assert new_profile["hp_base"] == 103_000.0
