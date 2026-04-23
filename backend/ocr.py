"""
============================================================
  FORGE MASTER — OCR module (PaddleOCR-based)

  Single place that knows about Pillow + the deep-learning
  OCR engine. Everything else talks to this module via four
  functions:

      is_available()       -> bool
      capture_region(bbox) -> PIL.Image | None
      ocr_image(img)       -> str
      run_ocr(bboxes)      -> str   # concat "\\n\\n"

  Engine: PaddleOCR family. Two install flavours are
  supported, auto-selected at first call:

    1. rapidocr_onnxruntime  (preferred: ~20 MB, pure CPU,
                              ships the same PP-OCR model as
                              PaddleOCR via ONNX Runtime)
    2. paddleocr             (fallback: heavier, pulls the
                              full paddlepaddle framework,
                              same model, same accuracy)

  Install one of:
      pip install rapidocr_onnxruntime pillow
      pip install paddleocr paddlepaddle pillow

  All imports are LAZY: an app booted without OCR deps pays
  no cost and never crashes at boot; is_available() simply
  reports False until a backend is found.
============================================================
"""

from __future__ import annotations

import logging
from typing import List, Optional, Sequence, Tuple

log = logging.getLogger(__name__)

Bbox = Tuple[int, int, int, int]

# Lazy cache. `_available` is tri-state:
#   None  = not yet checked
#   True  = OCR stack ready (Pillow + a DL backend loaded)
#   False = OCR unavailable (missing Pillow or no backend)
_available:   Optional[bool] = None
_ImageGrab               = None     # PIL.ImageGrab
_PIL_Image               = None     # PIL.Image
_engine_name: Optional[str] = None  # "rapidocr" | "paddleocr"
_engine:                 object = None  # the instantiated engine


def _init() -> bool:
    """Locate an available PaddleOCR-family backend and initialise it.

    Tries rapidocr_onnxruntime first (lighter), then paddleocr.
    Both are imported lazily so a boot without DL deps costs nothing.
    Returns True on success, False otherwise (with a warning log).
    """
    global _available, _ImageGrab, _PIL_Image, _engine, _engine_name
    if _available is not None:
        return _available

    # PIL is required for screen capture either way.
    try:
        from PIL import ImageGrab as _IG
        from PIL import Image as _Im
    except Exception as e:
        log.warning("OCR disabled: Pillow missing (%s)", e)
        _available = False
        return False

    # --- Backend #1: rapidocr_onnxruntime (preferred) ---
    try:
        from rapidocr_onnxruntime import RapidOCR  # type: ignore
        _engine = RapidOCR()
        _engine_name = "rapidocr"
        _ImageGrab = _IG
        _PIL_Image = _Im
        _available = True
        log.info("OCR ready — engine: rapidocr_onnxruntime (PP-OCR model)")
        return True
    except Exception as e:
        log.debug("rapidocr_onnxruntime unavailable: %s", e)

    # --- Backend #2: paddleocr (fallback) ---
    try:
        from paddleocr import PaddleOCR  # type: ignore
        _engine = PaddleOCR(use_angle_cls=False, lang="en", show_log=False)
        _engine_name = "paddleocr"
        _ImageGrab = _IG
        _PIL_Image = _Im
        _available = True
        log.info("OCR ready — engine: paddleocr")
        return True
    except Exception as e:
        log.debug("paddleocr unavailable: %s", e)

    log.warning(
        "OCR disabled: install `rapidocr_onnxruntime` (recommended) "
        "or `paddleocr paddlepaddle` to enable it."
    )
    _available = False
    return False


def is_available() -> bool:
    """Public flag: True if capture + OCR will work."""
    return _init()


def engine_name() -> Optional[str]:
    """Return the name of the selected backend, or None if unavailable."""
    _init()
    return _engine_name


def capture_region(bbox: Bbox):
    """Grab a rectangular screen region. Returns a PIL.Image, or None."""
    if not _init():
        return None
    try:
        return _ImageGrab.grab(bbox=tuple(bbox))
    except Exception as e:
        log.warning("capture_region(%r) failed: %s", bbox, e)
        return None


def _to_numpy(img):
    """Convert a PIL image to an RGB numpy array (both engines want np).

    Imported lazily so numpy is only required at the first OCR call.
    """
    import numpy as np  # local import
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


def _lines_from_paddleocr(result) -> List[str]:
    # PaddleOCR returns [[box, (text, conf)], ...] wrapped in an outer
    # list (one entry per image).
    if not result:
        return []
    out: List[str] = []
    inner = result[0] if result and isinstance(result[0], list) else result
    for item in inner or []:
        try:
            text = item[1][0].strip()
        except Exception:
            continue
        if text:
            out.append(text)
    return out


def ocr_image(img) -> str:
    """OCR a PIL image via the selected backend.

    The image goes through `fix_ocr.recolour_ui_labels()` first, which
    re-paints every pixel belonging to the game's rarity/epoch label
    palette (red, cyan, green, yellow, purple, teal, brown, orange) —
    including their anti-aliased halos — with a uniform dark blue so
    PaddleOCR reads them at consistent contrast. No-op on captures
    that contain no coloured labels, so it's safe to call always.

    Returns a `\\n`-joined string, one line per detected text box,
    top-to-bottom as returned by the engine. '' on failure.
    """
    if img is None or not _init():
        return ""
    try:
        # Image-level pre-processing (lives in fix_ocr for logical
        # grouping: every OCR-quality improvement is in that module).
        from .fix_ocr import recolour_ui_labels
        img = recolour_ui_labels(img)
        arr = _to_numpy(img)
        if _engine_name == "rapidocr":
            result, _elapsed = _engine(arr)                 # type: ignore[misc]
            lines = _lines_from_rapidocr(result)
        elif _engine_name == "paddleocr":
            result = _engine.ocr(arr, cls=False)            # type: ignore[attr-defined]
            lines = _lines_from_paddleocr(result)
        else:
            return ""
        return "\n".join(lines)
    except Exception as e:
        log.warning("ocr_image() failed (%s): %s", _engine_name, e)
        return ""


def run_ocr(bboxes: Sequence[Bbox]) -> str:
    """Capture + OCR each bbox, join results with blank lines.

    Empty / failed bboxes are silently skipped — the caller can detect
    'totally empty output' by checking the return string itself.
    """
    if not _init():
        return ""
    out: List[str] = []
    for bbox in bboxes:
        img = capture_region(bbox)
        if img is None:
            continue
        text = ocr_image(img).strip()
        if text:
            out.append(text)
    return "\n\n".join(out)
