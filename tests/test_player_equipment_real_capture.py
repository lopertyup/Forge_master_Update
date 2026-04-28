"""
End-to-end smoke test on the real profile screenshots committed
to ``tests/profile joueur.png`` and ``tests/profile adversaire.png``.

The test does NOT assert on the precise (age, idx, rarity) values
matched by the icon identifier -- the colour-based age heuristic
is known to misfire on a few items (tracked separately) and the
test would become brittle. Instead we assert on the PIPELINE
contract:

  * the scanner returns 8 slot dicts (one per EQUIPMENT_SLOTS)
  * every slot has the persisted-schema keys
  * level fields are non-negative integers
  * the Weapon slot, when matched, sets attack_type to either
    "melee" or "ranged"

If a slot's age/idx are zero or its hp_flat/damage_flat are zero
we treat that as a soft miss (fallback for unknown items) and
keep going.
"""

import os

try:
    import pytest
except ImportError:
    pytest = None  # type: ignore

from PIL import Image

from backend.scanner import player_equipment as pes
from backend.constants import EQUIPMENT_SLOTS


_THIS_DIR = os.path.dirname(__file__)
_PROFILE_PLAYER   = os.path.join(_THIS_DIR, "profile joueur.png")
_PROFILE_OPPONENT = os.path.join(_THIS_DIR, "profile adversaire.png")


def _assert_well_formed(out, label):
    assert out is not None, f"{label}: scanner returned None"
    assert set(out.keys()) == set(EQUIPMENT_SLOTS), (
        f"{label}: missing slots {set(EQUIPMENT_SLOTS) - set(out.keys())}")
    for slot in EQUIPMENT_SLOTS:
        d = out[slot]
        # Schema check
        for key in ("__name__", "__rarity__", "__age__", "__idx__",
                    "__level__", "hp_flat", "damage_flat", "attack_type"):
            assert key in d, f"{label}: {slot} missing key {key}"
        # Level is non-negative
        assert int(d["__level__"]) >= 0
        # Numeric stats are non-negative
        assert float(d["hp_flat"])     >= 0.0
        assert float(d["damage_flat"]) >= 0.0
        # Weapon attack_type sanity
        if slot == "EQUIP_WEAPON" and d["attack_type"]:
            assert d["attack_type"] in ("melee", "ranged"), (
                f"{label}: unexpected attack_type {d['attack_type']!r}")


def test_scan_real_player_profile_produces_8_slots():
    if not os.path.isfile(_PROFILE_PLAYER):
        if pytest is not None:
            pytest.skip("profile joueur.png not present")
        return
    img = Image.open(_PROFILE_PLAYER)
    out = pes.scan_player_equipment_image(img, skip_per_slot_ocr=True)
    _assert_well_formed(out, "player")


def test_scan_real_player_profile_at_least_some_slots_have_data():
    """At least HALF the slots should produce a non-zero age / idx
    pair (i.e. the icon identifier matched SOMETHING). A total
    failure would mean the offsets are off."""
    if not os.path.isfile(_PROFILE_PLAYER):
        if pytest is not None:
            pytest.skip("profile joueur.png not present")
        return
    img = Image.open(_PROFILE_PLAYER)
    out = pes.scan_player_equipment_image(img, skip_per_slot_ocr=True)
    matched = sum(
        1 for slot in EQUIPMENT_SLOTS
        if out[slot]["hp_flat"] != 0.0 or out[slot]["damage_flat"] != 0.0
    )
    assert matched >= 4, (
        f"only {matched}/8 slots produced non-zero stats -- offsets "
        f"or identifier may be off. Output: {out}")


def test_scan_real_opponent_profile_well_formed():
    """Same shape on the opponent screenshot -- the layout matches."""
    if not os.path.isfile(_PROFILE_OPPONENT):
        if pytest is not None:
            pytest.skip("profile adversaire.png not present")
        return
    img = Image.open(_PROFILE_OPPONENT)
    out = pes.scan_player_equipment_image(img, skip_per_slot_ocr=True)
    _assert_well_formed(out, "opponent")
