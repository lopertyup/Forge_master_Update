"""
Tests for backend.scanner.weapon.

These tests focus on the OFFLINE / pure parts:
  * the scanner returns None when given garbage input
  * the lookup pulls the right WeaponLibrary fields when an Idx
    is forced (we mock identify_item to bypass template matching)
  * travel time falls out of WeaponLibrary.AttackRange and the
    on-disk ProjectilesLibrary.Speed
"""

import io

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

from PIL import Image

from backend.scanner import weapon as pws
def _blank_img(size=64, color=(0, 0, 0, 255)):
    return Image.new("RGBA", (size, size), color)


def test_scan_returns_none_on_none_input():
    assert pws.scan_player_weapon_image(None) is None


def test_scan_returns_none_on_unrecognisable_image(monkeypatch):
    """A blank black image triggers identify_age failure; the scanner
    should bail out rather than returning bogus data."""
    monkeypatch.setattr(pws, "identify_age_from_color", lambda *a, **kw: None)
    assert pws.scan_player_weapon_image(_blank_img()) is None


def test_scan_pulls_weapon_fields_from_library(monkeypatch):
    """Mock identify_age + identify_item so the scanner's lookup can be
    asserted in isolation. We pass a fake libs dict that mirrors the
    real WeaponLibrary / ProjectilesLibrary shape."""
    monkeypatch.setattr(pws, "identify_age_from_color", lambda *a, **kw: 1)
    monkeypatch.setattr(pws, "identify_rarity_from_color",
                        lambda *a, **kw: "Epic")
    monkeypatch.setattr(pws, "identify_item",
                        lambda *a, **kw: {"age": 1, "idx": 7})

    # Synthetic library dump: weapon idx 7 in age 1 is a ranged weapon
    # (range 7) firing projectile id 99 at 25 u/s -> travel = 0.28s.
    libs = {
        "weapon_library": {
            "{'Age': 1, 'Type': 'Weapon', 'Idx': 7}": {
                "WindupTime":     0.30,
                "AttackDuration": 1.20,
                "AttackRange":    7.0,
                "ProjectileId":   99,
            },
        },
        "projectiles_library": {
            "99": {"Id": 99, "Speed": 25.0},
        },
    }
    out = pws.scan_player_weapon_image(_blank_img(), libs=libs)
    assert out is not None
    assert out["weapon_age"]  == 1
    assert out["weapon_idx"]  == 7
    assert out["weapon_windup"]   == pytest.approx(0.30)
    assert out["weapon_recovery"] == pytest.approx(0.90)   # 1.20 - 0.30
    assert out["attack_type"]     == "ranged"
    assert out["projectile_speed"] == pytest.approx(25.0)
    # PvP travel uses PVP_COMBAT_DISTANCE (~1.5 u), NOT the weapon's
    # nominal AttackRange (7.0). Both fighters close in before firing.
    from backend.weapon.projectiles import PVP_COMBAT_DISTANCE
    assert out["projectile_travel_time"] == pytest.approx(
        PVP_COMBAT_DISTANCE / 25.0, abs=1e-6)


def test_scan_melee_weapon_zero_travel(monkeypatch):
    monkeypatch.setattr(pws, "identify_age_from_color", lambda *a, **kw: 0)
    monkeypatch.setattr(pws, "identify_rarity_from_color",
                        lambda *a, **kw: "Common")
    monkeypatch.setattr(pws, "identify_item",
                        lambda *a, **kw: {"age": 0, "idx": 3})
    libs = {
        "weapon_library": {
            "{'Age': 0, 'Type': 'Weapon', 'Idx': 3}": {
                "WindupTime":     0.50,
                "AttackDuration": 1.50,
                "AttackRange":    0.30,           # melee
                "ProjectileId":   0,
            },
        },
        "projectiles_library": {},
    }
    out = pws.scan_player_weapon_image(_blank_img(), libs=libs)
    assert out is not None
    assert out["attack_type"] == "melee"
    assert out["projectile_travel_time"] == 0.0
    assert out["projectile_speed"] == 0.0
    assert out["weapon_windup"]   == pytest.approx(0.50)
    assert out["weapon_recovery"] == pytest.approx(1.00)
