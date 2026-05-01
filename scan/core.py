"""
============================================================
  FORGE MASTER — Hybrid icon matcher (core)

  Cleaned-up visual matching core, derived from the old calibration tooling,
  the wiki-grid-specific glue removed (cell layout, OCR title
  reading, AutoItemMapping rename pipeline). Those concerns now
  live in ``scan.jobs.<job>.scan(capture, ...)`` per-job;
  ``scan.core`` is the matcher and nothing else.

  Pipeline (per crop):

      autocrop_capture(crop)  ─┐
                               ├──►  to_gray_arr / to_rgb_arr  ─►
      autocrop_reference(ref) ─┘     ensemble_score(crop, ref, ocr_name, stem)

  ensemble_score blends four signals into one [0, 1] number:

      NCC grayscale     (0.30) — pixel patterns
      NCC Sobel edges   (0.25) — silhouette
      Colour histogram  (0.10) — palette
      OCR text similarity (0.35) — ref filename ↔ OCR'd in-game name

  Sobel edges and colour histograms require OpenCV. Without
  ``cv2`` the module still works in degraded mode (Sobel falls
  back to plain NCC, colour histogram returns 0.5). This is a
  REQUIRED PROPERTY (cf. PLAN_REFACTO_SCAN.txt V7) — the project
  must boot on a machine with no opencv-python.

  Public API:

      DEFAULT_THRESHOLD            — global default min-score
      autocrop_capture(rgb)        — sprite-bbox crop of a live capture
      autocrop_reference(rgba)     — alpha-bbox crop of a PNG ref
      is_cell_filled(crop)         — variance-based "is this empty?"
      ensemble_score(...)          — single blended similarity score
      match(crop, refs, ocr_name)  — score crop against every ref,
                                      returns ``List[Candidate]`` sorted
      greedy_assignment(...)       — global de-conflicter for grids
============================================================
"""

from __future__ import annotations

import difflib
import logging
import re
from typing import List, Optional, Sequence, Tuple, TYPE_CHECKING

import numpy as np
from PIL import Image

from .types import Candidate

if TYPE_CHECKING:  # pragma: no cover - type-only
    from .refs import Reference


# ────────────────────────────────────────────────────────────
#  OpenCV is loaded lazily so the module imports without it.
# ────────────────────────────────────────────────────────────

try:
    import cv2 as _cv2  # type: ignore
    _CV2_AVAILABLE = True
except Exception:  # pragma: no cover - depends on the host machine
    _cv2 = None  # type: ignore
    _CV2_AVAILABLE = False


log = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────
#  Tunables
# ────────────────────────────────────────────────────────────

# Default minimum hybrid-score for a match to be considered
# confident. Per-job overrides allowed via the ``threshold``
# argument on every ``scan(...)`` entry-point.
DEFAULT_THRESHOLD: float = 0.30

# All matcher comparisons happen at this resolution (after
# autocrop). 128×128 is the same value the wiki-grid scanner
# uses; smaller is faster but blurs out distinctive details.
_MATCH_SIZE: Tuple[int, int] = (128, 128)

# Score weights for the hybrid matcher. Visual signals + OCR-text
# similarity are blended into a single [0, 1] score.
_NCC_WEIGHT:   float = 0.30   # grayscale pattern
_EDGE_WEIGHT:  float = 0.25   # Sobel-edge silhouette
_COLOR_WEIGHT: float = 0.10   # colour histogram (catches Rock vs Bone)
_TEXT_WEIGHT:  float = 0.35   # OCR vs ref-filename string similarity

# Background colour for compositing transparent references.
# Neutral mid-gray so the alpha edge does not register as a
# black halo during NCC.
_NEUTRAL_BG: Tuple[int, int, int] = (60, 60, 60)

# Variance threshold below which a cell is considered empty
# (no icon, just background). 16×16 grayscale resize, then
# variance of pixel values.
_FILLED_VARIANCE_THRESHOLD: float = 30.0


# ────────────────────────────────────────────────────────────
#  Bbox helpers (auto-crop)
# ────────────────────────────────────────────────────────────


def _alpha_bbox(rgba: Image.Image) -> Optional[Tuple[int, int, int, int]]:
    """Tight bbox of non-transparent pixels of an RGBA image.

    Returns None when the image is fully transparent or not
    RGBA — the caller falls back to the original image.
    """
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
                bg_distance_threshold: float = 25.0,
                ) -> Optional[Tuple[int, int, int, int]]:
    """Tight bbox of pixels whose colour differs from the
    corner background.

    Used on live captures (no alpha channel). Samples 5×5
    patches at each corner — their mean is treated as the
    dominant background colour, then any pixel further than
    ``bg_distance_threshold`` units away in RGB-Euclidean
    space is marked as foreground.

    A small 4 % margin is added so anti-aliased edges are
    not clipped.
    """
    arr = np.asarray(rgb.convert("RGB"))
    h, w = arr.shape[:2]
    if h < 4 or w < 4:
        return None
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
    h_pad = max(1, int((rmax - rmin) * 0.04))
    w_pad = max(1, int((cmax - cmin) * 0.04))
    return (max(0, int(cmin) - w_pad),
            max(0, int(rmin) - h_pad),
            min(w,   int(cmax) + 1 + w_pad),
            min(h,   int(rmax) + 1 + h_pad))


def _flatten_reference(ref: Image.Image) -> Image.Image:
    """Composite an RGBA reference onto neutral gray so
    transparent corners do not register as black during pixel
    comparison."""
    if ref.mode != "RGBA":
        return ref.convert("RGB")
    flat = Image.new("RGB", ref.size, _NEUTRAL_BG)
    flat.paste(ref, mask=ref.split()[3])
    return flat


def autocrop_reference(ref_rgba: Image.Image) -> Image.Image:
    """Tightly crop a reference PNG to its alpha bbox, then
    composite onto neutral gray. Returns RGB.

    Used by ``scan.refs.load_references`` to prepare every
    reference once at load-time.
    """
    bb = _alpha_bbox(ref_rgba)
    if bb is None:
        return _flatten_reference(ref_rgba)
    cropped = ref_rgba.crop(bb)
    flat = Image.new("RGB", cropped.size, _NEUTRAL_BG)
    flat.paste(cropped, mask=cropped.split()[3])
    return flat


def autocrop_capture(crop_rgb: Image.Image) -> Image.Image:
    """Tightly crop a live capture to its sprite (the colored
    pixels that differ from the corner-tile background).

    Used by ``match`` on the live crop right before scoring.
    """
    bb = _color_bbox(crop_rgb)
    if bb is None:
        return crop_rgb.convert("RGB")
    return crop_rgb.crop(bb).convert("RGB")


# ────────────────────────────────────────────────────────────
#  Array helpers (used by both refs and the matcher)
# ────────────────────────────────────────────────────────────


def to_gray_arr(img: Image.Image) -> "np.ndarray":
    """Resize → grayscale uint8 array at ``_MATCH_SIZE``.

    Public so ``scan.refs`` can pre-compute reference arrays
    once at load time.
    """
    return np.asarray(
        img.convert("L").resize(_MATCH_SIZE),
        dtype=np.uint8,
    )


def to_rgb_arr(img: Image.Image) -> "np.ndarray":
    """Resize → RGB uint8 array at ``_MATCH_SIZE``."""
    return np.asarray(
        img.convert("RGB").resize(_MATCH_SIZE),
        dtype=np.uint8,
    )


# ────────────────────────────────────────────────────────────
#  Cell occupancy
# ────────────────────────────────────────────────────────────


def is_cell_filled(icon_crop: Image.Image) -> bool:
    """Variance-based "does this cell contain an icon?".

    A cell is considered EMPTY when the 16×16 grayscale resize
    has near-uniform luminance (variance below the threshold).
    Live tiles always have enough detail to clear the bar; an
    empty slot in the wiki grid or an unequipped player slot
    is essentially a flat colour.
    """
    arr = np.asarray(
        icon_crop.convert("L").resize((16, 16)),
        dtype=np.float32,
    )
    return float(arr.var()) > _FILLED_VARIANCE_THRESHOLD


# ────────────────────────────────────────────────────────────
#  Similarity primitives
# ────────────────────────────────────────────────────────────


def ncc_grayscale(a: "np.ndarray", b: "np.ndarray") -> float:
    """Pearson NCC of two same-shape grayscale arrays. [-1, 1]."""
    af = a.astype(np.float32) - a.mean()
    bf = b.astype(np.float32) - b.mean()
    denom = float(np.sqrt((af * af).sum() * (bf * bf).sum()))
    if denom < 1e-6:
        return 0.0
    return float((af * bf).sum() / denom)


def ncc_edges(a: "np.ndarray", b: "np.ndarray") -> float:
    """NCC after Sobel edge extraction. Insensitive to
    colour/light. Falls back to plain NCC when OpenCV is
    unavailable — see PLAN_REFACTO_SCAN.txt V7."""
    if not _CV2_AVAILABLE:
        return ncc_grayscale(a, b)  # graceful fallback
    ax = _cv2.Sobel(a, _cv2.CV_32F, 1, 0, ksize=3)
    ay = _cv2.Sobel(a, _cv2.CV_32F, 0, 1, ksize=3)
    bx = _cv2.Sobel(b, _cv2.CV_32F, 1, 0, ksize=3)
    by = _cv2.Sobel(b, _cv2.CV_32F, 0, 1, ksize=3)
    a_mag = np.sqrt(ax * ax + ay * ay).astype(np.uint8)
    b_mag = np.sqrt(bx * bx + by * by).astype(np.uint8)
    return ncc_grayscale(a_mag, b_mag)


def color_hist_corr(a_rgb: "np.ndarray", b_rgb: "np.ndarray") -> float:
    """Bhattacharyya-distance based correlation of HS
    histograms. Returns a value in [0, 1] (1 = identical
    colour distribution). Neutral 0.5 fallback when OpenCV is
    unavailable."""
    if not _CV2_AVAILABLE:
        return 0.5
    a_hsv = _cv2.cvtColor(a_rgb, _cv2.COLOR_RGB2HSV)
    b_hsv = _cv2.cvtColor(b_rgb, _cv2.COLOR_RGB2HSV)
    bins = [30, 32]
    ranges = [0, 180, 0, 256]
    h_a = _cv2.calcHist([a_hsv], [0, 1], None, bins, ranges)
    h_b = _cv2.calcHist([b_hsv], [0, 1], None, bins, ranges)
    _cv2.normalize(h_a, h_a, alpha=0, beta=1, norm_type=_cv2.NORM_MINMAX)
    _cv2.normalize(h_b, h_b, alpha=0, beta=1, norm_type=_cv2.NORM_MINMAX)
    d = float(_cv2.compareHist(h_a, h_b, _cv2.HISTCMP_BHATTACHARYYA))
    return max(0.0, 1.0 - d)


# ────────────────────────────────────────────────────────────
#  Filename → item-name canonicaliser
# ────────────────────────────────────────────────────────────


def _ref_canonical_name(stem: str) -> str:
    """Strip the ``Icon{Age}{Slot}`` prefix from a reference
    filename stem, leaving just the item name.

    Examples::
        IconPrimitiveWeaponAxe       -> Axe
        IconQuantumWeaponBlackBow    -> BlackBow
        Axe                          -> Axe   (already-clean stem)

    Heuristic: drop the literal ``Icon`` then assume the next
    two PascalCase tokens are age + slot. Tolerates slightly
    malformed names by falling back to the raw stem.
    """
    if stem.startswith("Icon"):
        rest = stem[4:]
        tokens = re.findall(r"[A-Z][a-z]*", rest)
        if len(tokens) >= 3:
            return "".join(tokens[2:])
        if len(tokens) == 2:
            return tokens[1]
        return rest
    return stem


def text_similarity(ocr_name: str, ref_stem: str) -> float:
    """Fuzzy similarity between an OCR'd in-game name and the
    reference filename's item-name portion. Returns [0, 1].

    Spaces and case are normalised so 'Black Sword' matches
    'BlackSword' and 'BLACKSWORD'. An empty ``ocr_name``
    returns 0.0 (pure visual scoring).
    """
    if not ocr_name:
        return 0.0
    ref_name = _ref_canonical_name(ref_stem)
    a = re.sub(r"[\s_\-]+", "", ocr_name).lower()
    b = re.sub(r"[\s_\-]+", "", ref_name).lower()
    if not a or not b:
        return 0.0
    return float(difflib.SequenceMatcher(None, a, b).ratio())


# ────────────────────────────────────────────────────────────
#  Ensemble scorer
# ────────────────────────────────────────────────────────────


def ensemble_score(crop_gray: "np.ndarray",
                   ref_gray: "np.ndarray",
                   crop_rgb: "np.ndarray",
                   ref_rgb: "np.ndarray",
                   ocr_name: str,
                   ref_stem: str) -> float:
    """Weighted ensemble of visual NCCs + colour histogram +
    OCR text similarity.

    Components are clamped to ``[0, 1]`` then summed with the
    ``_*_WEIGHT`` constants. OCR text is the strongest single
    signal when the in-game name still matches a reference
    filename; visual signals dominate when an item has been
    renamed since the last calibration.

    Returns a float in roughly ``[0, 1]``. The match() function
    sorts on this value descending; the threshold consumed by
    job code is ``DEFAULT_THRESHOLD`` unless overridden.
    """
    ncc   = ncc_grayscale(crop_gray, ref_gray)
    edges = ncc_edges(crop_gray, ref_gray)
    color = color_hist_corr(crop_rgb, ref_rgb)
    text  = text_similarity(ocr_name, ref_stem)
    ncc_n   = max(0.0, ncc)
    edges_n = max(0.0, edges)
    score = (_NCC_WEIGHT   * ncc_n
             + _EDGE_WEIGHT  * edges_n
             + _COLOR_WEIGHT * color
             + _TEXT_WEIGHT  * text)
    return float(score)


# ────────────────────────────────────────────────────────────
#  Match — public entry point
# ────────────────────────────────────────────────────────────


def match(crop: Image.Image,
          refs: Sequence["Reference"],
          *,
          ocr_name: str = "",
          top_n: Optional[int] = None,
          autocrop: bool = True,
          ) -> List[Candidate]:
    """Score ``crop`` against every reference in ``refs``.

    Parameters
    ----------
    crop : PIL.Image.Image
        The live tile / popup icon to identify.
    refs : sequence of ``scan.refs.Reference``
        References pre-loaded by ``scan.refs.load_references``.
        Each reference carries the pre-computed gray and rgb
        arrays, plus optional age/slot metadata that gets
        propagated into the resulting Candidate.
    ocr_name : str
        OCR'd in-game name (popup title, wiki tile label).
        Empty string means "no text signal" — visual scoring
        only.
    top_n : int, optional
        If set, only return the top-N candidates. Default
        returns ALL candidates ranked descending so callers
        can implement greedy global assignment when scoring
        an entire panel at once.
    autocrop : bool
        Whether to autocrop the live crop to its sprite bbox
        before scoring. Default True; jobs that have already
        autocropped (or that work on perfectly framed icons)
        can skip the second pass.

    Returns
    -------
    list[Candidate]
        Sorted by score descending. ``score`` and ``name``
        are always populated; ``age`` / ``slot`` / ``payload``
        are propagated from the matched reference. Rarity and
        idx remain None — jobs fill those in from colour
        heuristics + AutoMapping lookups.
    """
    if not refs:
        return []

    sprite = autocrop_capture(crop) if autocrop else crop.convert("RGB")
    crop_gray = to_gray_arr(sprite)
    crop_rgb  = to_rgb_arr(sprite)

    scored: List[Candidate] = []
    for ref in refs:
        s = ensemble_score(
            crop_gray, ref.gray, crop_rgb, ref.rgb,
            ocr_name, ref.stem,
        )
        scored.append(Candidate(
            name=ref.stem,
            score=float(s),
            age=ref.age,
            slot=ref.slot,
            rarity=None,           # filled by job from border colour
            idx=ref.payload.get("idx") if ref.payload else None,
            payload=dict(ref.payload) if ref.payload else {},
        ))

    scored.sort(key=lambda c: c.score, reverse=True)
    if top_n is not None and top_n > 0:
        scored = scored[:top_n]
    return scored


# ────────────────────────────────────────────────────────────
#  Greedy global assignment (multi-cell panels)
# ────────────────────────────────────────────────────────────


def greedy_assignment(scored_per_cell: List[List[Candidate]]
                      ) -> List[Optional[Candidate]]:
    """Greedy global assignment: pick the highest-scoring
    (cell, ref) pair, claim it, remove the cell and ref from
    contention, repeat.

    Used by panel scans (wiki grid, opponent / player_equipment
    4×2 grids) to prevent two cells from being assigned the
    same reference, which is impossible in a wiki grid where
    every cell shows a different item.

    Parameters
    ----------
    scored_per_cell : list[list[Candidate]]
        ``scored_per_cell[i]`` is the full ranked list for
        cell ``i``. Empty list = empty cell, no candidates.

    Returns
    -------
    list[Optional[Candidate]]
        Same length as ``scored_per_cell``. Index ``i`` holds
        the Candidate assigned to cell ``i``, or None if the
        cell was empty / no reference was free for it.
    """
    n = len(scored_per_cell)
    pairs: List[Tuple[float, int, Candidate]] = []
    for cell_idx, scored in enumerate(scored_per_cell):
        for cand in scored:
            pairs.append((cand.score, cell_idx, cand))
    pairs.sort(key=lambda p: -p[0])

    out: List[Optional[Candidate]] = [None] * n
    used_refs: set = set()
    for _, cell_idx, cand in pairs:
        if out[cell_idx] is not None or cand.name in used_refs:
            continue
        out[cell_idx] = cand
        used_refs.add(cand.name)
    return out


__all__ = [
    "DEFAULT_THRESHOLD",
    "autocrop_capture",
    "autocrop_reference",
    "to_gray_arr",
    "to_rgb_arr",
    "is_cell_filled",
    "ncc_grayscale",
    "ncc_edges",
    "color_hist_corr",
    "text_similarity",
    "ensemble_score",
    "match",
    "greedy_assignment",
]
