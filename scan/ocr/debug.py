"""
============================================================
  FORGE MASTER — OCR scan debug dumps

  Every scan writes three things to <project_root>/debug_scan/
  so you can see exactly what the OCR engine was fed and what
  text came back:

    1) The RAW BlueStacks capture for each bbox (pre-processing
       not applied yet).
    2) The PROCESSED image after fix_ocr.recolour_ui_labels()
       repaints the coloured rarity/epoch glyphs — this is the
       image PaddleOCR actually sees.
    3) The raw OCR text and the post-fix_ocr text, side by side.

  Filename format:
      <stamp>__<zone>[__step<n>]__<tag>.<ext>

  Where:
      <stamp> = YYYYMMDD_HHMMSS_mmm
      <zone>  = profile | opponent | equipment | pet | mount | skill
      <step>  = 0, 1, ... (bbox index inside the zone; only for images)
      <tag>   = 1_raw | 2_processed | ocr_raw | ocr_fixed

  To disable: flip DEBUG_SCAN_ENABLED to False at the top of this
  module (or delete the debug_scan/ folder — it'll be recreated on
  the next scan unless the flag is off).
============================================================
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Optional

log = logging.getLogger(__name__)

# Master switch. Set to False to silently skip all dumps at runtime.
DEBUG_SCAN_ENABLED = True

# debug_scan/ sits at the project root, next to main.py.
# This file lives at backend/scanner/debug_scan.py, so we walk up
# two parents (.. then ..) to reach the project root.
_THIS_DIR    = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_THIS_DIR)
_ROOT_DIR    = os.path.dirname(_BACKEND_DIR)
DEBUG_DIR    = os.path.join(_ROOT_DIR, "debug_scan")


def _ensure_dir() -> bool:
    """Create debug_scan/ if missing. Returns False if it can't be made."""
    try:
        os.makedirs(DEBUG_DIR, exist_ok=True)
        return True
    except Exception as e:
        log.warning("debug_scan: could not create %s (%s)", DEBUG_DIR, e)
        return False


def new_stamp() -> str:
    """Fresh YYYYMMDD_HHMMSS_mmm timestamp — one per scan session."""
    now = time.time()
    ms  = int((now - int(now)) * 1000)
    return time.strftime("%Y%m%d_%H%M%S", time.localtime(now)) + f"_{ms:03d}"


def _stem(stamp: str, zone: str, step: Optional[int]) -> str:
    z = zone or "unknown"
    if step is None:
        return f"{stamp}__{z}"
    return f"{stamp}__{z}__step{step}"


def save_image(img: Any, stamp: str, zone: str, step: Optional[int], tag: str) -> None:
    """Write a PIL image to <stamp>__<zone>__step<n>__<tag>.png.

    Silently skipped when DEBUG_SCAN_ENABLED is False, when img is None,
    when the target dir can't be created, or when PIL fails to save —
    debug dumps must never interfere with the real scan pipeline.
    """
    if not DEBUG_SCAN_ENABLED or img is None:
        return
    if not _ensure_dir():
        return
    path = os.path.join(DEBUG_DIR, f"{_stem(stamp, zone, step)}__{tag}.png")
    try:
        img.save(path)
    except Exception as e:
        log.warning("debug_scan.save_image(%s) failed: %s", path, e)


def save_text(text: str, stamp: str, zone: str, tag: str) -> None:
    """Write a UTF-8 text file to <stamp>__<zone>__<tag>.txt.

    Same failure-silencing policy as save_image().
    """
    if not DEBUG_SCAN_ENABLED:
        return
    if not _ensure_dir():
        return
    path = os.path.join(DEBUG_DIR, f"{_stem(stamp, zone, step=None)}__{tag}.txt")
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text or "")
    except Exception as e:
        log.warning("debug_scan.save_text(%s) failed: %s", path, e)
