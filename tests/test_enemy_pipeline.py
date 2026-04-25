"""End-to-end smoke tests for backend.enemy_pipeline (Phase 3 glue)."""

from __future__ import annotations

from PIL import Image

from backend import enemy_pipeline as p
from backend.enemy_ocr_types import EnemyComputedStats, EnemyIdentifiedProfile


SAMPLE_OCR_TEXT = """\
Lv. 24 Forge
4.24m Total Damage
46.3m Total Health
+40.5% Critical Chance
+631% Critical Damage
+5.15% Health Regen
+35.1% Lifesteal
+58.7% Double Chance
+25.5% Damage
+2.65% Ranged Damage
"""


def _blank_capture(w=400, h=640, color=(20, 20, 30)) -> Image.Image:
    return Image.new("RGB", (w, h), color)


def test_pipeline_runs_on_blank_capture():
    """The pipeline must NOT crash on an empty capture; it should
    produce a profile + stats that are sensible (non-negative)."""
    stats, profile, raw = p.recompute_from_capture(
        _blank_capture(),
        ocr_text=SAMPLE_OCR_TEXT,
        skip_per_slot_ocr=True,
    )
    assert isinstance(stats, EnemyComputedStats)
    assert isinstance(profile, EnemyIdentifiedProfile)
    # Substats parsed from the text:
    assert profile.substat("CriticalChance") == 40.5
    assert profile.substat("LifeSteal") == 35.1
    assert profile.substat("DamageMulti") == 25.5
    assert profile.substat("RangedDamageMulti") == 2.65
    # Displayed totals captured from the text:
    assert profile.total_damage_displayed > 0
    assert profile.total_health_displayed > 0
    # Everything below is non-negative.
    assert stats.total_damage >= 0
    assert stats.total_health >= 0


def test_pipeline_populates_8_item_slots():
    """Even when icons can't be identified, the pipeline emits one
    IdentifiedItem per slot with a default Idx=0 — keeps the
    calculator's iteration straightforward."""
    _, profile, _ = p.recompute_from_capture(
        _blank_capture(),
        ocr_text="",
        skip_per_slot_ocr=True,
    )
    assert len(profile.items) == 8
    assert profile.items[0].slot == "Helmet"
    assert profile.items[5].slot == "Weapon"


def test_pipeline_substat_passthrough_to_stats():
    """Substats from OCR must reach the computed stats."""
    stats, _, _ = p.recompute_from_capture(
        _blank_capture(),
        ocr_text="+50% Critical Chance\n+100% Critical Damage",
        skip_per_slot_ocr=True,
    )
    assert abs(stats.critical_chance - 0.5) < 1e-6
    # base 1 + 0.20 game-default + 1.0 from OCR
    assert abs(stats.critical_damage - 2.20) < 1e-6


def test_pipeline_returns_raw_text_unchanged():
    text = "+12% Lifesteal"
    _, _, raw = p.recompute_from_capture(
        _blank_capture(), ocr_text=text, skip_per_slot_ocr=True,
    )
    assert raw == text
