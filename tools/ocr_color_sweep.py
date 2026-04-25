"""
============================================================
  FORGE MASTER — OCR color-sweep harness

  Problem
  -------
  `backend.fix_ocr.recolour_ui_labels()` repaints every pixel belonging
  to the game's rarity/epoch label palette (red, cyan, green, yellow,
  purple, teal, dark-blue, brown, orange) with a single replacement
  colour `LABEL_REPLACEMENT_COLOR`. That colour is the ONE knob that
  decides whether OCR reads the bracketed label cleanly or butchers it
  (e.g. `[Quantum]` → `Jelloo s66rh [wnaueno]`).

  This script sweeps ~150 candidate replacement colours against every
  image in `debug_test/`, runs OCR on each transformation, and ranks
  the colours by similarity (token-level F1) to the ground truth in
  `debug_test/format.txt`.

  Output
  ------
  `debug_test/sweep_results/`
    sweep_<image>.txt     One per input image. For each candidate
                          colour: the OCR output obtained with that
                          colour. You can eyeball these to sanity-check
                          the scoring.
    summary.txt           Final ranking: top colours by mean F1 across
                          all images, plus a per-category breakdown
                          (equipement / skill / pet / mount).

  Usage
  -----
      python tools/ocr_color_sweep.py                    # full sweep
      python tools/ocr_color_sweep.py --top 20           # keep 20 in summary
      python tools/ocr_color_sweep.py --categories equipement skill
      python tools/ocr_color_sweep.py --images equipement1 pet3

  Notes
  -----
  * Each image's detection mask is computed ONCE and reused for every
    colour (the mask depends only on UI_LABEL_COLORS, not on the
    replacement). So the expensive numpy work is paid once per image.
  * The OCR call dominates runtime. 150 colours × 29 images ≈ 4350
    OCR calls — expect ~10-15 min on a CPU with rapidocr-onnxruntime.
  * The scoring metric is token-level F1 (precision + recall of
    alphanumeric tokens, case-insensitive). It's robust to whitespace,
    line-order, and punctuation noise — what matters is whether the
    right words made it through.
============================================================
"""

from __future__ import annotations

import argparse
import colorsys
import os
import re
import sys
import time
from typing import Dict, List, Optional, Tuple

# ── Path setup: run from project root so `backend.*` imports work. ─
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from backend import fix_ocr, ocr  # noqa: E402


DEBUG_DIR = os.path.join(_ROOT, "debug_test")
OUT_DIR   = os.path.join(DEBUG_DIR, "sweep_results")
FORMAT_TXT = os.path.join(DEBUG_DIR, "format.txt")

RGB = Tuple[int, int, int]


# ══════════════════════════════════════════════════════════
# 1. Palette: 150 candidate replacement colours
# ══════════════════════════════════════════════════════════

def build_palette() -> List[RGB]:
    """~150 colours spanning the RGB cube in a useful way.

    Composition:
      * 6 greys at L ∈ {0, 20, 40, 60, 80, 100}%
      * HSL grid: 12 hues × 3 saturations × 4 lightnesses = 144

    Dedup is cheap — we cast through a dict to preserve insertion order.
    """
    palette: List[RGB] = []

    # Greys first — pure achromatic baselines.
    for l_pct in (0, 20, 40, 60, 80, 100):
        v = round(l_pct * 255 / 100)
        palette.append((v, v, v))

    # Hue grid. colorsys uses HLS, not HSL — same thing with reordered args.
    for h_deg in (0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330):
        h = h_deg / 360.0
        for s_pct in (100, 60, 30):
            s = s_pct / 100.0
            for l_pct in (15, 35, 55, 75):
                l = l_pct / 100.0
                r, g, b = colorsys.hls_to_rgb(h, l, s)
                palette.append((round(r * 255), round(g * 255), round(b * 255)))

    # Dedup while preserving order. (S=0 rows collapse onto greys.)
    seen = {}
    for rgb in palette:
        seen.setdefault(rgb, None)
    return list(seen.keys())


def rgb_hex(rgb: RGB) -> str:
    return "#%02X%02X%02X" % rgb


# ══════════════════════════════════════════════════════════
# 2. Ground truth: parse format.txt
# ══════════════════════════════════════════════════════════

# Section header: a line like "equipement1 :" or "skill3 : " (trailing space ok).
_SECTION_HEADER = re.compile(r"^(equipement|skill|pet|mount)(\d+)\s*:\s*$")


def parse_format(path: str) -> Dict[str, str]:
    """Parse format.txt into {image_stem: expected_text}."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Ground truth not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    out: Dict[str, List[str]] = {}
    current: Optional[str] = None
    for line in lines:
        m = _SECTION_HEADER.match(line.strip())
        if m:
            current = f"{m.group(1)}{m.group(2)}"
            out[current] = []
            continue
        if current is None:
            continue
        out[current].append(line.rstrip("\n"))

    # Strip leading/trailing blank lines inside each section.
    return {k: "\n".join(v).strip() for k, v in out.items()}


# ══════════════════════════════════════════════════════════
# 3. Mask cache: compute the UI-label mask once per image
# ══════════════════════════════════════════════════════════

def compute_mask(arr):
    """Union of masks for every palette colour in UI_LABEL_COLORS.

    This is the single expensive numpy operation per image. Doing it
    once and reusing it for every candidate colour is what makes the
    sweep tolerable.
    """
    import numpy as np
    mask = np.zeros(arr.shape[:2], dtype=bool)
    for target in fix_ocr.UI_LABEL_COLORS:
        mask |= fix_ocr._build_match_mask(arr, target)
    return mask


def paint(arr, mask, colour: RGB):
    """Return a new array with `mask` pixels replaced by `colour`."""
    out = arr.copy()
    out[mask] = colour
    return out


# ══════════════════════════════════════════════════════════
# 4. Scoring: token-level F1 against ground truth
# ══════════════════════════════════════════════════════════

# Tokens: words, numbers-with-percent/decimals/units, bracketed labels.
# We deliberately INCLUDE the brackets in the token set so "[Quantum]"
# is a single token — this directly rewards colour choices that let
# OCR keep the brackets intact (the #1 failure mode we're hunting).
_TOKEN_RE = re.compile(r"\[[^\[\]]+\]|[\w%.+\-]+")


def tokenize(text: str) -> List[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "")]


def f1(ocr_text: str, expected: str) -> float:
    """Token-level F1 (multiset): rewards both precision and recall."""
    o = tokenize(ocr_text)
    e = tokenize(expected)
    if not e:
        return 0.0
    if not o:
        return 0.0
    # Multiset intersection via a counter.
    from collections import Counter
    co, ce = Counter(o), Counter(e)
    tp = sum((co & ce).values())
    prec = tp / len(o)
    rec  = tp / len(e)
    if prec + rec == 0:
        return 0.0
    return 2 * prec * rec / (prec + rec)


# ══════════════════════════════════════════════════════════
# 5. Sweep driver
# ══════════════════════════════════════════════════════════

def list_images(categories: Optional[List[str]] = None,
                images:     Optional[List[str]] = None) -> List[Tuple[str, str]]:
    """Yield (stem, abspath) for every image in debug_test/ matching filters."""
    if not os.path.isdir(DEBUG_DIR):
        raise FileNotFoundError(f"{DEBUG_DIR} not found")
    all_pngs = sorted(
        f for f in os.listdir(DEBUG_DIR)
        if f.lower().endswith(".png")
    )
    out: List[Tuple[str, str]] = []
    for fname in all_pngs:
        stem = os.path.splitext(fname)[0]
        m = re.match(r"(equipement|skill|pet|mount)(\d+)$", stem)
        if not m:
            continue
        cat = m.group(1)
        if categories and cat not in categories:
            continue
        if images and stem not in images:
            continue
        out.append((stem, os.path.join(DEBUG_DIR, fname)))
    return out


def category_of(stem: str) -> str:
    m = re.match(r"(equipement|skill|pet|mount)", stem)
    return m.group(1) if m else "unknown"


def sweep(palette:      List[RGB],
          ground_truth: Dict[str, str],
          selection:    List[Tuple[str, str]],
          log_every:    int = 20) -> Dict:
    """Run the full image × colour sweep.

    Returns a nested results dict:
        {stem: {"category": c, "ocr": {colour_rgb: text}, "score": {colour_rgb: f1}}}
    """
    from PIL import Image
    import numpy as np

    if not ocr.is_available():
        print("ERROR: OCR engine not available. "
              "Install rapidocr-onnxruntime and re-run.")
        sys.exit(1)

    # CRITICAL: `ocr.ocr_image()` calls `recolour_ui_labels()` internally,
    # which would RE-PAINT any candidate colour whose hue happens to match
    # a UI_LABEL_COLORS entry (e.g. choosing candidate red would re-trigger
    # the repaint and clobber our test colour with the production default).
    # We do the painting ourselves, so we neutralise the engine's one.
    fix_ocr.recolour_ui_labels = lambda img: img
    print("  [neutralised backend.fix_ocr.recolour_ui_labels "
          "for the duration of the sweep]")

    results: Dict = {}
    total_calls = len(selection) * len(palette)
    done = 0
    t0 = time.time()

    for stem, path in selection:
        img = Image.open(path).convert("RGB")
        arr = np.array(img)
        mask = compute_mask(arr)
        expected = ground_truth.get(stem, "")

        per_image = {"category": category_of(stem),
                     "ocr": {}, "score": {}}

        # If the mask is entirely empty (no coloured labels at all),
        # the replacement colour can't change OCR output — run OCR once
        # with the default and broadcast the same result for every
        # candidate. Saves ~150× work on plain-text images.
        if not mask.any():
            text = ocr.ocr_image(img)
            score = f1(text, expected) if expected else 0.0
            for colour in palette:
                per_image["ocr"][colour] = text
                per_image["score"][colour] = score
                done += 1
            results[stem] = per_image
            print(f"  {stem:14s}  (no coloured pixels — 1 OCR call)")
            continue

        for colour in palette:
            arr_painted = paint(arr, mask, colour)
            img_painted = Image.fromarray(arr_painted)
            text = ocr.ocr_image(img_painted)
            per_image["ocr"][colour] = text
            per_image["score"][colour] = f1(text, expected) if expected else 0.0
            done += 1
            if done % log_every == 0:
                elapsed = time.time() - t0
                rate = done / elapsed if elapsed else 0
                eta  = (total_calls - done) / rate if rate else 0
                print(f"  {done}/{total_calls}  "
                      f"({done/total_calls*100:.0f}%)  "
                      f"elapsed={elapsed:.0f}s  ETA={eta:.0f}s")

        results[stem] = per_image

    return results


# ══════════════════════════════════════════════════════════
# 6. Output writers
# ══════════════════════════════════════════════════════════

def write_per_image(results: Dict, palette: List[RGB]) -> None:
    """One file per image listing every colour and its OCR output."""
    os.makedirs(OUT_DIR, exist_ok=True)
    for stem, data in results.items():
        path = os.path.join(OUT_DIR, f"sweep_{stem}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# {stem}\n")
            f.write(f"# Category: {data['category']}\n")
            f.write(f"# {len(palette)} candidate colours\n\n")
            # Sort colours by this image's score, best first.
            ranked = sorted(
                palette, key=lambda c: data["score"].get(c, 0), reverse=True
            )
            for colour in ranked:
                score = data["score"].get(colour, 0.0)
                text  = data["ocr"].get(colour, "")
                f.write("=" * 60 + "\n")
                f.write(f"colour: {rgb_hex(colour)}   rgb={colour}   F1={score:.3f}\n")
                f.write("-" * 60 + "\n")
                f.write(text.rstrip() + "\n\n")


def write_summary(results: Dict,
                  palette: List[RGB],
                  top_n:   int) -> None:
    """Overall ranking + per-category breakdown."""
    os.makedirs(OUT_DIR, exist_ok=True)

    # Mean score per colour across all images.
    overall: List[Tuple[RGB, float, int]] = []
    for colour in palette:
        scores = [data["score"].get(colour, 0.0)
                  for data in results.values()
                  if data.get("score")]
        if not scores:
            continue
        mean = sum(scores) / len(scores)
        overall.append((colour, mean, len(scores)))
    overall.sort(key=lambda t: t[1], reverse=True)

    # Per-category means.
    cats: Dict[str, List[Tuple[RGB, float]]] = {}
    for colour in palette:
        for cat in ("equipement", "skill", "pet", "mount"):
            scores = [data["score"].get(colour, 0.0)
                      for data in results.values()
                      if data["category"] == cat]
            if not scores:
                continue
            cats.setdefault(cat, []).append(
                (colour, sum(scores) / len(scores))
            )
    for cat in cats:
        cats[cat].sort(key=lambda t: t[1], reverse=True)

    path = os.path.join(OUT_DIR, "summary.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("# OCR colour sweep — summary\n")
        f.write(f"# palette: {len(palette)} candidates\n")
        f.write(f"# images:  {len(results)}\n")
        f.write(f"# metric:  token-level F1 against debug_test/format.txt\n\n")

        f.write(f"TOP {top_n} OVERALL\n")
        f.write("=" * 60 + "\n")
        f.write("rank  colour    rgb                 mean F1  n_imgs\n")
        f.write("-" * 60 + "\n")
        for i, (colour, mean, n) in enumerate(overall[:top_n], start=1):
            f.write(f"  {i:>3}  {rgb_hex(colour)}  "
                    f"{str(colour):18s}  {mean:.3f}    {n}\n")

        for cat, rows in cats.items():
            f.write(f"\nTOP {min(top_n, len(rows))} — {cat.upper()}\n")
            f.write("=" * 60 + "\n")
            f.write("rank  colour    rgb                 mean F1\n")
            f.write("-" * 60 + "\n")
            for i, (colour, mean) in enumerate(rows[:top_n], start=1):
                f.write(f"  {i:>3}  {rgb_hex(colour)}  "
                        f"{str(colour):18s}  {mean:.3f}\n")

        # Also report the current production colour for comparison.
        current = tuple(int(c) for c in fix_ocr.LABEL_REPLACEMENT_COLOR)
        f.write("\nCURRENT PRODUCTION COLOUR (for comparison)\n")
        f.write("=" * 60 + "\n")
        f.write(f"  {rgb_hex(current)}  rgb={current}\n")
        match = next((row for row in overall if row[0] == current), None)
        if match:
            rank = overall.index(match) + 1
            f.write(f"  rank in overall: {rank}/{len(overall)}   "
                    f"mean F1: {match[1]:.3f}\n")
        else:
            f.write("  (not present in tested palette)\n")

    print(f"\nWrote {path}")


# ══════════════════════════════════════════════════════════
# 7. CLI
# ══════════════════════════════════════════════════════════

def main() -> None:
    ap = argparse.ArgumentParser(description="OCR colour sweep harness")
    ap.add_argument("--top", type=int, default=15,
                    help="How many colours to list in the summary (default 15)")
    ap.add_argument("--categories", nargs="+",
                    choices=("equipement", "skill", "pet", "mount"),
                    help="Restrict to a subset of categories")
    ap.add_argument("--images", nargs="+",
                    help="Restrict to specific image stems, e.g. equipement2 skill1")
    ap.add_argument("--palette-limit", type=int, default=0,
                    help="Truncate palette to first N colours (for quick tests)")
    args = ap.parse_args()

    palette = build_palette()
    if args.palette_limit and args.palette_limit < len(palette):
        palette = palette[: args.palette_limit]
    print(f"Palette: {len(palette)} candidate colours")

    ground_truth = parse_format(FORMAT_TXT)
    print(f"Ground truth: {len(ground_truth)} sections parsed from format.txt")

    selection = list_images(args.categories, args.images)
    if not selection:
        print("No images match the filters.")
        sys.exit(1)
    print(f"Images: {len(selection)} selected")
    print(f"Total OCR calls: ~{len(selection) * len(palette)}")
    print()

    t0 = time.time()
    results = sweep(palette, ground_truth, selection)
    print(f"\nSweep complete in {time.time() - t0:.0f}s")

    write_per_image(results, palette)
    write_summary(results, palette, args.top)
    print(f"Per-image reports + summary in {OUT_DIR}")


if __name__ == "__main__":
    main()