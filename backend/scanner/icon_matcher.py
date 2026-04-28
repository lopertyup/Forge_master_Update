"""
============================================================
  FORGE MASTER â Icon identifier

  Maps the visual side of an OCR capture to the discrete game
  identifiers the calculators expect.

  Public API
  ----------
      identify_item(crop, slot, age)  -> dict | None
            keys: {"age", "idx", "name", "rarity_color"}
      identify_pet(crop)              -> dict | None
            keys: {"rarity", "id", "name"}
      identify_mount(crop)            -> dict | None
            keys: {"rarity", "id", "name"}
      identify_skill(crop)            -> dict | None
            keys: {"name", "rarity"}

      identify_rarity_from_color(border_crop) -> rarity name
      identify_age_from_color(bg_crop)        -> age int

      identify_all(capture, *offsets, slot_order, ...) -> dict
            convenience helper that runs the per-slot pipeline in
            one call.

  Identification source
  ---------------------
  All references live under ``data/icons/``:
      equipment/{AgeFolder}/{SlotFolder}/<SpriteName>.png
      pets/<SpriteName>.png
      mount/<SpriteName>.png
      skills/<SpriteName>.png

  Mapping <SpriteName> â game identifier comes from
  AutoItemMapping / AutoPetMapping / AutoMountMapping /
  AutoSkillMapping (loaded via enemy_libraries.load_libs).

  Matching uses a Sum-of-Absolute-Differences (SAD) on a 32x32
  grayscale resize â fast, no extra dependency. The wiki-grid
  scanner (icon_recognition.py) uses a heavier hybrid (NCC +
  edges + OCR text similarity + auto-crop) for higher accuracy
  when calibrating new patches.
============================================================
"""

from __future__ import annotations

import colorsys
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from PIL import Image
import numpy as np

from ..data.libraries import (
    DATA_DIR,
    ICONS_DIR,
    AGE_INT_TO_FOLDER,
    SLOT_TO_FOLDER,
    load_libs,
)

log = logging.getLogger(__name__)


# ============================================================
#  Slot type ids (mirrors AutoItemMapping.Type)
# ============================================================

SLOT_TO_TYPE_ID: Dict[str, int] = {
    "Helmet":   0,
    "Body":     1,
    "Gloves":   2,
    "Necklace": 3,
    "Ring":     4,
    "Weapon":   5,
    "Shoe":     6,
    "Belt":     7,
}


# ============================================================
#  Template matching (32x32 SAD)
# ============================================================

_MATCH_SIZE = (32, 32)


def _to_match_array(img: Image.Image) -> np.ndarray:
    """Resize, grayscale, normalise to float32. Used on both sides of SAD."""
    return np.asarray(
        img.convert("L").resize(_MATCH_SIZE),
        dtype=np.float32,
    )


def template_match_score(crop: Image.Image, reference: Image.Image) -> float:
    """SAD on 32x32 grayscale. Returns ``-SAD`` so callers use ``max()``."""
    a = _to_match_array(crop)
    b = _to_match_array(reference)
    return -float(np.sum(np.abs(a - b)))


def _best_match(
    crop: Image.Image,
    candidates: Iterable[Tuple[Image.Image, dict]],
) -> Optional[Tuple[float, dict]]:
    """Return (score, payload) of the best match, or None if no candidate."""
    best_score = float("-inf")
    best_payload: Optional[dict] = None
    for ref, payload in candidates:
        s = template_match_score(crop, ref)
        if s > best_score:
            best_score = s
            best_payload = payload
    if best_payload is None:
        return None
    return best_score, best_payload


def _open_rgba(path: Path) -> Optional[Image.Image]:
    try:
        return Image.open(path).convert("RGBA")
    except Exception:
        log.exception("cannot open %s", path)
        return None


# ============================================================
#  Per-domain reference loading
# ============================================================

# Cached PIL images per (folder) so we don\'t re-open files on every match.
_cache: Dict[str, List[Tuple[Image.Image, dict]]] = {}


def _load_pet_refs() -> List[Tuple[Image.Image, dict]]:
    if "pets" in _cache:
        return _cache["pets"]
    refs: List[Tuple[Image.Image, dict]] = []
    auto = load_libs().get("auto_pet_mapping", {})
    # Build sprite_name -> (rarity, id, name) lookup
    by_sprite = {v["SpriteName"]: v for v in auto.values()}
    folder = ICONS_DIR / "pets"
    for png in sorted(folder.glob("*.png")):
        meta = by_sprite.get(png.stem)
        if meta is None:
            log.warning("identifier: pet %s.png has no AutoPetMapping entry",
                         png.stem)
            continue
        img = _open_rgba(png)
        if img is None:
            continue
        refs.append((img, {"rarity": meta["Rarity"], "id": meta["Id"],
                            "name": meta["PetName"]}))
    _cache["pets"] = refs
    return refs


def _load_mount_refs() -> List[Tuple[Image.Image, dict]]:
    if "mounts" in _cache:
        return _cache["mounts"]
    refs: List[Tuple[Image.Image, dict]] = []
    auto = load_libs().get("auto_mount_mapping", {})
    by_sprite = {v["SpriteName"]: v for v in auto.values()}
    folder = ICONS_DIR / "mount"
    for png in sorted(folder.glob("*.png")):
        meta = by_sprite.get(png.stem)
        if meta is None:
            log.warning("identifier: mount %s.png has no AutoMountMapping entry",
                         png.stem)
            continue
        img = _open_rgba(png)
        if img is None:
            continue
        refs.append((img, {"rarity": meta["Rarity"], "id": meta["Id"],
                            "name": meta["MountName"]}))
    _cache["mounts"] = refs
    return refs


def _load_skill_refs() -> List[Tuple[Image.Image, dict]]:
    if "skills" in _cache:
        return _cache["skills"]
    refs: List[Tuple[Image.Image, dict]] = []
    auto = load_libs().get("auto_skill_mapping", {})
    by_sprite = {v["SpriteName"]: v for v in auto.values()}
    folder = ICONS_DIR / "skills"
    for png in sorted(folder.glob("*.png")):
        meta = by_sprite.get(png.stem)
        if meta is None:
            log.warning("identifier: skill %s.png has no AutoSkillMapping entry",
                         png.stem)
            continue
        img = _open_rgba(png)
        if img is None:
            continue
        refs.append((img, {"name": meta["Type"], "rarity": meta["Rarity"]}))
    _cache["skills"] = refs
    return refs


def _load_item_refs(age: int, slot: str) -> List[Tuple[Image.Image, dict]]:
    cache_key = f"item_{age}_{slot}"
    if cache_key in _cache:
        return _cache[cache_key]
    refs: List[Tuple[Image.Image, dict]] = []
    age_folder = AGE_INT_TO_FOLDER.get(age)
    slot_folder = SLOT_TO_FOLDER.get(slot)
    if age_folder is None or slot_folder is None:
        log.warning("identifier: unknown age=%r slot=%r", age, slot)
        _cache[cache_key] = refs
        return refs

    folder = ICONS_DIR / "equipment" / age_folder / slot_folder
    if not folder.is_dir():
        log.warning("identifier: missing folder %s", folder)
        _cache[cache_key] = refs
        return refs

    auto = load_libs().get("auto_item_mapping", {})
    type_id = SLOT_TO_TYPE_ID.get(slot)
    by_sprite = {
        v["SpriteName"]: v for v in auto.values()
        if v.get("Age") == age and v.get("Type") == type_id
    }
    for png in sorted(folder.glob("*.png")):
        meta = by_sprite.get(png.stem)
        if meta is None:
            log.debug("identifier: item %s/%s/%s.png has no AutoItemMapping entry",
                       age_folder, slot_folder, png.stem)
            continue
        img = _open_rgba(png)
        if img is None:
            continue
        refs.append((img, {"age": age, "idx": meta["Idx"],
                            "name": meta["ItemName"]}))
    _cache[cache_key] = refs
    return refs


def reset_caches() -> None:
    """Forget cached references (e.g. after icon_recognition renames PNGs)."""
    _cache.clear()


# ============================================================
#  Public identifiers
# ============================================================

def identify_pet(crop: Image.Image) -> Optional[dict]:
    """Best-match a pet icon â ``{"rarity", "id", "name"}``."""
    if crop is None:
        return None
    refs = _load_pet_refs()
    result = _best_match(crop, refs)
    return result[1] if result else None


def identify_mount(crop: Image.Image) -> Optional[dict]:
    """Best-match a mount icon â ``{"rarity", "id", "name"}``."""
    if crop is None:
        return None
    refs = _load_mount_refs()
    result = _best_match(crop, refs)
    return result[1] if result else None


def identify_skill(crop: Image.Image) -> Optional[dict]:
    """Best-match a skill icon â ``{"name", "rarity"}``."""
    if crop is None:
        return None
    refs = _load_skill_refs()
    result = _best_match(crop, refs)
    return result[1] if result else None


def identify_item(crop: Image.Image, slot: str, age: int) -> Optional[dict]:
    """Best-match an equipment icon â ``{"age", "idx", "name"}``.

    Returns ``None`` when no labelled reference exists for (age, slot).
    """
    if crop is None:
        return None
    refs = _load_item_refs(age, slot)
    if not refs:
        return None
    result = _best_match(crop, refs)
    return result[1] if result else None


# ============================================================
#  Colour-based heuristics (rarity / age)
# ============================================================
#
# Calibrated on the default opponent-panel screenshots. Tweak in
# place when the game re-skins; numbers in HSV space, all 0..1.

# Border colour â rarity.
RARITY_COLORS_HSV: Dict[str, Tuple[float, float, float]] = {
    "Common":    (0.00, 0.00, 0.55),  # gris
    "Rare":      (0.61, 0.80, 0.90),  # bleu
    "Epic":      (0.78, 0.70, 0.85),  # violet
    "Legendary": (0.11, 0.90, 1.00),  # or
    "Ultimate":  (0.00, 0.85, 0.90),  # rouge
    "Mythic":    (0.83, 0.90, 0.95),  # rose / magenta
}

# Background colour â Age index.
AGE_COLORS_HSV: Dict[int, Tuple[float, float, float]] = {
    0: (0.07, 0.50, 0.45),   # Primitive    â brun
    1: (0.00, 0.00, 0.40),   # Medieval     â gris foncé
    2: (0.55, 0.40, 0.60),   # EarlyModern  â bleu-gris
    3: (0.58, 0.30, 0.70),   # Modern       â bleu clair
    4: (0.70, 0.40, 0.50),   # Space        â violet
    5: (0.72, 0.55, 0.55),   # Interstellar â indigo
    6: (0.78, 0.55, 0.60),   # Multiverse   â magenta
    7: (0.50, 0.65, 0.60),   # Quantum      â turquoise
    8: (0.95, 0.60, 0.45),   # Underworld   â rouge sombre
    9: (0.13, 0.65, 0.90),   # Divine       â or
}


def _hsv_distance(h1: float, s1: float, v1: float,
                   h2: float, s2: float, v2: float) -> float:
    """Squared HSV distance with circular hue."""
    dh = min(abs(h1 - h2), 1.0 - abs(h1 - h2))
    return (dh * 2.0) ** 2 + (s1 - s2) ** 2 + (v1 - v2) ** 2


def _dominant_color_hsv(img: Image.Image) -> Tuple[float, float, float]:
    """Coarse mean-RGB downscale â HSV.

    Pixels with alpha < 64 are ignored so transparent corners don\'t drag
    the mean toward black.
    """
    small = img.convert("RGBA").resize((8, 8))
    arr = np.asarray(small, dtype=np.float32)
    rgb = arr[..., :3] / 255.0
    a = arr[..., 3]
    mask = a >= 64
    if not mask.any():
        return (0.0, 0.0, 0.0)
    avg = rgb[mask].mean(axis=0)
    return colorsys.rgb_to_hsv(float(avg[0]), float(avg[1]), float(avg[2]))


def identify_rarity_from_color(border_crop: Image.Image) -> str:
    if border_crop is None:
        return "Common"
    h, s, v = _dominant_color_hsv(border_crop)
    return min(
        RARITY_COLORS_HSV,
        key=lambda r: _hsv_distance(h, s, v, *RARITY_COLORS_HSV[r]),
    )


def identify_age_from_color(bg_crop: Image.Image) -> int:
    if bg_crop is None:
        return 0
    h, s, v = _dominant_color_hsv(bg_crop)
    return min(
        AGE_COLORS_HSV,
        key=lambda a: _hsv_distance(h, s, v, *AGE_COLORS_HSV[a]),
    )


# ============================================================
#  Convenience: bulk identify from a master capture + offsets
# ============================================================

def identify_all(
    capture: Image.Image,
    *,
    equipment_offsets: List[Tuple[int, int, int, int]],
    border_offsets:    List[Tuple[int, int, int, int]],
    bg_offsets:        List[Tuple[int, int, int, int]],
    pet_offsets:       List[Tuple[int, int, int, int]],
    mount_offset:      Optional[Tuple[int, int, int, int]],
    skill_offsets:     List[Tuple[int, int, int, int]],
    slot_order:        List[str],
) -> Dict[str, Any]:
    """One-shot helper used by the OCR pipelines.

    Returns the dict consumed by enemy_pipeline / player_equipment_scanner :

        {
          "items":  [{"slot", "age", "idx", "name", "rarity"}, ...],
          "pets":   [{"id", "rarity", "name"}, ...],
          "mount":  {"id", "rarity", "name"} | None,
          "skills": [{"name", "rarity"}, ...],
        }

    Any missing identification is silently dropped â the caller will
    see a shorter list and the calculator will treat the slot as empty.
    """
    items: List[Dict[str, Any]] = []
    for i, slot in enumerate(slot_order):
        if i >= len(equipment_offsets):
            break
        icon = capture.crop(equipment_offsets[i])
        rarity = (identify_rarity_from_color(capture.crop(border_offsets[i]))
                   if i < len(border_offsets) else "Common")
        age = (identify_age_from_color(capture.crop(bg_offsets[i]))
                if i < len(bg_offsets) else 0)
        match = identify_item(icon, slot, age)
        items.append({
            "slot":   slot,
            "age":    match["age"] if match else age,
            "idx":    match["idx"] if match else 0,
            "name":   match["name"] if match else None,
            "rarity": rarity,
        })

    pets: List[Dict[str, Any]] = []
    for ofs in pet_offsets:
        match = identify_pet(capture.crop(ofs))
        if match:
            pets.append(match)

    mount = None
    if mount_offset is not None:
        mount = identify_mount(capture.crop(mount_offset))

    skills: List[Dict[str, Any]] = []
    for ofs in skill_offsets:
        match = identify_skill(capture.crop(ofs))
        if match:
            skills.append(match)

    return {
        "items":  items,
        "pets":   pets,
        "mount":  mount,
        "skills": skills,
    }
