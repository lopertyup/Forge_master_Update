"""
============================================================
  Tests for weapon_projectiles — projectile travel time
  helpers used by the simulation engine.

  Designed to run under pytest when available; the assertions
  are also valid plain Python so an `approx` shim keeps them
  exercisable without pytest installed (mirrors the pattern
  used by test_weapon_breakpoints.py).
============================================================
"""

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

from backend import weapon_projectiles as wp


# ============================================================
#  Range-based shortcuts
# ============================================================

def test_melee_range_returns_zero_travel_time():
    """A weapon at the melee range (0.3 u) skips the lookup entirely."""
    assert wp.get_travel_time("Club", weapon_range=0.3) == 0.0


def test_ranged_default_uses_full_seven_units():
    """When weapon_range is omitted the helper assumes RANGE_RANGED=7."""
    # Bow: speed 20 in fallback table → 7/20 = 0.35 s
    assert wp.get_travel_time("Bow") == pytest.approx(0.35)


def test_explicit_range_overrides_default():
    """A custom weapon_range scales travel time linearly."""
    # Bow at half range = 3.5/20 = 0.175 s
    assert wp.get_travel_time("Bow", weapon_range=3.5) == pytest.approx(0.175)


# ============================================================
#  Per-weapon travel times (cross-checked against the chantier
#  doc reference table)
# ============================================================

def test_bow_travel_time():
    """Bow: 7 / 20 u·s⁻¹ = 0.35 s."""
    assert wp.get_travel_time("Bow") == pytest.approx(0.35)


def test_crossbow_travel_time():
    """Crossbow: 7 / 25 u·s⁻¹ = 0.28 s."""
    assert wp.get_travel_time("Crossbow") == pytest.approx(0.28)


def test_quantumstaff_travel_time():
    """Quantumstaff: 7 / 30 u·s⁻¹ ≈ 0.2333 s."""
    assert wp.get_travel_time("Quantumstaff") == pytest.approx(7.0 / 30.0,
                                                                abs=1e-6)


def test_tomahawk_slow_projectile():
    """Tomahawk: 7 / 15 u·s⁻¹ ≈ 0.4667 s — slowest in the catalogue."""
    assert wp.get_travel_time("Tomahawk") == pytest.approx(7.0 / 15.0,
                                                            abs=1e-6)


# ============================================================
#  Lookup by ProjectileId (ProjectilesLibrary.json)
# ============================================================

def test_projectile_id_lookup_overrides_fallback():
    """Lookup via projectile_id should hit ProjectilesLibrary first.

    The on-disk JSON keys id 0 with Speed 20.0, so a Bow-shaped
    request with projectile_id=0 must compute 7/20 = 0.35 s.
    """
    assert wp.get_travel_time(weapon_name="Bow",
                              projectile_id=0) == pytest.approx(0.35)


def test_projectile_id_lookup_with_dict_lib():
    """Tests that an injected lib dict is honoured (no disk I/O)."""
    fake_lib = {"42": {"Id": 42, "Speed": 14.0}}
    speed = wp.get_projectile_speed_by_id(42, lib=fake_lib)
    assert speed == pytest.approx(14.0)
    # And full helper:
    assert wp.get_travel_time(projectile_id=42, lib=fake_lib) \
        == pytest.approx(7.0 / 14.0, abs=1e-6)


def test_projectile_id_unknown_returns_none():
    """An id that is not in the lib falls back to the table."""
    assert wp.get_projectile_speed_by_id(9999, lib={}) is None


# ============================================================
#  Normalisation / lookup edge cases
# ============================================================

def test_case_insensitive_weapon_name():
    """The fallback table accepts any casing."""
    assert wp.get_projectile_speed("BLOWGUN") == pytest.approx(20.0)
    assert wp.get_projectile_speed("blowgun") == pytest.approx(20.0)
    assert wp.get_projectile_speed("BloWgUn") == pytest.approx(20.0)


def test_unknown_weapon_returns_none():
    """An unknown weapon (not in table, no projectile_id) returns None."""
    assert wp.get_projectile_speed("DefinitelyNotAWeapon") is None


def test_get_travel_time_returns_zero_when_speed_unknown():
    """Unknown weapon → fall back to legacy instant-hit."""
    assert wp.get_travel_time("DefinitelyNotAWeapon") == 0.0


def test_no_args_returns_none_speed():
    """Calling get_projectile_speed with no args returns None."""
    assert wp.get_projectile_speed() is None
