"""
============================================================
  FORGE MASTER UI — Smoke tests
  Run:  python -m unittest discover -s tests
  or:   python -m tests.test_smoke
============================================================

Lightweight sanity checks that fail fast when something big
breaks — imports, parser basics, OCR normalisation of the
lines we've already hit as regressions, simulation shape.

No GUI, no OCR engine, no screen grab. Safe on a headless box.
"""
from __future__ import annotations

import os
import sys
import unittest

# Make sure `backend` and `ui` resolve when tests are run from the
# repo root OR from inside tests/.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


class TestImports(unittest.TestCase):
    """The modules must at least *import* cleanly on a fresh checkout."""

    def test_backend_modules_import(self):
        import backend  # noqa: F401
        from backend import (
            constants, fix_ocr, parser, persistence,
            simulation, stats, zone_store,
        )  # noqa: F401

    def test_ocr_module_is_importable_without_engine(self):
        # ocr.py uses lazy imports: importing it must NOT require
        # Pillow / rapidocr to be installed.
        from backend import ocr
        # is_available() is allowed to return False — we only check
        # that it doesn't raise.
        self.assertIsInstance(ocr.is_available(), bool)


class TestParseFlat(unittest.TestCase):
    def test_k_m_b_suffixes(self):
        from backend.parser import parse_flat
        self.assertEqual(parse_flat("42"),     42.0)
        self.assertEqual(parse_flat("1k"),     1_000.0)
        self.assertEqual(parse_flat("2.5m"),   2_500_000.0)
        self.assertEqual(parse_flat("1.3b"),   1_300_000_000.0)
        # Comma-as-decimal (French locale screenshots).
        self.assertEqual(parse_flat("1,5k"),   1_500.0)

    def test_empty_or_junk_returns_zero(self):
        from backend.parser import parse_flat
        self.assertEqual(parse_flat(""),       0.0)
        self.assertEqual(parse_flat("junk"),   0.0)


class TestFixOcrNormalise(unittest.TestCase):
    """Past regressions — adding a test for each keeps them dead."""

    def _norm(self, line: str) -> str:
        from backend.fix_ocr import _normalize_line
        return _normalize_line(line)

    # --- Bracket labels ------------------------------------------------
    def test_bracket_early_modern_survives_dash(self):
        out = self._norm("[Early-Modern] Treasure Key")
        self.assertIn("[Early-Modern]", out)

    def test_bracket_lowercase_casing(self):
        out = self._norm("[interstellar] Psi Choker")
        self.assertIn("[Interstellar]", out)

    def test_partial_bracket_recovery_close_only(self):
        out = self._norm("interstellarjimpactors")
        self.assertIn("[Interstellar]", out)

    def test_partial_bracket_recovery_both_mangled(self):
        out = self._norm("(nterstellarj Adamantum")
        self.assertIn("[Interstellar]", out)
        self.assertIn("Adamantum", out)

    def test_bracketless_fallback_capitalised_rest(self):
        out = self._norm("Space Solarius Ring")
        self.assertIn("[Space]", out)

    # --- Stat-name typos ----------------------------------------------
    def test_lifesteal_typos(self):
        for wrong in ("+16.9%LifFesteal", "+16.9%LiFesteal", "+16.9%LifeSteal"):
            out = self._norm(wrong)
            self.assertIn("Lifesteal", out, f"failed on {wrong!r} -> {out!r}")

    # --- Numeric cleanup ----------------------------------------------
    def test_level_prefix_normalised(self):
        for raw in ("LV.121", "Lv:121", "L0 121"):
            out = self._norm(raw)
            self.assertIn("Lv.", out, f"failed on {raw!r} -> {out!r}")
            self.assertIn("121", out)

    def test_oh_to_zero_inside_number(self):
        out = self._norm("23okDamage")
        self.assertIn("230k", out)
        self.assertIn("Damage", out)


class TestParseProfile(unittest.TestCase):
    """Parser must survive a plausible player stat block."""

    SAMPLE = (
        "42.0m Total Health\n"
        "318k Total Damage\n"
        "+25% Health\n"
        "+18.5% Damage\n"
        "+11.8% Critical Chance\n"
        "+8.13% Lifesteal\n"
    )

    def test_parse_profile_basic_fields(self):
        from backend.parser import parse_profile_text
        p = parse_profile_text(self.SAMPLE)
        self.assertAlmostEqual(p["hp_total"],     42_000_000.0)
        self.assertAlmostEqual(p["attack_total"], 318_000.0)
        self.assertAlmostEqual(p["health_pct"],   25.0)
        self.assertAlmostEqual(p["damage_pct"],   18.5)
        self.assertAlmostEqual(p["crit_chance"],  11.8)
        self.assertAlmostEqual(p["lifesteal"],    8.13)

    def test_parse_profile_missing_fields_default_zero(self):
        from backend.parser import parse_profile_text
        p = parse_profile_text("")
        self.assertEqual(p["hp_total"],    0.0)
        self.assertEqual(p["crit_chance"], 0.0)
        self.assertEqual(p["melee_pct"],   0.0)


class TestSimulationAvailable(unittest.TestCase):
    """simulate_batch must be importable and callable.

    We deliberately do NOT run it here: the full combat_stats dict
    shape is a moving target (attack_type, pets, skills, mount...).
    A dedicated integration test suite is a better home for that.
    """

    def test_simulate_batch_is_callable(self):
        from backend.simulation import simulate_batch
        self.assertTrue(callable(simulate_batch))


if __name__ == "__main__":
    unittest.main(verbosity=2)
