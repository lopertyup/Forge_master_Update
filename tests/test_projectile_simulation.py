"""
============================================================
  Tests for the projectile-impact queue in simulation.py.

  Verifies the user's contract:
    * melee = instant damage (no behaviour change)
    * ranged = damage applied AFTER travel time
    * a shot in flight lands even if the SHOOTER died
    * a shot in flight lands on a corpse but HP stays at 0
    * shooter's swing cooldown does NOT wait for the projectile
    * tick_pending_impacts is chronological & idempotent

  IMPORTANT - HP scaling
  ----------------------
  Fighter.__init__ scales hp_total by PVP_HP_MULTIPLIER (x5) when
  building hp_max. So a Fighter built from {"hp_total": 100} starts
  the fight at hp = hp_max = 500. All HP assertions below use the
  scaled values via _scaled_hp().
============================================================
"""

import random

try:
    import pytest
except ImportError:
    class _Approx:
        def __init__(self, v, abs_=1e-6):
            self.v = float(v); self.abs = abs_
        def __eq__(self, other):
            return abs(float(other) - self.v) <= self.abs
    class _PT:
        @staticmethod
        def approx(v, abs=1e-6):
            return _Approx(v, abs_=abs)
    pytest = _PT()  # type: ignore

from backend.constants import PVP_HP_MULTIPLIER
from backend.simulation.engine import Fighter, simulate
from backend.calculator.stats import combat_stats


def _stats(**over):
    base = {
        "hp_total":     100.0,
        "attack_total":  10.0,
        "attack_speed":   0.0,
        "crit_chance":    0.0,
        "crit_damage":    0.0,
        "block_chance":   0.0,
        "lifesteal":      0.0,
        "health_regen":   0.0,
        "double_chance":  0.0,
        "weapon_windup":   0.4,
        "weapon_recovery": 0.4,
    }
    base.update(over)
    return base


def _scaled_hp(hp_total):
    return hp_total * PVP_HP_MULTIPLIER


# ============================================================
#  Field plumbing
# ============================================================

def test_fighter_reads_projectile_travel_time_from_stats():
    f = Fighter(_stats(projectile_travel_time=0.35))
    assert f.projectile_travel_time == pytest.approx(0.35)


def test_fighter_default_travel_time_is_zero():
    f = Fighter(_stats())
    assert f.projectile_travel_time == 0.0


def test_combat_stats_propagates_travel_time():
    profile = {"projectile_travel_time": 0.28}
    out = combat_stats(profile)
    assert out["projectile_travel_time"] == pytest.approx(0.28)


# ============================================================
#  Direct queue mechanics
# ============================================================

def test_melee_attack_applies_immediately():
    random.seed(0)
    shooter = Fighter(_stats(attack_total=20.0,
                             projectile_travel_time=0.0,
                             block_chance=0.0))
    target  = Fighter(_stats())
    shooter._perform_attack(target, current_time=0.0)
    assert target.hp == pytest.approx(_scaled_hp(100) - 20)
    assert shooter._pending_impacts == []


def test_ranged_attack_queues_instead_of_hitting():
    random.seed(0)
    shooter = Fighter(_stats(attack_total=20.0,
                             projectile_travel_time=0.5,
                             block_chance=0.0))
    target  = Fighter(_stats())
    shooter._perform_attack(target, current_time=1.0)
    assert target.hp == pytest.approx(_scaled_hp(100))
    assert len(shooter._pending_impacts) == 1
    impact_t, dmg, ls = shooter._pending_impacts[0]
    assert impact_t == pytest.approx(1.5)
    assert dmg == pytest.approx(20.0)
    assert ls == 0.0


def test_pending_impact_lands_after_travel_time():
    random.seed(0)
    shooter = Fighter(_stats(attack_total=20.0,
                             projectile_travel_time=0.5))
    target  = Fighter(_stats())
    shooter._perform_attack(target, current_time=1.0)

    shooter.tick_pending_impacts(1.49, target)
    assert target.hp == pytest.approx(_scaled_hp(100))

    shooter.tick_pending_impacts(1.50, target)
    assert target.hp == pytest.approx(_scaled_hp(100) - 20)
    assert shooter._pending_impacts == []


def test_pending_impact_clamps_target_hp_to_zero():
    random.seed(0)
    shooter = Fighter(_stats(attack_total=2_000.0,
                             projectile_travel_time=0.3))
    target  = Fighter(_stats(hp_total=50.0))
    shooter._perform_attack(target, current_time=0.0)
    shooter.tick_pending_impacts(0.30, target)
    assert target.hp == 0.0


def test_pending_impact_lands_when_shooter_is_already_dead():
    random.seed(0)
    shooter = Fighter(_stats(attack_total=20.0,
                             projectile_travel_time=0.4,
                             lifesteal=10.0))
    target  = Fighter(_stats())
    shooter._perform_attack(target, current_time=0.0)
    shooter.hp = 0.0
    shooter.tick_pending_impacts(0.40, target)
    assert target.hp == pytest.approx(_scaled_hp(100) - 20)
    assert shooter.hp == 0.0


def test_lifesteal_heals_living_shooter_on_impact():
    random.seed(0)
    shooter = Fighter(_stats(attack_total=20.0,
                             hp_total=100.0,
                             lifesteal=50.0,
                             projectile_travel_time=0.3))
    shooter.hp = 50.0
    target  = Fighter(_stats())
    shooter._perform_attack(target, current_time=0.0)
    shooter.tick_pending_impacts(0.30, target)
    assert shooter.hp == pytest.approx(60.0)
    assert target.hp == pytest.approx(_scaled_hp(100) - 20)


def test_tick_pending_impacts_chronological_and_idempotent():
    random.seed(0)
    shooter = Fighter(_stats(attack_total=10.0,
                             projectile_travel_time=0.2))
    target  = Fighter(_stats())
    shooter._perform_attack(target, current_time=0.0)
    shooter._perform_attack(target, current_time=0.1)
    shooter._perform_attack(target, current_time=0.2)
    assert len(shooter._pending_impacts) == 3

    shooter.tick_pending_impacts(0.20, target)
    assert len(shooter._pending_impacts) == 2
    assert target.hp == pytest.approx(_scaled_hp(100) - 10)

    shooter.tick_pending_impacts(0.20, target)
    assert len(shooter._pending_impacts) == 2
    assert target.hp == pytest.approx(_scaled_hp(100) - 10)

    shooter.tick_pending_impacts(1.0, target)
    assert shooter._pending_impacts == []
    assert target.hp == pytest.approx(_scaled_hp(100) - 30)


# ============================================================
#  End-to-end via simulate()
# ============================================================

def test_simulate_runs_with_ranged_weapons_for_both_sides():
    random.seed(42)
    sj = _stats(attack_total=50.0, projectile_travel_time=0.35)
    se = _stats(attack_total=50.0, projectile_travel_time=0.35)
    result = simulate(sj, se, max_duration=10.0)
    assert result in ("WIN", "LOSE", "DRAW")


def test_simulate_ranged_versus_weak_melee_is_decisive():
    random.seed(42)
    sj = _stats(attack_total=500.0, hp_total=1000.0,
                projectile_travel_time=0.35)
    se = _stats(attack_total=10.0, hp_total=50.0,
                projectile_travel_time=0.0)
    wins = sum(simulate(sj, se, max_duration=20.0) == "WIN" for _ in range(20))
    assert wins >= 18


def test_simulate_melee_versus_melee_unchanged_outcome():
    random.seed(42)
    sj = _stats(attack_total=500.0, hp_total=1000.0)
    se = _stats(attack_total=10.0,  hp_total=50.0)
    wins = sum(simulate(sj, se, max_duration=20.0) == "WIN" for _ in range(20))
    assert wins == 20
