"""
============================================================
  FORGE MASTER â Wiki icon recognition (ORB-based)

  Reads a screenshot of the in-game item-selector popup
  (a 4-column Ã 2-row grid of icons with a name beneath
  each) and matches every cell against
  data/icons/equipment/{Age}/{Slot}/*.png using ORB feature
  matching (OpenCV).

  All layout values are PERCENTAGES near the top of the file
  with an ASCII diagram. Tweak them and run with --show-bboxes
  to visualise the crops on your capture.

  Public API:
      scan_grid(capture, age, slot, threshold) -> List[CellMatch]
      apply_results(matches, age, slot, dry_run=False) -> ApplyReport

  Standalone CLI:
      python -m backend.scanner.icon_recognition <image.png> <age_int> <slot>
                                          [--threshold 0.10]
                                          [--show-bboxes]
                                          [--debug-dir <folder>]
                                          [--apply]

  Requires:
      pip install opencv-python   # ORB
      pip install rapidocr-onnxruntime   # OCR (optional but useful)
============================================================
"""

from __future__ import annotations

import json
import logging
import difflib
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw

# OpenCV is loaded lazily so the module still imports without it.
try:
    import cv2 as _cv2
    _CV2_AVAILABLE = True
except Exception:
    _cv2 = None
    _CV2_AVAILABLE = False

from .icon_matcher import SLOT_TO_TYPE_ID

log = logging.getLogger(__name__)


# ============================================================
#  Paths & names
# ============================================================
# Lives at backend/scanner/icon_recognition.py — three parents up
# is the project root.
DATA_DIR     = Path(__file__).resolve().parent.parent.parent / "data"
ICONS_DIR    = DATA_DIR / "icons" / "equipment"
ARCHIVE_DIR  = DATA_DIR / "_archive"
AUTO_MAPPING = DATA_DIR / "AutoItemMapping.json"

AGE_INT_TO_FOLDER: Dict[int, str] = {
    0: "Primitive", 1: "Medieval", 2: "Early-Modern", 3: "Modern",
    4: "Space",     5: "Interstellar", 6: "Multiverse", 7: "Quantum",
    8: "Underworld", 9: "Divine",
}
AGE_INT_TO_NAME: Dict[int, str] = {
    0: "Primitive", 1: "Medieval", 2: "Earlymodern", 3: "Modern",
    4: "Space",     5: "Interstellar", 6: "Multiverse", 7: "Quantum",
    8: "Underworld", 9: "Divine",
}
SLOT_TO_FOLDER: Dict[str, str] = {
    "Helmet": "Headgear", "Body": "Armor", "Gloves": "Glove",
    "Necklace": "Neck",   "Ring": "Ring",  "Weapon": "Weapon",
    "Shoe": "Foot",       "Belt": "Belt",
}


# ============================================================
#  WIKI GRID LAYOUT â EDIT THESE TO TUNE THE CROPS
# ============================================================
#
#  Every value below is a PERCENTAGE (0â100) of the capture\'s
#  size. Picture your capture as a rectangle 100% wide Ã 100% tall.
#
#  Visual map of the grid (defaults shown):
#
#       LEFT_MARGIN_PCT (2.5%)        RIGHT_MARGIN_PCT (1.5%)
#       v                                              v
#  +----+--------+-+--------+-+--------+-+--------+----+   <- TOP_MARGIN_PCT (18%)
#  |    | cell 0 | | cell 1 | | cell 2 | | cell 3 |    |      (header "AGE ITEMS")
#  |    +--------+ +--------+ +--------+ +--------+    |
#  +-------------- ROW_GAP_PCT (2%) -------------------+
#  |    | cell 4 | | cell 5 | | cell 6 | | cell 7 |    |
#  |    +--------+ +--------+ +--------+ +--------+    |
#  +---------------------------------------------------+   <- BOTTOM_MARGIN_PCT (1.5%)
#
#  Each cell is split into icon (top) + text (bottom):
#
#  +-----------------------------+
#  | <- ICON_LEFT_INSET_PCT (10%)|
#  |   +---------------------+   |   <- ICON_TOP_INSET_PCT (5%)
#  |   |                     |   |
#  |   |    icon image       |   |   <- ICON_HEIGHT_PCT (72%) of cell h
#  |   |                     |   |
#  |   +---------------------+   |
#  |        "Item name"          |   <- TEXT_HEIGHT_PCT (20%) of cell h
#  +-----------------------------+   (taken from the bottom of the cell)
#
#  Tip: run
#      python -m backend.scanner.icon_recognition <img> <age> <slot> --show-bboxes
#  to dump an overlay PNG with red icon boxes + green text boxes drawn
#  on top of your capture. Adjust the *_PCT values until the boxes line
#  up nicely.

COLS: int = 4
ROWS: int = 2
N_CELLS: int = COLS * ROWS

# Margins around the grid (% of capture).
TOP_MARGIN_PCT:    float = 20
BOTTOM_MARGIN_PCT: float = 10
LEFT_MARGIN_PCT:   float = 2.5
RIGHT_MARGIN_PCT:  float = 1.5
ROW_GAP_PCT:       float = 5.0

# Within each cell (% of cell size).
ICON_TOP_INSET_PCT:  float = 5.0
ICON_LEFT_INSET_PCT: float = 10.0
ICON_HEIGHT_PCT:     float = 72.0
TEXT_HEIGHT_PCT:     float = 20.0


def _grid_bounds() -> Tuple[float, float, float, float]:
    """(x0, y0, x1, y1) of the grid area in [0, 1] coords."""
    x0 = LEFT_MARGIN_PCT  / 100.0
    x1 = 1.0 - RIGHT_MARGIN_PCT  / 100.0
    y0 = TOP_MARGIN_PCT   / 100.0
    y1 = 1.0 - BOTTOM_MARGIN_PCT / 100.0
    return (x0, y0, x1, y1)


def _icon_ratio() -> Tuple[float, float, float, float]:
    """(x, y, w, h) of the icon area inside one cell, in [0,1]."""
    x = ICON_LEFT_INSET_PCT / 100.0
    y = ICON_TOP_INSET_PCT  / 100.0
    w = 1.0 - 2.0 * x
    h = ICON_HEIGHT_PCT / 100.0
    return (x, y, w, h)


def _text_ratio() -> Tuple[float, float, float, float]:
    """(x, y, w, h) of the text area inside one cell, in [0,1]."""
    h = TEXT_HEIGHT_PCT / 100.0
    y = 1.0 - h
    return (0.05, y, 0.90, h)


# ============================================================
#  Scoring & matcher tuning
# ============================================================

# Threshold default â minimum ratio of "good ORB matches" /
# max(crop_keypoints, ref_keypoints) to consider a match valid.
DEFAULT_THRESHOLD: float = 0.30

# Match preprocessing
_NEUTRAL_BG: Tuple[int, int, int] = (60, 60, 60)

# Cell occupancy (variance of grayscale luminance, 16x16 sample).
_FILLED_VARIANCE_THRESHOLD: float = 30.0


# ============================================================
#  Data classes
# ============================================================

@dataclass
class CellMatch:
    cell_idx: int
    row: int
    col: int
    icon_bbox: Tuple[int, int, int, int]
    text_bbox: Tuple[int, int, int, int]
    is_filled: bool
    ocr_name: str
    best_match: Optional[str]
    score: float
    candidates: List[Tuple[str, float]] = field(default_factory=list)


@dataclass
class ApplyReport:
    updated:     List[Dict] = field(default_factory=list)
    skipped:     List[Dict] = field(default_factory=list)
    backup_path: Optional[str] = None
    dry_run:     bool = False


# ============================================================
#  Geometry helpers
# ============================================================

def _cell_bboxes(W: int, H: int) -> List[Tuple[int, int, int, int]]:
    """Pixel bboxes for the COLSÃROWS cells, reading order."""
    gx0, gy0, gx1, gy1 = _grid_bounds()
    grid_w = (gx1 - gx0) * W
    grid_h = (gy1 - gy0) * H
    row_gap_px = (ROW_GAP_PCT / 100.0) * H
    total_row_gap = row_gap_px * (ROWS - 1)
    cell_h = (grid_h - total_row_gap) / ROWS
    cell_w = grid_w / COLS

    out = []
    for r in range(ROWS):
        for c in range(COLS):
            x0 = int(round(gx0 * W + c * cell_w))
            y0 = int(round(gy0 * H + r * (cell_h + row_gap_px)))
            x1 = int(round(x0 + cell_w))
            y1 = int(round(y0 + cell_h))
            out.append((x0, y0, x1, y1))
    return out


def _sub_bbox(cell, ratio):
    cx0, cy0, cx1, cy1 = cell
    cw, ch = cx1 - cx0, cy1 - cy0
    rx, ry, rw, rh = ratio
    x0 = cx0 + int(round(rx * cw))
    y0 = cy0 + int(round(ry * ch))
    x1 = x0 + int(round(rw * cw))
    y1 = y0 + int(round(rh * ch))
    return (x0, y0, x1, y1)


def visualize_layout(capture: Image.Image,
                     out_path: Path) -> Path:
    """Draw cell + icon + text bboxes on top of the capture.

    Returns the saved path. Use this to iteratively tune the
    *_PCT constants until the rectangles line up with your wiki
    capture.

    Colours:
      yellow  = cell outer rectangle
      red     = icon crop (what gets template-matched)
      green   = text crop (what gets OCR\'d)
    """
    W, H = capture.size
    overlay = capture.convert("RGB").copy()
    draw = ImageDraw.Draw(overlay)

    for idx, cbb in enumerate(_cell_bboxes(W, H)):
        # Cell outer
        draw.rectangle(cbb, outline=(255, 220, 0), width=2)
        # Icon
        ibb = _sub_bbox(cbb, _icon_ratio())
        draw.rectangle(ibb, outline=(255, 60, 60), width=2)
        # Text
        tbb = _sub_bbox(cbb, _text_ratio())
        draw.rectangle(tbb, outline=(60, 220, 60), width=2)
        # Cell index label (top-left of the cell)
        draw.text((cbb[0] + 4, cbb[1] + 4), str(idx),
                  fill=(255, 220, 0))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    overlay.save(out_path)
    return out_path


# ============================================================
#  Cell occupancy
# ============================================================

def _is_cell_filled(icon_crop: Image.Image) -> bool:
    arr = np.asarray(
        icon_crop.convert("L").resize((16, 16)),
        dtype=np.float32,
    )
    return float(arr.var()) > _FILLED_VARIANCE_THRESHOLD


# ============================================================
#  OCR (lazy)
# ============================================================

_FORBIDDEN_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _clean_ocr_name(raw: str) -> str:
    s = raw.strip().replace("\n", " ").replace("\r", " ")
    s = re.sub(r"\s+", " ", s)
    s = _FORBIDDEN_FILENAME_CHARS.sub("", s)
    return s


def _ocr_text(crop: Image.Image) -> str:
    try:
        from . import ocr  # type: ignore
        if not ocr.is_available():
            log.warning("icon_recognition: OCR backend unavailable; "
                        "names will be empty.")
            return ""
        text = ocr.ocr_image(crop) or ""
    except Exception:
        log.exception("icon_recognition: OCR pass failed")
        return ""
    return _clean_ocr_name(text)


# ============================================================
#  Multi-metric matcher
# ============================================================
#
#  Three complementary similarity signals are combined into a
#  single score:
#
#    1. NCC on grayscale       - "do the pixel patterns line up"
#                                Robust + fast. Works great on
#                                same-style icons.
#    2. NCC on Sobel edges     - "do the silhouettes line up"
#                                Insensitive to color/brightness.
#    3. Color histogram corr.  - "do the colors look similar"
#                                Catches Rock vs Bone-style cases
#                                where shapes differ subtly but
#                                colors strongly disagree.
#
#  Final score = weighted average mapped into [0, 1].
#  Ensemble outperforms any single metric and degrades gracefully
#  when one signal is unreliable.

_MATCH_SIZE: Tuple[int, int] = (128, 128)
# Score weights for the hybrid matcher. Visual signals + OCR-text
# similarity are blended into a single [0, 1] score. OCR text is the
# strongest signal when the in-game name still matches a reference
# filename; visual signals dominate when an item has been renamed.
_NCC_WEIGHT:    float = 0.30   # grayscale pattern
_EDGE_WEIGHT:   float = 0.25   # Sobel-edge silhouette
_COLOR_WEIGHT:  float = 0.10   # color histogram (catches Rock vs Bone
                                #                  when shapes are close)
_TEXT_WEIGHT:   float = 0.35   # OCR vs ref-filename string similarity


def _flatten_reference(ref: Image.Image) -> Image.Image:
    """Composite RGBA references onto neutral gray so transparent
    corners do not register as black during pixel comparison."""
    if ref.mode != "RGBA":
        return ref.convert("RGB")
    flat = Image.new("RGB", ref.size, _NEUTRAL_BG)
    flat.paste(ref, mask=ref.split()[3])
    return flat


# ----------------------------------------------------------------
#  Auto-crop: tightly recrop both wiki captures and references onto
#  just the sprite itself before comparison. Removes the "small
#  sprite floating in big background" mismatch that destroyed
#  signal in the previous matcher.
# ----------------------------------------------------------------

def _alpha_bbox(rgba: Image.Image) -> Optional[Tuple[int, int, int, int]]:
    """Tight bbox of non-transparent pixels of an RGBA image."""
    if rgba.mode != "RGBA":
        return None
    alpha = np.asarray(rgba.split()[3])
    rows = np.any(alpha > 30, axis=1)
    cols = np.any(alpha > 30, axis=0)
    if not rows.any() or not cols.any():
        return None
    rmin, rmax = np.where(rows)[0][[0, -1]]
    cmin, cmax = np.where(cols)[0][[0, -1]]
    return (int(cmin), int(rmin), int(cmax) + 1, int(rmax) + 1)


def _color_bbox(rgb: Image.Image,
                bg_distance_threshold: float = 25.0) -> Optional[Tuple[int, int, int, int]]:
    """Tight bbox of pixels whose color differs from the corner
    background (the tile color in wiki captures)."""
    arr = np.asarray(rgb.convert("RGB"))
    h, w = arr.shape[:2]
    if h < 4 or w < 4:
        return None
    # Sample 5x5 patches at each corner; their mean is the dominant
    # background color.
    corners = np.concatenate([
        arr[:5, :5].reshape(-1, 3),
        arr[-5:, -5:].reshape(-1, 3),
        arr[:5, -5:].reshape(-1, 3),
        arr[-5:, :5].reshape(-1, 3),
    ])
    bg = corners.mean(axis=0)
    dist = np.sqrt(((arr.astype(np.float32) - bg) ** 2).sum(axis=2))
    mask = dist > bg_distance_threshold
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)
    if not rows.any() or not cols.any():
        return None
    rmin, rmax = np.where(rows)[0][[0, -1]]
    cmin, cmax = np.where(cols)[0][[0, -1]]
    # Small margin so we don\'t cut anti-aliased edges.
    h_pad = max(1, int((rmax - rmin) * 0.04))
    w_pad = max(1, int((cmax - cmin) * 0.04))
    return (max(0, int(cmin) - w_pad),
            max(0, int(rmin) - h_pad),
            min(w,   int(cmax) + 1 + w_pad),
            min(h,   int(rmax) + 1 + h_pad))


def _autocrop_reference(ref_rgba: Image.Image) -> Image.Image:
    """Tightly crop a reference PNG to its alpha bbox, then composite
    onto neutral gray. Returns RGB."""
    bb = _alpha_bbox(ref_rgba)
    if bb is None:
        return _flatten_reference(ref_rgba)
    cropped = ref_rgba.crop(bb)
    flat = Image.new("RGB", cropped.size, _NEUTRAL_BG)
    flat.paste(cropped, mask=cropped.split()[3])
    return flat


def _autocrop_capture(crop_rgb: Image.Image) -> Image.Image:
    """Tightly crop a wiki capture to its sprite (the colored pixels
    that differ from the corner-tile background)."""
    bb = _color_bbox(crop_rgb)
    if bb is None:
        return crop_rgb.convert("RGB")
    return crop_rgb.crop(bb).convert("RGB")


def _to_gray_arr(img: Image.Image) -> "np.ndarray":
    return np.asarray(
        img.convert("L").resize(_MATCH_SIZE),
        dtype=np.uint8,
    )


def _to_rgb_arr(img: Image.Image) -> "np.ndarray":
    return np.asarray(
        img.convert("RGB").resize(_MATCH_SIZE),
        dtype=np.uint8,
    )


def _ncc_grayscale(a: "np.ndarray", b: "np.ndarray") -> float:
    """Pearson NCC of two same-shape grayscale arrays. [-1, 1]."""
    af = a.astype(np.float32) - a.mean()
    bf = b.astype(np.float32) - b.mean()
    denom = float(np.sqrt((af * af).sum() * (bf * bf).sum()))
    if denom < 1e-6:
        return 0.0
    return float((af * bf).sum() / denom)


def _ncc_edges(a: "np.ndarray", b: "np.ndarray") -> float:
    """NCC after Sobel edge extraction. Insensitive to color/light."""
    if not _CV2_AVAILABLE:
        return _ncc_grayscale(a, b)  # graceful fallback
    ax = _cv2.Sobel(a, _cv2.CV_32F, 1, 0, ksize=3)
    ay = _cv2.Sobel(a, _cv2.CV_32F, 0, 1, ksize=3)
    bx = _cv2.Sobel(b, _cv2.CV_32F, 1, 0, ksize=3)
    by = _cv2.Sobel(b, _cv2.CV_32F, 0, 1, ksize=3)
    a_mag = np.sqrt(ax * ax + ay * ay).astype(np.uint8)
    b_mag = np.sqrt(bx * bx + by * by).astype(np.uint8)
    return _ncc_grayscale(a_mag, b_mag)


def _color_hist_corr(a_rgb: "np.ndarray", b_rgb: "np.ndarray") -> float:
    """Bhattacharyya-distance based correlation of HS histograms.
    Returns a value in [0, 1] (1 = identical color distribution)."""
    if not _CV2_AVAILABLE:
        return 0.5  # neutral fallback
    a_hsv = _cv2.cvtColor(a_rgb, _cv2.COLOR_RGB2HSV)
    b_hsv = _cv2.cvtColor(b_rgb, _cv2.COLOR_RGB2HSV)
    bins = [30, 32]
    ranges = [0, 180, 0, 256]
    h_a = _cv2.calcHist([a_hsv], [0, 1], None, bins, ranges)
    h_b = _cv2.calcHist([b_hsv], [0, 1], None, bins, ranges)
    _cv2.normalize(h_a, h_a, alpha=0, beta=1, norm_type=_cv2.NORM_MINMAX)
    _cv2.normalize(h_b, h_b, alpha=0, beta=1, norm_type=_cv2.NORM_MINMAX)
    # Bhattacharyya: 0 = identical, 1 = completely different
    d = float(_cv2.compareHist(h_a, h_b, _cv2.HISTCMP_BHATTACHARYYA))
    return max(0.0, 1.0 - d)


_REF_PREFIX_RE = re.compile(r"^Icon[A-Z][a-z]+(?:[A-Z][a-z]*)*", re.UNICODE)


def _ref_canonical_name(stem: str) -> str:
    """Strip the 'Icon{Age}{Slot}' prefix from a reference filename
    stem, leaving just the item name. Examples:
        IconPrimitiveWeaponAxe       -> Axe
        IconQuantumWeaponBlackBow    -> BlackBow
        Axe                          -> Axe   (already-clean stem)
    Heuristic: drop the longest leading run of "Icon" + age/slot
    PascalCase tokens before the actual item name. We approximate by
    removing the literal "Icon" then assuming the next two PascalCase
    tokens are age + slot.
    """
    if stem.startswith("Icon"):
        rest = stem[4:]
        # Split on uppercase boundaries
        tokens = re.findall(r"[A-Z][a-z]*", rest)
        # First token = age (Primitive, Medieval, etc.)
        # Second token = slot (Weapon, Helmet, Headgear, etc.)
        # Remaining tokens = item name (CamelCase joined)
        if len(tokens) >= 3:
            return "".join(tokens[2:])
        if len(tokens) == 2:
            return tokens[1]   # unusual: age + name only
        return rest
    return stem


def _text_similarity(ocr_name: str, ref_stem: str) -> float:
    """Fuzzy similarity between the OCR'd in-game name and the
    reference filename's item-name portion. Returns [0, 1].
    Spaces and case are normalised so 'Black Sword' matches
    'BlackSword' and 'BLACKSWORD'."""
    if not ocr_name:
        return 0.0
    ref_name = _ref_canonical_name(ref_stem)
    a = re.sub(r"[\s_\-]+", "", ocr_name).lower()
    b = re.sub(r"[\s_\-]+", "", ref_name).lower()
    if not a or not b:
        return 0.0
    return float(difflib.SequenceMatcher(None, a, b).ratio())


def _ensemble_score(crop_gray, ref_gray, crop_rgb, ref_rgb,
                    ocr_name: str, ref_stem: str) -> float:
    """Weighted ensemble of visual NCCs + color histogram + OCR
    text similarity. Components are clamped to [0, 1] then summed
    with the *_WEIGHT constants. OCR text is the strongest signal
    when the in-game name still matches the reference filename."""
    ncc   = _ncc_grayscale(crop_gray, ref_gray)
    edges = _ncc_edges(crop_gray, ref_gray)
    color = _color_hist_corr(crop_rgb, ref_rgb)
    text  = _text_similarity(ocr_name, ref_stem)
    ncc_n   = max(0.0, ncc)
    edges_n = max(0.0, edges)
    score = (_NCC_WEIGHT   * ncc_n
             + _EDGE_WEIGHT  * edges_n
             + _COLOR_WEIGHT * color
             + _TEXT_WEIGHT  * text)
    return float(score)


def _references(age: int, slot: str):
    """Load every reference PNG for (age, slot) and pre-compute the
    grayscale + RGB arrays used by the ensemble matcher (cached)."""
    age_folder  = AGE_INT_TO_FOLDER.get(age)
    slot_folder = SLOT_TO_FOLDER.get(slot)
    if not age_folder or not slot_folder:
        log.warning("_references: unknown age=%r slot=%r", age, slot)
        return []
    folder = ICONS_DIR / age_folder / slot_folder
    if not folder.is_dir():
        log.warning("_references: missing folder %s", folder)
        return []
    cache = _references._cache  # type: ignore[attr-defined]
    key = (age, slot)
    if key in cache:
        return cache[key]
    refs = []
    for png in sorted(folder.glob("*.png")):
        try:
            img = Image.open(png).convert("RGBA")
        except Exception:
            log.exception("_references: cannot open %s", png)
            continue
        cropped = _autocrop_reference(img)
        refs.append((png.stem, _to_gray_arr(cropped), _to_rgb_arr(cropped)))
    cache[key] = refs
    return refs

_references._cache = {}  # type: ignore[attr-defined]


def reset_caches() -> None:
    _references._cache.clear()  # type: ignore[attr-defined]


def _match_cell(icon_crop: Image.Image, refs, ocr_name: str = "",
                top_n: int = 3):
    """Score crop against every reference. Auto-crops the icon to
    its sprite bbox so the wiki and reference compare on the same
    effective scale, and blends OCR text similarity into the score
    so a correct OCR'd name reinforces the visual match."""
    sprite = _autocrop_capture(icon_crop)
    crop_gray = _to_gray_arr(sprite)
    crop_rgb  = _to_rgb_arr(sprite)
    scored = [(stem,
               _ensemble_score(crop_gray, ref_gray, crop_rgb, ref_rgb,
                               ocr_name, stem))
              for stem, ref_gray, ref_rgb in refs]
    scored.sort(key=lambda t: t[1], reverse=True)
    return scored[:top_n]


def _greedy_assignment(scored_per_cell: List[List[Tuple[str, float]]]
                       ) -> Dict[int, Tuple[str, float]]:
    """Greedy global assignment: pick the highest-scoring (cell, ref)
    pair, claim it, remove the cell and ref from contention, repeat.
    Prevents two cells from being assigned the same reference, which
    is impossible in a wiki grid where every cell shows a different
    item.

    Returns {cell_idx: (best_ref_stem, score)}.
    """
    pairs = []  # (score, cell_idx, ref_stem, candidates)
    for cell_idx, scored in enumerate(scored_per_cell):
        for ref_stem, score in scored:
            pairs.append((score, cell_idx, ref_stem))
    pairs.sort(key=lambda p: -p[0])

    assigned: Dict[int, Tuple[str, float]] = {}
    used_refs = set()
    for score, cell_idx, ref_stem in pairs:
        if cell_idx in assigned or ref_stem in used_refs:
            continue
        assigned[cell_idx] = (ref_stem, score)
        used_refs.add(ref_stem)
    return assigned


# ============================================================
#  Public scan
# ============================================================

def scan_grid(capture: Image.Image, age: int, slot: str,
              threshold: float = DEFAULT_THRESHOLD,
              debug_dir: Optional[Path] = None) -> List[CellMatch]:
    if not _CV2_AVAILABLE:
        log.error(
            "scan_grid: OpenCV not installed â ORB matching disabled. "
            "Install with: pip install opencv-python")

    W, H = capture.size
    cells = _cell_bboxes(W, H)
    refs  = _references(age, slot)
    if not refs:
        log.warning("scan_grid: no references for age=%d slot=%s", age, slot)

    if debug_dir is not None:
        debug_dir.mkdir(parents=True, exist_ok=True)
        capture.save(debug_dir / "_capture_full.png")
        visualize_layout(capture, debug_dir / "_layout_overlay.png")

    # First pass: collect per-cell candidate lists. We pre-compute
    # ALL candidates (not just top-3) so the global assignment step
    # can break conflicts later by switching a cell to its 2nd or 3rd
    # choice.
    out: List[CellMatch] = []
    full_candidates: List[List[Tuple[str, float]]] = []
    for idx, cbb in enumerate(cells):
        row, col = divmod(idx, COLS)
        icon_bb = _sub_bbox(cbb, _icon_ratio())
        text_bb = _sub_bbox(cbb, _text_ratio())

        icon_crop = capture.crop(icon_bb)
        if debug_dir is not None:
            icon_crop.save(debug_dir / f"cell_{idx}_icon.png")
            capture.crop(text_bb).save(debug_dir / f"cell_{idx}_text.png")

        if not _is_cell_filled(icon_crop):
            out.append(CellMatch(
                cell_idx=idx, row=row, col=col,
                icon_bbox=icon_bb, text_bbox=text_bb,
                is_filled=False, ocr_name="", best_match=None,
                score=0.0, candidates=[],
            ))
            full_candidates.append([])
            continue

        text_crop  = capture.crop(text_bb)
        ocr_name   = _ocr_text(text_crop)
        # top_n=999 => keep all references ranked
        candidates = (_match_cell(icon_crop, refs, ocr_name=ocr_name,
                                   top_n=999)
                       if refs else [])
        out.append(CellMatch(
            cell_idx=idx, row=row, col=col,
            icon_bbox=icon_bb, text_bbox=text_bb,
            is_filled=True, ocr_name=ocr_name,
            best_match=None, score=0.0,   # filled below
            candidates=candidates[:3],     # display only top-3
        ))
        full_candidates.append(candidates)

    # Second pass: greedy global assignment. Two cells in a wiki grid
    # are ALWAYS different items, so we never let the same reference
    # win twice. If cell 0 and cell 1 both score "Bone" highest, the
    # one with the higher score keeps Bone and the other falls back
    # to its 2nd-best candidate.
    assigned = _greedy_assignment(full_candidates)
    for m in out:
        if not m.is_filled:
            continue
        pick = assigned.get(m.cell_idx)
        if pick is None:
            continue
        m.best_match, m.score = pick

    for m in out:
        if m.is_filled and m.score < threshold:
            log.warning(
                "icon_recognition: low confidence on cell %d (r%dc%d) "
                "score=%.3f < %.3f, ocr=%r best=%r candidates=%s",
                m.cell_idx, m.row, m.col, m.score, threshold,
                m.ocr_name, m.best_match,
                [(c[0], round(c[1], 3)) for c in m.candidates],
            )
    return out


# ============================================================
#  Apply
# ============================================================

def _backup_auto_mapping() -> Path:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    dst = ARCHIVE_DIR / f"AutoItemMapping_{ts}.json"
    shutil.copy(AUTO_MAPPING, dst)
    return dst


def _load_auto_mapping():
    return json.loads(AUTO_MAPPING.read_text(encoding="utf-8"))


def _save_auto_mapping(data):
    tmp = AUTO_MAPPING.with_suffix(".tmp.json")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    backup = ARCHIVE_DIR / "AutoItemMapping_replaced.json"
    if backup.exists():
        backup.rename(backup.with_suffix(f".{int(time.time())}.json"))
    AUTO_MAPPING.rename(backup)
    tmp.rename(AUTO_MAPPING)


def apply_results(matches, age, slot, *, dry_run=False,
                  threshold=DEFAULT_THRESHOLD,
                  selected_indices=None) -> ApplyReport:
    report = ApplyReport(dry_run=dry_run)
    report.backup_path = None
    if dry_run:
        log.info("apply_results: DRY RUN â no files will be touched")
    else:
        report.backup_path = str(_backup_auto_mapping())

    # Always load AutoItemMapping so dry-run can preview the mapping
    # changes too. Writes are still gated on dry_run below.
    auto = _load_auto_mapping()
    type_id     = SLOT_TO_TYPE_ID.get(slot)
    age_folder  = AGE_INT_TO_FOLDER.get(age)
    slot_folder = SLOT_TO_FOLDER.get(slot)
    if type_id is None or age_folder is None or slot_folder is None:
        raise ValueError(f"Unknown age={age!r} or slot={slot!r}")
    folder = ICONS_DIR / age_folder / slot_folder
    selected = set(selected_indices) if selected_indices is not None \
        else set(range(N_CELLS))

    for m in matches:
        decision = {
            "cell_idx": m.cell_idx, "row": m.row, "col": m.col,
            "ocr_name": m.ocr_name, "best_match": m.best_match,
            "score": round(m.score, 4),
        }
        if m.cell_idx not in selected:
            decision["reason"] = "skipped_by_user"; report.skipped.append(decision); continue
        if not m.is_filled:
            decision["reason"] = "empty_cell"; report.skipped.append(decision); continue
        if not m.best_match:
            decision["reason"] = "no_reference_match"; report.skipped.append(decision); continue
        if m.score < threshold:
            decision["reason"] = "below_threshold"; report.skipped.append(decision); continue
        if not m.ocr_name:
            decision["reason"] = "empty_ocr"; report.skipped.append(decision); continue

        old_stem = m.best_match
        new_stem = m.ocr_name
        old_path = folder / f"{old_stem}.png"
        new_path = folder / f"{new_stem}.png"

        target_key = None
        if auto is not None:
            for k, entry in auto.items():
                if (entry.get("SpriteName") == old_stem
                        and entry.get("Age") == age
                        and entry.get("Type") == type_id):
                    target_key = k
                    break

        decision["folder"]        = str(folder)
        decision["old_filename"]  = old_path.name
        decision["new_filename"]  = new_path.name
        decision["mapping_key"]   = target_key
        decision["old_item_name"] = (auto[target_key]["ItemName"]
                                     if auto and target_key else None)

        if dry_run:
            decision["reason"] = "dry_run"; report.updated.append(decision); continue

        if old_path.exists() and old_stem != new_stem:
            try:
                if new_path.exists():
                    decision["reason"] = "rename_conflict"; report.skipped.append(decision); continue
                old_path.rename(new_path)
                decision["renamed"] = True
            except Exception as e:
                log.exception("apply_results: rename failed")
                decision["reason"] = f"rename_failed:{e}"; report.skipped.append(decision); continue
        else:
            decision["renamed"] = False

        if auto is not None and target_key is not None:
            auto[target_key]["ItemName"]   = new_stem
            auto[target_key]["SpriteName"] = new_stem
            decision["mapping_updated"] = True
        else:
            decision["mapping_updated"] = False
            decision["reason"] = "mapping_entry_not_found"; report.skipped.append(decision); continue

        report.updated.append(decision)

    if not dry_run and auto is not None:
        _save_auto_mapping(auto)
        reset_caches()
    return report


# ============================================================
#  CLI
# ============================================================

def _cli(argv):
    import argparse
    p = argparse.ArgumentParser(prog="backend.scanner.icon_recognition")
    p.add_argument("image")
    p.add_argument("age", type=int, choices=range(10))
    p.add_argument("slot", choices=list(SLOT_TO_FOLDER.keys()))
    p.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    p.add_argument("--debug-dir", type=str, default=None,
                   help="Folder where per-cell crops + layout overlay are dumped.")
    p.add_argument("--show-bboxes", action="store_true",
                   help="Save a single overlay PNG (yellow=cells, red=icon, "
                        "green=text) next to the input image and exit.")
    p.add_argument("--apply", action="store_true",
                   help="Persist matches (rename PNGs + update AutoItemMapping). "
                        "Without this flag, the run is a dry-run.")
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")

    img = Image.open(args.image)

    # --show-bboxes is a quick visual-tuning shortcut.
    if args.show_bboxes:
        out = Path(args.image).with_name(
            Path(args.image).stem + "_layout.png")
        visualize_layout(img, out)
        print(f"Layout overlay saved â {out}")
        return 0

    debug_dir = Path(args.debug_dir) if args.debug_dir else None
    matches = scan_grid(img, args.age, args.slot,
                        threshold=args.threshold, debug_dir=debug_dir)
    print(f"\n=== scan_grid({args.image}, age={args.age}, slot={args.slot}) ===")
    for m in matches:
        flag = "." if not m.is_filled else (
            "OK" if m.score >= args.threshold else "?")
        cands = ", ".join(f"{c[0]}={c[1]:.3f}" for c in m.candidates)
        print(f"  cell {m.cell_idx} (r{m.row}c{m.col}) {flag}  "
              f"ocr={m.ocr_name!r}  match={m.best_match!r}  score={m.score:.3f}")
        if m.candidates:
            print(f"      top-{len(m.candidates)}: {cands}")

    report = apply_results(matches, args.age, args.slot,
                           dry_run=not args.apply, threshold=args.threshold)
    print(f"\n=== apply_results (dry_run={report.dry_run}) ===")
    for u in report.updated:
        print(f"  + {u}")
    for s in report.skipped:
        print(f"  - {s}")
    if report.backup_path:
        print(f"\nbackup: {report.backup_path}")
 