"""
============================================================
  FORGE MASTER — Lv.NN cartouche extractor (popup variant)

  Single-cell popups (pet, mount, skill, equipment popup)
  carry the level as a small cartouche tucked into the
  bottom-left of the icon — visually separate from the rest
  of the popup chrome::

      ┌──────────────────────────────────┐
      │  [Ultimate] Stampede             │
      │  ┌────────┐                      │
      │  │  ICON  │   Cast on a bull...  │
      │  │        │                      │
      │  │ Lv.12  │   Passive:           │
      │  └────────┘   +43.4k Base Damage │
      └──────────────────────────────────┘

  Most of the time the full-popup OCR pass picks the badge up
  via the ``Lv\\.\\s*(\\d+)`` regex baked into
  ``parse_companion_meta`` / ``parse_skill_meta``. When the
  cartouche is small or has odd contrast, RapidOCR can drop
  it. This helper is the FALLBACK: it crops the bottom-left
  region of the popup capture, OCRs that strip on its own,
  and runs the same regex.

  Phase 3 jobs (pet/mount/skill) call ``extract_popup_level``
  only when ``parse_popup_metadata`` returns
  ``{"level": None}``. Phase 5 (equipment popup) will use the
  same helper from a tighter crop.

  Public API:

      extract_popup_level(capture, *, region=None) -> int | None
============================================================
"""

from __future__ import annotations

import logging
import re
from typing import Optional, Tuple

from PIL import Image

log = logging.getLogger(__name__)


# Default region for the Lv cartouche, expressed as fractions
# of the whole popup capture. Tuned conservatively: bottom-left
# 35 % of the popup, starting at 50 % of its height — wide
# enough to catch the cartouche on every popup variant we have
# screenshots for, narrow enough to avoid the description text.
# Job code can override via the ``region`` argument when the
# popup layout is known precisely (Phase 5 equipment popup).
_DEFAULT_REGION_FRAC: Tuple[float, float, float, float] = (
    0.00,   # left
    0.50,   # top
    0.35,   # right
    1.00,   # bottom
)


_RE_LV = re.compile(r"Lv\.?\s*(\d+)", re.IGNORECASE)


def _frac_to_box(size: Tuple[int, int],
                 frac: Tuple[float, float, float, float]
                 ) -> Tuple[int, int, int, int]:
    """Translate a (left, top, right, bottom) fraction tuple to
    pixel coordinates inside an image of the given size."""
    w, h = size
    l, t, r, b = frac
    return (
        max(0, int(w * l)),
        max(0, int(h * t)),
        min(w, int(w * r)),
        min(h, int(h * b)),
    )


def _crop(capture: Image.Image,
          region: Optional[Tuple[float, float, float, float]],
          ) -> Optional[Image.Image]:
    """Extract the cartouche subregion. Returns None if the
    crop would be empty (capture too small, region inverted)."""
    frac = region if region is not None else _DEFAULT_REGION_FRAC
    box = _frac_to_box(capture.size, frac)
    if box[2] <= box[0] or box[3] <= box[1]:
        return None
    return capture.crop(box)


def _run_ocr(crop: Image.Image,
             debug_zone: Optional[str] = None,
             debug_stamp: Optional[str] = None) -> str:
    """OCR a single crop. Returns ``""`` on any failure."""
    try:
        from scan import ocr as _ocr
    except Exception:  # pragma: no cover - defensive
        return ""
    if not _ocr.is_available():
        return ""
    try:
        return _ocr.ocr_image(
            crop,
            debug_stamp=debug_stamp,
            debug_zone=debug_zone,
        )
    except Exception:  # pragma: no cover - defensive
        log.exception("scan.jobs._lv: ocr_image() failed")
        return ""


def extract_popup_level(
    capture: Image.Image,
    *,
    region: Optional[Tuple[float, float, float, float]] = None,
    debug_zone: Optional[str] = None,
    debug_stamp: Optional[str] = None,
) -> Optional[int]:
    """Best-effort level extraction from a popup's Lv cartouche.

    Parameters
    ----------
    capture : PIL.Image.Image
        The full popup capture (same one the matcher consumes).
    region : (l, t, r, b) tuple of fractions, optional
        Override the default cartouche region. Each value is in
        ``[0, 1]`` and expresses a fraction of ``capture.size``.
        Defaults to ``(0.00, 0.50, 0.35, 1.00)`` — a box covering
        the bottom-left quadrant of the popup, wide enough for
        every layout we've seen.
    debug_zone, debug_stamp : Optional[str]
        Forwarded to ``ocr.ocr_image`` for project-wide debug
        dump infrastructure.

    Returns
    -------
    int | None
        The level integer when a ``Lv.NN`` substring is found;
        ``None`` otherwise. Callers should propagate ``None`` as
        ``level=0`` or whatever sentinel their data model uses.
    """
    if capture is None:
        return None
    crop = _crop(capture, region)
    if crop is None:
        return None
    text = _run_ocr(crop, debug_zone=debug_zone, debug_stamp=debug_stamp)
    if not text:
        return None
    m = _RE_LV.search(text)
    if not m:
        return None
    try:
        return int(m.group(1))
    except (TypeError, ValueError):  # pragma: no cover - regex guarantees digits
        return None


__all__ = [
    "extract_popup_level",
]
