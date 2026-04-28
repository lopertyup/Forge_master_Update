"""
Tests for backend.scanner.player_equipment.

We avoid requiring the real OCR backend by:
  * mocking identify_equipment_panel to return a deterministic set
    of IdentifiedItem records (one per slot)
  * passing a hand-crafted ``libs`` dict so the scanner's library
    lookups are predictable
  * passing skip_per_slot_ocr=True (returns level=1 for every slot)

Round-trip with persistence.save_equipment / load_equipment is
already covered by test_equipment_persistence.py.
"""

import os

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

from backend.scanner import player_equipment as pes
from backend.constants import EQUIPMENT_SLOTS
from backend.scanner.ocr_types import IdentifiedItem


def _blank_img(size=(800, 400)):
    return Image.new("RGBA", size, (0, 0, 0, 255))


def _fake_libs():
    """Synthetic libs covering one Helmet (idx 1, age 7), one Weapon
    (idx 0, age 7, melee), and a balancing config."""
    return {
        "item_balancing_config": {
            "LevelScalingBase": 1.01,
        },
        "item_balancing_library": {
            # Helmet: age 7, idx 1, level 50 -> Health 1000 * 1.01^49
            "{'Age': 7, 'Type': 'Helmet', 'Idx': 1}": {
                "Name": "Quantum Helmet",
                "EquipmentStats": [
                    {"StatNode": {"UniqueStat": {"StatType": "Health"}},
                     "Value": 1000.0},
                ],
            },
            # Weapon: age 7, idx 0, level 80 -> Damage 5000 * 1.01^79
            "{'Age': 7, 'Type': 'Weapon', 'Idx': 0}": {
                "Name": "Blackgun",
                "EquipmentStats": [
                    {"StatNode": {"UniqueStat": {"StatType": "Damage"}},
                     "Value": 5000.0},
                ],
            },
        },
        "weapon_library": {
            "{'Age': 7, 'Type': 'Weapon', 'Idx': 0}": {
                "AttackRange":   7.0,    # ranged
                "WindupTime":    0.5,
                "AttackDuration": 1.5,
            },
        },
    }


def test_scan_returns_none_on_none_input():
    assert pes.scan_player_equipment_image(None) is None


def test_scan_returns_8_slots(monkeypatch):
    """All 8 slots are present in the output, even when only some
    pieces could be identified."""
    fake_items = [
        IdentifiedItem(slot="Helmet", age=7, idx=1, rarity="Ultimate", level=50),
        IdentifiedItem(slot="Weapon", age=7, idx=0, rarity="Ultimate", level=80),
        # The other 6 slots: identify_all returns placeholder records
        IdentifiedItem(slot="Body",     age=0, idx=0, rarity="Common", level=1),
        IdentifiedItem(slot="Gloves",   age=0, idx=0, rarity="Common", level=1),
        IdentifiedItem(slot="Necklace", age=0, idx=0, rarity="Common", level=1),
        IdentifiedItem(slot="Ring",     age=0, idx=0, rarity="Common", level=1),
        IdentifiedItem(slot="Shoe",     age=0, idx=0, rarity="Common", level=1),
        IdentifiedItem(slot="Belt",     age=0, idx=0, rarity="Common", level=1),
    ]
    monkeypatch.setattr(pes, "identify_equipment_panel", lambda *a, **kw: fake_items)
    out = pes.scan_player_equipment_image(_blank_img(), libs=_fake_libs(),
                                          skip_per_slot_ocr=True)
    assert out is not None
    assert set(out.keys()) == set(EQUIPMENT_SLOTS)


def test_scan_pulls_level_scaled_helmet_hp(monkeypatch):
    """Helmet level 50 should scale Health by 1.01^49."""
    fake_items = [
        IdentifiedItem(slot="Helmet", age=7, idx=1, rarity="Ultimate", level=50),
        IdentifiedItem(slot="Body",     age=0, idx=0, rarity="Common", level=1),
        IdentifiedItem(slot="Gloves",   age=0, idx=0, rarity="Common", level=1),
        IdentifiedItem(slot="Necklace", age=0, idx=0, rarity="Common", level=1),
        IdentifiedItem(slot="Ring",     age=0, idx=0, rarity="Common", level=1),
        IdentifiedItem(slot="Weapon",   age=0, idx=0, rarity="Common", level=1),
        IdentifiedItem(slot="Shoe",     age=0, idx=0, rarity="Common", level=1),
        IdentifiedItem(slot="Belt",     age=0, idx=0, rarity="Common", level=1),
    ]
    monkeypatch.setattr(pes, "identify_equipment_panel", lambda *a, **kw: fake_items)
    out = pes.scan_player_equipment_image(_blank_img(), libs=_fake_libs())

    expected = 1000.0 * (1.01 ** 49)
    assert out["EQUIP_HELMET"]["__name__"] == "Quantum Helmet"
    assert out["EQUIP_HELMET"]["__age__"]   == 7
    assert out["EQUIP_HELMET"]["__level__"] == 50
    assert out["EQUIP_HELMET"]["hp_flat"]   == pytest.approx(expected, abs=1e-3)
    # No Damage stat on a Helmet
    assert out["EQUIP_HELMET"]["damage_flat"] == 0.0


def test_scan_resolves_weapon_attack_type(monkeypatch):
    """The scanner sets attack_type=ranged when the weapon's
    AttackRange >= 1.0."""
    fake_items = [
        IdentifiedItem(slot="Helmet",   age=0, idx=0, rarity="Common", level=1),
        IdentifiedItem(slot="Body",     age=0, idx=0, rarity="Common", level=1),
        IdentifiedItem(slot="Gloves",   age=0, idx=0, rarity="Common", level=1),
        IdentifiedItem(slot="Necklace", age=0, idx=0, rarity="Common", level=1),
        IdentifiedItem(slot="Ring",     age=0, idx=0, rarity="Common", level=1),
        IdentifiedItem(slot="Weapon",   age=7, idx=0, rarity="Ultimate", level=80),
        IdentifiedItem(slot="Shoe",     age=0, idx=0, rarity="Common", level=1),
        IdentifiedItem(slot="Belt",     age=0, idx=0, rarity="Common", level=1),
    ]
    monkeypatch.setattr(pes, "identify_equipment_panel", lambda *a, **kw: fake_items)
    out = pes.scan_player_equipment_image(_blank_img(), libs=_fake_libs())

    assert out["EQUIP_WEAPON"]["__name__"]    == "Blackgun"
    assert out["EQUIP_WEAPON"]["attack_type"] == "ranged"
    expected_dmg = 5000.0 * (1.01 ** 79)
    assert out["EQUIP_WEAPON"]["damage_flat"] == pytest.approx(expected_dmg, abs=1e-2)
    # Non-weapon slots leave attack_type empty
    assert out["EQUIP_HELMET"]["attack_type"] == ""


def test_scan_unknown_item_returns_empty_slot(monkeypatch):
    """A piece whose (age, type, idx) is missing from the library
    must NOT crash -- the corresponding slot stays at zeros."""
    fake_items = [
        IdentifiedItem(slot="Helmet",   age=99, idx=99, rarity="Mythic", level=1),
        IdentifiedItem(slot="Body",     age=0, idx=0, rarity="Common", level=1),
        IdentifiedItem(slot="Gloves",   age=0, idx=0, rarity="Common", level=1),
        IdentifiedItem(slot="Necklace", age=0, idx=0, rarity="Common", level=1),
        IdentifiedItem(slot="Ring",     age=0, idx=0, rarity="Common", level=1),
        IdentifiedItem(slot="Weapon",   age=0, idx=0, rarity="Common", level=1),
        IdentifiedItem(slot="Shoe",     age=0, idx=0, rarity="Common", level=1),
        IdentifiedItem(slot="Belt",     age=0, idx=0, rarity="Common", level=1),
    ]
    monkeypatch.setattr(pes, "identify_equipment_panel", lambda *a, **kw: fake_items)
    out = pes.scan_player_equipment_image(_blank_img(), libs=_fake_libs())

    # The age/idx are still recorded so a hand-edit can fix the lookup
    assert out["EQUIP_HELMET"]["__age__"] == 99
    assert out["EQUIP_HELMET"]["__idx__"] == 99
    # But the cached stats are zero (lookup miss)
    assert out["EQUIP_HELMET"]["hp_flat"] == 0.0
    assert out["EQUIP_HELMET"]["damage_flat"] == 0.0
