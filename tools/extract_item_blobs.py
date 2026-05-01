"""
============================================================
  Item sprite extractor — connected components on age sheets

  The per-age item spritesheets (data/sprites/{Age}AgeItems.png)
  are bin-packed Unity TextureAtlases — there is no regular
  grid, no companion JSON listing rectangles. This script does
  the next best thing: it isolates each opaque blob (alpha
  channel > 16) using 8-connectivity and saves it as an
  individual PNG under data/items/raw/.

  A blob's bbox is also written to data/items/raw/blobs.json
  so the labelling tool (label_item_sprites.py) can replay
  the same crops without rerunning detection.

  Two heuristics tame the noise:

    * components smaller than MIN_AREA pixels are ignored
      (keeps anti-aliased dust out of the result);

    * components whose bboxes overlap or sit within
      MERGE_GAP pixels of each other are merged into a
      single blob (handles weapons whose hilt + blade are
      strictly disjoint regions, like the Primitive
      slingshot's Y-frame and pebble).

  Usage:

      python tools/extract_item_blobs.py            # all ages
      python tools/extract_item_blobs.py --age 0    # only Primitive
      python tools/extract_item_blobs.py --dry-run  # report counts only

  The script is idempotent — re-running overwrites the raw
  crops and the JSON manifest in place.
============================================================
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from PIL import Image
from scipy import ndimage  # type: ignore

# Allow running the script directly from the repo root.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data.libraries import (  # noqa: E402  (import after sys.path tweak)
    AGE_TO_SPRITESHEET,
    SPRITES_DIR,
    DATA_DIR,
)

log = logging.getLogger(__name__)

# Tuneables — kept generous on purpose; the labelling pass will let the
# user discard any false positive in seconds.
MIN_AREA  = 200    # px² — smaller components are dropped as noise
MERGE_GAP = 0      # px  — bboxes within this distance merge into one (0 = no merging)
PADDING   = 4      # px  — extra margin around each saved crop


# ────────────────────────────────────────────────────────────
#  Geometry helpers
# ────────────────────────────────────────────────────────────


def _bbox_overlap_or_close(
    a: Tuple[int, int, int, int],
    b: Tuple[int, int, int, int],
    gap: int,
) -> bool:
    """True when bboxes overlap or are within ``gap`` pixels of one another.

    Bboxes are ``(x0, y0, x1, y1)`` half-open.
    """
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    if ax1 + gap < bx0 or bx1 + gap < ax0:
        return False
    if ay1 + gap < by0 or by1 + gap < ay0:
        return False
    return True


def _merge_bboxes(bboxes: List[Tuple[int, int, int, int]],
                  gap: int) -> List[Tuple[int, int, int, int]]:
    """Greedy union-find on bboxes that touch or are within ``gap`` px.

    Iterates until a full pass produces no merge. Quadratic in the
    number of input bboxes which is fine for a few hundred candidates.
    """
    boxes = list(bboxes)
    changed = True
    while changed:
        changed = False
        out: List[Tuple[int, int, int, int]] = []
        used = [False] * len(boxes)
        for i, a in enumerate(boxes):
            if used[i]:
                continue
            x0, y0, x1, y1 = a
            for j in range(i + 1, len(boxes)):
                if used[j]:
                    continue
                if _bbox_overlap_or_close((x0, y0, x1, y1), boxes[j], gap):
                    bx0, by0, bx1, by1 = boxes[j]
                    x0 = min(x0, bx0); y0 = min(y0, by0)
                    x1 = max(x1, bx1); y1 = max(y1, by1)
                    used[j] = True
                    changed = True
            out.append((x0, y0, x1, y1))
            used[i] = True
        boxes = out
    return boxes


def _pad_clip(bbox: Tuple[int, int, int, int],
              w: int, h: int, pad: int) -> Tuple[int, int, int, int]:
    x0, y0, x1, y1 = bbox
    return (
        max(0, x0 - pad), max(0, y0 - pad),
        min(w, x1 + pad), min(h, y1 + pad),
    )


# ────────────────────────────────────────────────────────────
#  Per-sheet detection
# ────────────────────────────────────────────────────────────


def detect_blobs(image_path: Path) -> List[Tuple[int, int, int, int]]:
    """Return the list of merged content bboxes for a spritesheet."""
    img  = Image.open(image_path).convert("RGBA")
    arr  = np.array(img)
    mask = (arr[..., 3] > 16)

    labeled, n = ndimage.label(mask, structure=np.ones((3, 3), dtype=int))
    if n == 0:
        return []

    # objects is 1-indexed by the CC algorithm
    slices = ndimage.find_objects(labeled)
    raw_bboxes: List[Tuple[int, int, int, int]] = []
    for sl in slices:
        if sl is None:
            continue
        ys, xs = sl
        y0, y1 = ys.start, ys.stop
        x0, x1 = xs.start, xs.stop
        area = (y1 - y0) * (x1 - x0)
        if area < MIN_AREA:
            continue
        raw_bboxes.append((x0, y0, x1, y1))

    if MERGE_GAP > 0:
        return _merge_bboxes(raw_bboxes, MERGE_GAP)
    return raw_bboxes


# ────────────────────────────────────────────────────────────
#  Driver
# ────────────────────────────────────────────────────────────


def extract_age(age: int, out_dir: Path, *, dry_run: bool = False) -> Dict:
    """Process one age. Returns the manifest entry for it."""
    sheet_name = AGE_TO_SPRITESHEET.get(age)
    if sheet_name is None:
        raise ValueError(f"Unknown age: {age}")
    sheet_path = SPRITES_DIR / sheet_name
    if not sheet_path.is_file():
        raise FileNotFoundError(sheet_path)

    img = Image.open(sheet_path).convert("RGBA")
    w, h = img.size
    bboxes = detect_blobs(sheet_path)
    log.info("Age %d (%s): %d blobs detected", age, sheet_name, len(bboxes))

    blobs_meta: List[Dict] = []
    for i, raw_bbox in enumerate(bboxes):
        bbox = _pad_clip(raw_bbox, w, h, PADDING)
        crop_path = out_dir / f"age{age}_blob_{i:03d}.png"
        if not dry_run:
            img.crop(bbox).save(crop_path)
        blobs_meta.append({
            "index":   i,
            "bbox":    list(bbox),
            "filename": crop_path.name,
        })

    return {
        "age":          age,
        "spritesheet":  sheet_name,
        "sheet_size":   [w, h],
        "blob_count":   len(bboxes),
        "blobs":        blobs_meta,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[2].strip())
    parser.add_argument("--age", type=int, choices=sorted(AGE_TO_SPRITESHEET),
                        help="Process a single age (default: all)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Detect and report counts, write nothing")
    parser.add_argument("--out", type=Path, default=DATA_DIR / "items" / "raw",
                        help="Output directory (default: data/items/raw)")
    parser.add_argument("-v", "--verbose", action="count", default=0)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.WARNING - 10 * min(args.verbose, 2),
        format="%(asctime)s %(levelname)-7s %(message)s",
    )

    if not args.dry_run:
        args.out.mkdir(parents=True, exist_ok=True)

    ages = [args.age] if args.age is not None else sorted(AGE_TO_SPRITESHEET)
    manifest: Dict[str, Dict] = {}
    for age in ages:
        manifest[str(age)] = extract_age(age, args.out, dry_run=args.dry_run)

    if not args.dry_run:
        manifest_path = args.out / "blobs.json"
        manifest_path.write_text(json.dumps(manifest, indent=2))
        print(f"Wrote {manifest_path}")
        for age_str, meta in manifest.items():
            print(f"  Age {age_str:>2}: {meta['blob_count']:>3} blobs")
    else:
        print("(dry-run) blob counts only:")
        for age_str, meta in manifest.items():
            print(f"  Age {age_str:>2}: {meta['blob_count']:>3} blobs "
                  f"({meta['spritesheet']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
