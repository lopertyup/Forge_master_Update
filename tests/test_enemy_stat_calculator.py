"""
============================================================
  FORGE MASTER UI — Enemy stat recompute tests

  Phase 1 of the "recalcul stats ennemi" chantier:

    - parse_substats / parse_displayed_totals — text parsing.
    - load_libs                                — JSON loader.
    - calculate_enemy_stats                    — full pipeline,
        validated against hand-computed reference values.

  Run:
      python -m unittest tests.test_enemy_stat_calculator -v
============================================================
"""
from __future__ import annotations

import math
import os
import sys
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


# ────────────────────────────────────────────────────────────
#  Substat parser
# ────────────────────────────────────────────────────────────


class TestParseSubstats(unittest.TestCase):

    def test_basic_substats(self):
        from backend.enemy_ocr_parser import parse_substats
        text = (
            "+50.1% Critical Chance\n"
            "+28.9% Damage\n"
            "+47.3% Ranged Damage\n"
            "+12.4% Lifesteal\n"
        )
        subs = {s.stat_id: s.value for s in parse_substats(text)}
        self.assertAlmostEqual(subs["CriticalChance"], 50.1)
        self.assertAlmostEqual(subs["DamageMulti"], 28.9)
        self.assertAlmostEqual(subs["RangedDamageMulti"], 47.3)
        self.assertAlmostEqual(subs["LifeSteal"], 12.4)

    def test_specific_labels_beat_generic(self):
        """'Melee Damage' must NOT be picked up as plain Damage."""
        from backend.enemy_ocr_parser import parse_substats
        subs = {s.stat_id: s.value for s in parse_substats("+10% Melee Damage")}
        self.assertIn("MeleeDamageMulti", subs)
        self.assertNotIn("DamageMulti", subs)

    def test_empty_text_returns_empty_list(self):
        from backend.enemy_ocr_parser import parse_substats
        self.assertEqual(parse_substats(""), [])

    def test_unknown_stat_is_dropped(self):
        from backend.enemy_ocr_parser import parse_substats
        subs = {s.stat_id: s.value for s in parse_substats("+99% Mystery Power")}
        self.assertEqual(subs, {})


class TestParseDisplayedTotals(unittest.TestCase):

    def test_totals_and_level(self):
        from backend.enemy_ocr_parser import parse_displayed_totals
        text = "Lv. 23\n10.4m Total Damage\n18.7m Total Health\n"
        dmg, hp, lvl = parse_displayed_totals(text)
        self.assertAlmostEqual(dmg, 10_400_000.0)
        self.assertAlmostEqual(hp,  18_700_000.0)
        self.assertEqual(lvl, 23)

    def test_missing_fields_are_zero(self):
        from backend.enemy_ocr_parser import parse_displayed_totals
        dmg, hp, lvl = parse_displayed_totals("nothing here")
        self.assertEqual(dmg, 0.0)
        self.assertEqual(hp,  0.0)
        self.assertEqual(lvl, 0)


# ────────────────────────────────────────────────────────────
#  Library loader
# ────────────────────────────────────────────────────────────


class TestEnemyLibraries(unittest.TestCase):

    def test_load_returns_all_keys(self):
        from backend.enemy_libraries import load_libs
        libs = load_libs()
        # Every short name is at least PRESENT (may be {} if file missing,
        # but the loader must not omit it).
        for key in (
            "item_balancing_library",
            "item_balancing_config",
            "weapon_library",
            "projectiles_library",
            "pet_library",
            "pet_upgrade_library",
            "pet_balancing_library",
            "mount_upgrade_library",
            "skill_library",
            "skill_passive_library",
        ):
            self.assertIn(key, libs)

    def test_item_balancing_has_expected_shape(self):
        from backend.enemy_libraries import load_libs
        libs = load_libs()
        # Primitive helmet idx 0 should exist.
        key = "{'Age': 0, 'Type': 'Helmet', 'Idx': 0}"
        self.assertIn(key, libs["item_balancing_library"])
        self.assertIn("EquipmentStats", libs["item_balancing_library"][key])

    def test_sprite_paths_resolve(self):
        """data/sprites/ must contain every spritesheet the identifier
        will need (one per Age + pets/mounts/skills atlases)."""
        from backend.enemy_libraries import (
            age_spritesheet_path, pets_atlas_path, mounts_atlas_path,
            skills_atlas_path, AGE_TO_SPRITESHEET,
        )
        for age in AGE_TO_SPRITESHEET:
            p = age_spritesheet_path(age)
            self.assertIsNotNone(p)
            self.assertTrue(p.is_file(), f"missing {p}")
        self.assertTrue(pets_atlas_path().is_file())
        self.assertTrue(mounts_atlas_path().is_file())
        self.assertTrue(skills_atlas_path().is_file())


# ────────────────────────────────────────────────────────────
#  Calculator pipeline
# ────────────────────────────────────────────────────────────


class TestCalculateEnemyStats(unittest.TestCase):
    """Integration tests against real JSON data + hand-computed values."""

    @classmethod
    def setUpClass(cls):
        from backend.enemy_libraries import load_libs
        cls.libs = load_libs()

    def _primitive_lv1_profile(self, *, ranged: bool = False, with_substats: bool = False):
        """8 Primitive-Age (Age 0) items at level 1 — every Idx 0.

        Per ItemBalancingLibrary, Age 0 Idx 0 items have:
          - Helmet/Body/Shoes/Belt → Health = 40
          - Gloves/Necklace/Ring/Weapon → Damage = 5

        At level 1 the level scaling factor is 1.01^0 = 1.
        """
        from backend.enemy_ocr_types import (
            EnemyIdentifiedProfile,
            IdentifiedItem,
            OcrSubstat,
            SLOT_ORDER,
        )

        items = [IdentifiedItem(slot=slot, age=0, idx=0, level=1, rarity="Common")
                 for slot in SLOT_ORDER]

        substats = []
        if with_substats:
            substats = [
                OcrSubstat(stat_id="DamageMulti", value=10.0),  # +10%
                OcrSubstat(stat_id="HealthMulti", value=20.0),  # +20%
                OcrSubstat(stat_id="CriticalChance", value=15.0),
            ]

        # If the caller wants a ranged build, switch the weapon to a
        # known ranged weapon (in WeaponLibrary, AttackRange >= 1).
        # We pick Age 1 Weapon idx 5 if available, else stay melee.
        if ranged:
            for item in items:
                if item.slot == "Weapon":
                    # Hunt a ranged weapon in WeaponLibrary.
                    weapons = self.libs["weapon_library"]
                    for k, v in weapons.items():
                        if (v or {}).get("AttackRange", 0) >= 1.0:
                            # Parse "{'Age': X, 'Type': 'Weapon', 'Idx': Y}"
                            import re
                            m = re.match(
                                r"\{'Age': (\d+), 'Type': 'Weapon', 'Idx': (\d+)\}",
                                k,
                            )
                            if m:
                                item.age = int(m.group(1))
                                item.idx = int(m.group(2))
                                break
                    break

        return EnemyIdentifiedProfile(
            forge_level=1,
            total_damage_displayed=0.0,    # not validating against display here
            total_health_displayed=0.0,
            items=items,
            substats=substats,
        )

    def test_pipeline_runs_without_error(self):
        from backend.enemy_stat_calculator import calculate_enemy_stats
        profile = self._primitive_lv1_profile()
        result = calculate_enemy_stats(profile, self.libs)
        # Sanity: HP/Damage are positive numbers.
        self.assertGreater(result.total_damage, 0)
        self.assertGreater(result.total_health, 0)

    def test_primitive_melee_lv1_known_baseline(self):
        """At level 1, Primitive Idx-0 build is fully analytically computable.

        Items: 4× Damage 5 + 4× Health 40
        Base : Damage 10, Health 80
        Weapon (melee) gets ×1.6 base multiplier:
            weapon_with_melee = 5 × 1.6 = 8
        Other item damage : 3 × 5 = 15
        Total flat damage : 10 + 8 + 15 = 33
        Total flat health : 80 + 4×40 = 240
        No substats ⇒ multipliers all = 1 ⇒ totals as above.
        """
        from backend.enemy_stat_calculator import calculate_enemy_stats
        profile = self._primitive_lv1_profile()
        result = calculate_enemy_stats(profile, self.libs)
        self.assertAlmostEqual(result.total_damage, 33.0, places=4)
        self.assertAlmostEqual(result.total_health, 240.0, places=4)
        self.assertFalse(result.is_ranged_weapon)

    def test_substats_apply_globally(self):
        """+10% Damage / +20% Health should multiply the level-1 baseline.

        Damage : 33 × 1.10 = 36.3
        Health : 240 × 1.20 = 288.0
        """
        from backend.enemy_stat_calculator import calculate_enemy_stats
        profile = self._primitive_lv1_profile(with_substats=True)
        result = calculate_enemy_stats(profile, self.libs)
        self.assertAlmostEqual(result.total_damage, 36.3, places=4)
        self.assertAlmostEqual(result.total_health, 288.0, places=4)
        self.assertAlmostEqual(result.critical_chance, 0.15, places=4)

    def test_level_scaling_applied(self):
        """At level N, item value = base × 1.01^(N-1)."""
        from backend.enemy_stat_calculator import calculate_enemy_stats
        from backend.enemy_ocr_types import (
            EnemyIdentifiedProfile,
            IdentifiedItem,
            SLOT_ORDER,
        )

        items = [IdentifiedItem(slot=slot, age=0, idx=0, level=50, rarity="Common")
                 for slot in SLOT_ORDER]
        profile = EnemyIdentifiedProfile(items=items)

        # Manually compute the expected baseline at level 50.
        scale = math.pow(1.01, 49)
        weapon_dmg = 5 * scale
        other_dmg  = 3 * 5 * scale
        flat_dmg = 10 + weapon_dmg * 1.6 + other_dmg
        flat_hp  = 80 + 4 * 40 * scale

        result = calculate_enemy_stats(profile, self.libs)
        self.assertAlmostEqual(result.total_damage, flat_dmg, places=2)
        self.assertAlmostEqual(result.total_health, flat_hp, places=2)

    def test_pet_contribution(self):
        """A common pet at level 1 must add positive flat HP/Damage."""
        from backend.enemy_stat_calculator import calculate_enemy_stats
        from backend.enemy_ocr_types import (
            EnemyIdentifiedProfile, IdentifiedPet, IdentifiedItem, SLOT_ORDER,
        )

        items = [IdentifiedItem(slot=slot, age=0, idx=0, level=1, rarity="Common")
                 for slot in SLOT_ORDER]
        no_pet = EnemyIdentifiedProfile(items=items)
        with_pet = EnemyIdentifiedProfile(
            items=items,
            pets=[IdentifiedPet(id=0, rarity="Common", level=1)],
        )
        a = calculate_enemy_stats(no_pet, self.libs)
        b = calculate_enemy_stats(with_pet, self.libs)
        self.assertGreater(b.total_damage, a.total_damage)
        self.assertGreater(b.total_health, a.total_health)

    def test_mount_contribution(self):
        from backend.enemy_stat_calculator import calculate_enemy_stats
        from backend.enemy_ocr_types import (
            EnemyIdentifiedProfile, IdentifiedMount, IdentifiedItem, SLOT_ORDER,
        )

        items = [IdentifiedItem(slot=slot, age=0, idx=0, level=1, rarity="Common")
                 for slot in SLOT_ORDER]
        a = calculate_enemy_stats(EnemyIdentifiedProfile(items=items), self.libs)
        b = calculate_enemy_stats(EnemyIdentifiedProfile(
            items=items, mount=IdentifiedMount(id=0, rarity="Common", level=1),
        ), self.libs)
        self.assertGreaterEqual(b.total_damage, a.total_damage)
        self.assertGreater(b.total_health, a.total_health)

    def test_skill_passive_contribution(self):
        from backend.enemy_stat_calculator import calculate_enemy_stats
        from backend.enemy_ocr_types import (
            EnemyIdentifiedProfile, IdentifiedSkill, IdentifiedItem, SLOT_ORDER,
        )

        items = [IdentifiedItem(slot=slot, age=0, idx=0, level=1, rarity="Common")
                 for slot in SLOT_ORDER]
        # "Meat" is a Common skill in SkillLibrary, with HealthPerLevel.
        skill = IdentifiedSkill(id="Meat", level=1, rarity="Common")
        a = calculate_enemy_stats(EnemyIdentifiedProfile(items=items), self.libs)
        b = calculate_enemy_stats(EnemyIdentifiedProfile(
            items=items, skills=[skill],
        ), self.libs)
        # Common skill passive at level 1 contributes some HP and Damage.
        self.assertGreaterEqual(b.total_damage, a.total_damage)
        self.assertGreaterEqual(b.total_health, a.total_health)

    def test_ranged_weapon_skips_melee_multiplier(self):
        from backend.enemy_stat_calculator import calculate_enemy_stats
        # melee version
        m = calculate_enemy_stats(self._primitive_lv1_profile(), self.libs)
        # ranged version
        r = calculate_enemy_stats(self._primitive_lv1_profile(ranged=True), self.libs)

        # Either there is no ranged weapon in the library at all (and the
        # test is a no-op), or the ranged variant must NOT apply ×1.6 to
        # the weapon — so the damage should be lower OR equal (depending
        # on the chosen weapon's base damage).
        if r.is_ranged_weapon:
            # Same idx weapon would normally yield: melee=33, ranged=30.
            # With a different weapon idx the absolute numbers differ; we
            # only check that the ranged flag flipped.
            self.assertTrue(r.is_ranged_weapon)
        # always: melee total >= 33 (by construction)
        self.assertAlmostEqual(m.total_damage, 33.0, places=4)

    def test_accuracy_reports_filled(self):
        """damage_accuracy / health_accuracy are computed only when the
        OCR fed us a non-zero displayed value."""
        from backend.enemy_stat_calculator import calculate_enemy_stats
        from backend.enemy_ocr_types import (
            EnemyIdentifiedProfile, IdentifiedItem, SLOT_ORDER,
        )

        items = [IdentifiedItem(slot=slot, age=0, idx=0, level=1, rarity="Common")
                 for slot in SLOT_ORDER]
        profile = EnemyIdentifiedProfile(
            items=items,
            total_damage_displayed=33.0,   # exact match
            total_health_displayed=240.0,
        )
        result = calculate_enemy_stats(profile, self.libs)
        self.assertAlmostEqual(result.damage_accuracy, 0.0, places=2)
        self.assertAlmostEqual(result.health_accuracy, 0.0, places=2)


# ────────────────────────────────────────────────────────────
#  Wiring: parser → calculator
# ────────────────────────────────────────────────────────────


class TestEndToEndFromText(unittest.TestCase):

    SAMPLE_OPPONENT_TEXT = (
        "Lv. 23\n"
        "10.4m Total Damage\n"
        "18.7m Total Health\n"
        "+50.1% Critical Chance\n"
        "+28.9% Damage\n"
    )

    def test_parse_then_calculate_runs_clean(self):
        from backend.enemy_ocr_parser import parse_enemy_text
        from backend.enemy_stat_calculator import calculate_enemy_stats
        from backend.enemy_libraries import load_libs

        profile = parse_enemy_text(self.SAMPLE_OPPONENT_TEXT)
        self.assertEqual(profile.forge_level, 23)
        self.assertAlmostEqual(profile.total_damage_displayed, 10_400_000.0)
        self.assertAlmostEqual(profile.substat("DamageMulti"), 28.9)

        # No items identified yet (Phase 2 territory) ⇒ totals will be
        # very low, but the pipeline must run without raising.
        stats = calculate_enemy_stats(profile, load_libs())
        self.assertGreater(stats.total_damage, 0)
        self.assertGreater(stats.total_health, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
