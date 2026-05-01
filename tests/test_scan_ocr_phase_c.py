from __future__ import annotations

from pathlib import Path

from scan.ocr.parsers.companion import parse_companion_text
from scan.ocr.parsers.equipment import parse_equipment_popup_text
from scan.ocr.parsers.skill import parse_skill_text


def test_equipment_parser_preserves_negative_skill_cooldown_and_substats():
    parsed = parse_equipment_popup_text(
        "[Quantum] Energy Helmet\nLv. 87\n12.3m Health\n"
        "+11.5% Critical Chance\n-8.0% Skill Cooldown",
        slot="Helmet",
    )

    assert parsed["__name__"] == "Energy Helmet"
    assert parsed["__age__"] == 7
    assert parsed["__level__"] == 87
    assert parsed["hp_flat"] == 12_300_000.0
    assert parsed["substats"]["Crit Chance"] == 11.5
    assert parsed["substats"]["Skill Cooldown"] == -8.0


def test_companion_parser_reads_hp_damage_and_variable_substats():
    parsed = parse_companion_text(
        "[Ultimate] Electry\nLv.15\n3.93m Health\n1.47m Damage\n"
        "+19.7% Lifesteal\n+33.5% Attack Speed"
    )

    assert parsed["__name__"] == "Electry"
    assert parsed["__rarity__"] == "Ultimate"
    assert parsed["hp_flat"] == 3_930_000.0
    assert parsed["damage_flat"] == 1_470_000.0
    assert parsed["substats"] == {"Lifesteal": 19.7, "Attack Speed": 33.5}


def test_skill_parser_reads_passives_and_type():
    parsed = parse_skill_text(
        "[Ultimate] Lightning\nLv.6\ndealing 432k Damage\n"
        "Passive:\n+44.7k Base Damage +358k Base Health"
    )

    assert parsed["__name__"] == "Lightning"
    assert parsed["type"] == "damage"
    assert parsed["damage_flat"] == 44_700.0
    assert parsed["hp_flat"] == 358_000.0
    assert parsed["substats"] == {}


def test_player_jobs_do_not_import_visual_identification_helpers():
    forbidden = (
        "from ..core",
        "from ..colors",
        "from ..refs",
        "from ._flat import",
        "from ._panel import",
    )
    for rel in (
        "scan/jobs/equipment_popup.py",
        "scan/jobs/player_equipment.py",
        "scan/jobs/pet.py",
        "scan/jobs/mount.py",
        "scan/jobs/skill.py",
    ):
        text = Path(rel).read_text(encoding="utf-8")
        assert not any(pattern in text for pattern in forbidden), rel

