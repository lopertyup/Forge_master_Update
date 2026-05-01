from __future__ import annotations

from pathlib import Path

from backend.persistence import _migrate_profile
from backend.persistence.profile_store import store
from data.canonical import SUBSTAT_KEYS


def test_profile_round_trip_preserves_negative_cooldown_and_variable_substats(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "PROFILE_PATH", tmp_path / "profile.txt")
    profile = store.empty_profile()
    profile["equipment"]["Helmet"].update({
        "__name__": "Energy Helmet",
        "__level__": 87,
        "__age__": 7,
        "__rarity__": "Ultimate",
        "hp_flat": 123.0,
        "substats": {"Skill Cooldown": -8.0, "Crit Chance": 11.5},
    })
    profile["pets"]["Pet_1"].update({
        "__name__": "Electry",
        "damage_flat": 42.0,
        "substats": {},
    })

    store.save_profile(profile)
    loaded = store.load_profile()

    helmet = loaded["equipment"]["Helmet"]
    assert helmet["substats"]["Skill Cooldown"] == -8.0
    assert helmet["substats"]["Crit Chance"] == 11.5
    assert loaded["pets"]["Pet_1"]["substats"] == {}
    assert loaded["substats_total"]["Skill Cooldown"] == -8.0
    assert set(SUBSTAT_KEYS).issubset(loaded["substats_total"])


def test_save_recalculates_substats_total(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "PROFILE_PATH", tmp_path / "profile.txt")
    profile = store.empty_profile()
    profile["substats_total"]["Crit Damage"] = 999.0
    profile["equipment"]["Ring"]["substats"] = {"Crit Damage": 15.0}
    profile["mount"]["Mount"]["substats"] = {"Crit Damage": 2.5}
    profile["skills"]["Skill_1"]["substats"] = {"Crit Damage": 100.0}

    store.save_profile(profile)
    loaded = store.load_profile()

    assert loaded["substats_total"]["Crit Damage"] == 17.5


def test_legacy_migration_converts_slot_names_and_backs_up(tmp_path, monkeypatch):
    profile_txt = tmp_path / "profile.txt"
    equipment_txt = tmp_path / "equipment.txt"
    pets_txt = tmp_path / "pets.txt"
    mount_txt = tmp_path / "mount.txt"
    skills_txt = tmp_path / "skills.txt"
    new_profile = tmp_path / "profile_store" / "profile.txt"

    profile_txt.write_text("[PLAYER]\nskill_cooldown = -3.5\nattack_type = ranged\n", encoding="utf-8")
    equipment_txt.write_text(
        "[EQUIP_HELMET]\n__name__ = Old Helmet\nskill_cooldown = -8.0\n",
        encoding="utf-8",
    )
    pets_txt.write_text("[PET1]\n__name__ = Pet A\ncrit_damage = 12.0\n", encoding="utf-8")
    mount_txt.write_text("[MOUNT]\n__name__ = Mount A\nhp_flat = 10\n", encoding="utf-8")
    skills_txt.write_text("[S1]\n__name__ = Skill A\npassive_damage = 5\n", encoding="utf-8")

    monkeypatch.setattr(store, "PROFILE_PATH", new_profile)
    monkeypatch.setattr(_migrate_profile, "PROFILE_FILE", str(profile_txt))
    monkeypatch.setattr(_migrate_profile, "EQUIPMENT_FILE", str(equipment_txt))
    monkeypatch.setattr(_migrate_profile, "PETS_FILE", str(pets_txt))
    monkeypatch.setattr(_migrate_profile, "MOUNT_FILE", str(mount_txt))
    monkeypatch.setattr(_migrate_profile, "SKILLS_FILE", str(skills_txt))
    monkeypatch.setattr(
        _migrate_profile,
        "LEGACY_FILES",
        tuple(Path(p) for p in (profile_txt, equipment_txt, pets_txt, mount_txt, skills_txt)),
    )

    assert _migrate_profile.migrate_legacy_profile_once() is True
    loaded = store.load_profile()

    assert loaded["equipment"]["Helmet"]["__name__"] == "Old Helmet"
    assert loaded["equipment"]["Helmet"]["substats"]["Skill Cooldown"] == -8.0
    assert loaded["pets"]["Pet_1"]["__name__"] == "Pet A"
    assert loaded["skills"]["Skill_1"]["damage_flat"] == 5.0
    assert loaded["base_profile"]["skill_cooldown"] == -3.5
    assert (tmp_path / "equipment.txt.legacy.bak").is_file()

