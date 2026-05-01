from __future__ import annotations

from game_controller import GameController
from backend.persistence.profile_store import store


def test_controller_player_setters_write_profile_store(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "PROFILE_PATH", tmp_path / "profile.txt")
    store.save_profile(store.empty_profile())

    controller = GameController()
    controller.set_profile({
        "hp_base": 80.0,
        "attack_base": 10.0,
        "health_pct": 0.0,
        "damage_pct": 0.0,
        "melee_pct": 0.0,
        "ranged_pct": 0.0,
        "attack_type": "melee",
    })
    controller.set_equipment_slot("EQUIP_HELMET", {
        "__name__": "Helmet A",
        "__level__": 2,
        "__age__": 7,
        "hp_flat": 100.0,
        "skill_cooldown": -8.0,
    })
    controller.set_pet("PET1", {
        "__name__": "Pet A",
        "__level__": 1,
        "__rarity__": "Ultimate",
        "hp_flat": 10.0,
        "damage_flat": 5.0,
        "crit_damage": 12.0,
    })
    controller.set_mount({
        "__name__": "Mount A",
        "__level__": 1,
        "__rarity__": "Rare",
        "hp_flat": 20.0,
        "damage_flat": 7.0,
    })
    controller.set_skill("S1", {
        "__name__": "Skill A",
        "__level__": 1,
        "__rarity__": "Legendary",
        "passive_damage": 3.0,
        "passive_hp": 4.0,
        "type": "buff",
    })

    profile = store.load_profile()
    assert profile["base_profile"]["hp_base"] == 84.0
    assert profile["equipment"]["Helmet"]["__name__"] == "Helmet A"
    assert profile["equipment"]["Helmet"]["substats"]["Skill Cooldown"] == -8.0
    assert profile["pets"]["Pet_1"]["__name__"] == "Pet A"
    assert profile["pets"]["Pet_1"]["substats"]["Crit Damage"] == 12.0
    assert profile["mount"]["Mount"]["__name__"] == "Mount A"
    assert profile["skills"]["Skill_1"]["damage_flat"] == 3.0
    assert profile["skills"]["Skill_1"]["hp_flat"] == 4.0
    assert profile["substats_total"]["Skill Cooldown"] == -8.0
    assert profile["substats_total"]["Crit Damage"] == 12.0
