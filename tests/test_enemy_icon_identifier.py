"""Tests for backend.enemy_icon_identifier (Phase 2)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

import pytest
from PIL import Image

from backend import enemy_icon_identifier as ii
from backend.enemy_libraries import (
    DATA_DIR,
    pets_atlas_path,
    mounts_atlas_path,
    skills_atlas_path,
)


# ────────────────────────────────────────────────────────────
#  Self-match: identifying a sprite extracted from its own
#  atlas must yield exactly the same identifier.
# ────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_caches() -> Iterator[None]:
    ii.reset_caches()
    yield
    ii.reset_caches()


def _atlas_entries(kind: str):
    cfg = ii._load_manual_mapping()[kind]
    sheet = ii._atlas(kind)
    for idx_str, data in cfg["mapping"].items():
        crop = ii.extract_sprite(sheet, int(idx_str), kind)
        yield int(idx_str), data, crop


def test_pets_self_match():
    miss = []
    for idx, data, crop in _atlas_entries("pets"):
        out = ii.identify_pet(crop)
        assert out is not None, f"no match for pet idx={idx}"
        if out["id"] != data["id"] or out["rarity"] != data["rarity"]:
            miss.append((idx, data, out))
    assert not miss, f"misidentified: {miss[:3]}"


def test_mounts_self_match():
    miss = []
    for idx, data, crop in _atlas_entries("mounts"):
        out = ii.identify_mount(crop)
        assert out is not None
        if out["id"] != data["id"] or out["rarity"] != data["rarity"]:
            miss.append((idx, data, out))
    assert not miss, f"misidentified: {miss[:3]}"


def test_skills_self_match():
    miss = []
    for idx, data, crop in _atlas_entries("skills"):
        out = ii.identify_skill(crop)
        assert out is not None
        if out["id"] != data.get("name"):
            miss.append((idx, data, out))
    assert not miss, f"misidentified: {miss[:3]}"


# ────────────────────────────────────────────────────────────
#  Colour heuristics — synthetic patches with known HSV.
# ────────────────────────────────────────────────────────────


def _solid(rgb, w=24, h=24):
    return Image.new("RGB", (w, h), rgb)


def test_rarity_color_classifies_blue_as_rare():
    # Pure mid-saturation blue (HSV ~ 0.61, 0.80, 0.90) → Rare.
    assert ii.identify_rarity_from_color(_solid((46, 91, 230))) == "Rare"


def test_rarity_color_classifies_gold_as_legendary():
    assert ii.identify_rarity_from_color(_solid((255, 200, 26))) == "Legendary"


def test_age_color_classifies_brown_as_primitive():
    # ~ HSV (0.07, 0.50, 0.45) → Primitive (age 0).
    assert ii.identify_age_from_color(_solid((115, 88, 60))) == 0


# ────────────────────────────────────────────────────────────
#  identify_item gracefully returns None when no labels exist.
# ────────────────────────────────────────────────────────────


def test_identify_item_returns_none_without_labels(monkeypatch, tmp_path):
    """If data/items/<SpriteName>.png doesn't exist, identification
    returns None and the caller is expected to fall back to Idx=0."""
    # Force the labels cache to point at an empty dir.
    fake_items = tmp_path / "items"
    fake_items.mkdir()
    monkeypatch.setattr(ii, "ITEMS_ROOT", fake_items)
    # Reset cached labels so the test's empty dir is consulted.
    ii.reset_caches()
    crop = Image.new("RGB", (32, 32), (200, 50, 50))
    assert ii.identify_item(crop, "Helmet", 0) is None


# ────────────────────────────────────────────────────────────
#  identify_all wires every offset together.
# ────────────────────────────────────────────────────────────


def test_identify_all_returns_expected_shape():
    # A blank 400×640 capture; we don't care about the matches'
    # accuracy here, only the structure.
    capture = Image.new("RGB", (400, 640), (10, 10, 10))
    out = ii.identify_all(
        capture,
        equipment_offsets=[(0, 0, 32, 32)] * 8,
        border_offsets   =[(0, 0, 4, 32)] * 8,
        bg_offsets       =[(8, 8, 16, 16)] * 8,
        pet_offsets      =[(0, 0, 32, 32)] * 3,
        mount_offset     =(0, 0, 32, 32),
        skill_offsets    =[(0, 0, 32, 32)] * 3,
        slot_order=["Helmet", "Body", "Gloves", "Necklace",
                    "Ring", "Weapon", "Shoe", "Belt"],
    )
    assert set(out) == {"items", "pets", "mount", "skills"}
    assert len(out["items"]) == 8
    assert len(out["pets"]) == 3
    assert out["mount"] is not None
    assert len(out["skills"]) == 3
    for it in out["items"]:
        assert {"slot", "age", "idx", "rarity"} <= set(it)
