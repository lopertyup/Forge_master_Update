"""OCR facade used by scan jobs."""

from __future__ import annotations

from .engine import capture_and_ocr, capture_region, is_available, ocr_image, run_ocr
from .fix import fix_ocr
from . import debug

__all__ = [
    "is_available",
    "capture_region",
    "capture_and_ocr",
    "ocr_image",
    "run_ocr",
    "fix_ocr",
    "debug",
]
