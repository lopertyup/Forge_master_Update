"""
============================================================
  FORGE MASTER — Enemy icon identifier (Phase 2)

  Maps the visual side of an OCR capture to the discrete game
  identifiers the calculator expects. Four kinds of work:

    identify_pet(crop)    -> {"id", "rarity"}   from Pets.png
    identify_mount(crop)  -> {"id", "rarity"}   from MountIcons.png
    identify_skill(crop)  -> {"id", "rarity"}   from SkillIcons.png
    identify_item(crop, slot, age)
                          -> {"age", "idx"}     from data/items/*.png
                                                 (filled in by label tool)

  Plus three helpers for visible properties read off a small
  patch of the icon's chrome:

    identify_rarity_from_color(border_crop) -> rarity name
    identify_age_from_color(bg_crop)        -> age int
    extract_sprite(sheet, idx, kind)        -> PIL.Image

  Matching strategy (deliberately simple, fast, dependency-free
  beyond Pillow + NumPy):

    * SAD on a 32×32 grayscale resize. Lower SAD = better match,
      but the public score returned is ``-SAD`` so callers can use
      ``max(...)`` consistently.
    * For pets/mounts/skills, the reference set is small (≤ 25)
      so we just scan all sprites and pick the best score.
    * For items, the reference set lives under ``data/items/`` and
      is filtered by (age, slot) before scanning. When that
      filtered list is empty (label tool not run yet for this
      age/slot), the function returns ``None`` and the caller
      should fall back to ``Idx=0`` with a logged warning.

  HSV tables for rarity / age detection are calibrated on the
  defaults observed in the reference UI screenshots; they live at
  the bottom of this file and can be tweaked in place if the game
  re-skins its frames.
============================================================
"""

from __future__ import annotations

import colorsys
import json
import logging
import threading
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from PIL import Image
import numpy as np

from .enemy_libraries import (
    DATA_DIR,
    SPRITES_DIR,
    age_spritesheet_path,
    mounts_atlas_path,
    pets_atlas_path,
    skills_atlas_path,
)

log = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════
#  Mapping caches — loaded once, thread-safe
# ════════════════════════════════════════════════════════════

_lock = threading.Lock()
_manual_mapping: Optional[dict] = None
_auto_mapping:   Optional[dict] = None
_item_labels:    Optional[dict] = None
_sprite_atlases: Dict[str, Image.Image] = {}


def _load_manual_mapping() -> dict:
    global _manual_mapping
    if _manual_mapping is None:
        with _lock:
            if _manual_mapping is None:
                path = DATA_DIR / "ManualSpriteMapping.json"
                _manual_mapping = json.loads(path.read_text())
    return _manual_mapping


def _load_auto_mapping() -> dict:
    global _auto_mapping
    if _auto_mapping is None:
        with _lock:
            if _auto_mapping is None:
                path = DATA_DIR / "AutoItemMapping.json"
                _auto_mapping = json.loads(path.read_text())
    return _auto_mapping


def _load_item_labels() -> dict:
    """Optional — written by tools/label_item_sprites.py.

    Schema:
        {
          "labels": {
            "<SpriteName>": {"Age": 0, "Type": 0, "Idx": 0,
                             "filename": "IconPrimitiveHeadgearSkull.png"},
            ...
          }
        }
    """
    global _item_labels
    if _item_labels is None:
        with _lock:
            if _item_labels is None:
                path = DATA_DIR / "items" / "labels.json"
                if path.is_file():
                    _item_labels = json.loads(path.read_text())
                else:
                    _item_labels = {"labels": {}}
    return _item_labels


def reset_caches() -> None:
    """Forget loaded mappings and atlases. Used by tests."""
    global _manual_mapping, _auto_mapping, _item_labels
    with _lock:
        _manual_mapping = None
        _auto_mapping = None
        _item_labels = None
        _sprite_atlases.clear()


# ════════════════════════════════════════════════════════════
#  Sprite extraction
# ════════════════════════════════════════════════════════════


def _atlas(kind: str) -> Image.Image:
    """Return the cached spritesheet image for pets / mounts / skills."""
    if kind in _sprite_atlases:
        return _sprite_atlases[kind]
    paths = {
        "pets":   pets_atlas_path(),
        "mounts": mounts_atlas_path(),
        "skills": skills_atlas_path(),
    }
    if kind not in paths:
        raise ValueError(f"Unknown atlas kind: {kind!r}")
    with _lock:
        if kind not in _sprite_atlases:
            _sprite_atlases[kind] = Image.open(paths[kind]).convert("RGBA")
    return _sprite_atlases[kind]


def extract_sprite(sheet: Image.Image, sprite_index: int, kind: str) -> Image.Image:
    """Cut out one sprite from a uniform-grid atlas."""
    cfg  = _load_manual_mapping()[kind]
    cols = int(cfg["grid"]["columns"])
    sw   = int(cfg["sprite_size"]["width"])
    sh   = int(cfg["sprite_size"]["height"])
    row, col = divmod(int(sprite_index), cols)
    return sheet.crop((col * sw, row * sh, (col + 1) * sw, (row + 1) * sh))


# ════════════════════════════════════════════════════════════
#  Template matching
# ════════════════════════════════════════════════════════════


_MATCH_SIZE = (32, 32)


def _to_match_array(img: Image.Image) -> np.ndarray:
    """Resize, grayscale, normalise to float32. Used on both sides of SAD."""
    return np.asarray(
        img.convert("L").resize(_MATCH_SIZE),
        dtype=np.float32,
    )


def template_match_score(crop: Image.Image, reference: Image.Image) -> float:
    """SAD on 32×32 grayscale. Returns ``-SAD`` so callers use ``max``."""
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


# ════════════════════════════════════════════════════════════
#  Pet / Mount / Skill identification
# ════════════════════════════════════════════════════════════


def _identify_from_atlas(crop: Image.Image, kind: str,
                         payload_keys: Tuple[str, ...]) -> Optional[dict]:
    if crop is None:
        return None
    sheet = _atlas(kind)
    cfg   = _load_manual_mapping()[kind]
    candidates: List[Tuple[Image.Image, dict]] = []
    for idx_str, data in cfg["mapping"].items():
        ref = extract_sprite(sheet, int(idx_str), kind)
        payload = {k: data[k] for k in payload_keys if k in data}
        candidates.append((ref, payload))
    result = _best_match(crop, candidates)
    if result is None:
        return None
    return result[1]


def identify_pet(icon_crop: Image.Image) -> Optional[dict]:
    """Best-match a pet icon → ``{"id": int, "rarity": str}``."""
    return _identify_from_atlas(icon_crop, "pets", ("id", "rarity"))


def identify_mount(icon_crop: Image.Image) -> Optional[dict]:
    """Best-match a mount icon → ``{"id": int, "rarity": str}``."""
    return _identify_from_atlas(icon_crop, "mounts", ("id", "rarity"))


def identify_skill(icon_crop: Image.Image) -> Optional[dict]:
    """Best-match a skill icon → ``{"id": str, "rarity": str|None}``.

    The skill mapping in ManualSpriteMapping uses ``name`` as the
    skill-library key; rarity is encoded per-sprite in some entries.
    """
    sheet = _atlas("skills")
    cfg   = _load_manual_mapping()["skills"]
    candidates: List[Tuple[Image.Image, dict]] = []
    for idx_str, data in cfg["mapping"].items():
        ref = extract_sprite(sheet, int(idx_str), "skills")
        payload = {"id": data.get("name", "")}
        if "rarity" in data:
            payload["rarity"] = data["rarity"]
        candidates.append((ref, payload))
    if icon_crop is None:
        return None
    result = _best_match(icon_crop, candidates)
    return result[1] if result else None


# ════════════════════════════════════════════════════════════
#  Item identification
# ════════════════════════════════════════════════════════════

# Slot-name (UI) → Type id (ItemBalancingLibrary)
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


# Items are organised under icons_checker/<AgeName>/<SlotDir>/<SpriteName>.png
# (project root, runtime asset). The slot directory uses friendly names
# (Headgear/Armor/Glove/Neck/Ring/Weapon/Foot/Belt) that differ from the
# JSON TypeName -- the alias map below converts.
ITEMS_ROOT = Path(__file__).resolve().parent.parent / "icons_checker"

# AutoItemMapping AgeName values are PascalCase ("Earlymodern" with no
# hyphen) but the on-disk folder layout uses "Early-Modern" with a
# hyphen. We key everything on the integer Age index so both can stay
# decoupled.
_AGE_INT_TO_FOLDER: Dict[int, str] = {
    0: "Primitive",
    1: "Medieval",
    2: "Early-Modern",
    3: "Modern",
    4: "Space",
    5: "Interstellar",
    6: "Multiverse",
    7: "Quantum",
    8: "Underworld",
    9: "Divine",
}

# Slot UI name → user-folder slot directory. The TypeName in AutoItemMapping
# uses Helmet/Armour/Gloves/Necklace/Ring/Weapon/Shoes/Belt; the user-organised
# folders use Headgear/Armor/Glove/Neck/Ring/Weapon/Foot/Belt.
_SLOT_TO_FOLDER: Dict[str, str] = {
    "Helmet":   "Headgear",
    "Body":     "Armor",
    "Gloves":   "Glove",
    "Necklace": "Neck",
    "Ring":     "Ring",
    "Weapon":   "Weapon",
    "Shoe":     "Foot",
    "Belt":     "Belt",
}


def _items_dir(age: Optional[int] = None, slot: Optional[str] = None) -> Path:
    """Path to the item-icons folder. Drill all the way down when both
    ``age`` and ``slot`` are given."""
    p = ITEMS_ROOT
    if age is not None:
        folder = _AGE_INT_TO_FOLDER.get(age)
        if folder:
            p = p / folder
    if slot is not None:
        folder = _SLOT_TO_FOLDER.get(slot)
        if folder:
            p = p / folder
    return p


def identify_item(icon_crop: Image.Image, slot: str, age: int) -> Optional[dict]:
    """Best-match an equipment icon against the labeled item references
    under ``helper/icons_organized/<AgeName>/<SlotDir>/<SpriteName>.png``.

    Returns ``{"age": int, "idx": int}`` or ``None`` when no labeled
    reference exists for ``(age, slot)``.
    """
    if icon_crop is None:
        return None
    type_id = SLOT_TO_TYPE_ID.get(slot)
    if type_id is None:
        log.debug("identify_item: unknown slot %r", slot)
        return None

    auto = _load_auto_mapping()
    folder = _items_dir(age, slot)
    if not folder.is_dir():
        log.warning(
            "identify_item: missing folder %s — fill helper/icons_organized "
            "for age=%d slot=%s", folder, age, slot,
        )
        return None

    # Map SpriteName → entry, restricted to (age, type_id).
    by_sprite = {
        e["SpriteName"]: e for e in auto.values()
        if e.get("Age") == age and e.get("Type") == type_id
        and e.get("SpriteName")
    }

    candidates: List[Tuple[Image.Image, dict]] = []
    for png in folder.glob("*.png"):
        entry = by_sprite.get(png.stem)
        if entry is None:
            log.debug("identify_item: %s has no AutoItemMapping entry", png.name)
            continue
        try:
            ref = Image.open(png).convert("RGBA")
        except Exception:
            log.debug("identify_item: cannot open %s", png, exc_info=True)
            continue
        candidates.append((ref, {"age": age, "idx": int(entry["Idx"])}))

    if not candidates:
        log.warning(
            "identify_item: no usable references in %s for slot=%s age=%d",
            folder, slot, age,
        )
        return None

    result = _best_match(icon_crop, candidates)
    return result[1] if result else None


# ════════════════════════════════════════════════════════════
#  Colour-based heuristics (rarity / age)
# ════════════════════════════════════════════════════════════
#
# Calibrated on the default opponent-panel screenshots. Tweak in
# place when the game re-skins; numbers in HSV space, all 0..1.

# Border colour → rarity.
RARITY_COLORS_HSV: Dict[str, Tuple[float, float, float]] = {
    "Common":    (0.00, 0.00, 0.55),  # gris
    "Rare":      (0.61, 0.80, 0.90),  # bleu
    "Epic":      (0.78, 0.70, 0.85),  # violet
    "Legendary": (0.11, 0.90, 1.00),  # or
    "Ultimate":  (0.00, 0.85, 0.90),  # rouge
    "Mythic":    (0.83, 0.90, 0.95),  # rose / magenta
}

# Background colour → Age index.
AGE_COLORS_HSV: Dict[int, Tuple[float, float, float]] = {
    0: (0.07, 0.50, 0.45),   # Primitive    — brun
    1: (0.00, 0.00, 0.40),   # Medieval     — gris foncé
    2: (0.55, 0.40, 0.60),   # EarlyModern  — bleu-gris
    3: (0.58, 0.30, 0.70),   # Modern       — bleu clair
    4: (0.70, 0.40, 0.50),   # Space        — violet
    5: (0.72, 0.55, 0.55),   # Interstellar — indigo
    6: (0.78, 0.55, 0.60),   # Multiverse   — magenta
    7: (0.50, 0.65, 0.60),   # Quantum      — turquoise
    8: (0.95, 0.60, 0.45),   # Underworld   — rouge sombre
    9: (0.13, 0.65, 0.90),   # Divine       — or
}


def _hsv_distance(h1: float, s1: float, v1: float,
                  h2: float, s2: float, v2: float) -> float:
    """Squared HSV distance with circular hue."""
    dh = min(abs(h1 - h2), 1.0 - abs(h1 - h2))
    return (dh * 2.0) ** 2 + (s1 - s2) ** 2 + (v1 - v2) ** 2


def _dominant_color_hsv(img: Image.Image) -> Tuple[float, float, float]:
    """Coarse mean-RGB downscale → HSV.

    8×8 keeps the cost negligible while filtering out the JPEG-style
    noise the game's UI sometimes carries. Pixels with alpha < 64
    are ignored so transparent corners don't drag the mean toward
    black.
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


# ════════════════════════════════════════════════════════════
#  Convenience: bulk identify from a master capture + offsets
# ════════════════════════════════════════════════════════════


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
    """One-shot helper for the OCR pipeline.

    Returns a dict with the same shape ``capture_and_identify_opponent``
    consumes:

        {
          "items":  [{"slot", "age", "idx", "rarity"}, ...],
          "pets":   [{"id", "rarity"}, ...],
          "mount":  {"id", "rarity"} | None,
          "skills": [{"id", "rarity"}, ...],
        }

    Any missing identification is silently dropped — the caller will
    see a shorter list and the calculator will treat the slot as empty.
    """
    items: List[Dict[str, Any]] = []
    for i, slot in enumerate(slot_order):
        if i >= len(equipment_offsets):
            break
        icon = capture.crop(equipment_offsets[i])
        rarity = identify_rarity_from_color(capture.crop(border_offsets[i])) \
            if i < len(border_offsets) else "Common"
        age = identify_age_from_color(capture.crop(bg_offsets[i])) \
            if i < len(bg_offsets) else 0
        match = identify_item(icon, slot, age)
        items.append({
            "slot":   slot,
            "age":    match["age"] if match else age,
            "idx":    match["idx"] if match else 0,
            "rarity": rarity,
        })

    pets = []
    for ofs in pet_offsets:
        match = identify_pet(capture.crop(ofs))
        if match:
            pets.append(match)

    mount = None
    if mount_offset is not None:
        mount = identify_mount(capture.crop(mount_offset))

    skills = []
    for ofs in skill_offsets:
        match = identify_skill(capture.crop(ofs))
        if match:
            skills.append(match)

    return {
        "items":  items,
        "pets":   pets,
        "mount":  mount,
        "skills": skills,}
