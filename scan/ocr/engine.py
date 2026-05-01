"""
============================================================
  FORGE MASTER — OCR module (RapidOCR-based)

  Single place that knows about Pillow + RapidOCR.
  Everything else talks to this module via four functions:

      is_available()       -> bool
      capture_region(bbox) -> PIL.Image | None
      ocr_image(img)       -> str
      run_ocr(bboxes)      -> str   # concat "\\n\\n"

  Engine: rapidocr_onnxruntime (PP-OCR model via ONNX Runtime).

  Install:
      pip install rapidocr-onnxruntime pillow

  All imports are LAZY: an app booted without OCR deps pays
  no cost and never crashes at boot; is_available() simply
  reports False until the backend is found.
============================================================
"""

from __future__ import annotations

import logging
import threading
from typing import List, Optional, Sequence, Tuple

log = logging.getLogger(__name__)

Bbox = Tuple[int, int, int, int]

# Lazy cache. `_available` is tri-state:
#   None  = not yet checked
#   True  = OCR stack ready (Pillow + RapidOCR loaded)
#   False = OCR unavailable (missing Pillow or RapidOCR)
_available:   Optional[bool] = None
_ImageGrab               = None
_PIL_Image               = None
_engine:                 object = None

# Thread safety:
#   _init_lock   — serialises first-time init so RapidOCR() is never
#                  instantiated twice when two scan threads race each
#                  other on cold start.
#   _engine_lock — serialises inference. RapidOCR's preprocessing holds
#                  per-call state and is not documented as thread-safe;
#                  the UI has one user and at most a handful of scans
#                  in flight, so serialising is free in practice.
_init_lock:   threading.Lock = threading.Lock()
_engine_lock: threading.Lock = threading.Lock()


def _init() -> bool:
    """Locate RapidOCR and initialise it.

    Imported lazily so a boot without DL deps costs nothing.
    Returns True on success, False otherwise (with a warning log).
    Thread-safe: concurrent first calls will only instantiate the
    engine once thanks to `_init_lock` + the double-checked flag.
    """
    global _available, _ImageGrab, _PIL_Image, _engine
    # Fast path — the vast majority of calls hit this and avoid lock
    # acquisition entirely.
    if _available is not None:
        return _available

    with _init_lock:
        # Re-check inside the critical section: another thread may have
        # completed the init between our fast-path check and here.
        if _available is not None:
            return _available

        try:
            from PIL import ImageGrab as _IG
            from PIL import Image as _Im
        except Exception as e:
            log.warning("OCR disabled: Pillow missing (%s)", e)
            _available = False
            return False

        try:
            from rapidocr_onnxruntime import RapidOCR  # type: ignore
            _engine = RapidOCR()
            _ImageGrab = _IG
            _PIL_Image = _Im
            _available = True
            log.info("OCR ready — engine: rapidocr_onnxruntime (PP-OCR model)")
            return True
        except Exception as e:
            log.debug("rapidocr_onnxruntime unavailable: %s", e)

        log.warning(
            "OCR disabled: install `rapidocr-onnxruntime pillow` to enable it."
        )
        _available = False
        return False


def is_available() -> bool:
    """Public flag: True if capture + OCR will work."""
    return _init()


def capture_region(bbox: Bbox):
    """Grab a rectangular screen region. Returns a PIL.Image, or None."""
    if not _init():
        return None
    try:
        return _ImageGrab.grab(bbox=tuple(bbox))
    except Exception as e:
        log.warning("capture_region(%r) failed: %s", bbox, e)
        return None


def capture_and_ocr(bbox: Bbox,
                    debug_stamp: Optional[str] = None,
                    debug_zone:  Optional[str] = None,
                    debug_step:  int = 0):
    """Grab + OCR one bbox in a single call.

    Returns ``(PIL.Image | None, str)``. Used by the enemy
    identification pipeline which needs BOTH the raw image (for icon
    template matching) AND the extracted text. Existing callers that
    only need the text keep using ``run_ocr``; the image returned here
    is the one OCR ran on (un-recoloured).
    """
    if not _init():
        return None, ""
    img = capture_region(bbox)
    if img is None:
        return None, ""
    text = ocr_image(
        img,
        debug_stamp=debug_stamp,
        debug_zone=debug_zone,
        debug_step=debug_step,
    )
    return img, text


def _to_numpy(img):
    """Convert a PIL image to an RGB numpy array."""
    import numpy as np
    return np.array(img.convert("RGB"))


def _lines_from_rapidocr(result) -> List[str]:
    # RapidOCR returns (result, elapsed). `result` is a list of
    # [box, text, confidence] triples, roughly top-to-bottom already.
    if not result:
        return []
    out: List[str] = []
    data = result[0] if isinstance(result, tuple) else result
    for item in data or []:
        if len(item) >= 2:
            text = str(item[1]).strip()
            if text:
                out.append(text)
    return out


def ocr_image(
    img,
    debug_stamp: Optional[str] = None,
    debug_zone:  Optional[str] = None,
    debug_step:  Optional[int] = None,
) -> str:
    """OCR a PIL image via RapidOCR.

    The image goes through `fix_ocr.recolour_ui_labels()` first, which
    re-paints every pixel belonging to the game's rarity/epoch label
    palette with a uniform replacement colour so RapidOCR reads them
    at consistent contrast. When `debug_zone` is one of the known
    zone keys (equipment/skill/pet/mount), the zone-specific best
    colour from `ZONE_REPLACEMENT_COLORS` is used; otherwise the
    module default applies.

    When `debug_stamp` and `debug_zone` are provided, both the raw
    input image AND the recoloured image are saved under
    <project_root>/debug_scan/.

    Returns a `\\n`-joined string, one line per detected text box,
    top-to-bottom as returned by the engine. '' on failure.
    """
    if img is None or not _init():
        return ""
    try:
        if debug_stamp is not None and debug_zone is not None:
            try:
                from . import debug
                debug.save_image(img, debug_stamp, debug_zone, debug_step, "1_raw")
            except Exception:
                log.debug("debug_scan raw dump skipped", exc_info=True)

        from .fix import recolour_ui_labels, ZONE_REPLACEMENT_COLORS
        # Per-zone replacement colour — the OCR colour sweep showed
        # equipment/skill/pet/mount each have their own optimum.
        # Zones not listed fall back to the module default.
        replacement = ZONE_REPLACEMENT_COLORS.get(debug_zone) if debug_zone else None
        img = recolour_ui_labels(img, replacement=replacement)

        if debug_stamp is not None and debug_zone is not None:
            try:
                from . import debug
                debug.save_image(img, debug_stamp, debug_zone, debug_step, "2_processed")
            except Exception:
                log.debug("debug_scan processed dump skipped", exc_info=True)

        arr = _to_numpy(img)
        # Serialise engine access — RapidOCR is not guaranteed to be
        # thread-safe for concurrent inference. See `_engine_lock`.
        with _engine_lock:
            result, _elapsed = _engine(arr)  # type: ignore[misc]
        lines = _lines_from_rapidocr(result)
        return "\n".join(lines)
    except Exception as e:
        log.warning("ocr_image() failed: %s", e)
        return ""


def run_ocr(
    bboxes:      Sequence[Bbox],
    debug_stamp: Optional[str] = None,
    debug_zone:  Optional[str] = None,
) -> str:
    """Capture + OCR each bbox, join results with blank lines.

    Empty / failed bboxes are silently skipped.
    """
    if not _init():
        return ""
    out: List[str] = []
    for step, bbox in enumerate(bboxes):
        img = capture_region(bbox)
        if img is None:
            continue
        text = ocr_image(
            img,
            debug_stamp=debug_stamp,
            debug_zone=debug_zone,
            debug_step=step,
        ).strip()
        if text:
            out.append(text)
    return "\n\n".join(out)


def capture_and_ocr(
    bbox: Bbox,
    debug_stamp: Optional[str] = None,
    debug_zone:  Optional[str] = None,
    debug_step:  int = 0,
):
    """Grab + OCR one bbox in a single call.

    Returns ``(PIL.Image | None, str)``. Used by the enemy
    identification pipeline which needs BOTH the raw image (for icon
    template matching) AND the extracted text. Existing callers that
    only need the text keep using ``run_ocr``; the image returned here
    is the one OCR ran on (un-recoloured).
    """
    if not _init():
        return None, ""
    img = capture_region(bbox)
    if img is None:
        return None, ""
    text = ocr_image(
        img,
        debug_stamp=debug_stamp,
        debug_zone=debug_zone,
        debug_step=debug_step,
    )
    return img, text
