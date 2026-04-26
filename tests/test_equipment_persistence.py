"""
Tests for backend.persistence.equipment -- equipment.txt I/O.

Covers:
  * empty_equipment_slot / empty_equipment factories
  * load returns 8 zero-valued slots when the file is missing
  * save -> load round-trip preserves identity + numeric fields
  * unknown sections in the file are ignored gracefully
  * malformed numeric values fall back to 0 with a warning, not crash
"""

import os
import tempfile

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

from backend import constants
from backend.persistence import equipment as eq_mod


def _redirect_to_tmp(monkeypatch, tmp_dir):
    """Point EQUIPMENT_FILE at a temporary path so the real file is
    untouched."""
    path = os.path.join(tmp_dir, "equipment.txt")
    monkeypatch.setattr(constants, "EQUIPMENT_FILE", path)
    monkeypatch.setattr(eq_mod, "EQUIPMENT_FILE", path)
    return path


def test_empty_slot_has_all_keys():
    slot = eq_mod.empty_equipment_slot()
    for k in ("__name__", "__rarity__", "__age__", "__idx__", "__level__",
              "hp_flat", "damage_flat", "attack_type"):
        assert k in slot
    assert slot["__name__"] == ""
    assert slot["hp_flat"] == 0.0


def test_empty_equipment_has_8_slots():
    eq = eq_mod.empty_equipment()
    assert len(eq) == 8
    assert set(eq.keys()) == set(constants.EQUIPMENT_SLOTS)


def test_load_missing_file_returns_zero_slots(monkeypatch, tmp_path):
    _redirect_to_tmp(monkeypatch, str(tmp_path))
    eq = eq_mod.load_equipment()
    assert set(eq.keys()) == set(constants.EQUIPMENT_SLOTS)
    for slot in constants.EQUIPMENT_SLOTS:
        assert eq[slot]["hp_flat"] == 0.0
        assert eq[slot]["__name__"] == ""


def test_round_trip_preserves_fields(monkeypatch, tmp_path):
    _redirect_to_tmp(monkeypatch, str(tmp_path))
    eq = eq_mod.empty_equipment()
    eq["EQUIP_HELMET"]["__name__"]  = "Quantum Helmet"
    eq["EQUIP_HELMET"]["__rarity__"] = "ultimate"
    eq["EQUIP_HELMET"]["__age__"]    = 7
    eq["EQUIP_HELMET"]["__idx__"]    = 0
    eq["EQUIP_HELMET"]["__level__"]  = 87
    eq["EQUIP_HELMET"]["hp_flat"]    = 1_234_567.0
    eq["EQUIP_WEAPON"]["__name__"]    = "Quantumstaff"
    eq["EQUIP_WEAPON"]["__rarity__"]  = "ultimate"
    eq["EQUIP_WEAPON"]["__age__"]     = 7
    eq["EQUIP_WEAPON"]["__level__"]   = 80
    eq["EQUIP_WEAPON"]["damage_flat"] = 5_678_901.0
    eq["EQUIP_WEAPON"]["attack_type"] = "ranged"

    eq_mod.save_equipment(eq)
    eq2 = eq_mod.load_equipment()

    assert eq2["EQUIP_HELMET"]["__name__"]   == "Quantum Helmet"
    assert eq2["EQUIP_HELMET"]["__rarity__"] == "ultimate"
    assert eq2["EQUIP_HELMET"]["__age__"]    == 7
    assert eq2["EQUIP_HELMET"]["__idx__"]    == 0
    assert eq2["EQUIP_HELMET"]["__level__"]  == 87
    assert eq2["EQUIP_HELMET"]["hp_flat"]    == pytest.approx(1_234_567.0)
    assert eq2["EQUIP_WEAPON"]["damage_flat"] == pytest.approx(5_678_901.0)
    assert eq2["EQUIP_WEAPON"]["attack_type"] == "ranged"


def test_load_ignores_unknown_section(monkeypatch, tmp_path):
    """A stray [SOMETHING] section in equipment.txt must not crash the
    loader."""
    path = _redirect_to_tmp(monkeypatch, str(tmp_path))
    with open(path, "w", encoding="utf-8") as f:
        f.write("[SOMETHING_UNRELATED]\n")
        f.write("__name__ = bogus\n\n")
        f.write("[EQUIP_HELMET]\n")
        f.write("__name__ = Helm A\n")
        f.write("__level__ = 12\n")
    eq = eq_mod.load_equipment()
    assert eq["EQUIP_HELMET"]["__name__"] == "Helm A"
    assert eq["EQUIP_HELMET"]["__level__"] == 12


def test_load_tolerates_bad_numeric_value(monkeypatch, tmp_path):
    """A garbage numeric field falls back to 0 rather than raising."""
    path = _redirect_to_tmp(monkeypatch, str(tmp_path))
    with open(path, "w", encoding="utf-8") as f:
        f.write("[EQUIP_BODY]\n")
        f.write("__level__ = NOPE\n")
        f.write("hp_flat = also_bad\n")
    eq = eq_mod.load_equipment()
    assert eq["EQUIP_BODY"]["__level__"] == 0
    assert eq["EQUIP_BODY"]["hp_flat"] == 0.0
