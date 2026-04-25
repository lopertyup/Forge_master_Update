"""
============================================================
  Tests for the discrete (breakpoint-aware) attack-speed model
  + the helper/weapon atq speed/ loader.

  Designed to run under pytest when available; the assertions
  are also valid plain Python so an `approx` shim is enough to
  exercise them without pytest installed.
============================================================
"""

import math

try:
    import pytest
except ImportError:           # graceful fallback for the sandbox
    class _Approx:
        def __init__(self, v, abs_=1e-6):
            self.v = float(v); self.abs = abs_
        def __eq__(self, other):
            return abs(float(other) - self.v) <= self.abs
        def __repr__(self):
            return f"approx({self.v}, abs={self.abs})"

    class _PT:
        @staticmethod
        def approx(v, abs=1e-6):
            return _Approx(v, abs_=abs)
    pytest = _PT()  # type: ignore

from backend.stats import (
    swing_time,
    swing_time_discrete,
    swing_time_double,
    POST_ATTACK_FIXED,
    DOUBLE_ATTACK_GAP,
)
from backend import weapon_breakpoints as wb


# ============================================================
#  swing_time_discrete
# ============================================================

def test_discrete_baseline_no_speed():
    """W=0.5, R=0.5, 0% -> 0.5 + 0.5 + 0.2 = 1.2 s."""
    assert swing_time_discrete(0.5, 0.5, 0.0) == pytest.approx(1.2)


def test_discrete_floors_to_nearest_tenth():
    """Wind-up of 0.567 -> 0.5 (floor) at 0% speed."""
    cycle = swing_time_discrete(0.567, 0.0, 0.0)
    assert cycle == pytest.approx(0.5 + POST_ATTACK_FIXED)


def test_discrete_zero_inputs():
    """All-zero windup/recovery still pays the 0.2 s post-attack window."""
    assert swing_time_discrete(0.0, 0.0, 0.0) == pytest.approx(POST_ATTACK_FIXED)


def test_discrete_speed_50pct():
    """W=0.5, R=0.5, 50% -> floor(5/1.5)=3 -> 0.3 + 0.3 + 0.2 = 0.8 s."""
    assert swing_time_discrete(0.5, 0.5, 50.0) == pytest.approx(0.8)


def test_discrete_speed_below_breakpoint_does_not_change_cycle():
    """Going from 0% to a sub-breakpoint speed leaves cycle untouched.

    Picks W=R=0.55 so floor(W*10) has slack; the first breakpoint
    only kicks in once W/mult drops below 0.5.
    """
    base = swing_time_discrete(0.55, 0.55, 0.0)
    sub  = swing_time_discrete(0.55, 0.55, 5.0)
    assert base == pytest.approx(sub)


def test_discrete_negative_speed_floors_to_zero():
    """Negative attack-speed should not produce a negative cycle."""
    assert swing_time_discrete(0.5, 0.5, -100.0) >= 0.0


def test_discrete_matches_club_at_zero_speed():
    """Club: W=0.9333, R=0.5667, 0% -> floor(9.33)+floor(5.67)+0.2 = 1.6 s."""
    W = 0.9333333370741457
    R = 0.5666666629258543
    assert swing_time_discrete(W, R, 0.0) == pytest.approx(1.6, abs=0.01)


# ============================================================
#  swing_time_double
# ============================================================

def test_double_adds_stepped_gap_only():
    """Confirmed in real combat (PATCH P4): a double swing is one
    full single cycle (windup + recovery + 0.2 s post) plus a
    stepped 0.25 s gap. The 0.2 s post-attack window is NOT paid a
    second time. W=R=0.5 at 0%: 1.2 + floor(2.5)/10 = 1.4 s.
    """
    single = swing_time_discrete(0.5, 0.5, 0.0)
    double = swing_time_double  (0.5, 0.5, 0.0)
    expected_gap = math.floor(DOUBLE_ATTACK_GAP * 10) / 10
    assert double == pytest.approx(single + expected_gap)


def test_double_gap_shrinks_with_speed():
    """At high enough attack speed the 0.25 s gap floors to 0.0 s,
    so swing_time_double collapses to swing_time_discrete (no extra
    post-attack window after PATCH P4).
    """
    fast = swing_time_double  (0.5, 0.5, 1000.0)
    base = swing_time_discrete(0.5, 0.5, 1000.0)
    assert fast == pytest.approx(base)


# ============================================================
#  swing_time legacy / discrete dispatch
# ============================================================

def test_legacy_swing_time_unchanged_when_no_weapon_data():
    """No windup/recovery -> linear ATTACK_INTERVAL / speed_mult."""
    assert swing_time(0.0)  == pytest.approx(0.25)
    assert swing_time(50.0) == pytest.approx(0.25 / 1.5, abs=1e-9)


def test_legacy_falls_through_when_only_one_arg_given():
    """A partial signature must NOT use the discrete formula."""
    assert swing_time(0.0, windup=0.5)   == pytest.approx(0.25)
    assert swing_time(0.0, recovery=0.5) == pytest.approx(0.25)


def test_dispatch_to_discrete_when_both_provided():
    """When both kwargs are given the discrete formula kicks in."""
    assert swing_time(0.0, windup=0.5, recovery=0.5) == pytest.approx(1.2)


# ============================================================
#  weapon_breakpoints loader + helpers
# ============================================================

def test_loader_returns_none_for_unknown():
    assert wb.load_weapon_breakpoints("DefinitelyNotAWeapon") is None
    assert wb.load_weapon_breakpoints("") is None


def test_known_list_non_empty():
    keys = wb.list_known_weapons()
    assert len(keys) > 0
    assert "PrimitiveWeaponClub" in keys


def test_loader_parses_club_tables():
    bp = wb.load_weapon_breakpoints("PrimitiveWeaponClub")
    assert bp is not None
    for k in ("primary_weapon_cycle",
              "rhythmic_windup_steps",
              "double_attack_cycle"):
        assert k in bp


def test_get_current_cycle_finds_current_row():
    bp = wb.load_weapon_breakpoints("PrimitiveWeaponClub")
    assert wb.get_current_cycle(bp) == pytest.approx(1.2)


def test_get_meta_windup_finds_meta_row():
    bp = wb.load_weapon_breakpoints("PrimitiveWeaponClub")
    meta = wb.get_meta_windup(bp)
    assert meta is not None
    assert meta["status"] == "META"


def test_next_breakpoint_strictly_above_current():
    bp = wb.load_weapon_breakpoints("PrimitiveWeaponClub")
    nxt = wb.get_next_breakpoint(bp, current_speed_pct=0.0)
    assert nxt is not None
    assert nxt["req_speed"] > 0
    assert nxt["status"] not in ("REACHED", "CURRENT")


def test_next_breakpoint_returns_none_above_max():
    bp = wb.load_weapon_breakpoints("PrimitiveWeaponClub")
    assert wb.get_next_breakpoint(bp, current_speed_pct=10_000.0) is None


def test_weapon_key_from_name_basic():
    assert wb.weapon_key_from_name(0, "Club") == "PrimitiveWeaponClub"


def test_weapon_key_from_name_handles_ampersand():
    assert wb.weapon_key_from_name(1, "Sword&Shield") == "MedievalWeaponSwordandshield"


def test_weapon_key_returns_empty_when_no_match():
    assert wb.weapon_key_from_name(0, "NotAWeapon") == ""
    assert wb.weapon_key_from_name(99, "Anything")  == ""


# ============================================================
#  End-to-end: Fighter consumes weapon_windup/recovery
# ============================================================

def test_fighter_uses_discrete_when_weapon_windup_present():
    from backend.simulation import Fighter
    stats = {
        "hp_total": 100, "attack_total": 50, "attack_speed": 0.0,
        "crit_chance": 0, "crit_damage": 0, "block_chance": 0,
        "lifesteal": 0, "health_regen": 0, "double_chance": 0,
        "weapon_windup":   0.5,
        "weapon_recovery": 0.5,
    }
    f = Fighter(stats)
    assert f.base_swing_time   == pytest.approx(1.2)
    # Double cycle: 1.2 (single) + floor(0.25*10)/10 = 1.4 s after PATCH P4.
    assert f.double_swing_time == pytest.approx(1.4)


def test_fighter_falls_back_to_legacy_when_no_weapon_data():
    from backend.simulation import Fighter
    stats = {
        "hp_total": 100, "attack_total": 50, "attack_speed": 50.0,
        "crit_chance": 0, "crit_damage": 0, "block_chance": 0,
        "lifesteal": 0, "health_regen": 0, "double_chance": 0,
    }
    f = Fighter(stats)
    assert f.base_swing_time   == pytest.approx(0.25 / 1.5, abs=1e-9)
    assert f.double_swing_time == pytest.approx(f.base_swing_time * 2.0, abs=1e-9)
