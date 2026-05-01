"""
============================================================
  FORGE MASTER — Popup title / metadata extractor

  Single-cell popups (pet, mount, skill, equipment) all carry
  a textual header line of the shape::

      [Ultimate] Stampede
      [Rare]     Crab
      [Quantum]  Energy Helmet

  …followed by a ``Lv.NN`` badge somewhere in the popup. This
  helper runs OCR on the WHOLE popup capture once and extracts
  the three pieces of metadata downstream jobs need:

      tag    — the contents of the [<X>] bracket, exactly as
               OCR'd (case preserved). For pet/mount/skill this
               is the rarity name; for equipment popups it is
               the age name. ``None`` when the bracket is
               missing or unreadable.
      name   — the in-game item name (text after the bracket).
               Passed to ``scan.core.match`` as ``ocr_name`` to
               boost the matcher's text-similarity component.
               ``None`` when nothing parseable was found.
      level  — integer extracted from a ``Lv.NN`` substring
               anywhere in the popup. ``None`` when missing.
      raw    — the full OCR'd text (post fix_ocr) in case a
               caller wants to do additional regex work
               (skill description, passives, etc.).

  The parsers in ``scan.ocr.parsers`` already
  encode the regex bestiary for these popups; we delegate to
  them rather than duplicate the patterns. The OCR pass goes
  through ``scan.ocr.ocr_image`` so the recolour /
  threshold tricks calibrated for in-game UI labels apply.

  Public API:

      parse_popup_metadata(capture, kind="companion")
          -> {tag, name, level, raw}

  ``kind="skill"`` selects ``parse_skill_meta`` (different
  passive-block handling); any other value uses
  ``parse_companion_meta`` which is the right parser for
  pet/mount popups (and a safe fallback for equipment popups
  too — they share the ``[Rarity] Name`` + ``Lv.NN`` shape).
============================================================
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from PIL import Image

log = logging.getLogger(__name__)


def _ocr_full_popup(capture: Image.Image,
                    *,
                    debug_zone: Optional[str] = None,
                    debug_stamp: Optional[str] = None) -> str:
    """OCR the entire popup capture via the shared OCR module.

    Lazy-imports ``scan.ocr`` so ``scan.jobs._title``
    can be imported in headless tests without Pillow + RapidOCR.

    Returns ``""`` when the OCR backend is unavailable; callers
    treat the empty string as "no balise found" and fall back to
    colour heuristics.
    """
    try:
        from scan import ocr as _ocr
    except Exception:  # pragma: no cover - defensive
        log.warning("scan.jobs._title: scan.ocr unavailable")
        return ""

    if not _ocr.is_available():
        return ""
    try:
        return _ocr.ocr_image(
            capture,
            debug_stamp=debug_stamp,
            debug_zone=debug_zone,
        )
    except Exception:  # pragma: no cover - defensive
        log.exception("scan.jobs._title: ocr_image() failed")
        return ""


def _normalise_text(raw: str, *, context: Optional[str] = None) -> str:
    """Run the project's ``fix_ocr`` normaliser when available.

    The normaliser fixes the ``Lv .12`` / ``[Ultimate ]`` /
    ``Stampede.`` artefacts the engine routinely emits and is
    already battle-tested on the existing OCR popups. Falls back
    to the raw text on import or runtime errors.
    """
    if not raw:
        return ""
    try:
        from scan.ocr.fix import fix_ocr
    except Exception:  # pragma: no cover - defensive
        return raw
    try:
        return fix_ocr(raw, context=context)
    except Exception:  # pragma: no cover - defensive
        log.exception("scan.jobs._title: fix_ocr() failed — using raw text")
        return raw


def _parse_meta(text: str, *, kind: str) -> Dict[str, Any]:
    """Delegate to the legacy text parsers.

    Both ``parse_companion_meta`` and ``parse_skill_meta``
    return a dict with keys ``name``, ``rarity``, ``level`` (and
    a few stat fields we ignore here). The caller treats the
    ``rarity`` value as the bracket tag — for equipment popups
    the same regex matches an age name.
    """
    if not text:
        return {"name": None, "rarity": None, "level": None}

    try:
        from scan.ocr.parsers import (
            parse_companion_meta,
            parse_skill_meta,
        )
    except Exception:  # pragma: no cover - defensive
        log.exception("scan.jobs._title: text_parser unavailable")
        return {"name": None, "rarity": None, "level": None}

    if kind == "skill":
        meta = parse_skill_meta(text)
    else:
        meta = parse_companion_meta(text)
    return {
        "name":   meta.get("name"),
        "rarity": meta.get("rarity"),
        "level":  meta.get("level"),
    }


# ────────────────────────────────────────────────────────────
#  Public API
# ────────────────────────────────────────────────────────────


def parse_popup_metadata(
    capture: Image.Image,
    *,
    kind: str = "companion",
    debug_zone: Optional[str] = None,
    debug_stamp: Optional[str] = None,
) -> Dict[str, Any]:
    """OCR a popup capture and return its parsed metadata.

    Parameters
    ----------
    capture : PIL.Image.Image
        The full popup capture (the same image the matcher will
        autocrop down to the icon sprite). The OCR pass needs
        the whole popup so it can read both the title bar and
        the ``Lv.NN`` cartouche bottom-left of the icon.
    kind : str
        ``"skill"`` to apply ``parse_skill_meta`` (handles the
        passive block); anything else (default ``"companion"``)
        applies ``parse_companion_meta`` which is the right
        parser for pet / mount / equipment popups.
    debug_zone, debug_stamp : Optional[str]
        Forwarded to ``ocr.ocr_image`` for the project-wide
        debug-scan dump infrastructure.

    Returns
    -------
    dict
        ``{"tag": str | None, "name": str | None,
           "level": int | None, "raw": str}``

        ``tag`` is the contents of the ``[<X>]`` bracket. The
        legacy parsers lower-case it; we re-capitalise so the
        rest of ``scan/`` can use the canonical
        ``RARITY_NAMES`` / ``AGE_NAME_TO_INT`` lookups directly.
    """
    raw = _ocr_full_popup(
        capture,
        debug_zone=debug_zone,
        debug_stamp=debug_stamp,
    )
    text = _normalise_text(raw, context=debug_zone)
    meta = _parse_meta(text, kind=kind)

    # The legacy parsers return rarity/age lower-cased ("rare",
    # "ultimate", "modern", ...). Our reference tables use
    # capitalised forms ("Rare", "Ultimate", "Modern"). Normalise
    # at the boundary so callers stay simple.
    tag_lc = meta["rarity"]
    tag = tag_lc.title() if tag_lc else None

    name = meta["name"] or None
    level = meta["level"]

    return {
        "tag":   tag,
        "name":  name,
        "level": level,
        "raw":   text,
    }


__all__ = [
    "parse_popup_metadata",
]
