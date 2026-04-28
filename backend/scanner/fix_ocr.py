"""
============================================================
  FORGE MASTER — OCR text fixer (extraction-based)

  Philosophy: DO NOT filter noise — extract signal.

  The input is raw OCR output (RapidOCR / PaddleOCR on
  BlueStacks captures). We walk the text line by line,
  recognise ONLY the known tokens (level badges, rarity
  names, flat stats, substats, keywords), normalise each
  one, and rebuild the output in the form the parser expects.
  Everything that matches no pattern is silently dropped.

  Benefits vs the old blacklist approach:
    - No _DROP_PATTERNS to maintain.
    - Immune by default to every new OCR artefact.
    - Double-scan de-duplication comes for free.
    - Canonical stat ordering comes for free.

  Public API:

      fix_ocr(text: str, context: Optional[str] = None) -> str

  Context values: "profile", "opponent", "item" / "equipment",
  "pet", "mount", "skill", or None (generic passthrough).
============================================================
"""

from __future__ import annotations

import difflib
import re
from typing import Any, Dict, List, NamedTuple, Optional


# ════════════════════════════════════════════════════════════
#  Image pre-processing — UI label re-colouring
# ════════════════════════════════════════════════════════════
# Forge Master renders rarity/epoch labels in a palette of
# saturated colours (red, cyan, green, yellow, purple, teal,
# brown, orange). PaddleOCR reads the darker colours fine but
# fails on the brightly-saturated glyphs because their luminance
# against the light UI backgrounds is too low for its default
# thresholds.
#
# Before OCR we therefore re-paint every pixel belonging to one
# of these label colours (including its anti-aliased halo) with
# a replacement colour. The text then becomes high-contrast and
# uniformly coloured — OCR reads it cleanly regardless of which
# tier/epoch the label originally belonged to.
#
# The replacement colour is NOT one-size-fits-all. A palette
# sweep (150 candidates × 29 ground-truth images, token-level F1
# vs debug_test/format.txt — see tools/ocr_color_sweep.py) showed
# that each UI zone has its own optimum:
#
#     equipment → #BFD2AC  (pastel olive)   F1 ≈ 0.336
#     pet       → #FF8C1A  (orange)         F1 ≈ 0.245
#     mount     → #1AFFFF  (cyan)           F1 ≈ 0.224
#     skill     → #4747D1  (blue)           F1 ≈ 0.211
#     (overall) → #E6E699  (pale yellow)    F1 ≈ 0.246
#
# Callers pick the zone-specific colour via ZONE_REPLACEMENT_COLORS
# and pass it to `recolour_ui_labels(img, replacement=…)`. If they
# don't, the default `LABEL_REPLACEMENT_COLOR` is used (the overall
# sweep winner, safe for profile/opponent where the text is black
# and no repainting actually happens).

LABEL_REPLACEMENT_COLOR = (0xE6, 0xE6, 0x99)  # pale yellow    (#E6E699)

# Per-zone override — values come from the OCR colour sweep
# (tools/ocr_color_sweep.py, summary in debug_test/). Zones not in
# this dict fall through to LABEL_REPLACEMENT_COLOR.
ZONE_REPLACEMENT_COLORS = {
    "equipment": (0xBF, 0xD2, 0xAC),  # pastel olive   (#BFD2AC)
    "pet":       (0xFF, 0x8C, 0x1A),  # orange         (#FF8C1A)
    "mount":     (0x1A, 0xFF, 0xFF),  # cyan           (#1AFFFF)
    "skill":     (0x47, 0x47, 0xD1),  # blue           (#4747D1)
}

# Forge Master UI label palette.
#
# ⚠ Light grey #E0E0E0 is intentionally EXCLUDED. It matches the
#   UI panel background of the second item card ("NEW!" row), so
#   enabling it repaints the entire panel blue and hides the real
#   text. Grey labels would need a glyph-vs-background detector
#   (e.g. anti-alias edge detection) to be safe — not worth the
#   complexity unless the game actually ships a grey-label tier.
UI_LABEL_COLORS = (
    (0xFF, 0x1C, 0x1C),  # red        — [Space]
    (0x1C, 0xAF, 0xFF),  # cyan       — [Medieval]
    (0x1C, 0xFF, 0x41),  # green      — [Early-Modern]
    (0xF8, 0xFF, 0x1C),  # yellow     — [Modern]
    (0xAA, 0x1C, 0xFF),  # purple     — [Interstellar]
    (0x2D, 0xFF, 0xDA),  # teal       — [Multiverse]
    (0x3B, 0x17, 0xD2),  # dark blue  — [Quantum]
    (0x6F, 0x30, 0x31),  # brown      — [Underworld]
    (0xFF, 0x57, 0x01),  # orange     — [Divine]
)

# Tunables for the hue matcher used by `recolour_ui_labels`.
# We use chroma = max(R,G,B) − min(R,G,B) as the "colourfulness"
# measure rather than distance-from-white. This is critical
# because the palette includes a desaturated colour (brown
# #6F3031) whose vector toward white is (144,207,206), almost
# parallel to a pure-grey pixel's (215,215,215). Using chroma
# instead — brown has chroma=63, every grey has chroma=0 —
# cleanly separates them.
_HUE_MIN_CHROMA = 20.0   # min (max−min) for a pixel to have "enough colour"
_HUE_COS_SIM    = 0.92   # min cosine similarity between pixel hue and target hue

# Number of erosion iterations used to detect "solid interior" regions
# inside the match mask. A pixel survives erosion iff it has N matching
# 4-neighbours in every direction, i.e. lies at least N pixels deep
# inside a same-colour blob. The "deep interior" found this way is
# SUBTRACTED from the mask before re-painting, so large saturated-colour
# backgrounds (highlighted/equipped card tiles, icon badge squares) do
# not get repainted alongside the glyphs.
#
# Glyph strokes at the rendered UI resolution are ~2–3 px wide, so they
# fully disappear from the eroded mask after 3 iterations (their
# interior is empty) and are preserved for re-painting. Anything thicker
# than ~7 px keeps a non-empty interior → excluded.
_MASK_EROSION_ITERATIONS = 3


def _build_match_mask(arr: Any, target: tuple) -> Any:
    """Boolean mask of pixels that match `target` colour (including halo).

    Detection is chroma-based: we compute each pixel's chroma vector
    `(R-min, G-min, B-min)` (normalised by chroma = max-min) and compare
    its direction against the target's by cosine similarity. A pixel
    matches iff:

        chroma ≥ _HUE_MIN_CHROMA   (rules out near-grey pixels)
        cos_sim ≥ _HUE_COS_SIM     (same hue as target)

    Why chroma and not distance-from-white? Because our palette mixes
    highly-saturated colours (red, cyan…) with a desaturated one
    (brown #6F3031). Brown's distance-from-white is (144, 207, 206) —
    almost parallel to a pure-grey pixel's (215, 215, 215). Using
    chroma avoids this: brown's chroma is 63, every grey's is 0.

    Halo-on-white handling: a blend `C*α + 255*(1-α)` has chroma
    `chroma(C)*α` — smaller magnitude, same direction. Halos within
    the `_HUE_MIN_CHROMA` band of colour thus match; halos fading
    further toward white drop below the threshold (and are visually
    near-white anyway, so OCR wouldn't have read them as glyph
    pixels).
    """
    import numpy as np

    tR, tG, tB = (float(c) for c in target)
    t_min = min(tR, tG, tB)
    t_chroma = max(tR, tG, tB) - t_min
    if t_chroma < 1.0:
        # Achromatic target (pure grey/white/black). Not supported by the
        # hue matcher — the caller should exclude these from the palette.
        return np.zeros(arr.shape[:2], dtype=bool)

    # Target's normalised chroma vector (one component = 1, others in [0,1]).
    dtR = (tR - t_min) / t_chroma
    dtG = (tG - t_min) / t_chroma
    dtB = (tB - t_min) / t_chroma
    t_mag = float(np.sqrt(dtR * dtR + dtG * dtG + dtB * dtB))

    R = arr[:, :, 0].astype(np.float32)
    G = arr[:, :, 1].astype(np.float32)
    B = arr[:, :, 2].astype(np.float32)

    p_min = np.minimum(np.minimum(R, G), B)
    p_max = np.maximum(np.maximum(R, G), B)
    p_chroma = p_max - p_min

    # Normalise by chroma, guarding against the fully-neutral case.
    safe = np.maximum(p_chroma, 1e-6)
    dpR = (R - p_min) / safe
    dpG = (G - p_min) / safe
    dpB = (B - p_min) / safe
    p_mag = np.sqrt(dpR * dpR + dpG * dpG + dpB * dpB)

    cos_sim = (dpR * dtR + dpG * dtG + dpB * dtB) / (p_mag * t_mag + 1e-6)

    return (p_chroma >= _HUE_MIN_CHROMA) & (cos_sim >= _HUE_COS_SIM)


def _erode_mask_4conn(mask: Any, iterations: int) -> Any:
    """4-connected binary erosion applied `iterations` times.

    A pixel survives one erosion step iff all four of its von Neumann
    neighbours (up, down, left, right) are also in the mask. Pixels on
    the image border treat out-of-bounds neighbours as "outside the
    mask" and therefore erode away, which is what we want (a blob
    touching the border cannot be distinguished from an interior one).

    Implemented with four shifted AND operations rather than a 2D
    convolution so it stays a tight numpy-only routine.
    """
    import numpy as np
    eroded = mask
    for _ in range(max(0, iterations)):
        next_mask = np.zeros_like(eroded)
        # Only keep pixels where the neighbour in each direction is also in the mask.
        # Slice-assignment is equivalent to the 4-connected AND of shifted masks.
        next_mask[1:-1, 1:-1] = (
            eroded[1:-1, 1:-1]
            & eroded[:-2, 1:-1]
            & eroded[2:,  1:-1]
            & eroded[1:-1, :-2]
            & eroded[1:-1, 2:]
        )
        eroded = next_mask
    return eroded


def recolour_ui_labels(img: Any, replacement: Optional[tuple] = None) -> Any:
    """Re-paint every UI-label pixel with `replacement` (or the default).

    Walks every target in `UI_LABEL_COLORS`, builds a boolean mask of
    matching pixels (via `_build_match_mask`), then paints the union of
    those masks with the replacement colour. Returns a new PIL image;
    the original is not modified. If no pixel matches (e.g. capture
    contains no coloured labels at all), returns the original image
    unchanged.

    `replacement` is an (R, G, B) tuple. When None, falls back to
    `LABEL_REPLACEMENT_COLOR`. Callers should usually pass the
    zone-specific value from `ZONE_REPLACEMENT_COLORS` — a colour
    sweep showed each zone has its own best replacement.

    Falls back silently to returning the input unchanged if numpy / PIL
    happen to be missing (should never happen at runtime since the OCR
    engine pulls them in anyway).
    """
    try:
        import numpy as np
        from PIL import Image
    except Exception:
        return img

    arr = np.array(img.convert("RGB"))

    mask = np.zeros(arr.shape[:2], dtype=bool)
    for target in UI_LABEL_COLORS:
        mask |= _build_match_mask(arr, target)

    if not mask.any():
        return img

    # Strip "solid interior" pixels from the mask. Some cards (notably
    # highlighted / equipped [Space] items) have a saturated red tile
    # as their background — the exact same hue as the label text. Without
    # this step, that entire tile matches the mask and gets repainted to
    # the replacement colour, wiping out the contrast between the now-
    # olive text and the now-olive background and producing garbled OCR
    # (e.g. "sdeas [aeeds]" instead of "[Space] Straps").
    #
    # Erosion by _MASK_EROSION_ITERATIONS peels that many pixels off the
    # mask's perimeter. Thin glyph strokes (~2–3 px wide) fully vanish
    # from the eroded mask → their interior set is empty → `mask & ~interior`
    # still covers the whole glyph. Thick solid blobs keep a non-empty
    # interior → we SUBTRACT it from the mask, leaving only a ~N-pixel
    # boundary ring that gets repainted. The blob's interior keeps its
    # original colour, so OCR still sees high-contrast glyphs (repainted)
    # against the untouched card background.
    interior = _erode_mask_4conn(mask, _MASK_EROSION_ITERATIONS)
    mask = mask & ~interior

    if not mask.any():
        return img

    arr[mask] = replacement if replacement is not None else LABEL_REPLACEMENT_COLOR
    return Image.fromarray(arr.astype("uint8"))


# ── Known stats (closed list) ────────────────────────────────
_KNOWN_STATS = (
    "Critical Chance", "Critical Damage",
    "Block Chance", "Health Regen",
    "Lifesteal", "Double Chance",
    "Melee Damage", "Ranged Damage",
    "Attack Speed", "Skill Damage", "Skill Cooldown",
    # 1-word names last (shortest match loses to longer prefix).
    "Damage", "Health",
)

# Canonical display order (matches the in-game stat sheet).
_STAT_ORDER = (
    "Critical Chance",
    "Critical Damage",
    "Block Chance",
    "Health Regen",
    "Lifesteal",
    "Double Chance",
    "Damage",
    "Melee Damage",
    "Ranged Damage",
    "Attack Speed",
    "Skill Damage",
    "Skill Cooldown",
    "Health",
)
_STAT_RANK: Dict[str, int] = {name: i for i, name in enumerate(_STAT_ORDER)}

# Longest-first so "Health Regen" wins over "Health" on prefix match.
_KNOWN_STATS_SORTED = tuple(sorted(_KNOWN_STATS, key=lambda s: -len(s)))

# CamelCase → spaced canonical. Applied BEFORE the generic
# "([a-z])([A-Z])" split so 1-word names survive intact.
_STAT_CAMEL_MAP = {
    "AttackSpeed":    "Attack Speed",
    "DoubleChance":   "Double Chance",
    "BlockChance":    "Block Chance",
    "HealthRegen":    "Health Regen",
    "MeleeDamage":    "Melee Damage",
    "RangedDamage":   "Ranged Damage",
    "SkillDamage":    "Skill Damage",
    "SkillCooldown":  "Skill Cooldown",
    "CriticalChance": "Critical Chance",
    "CriticalDamage": "Critical Damage",
    "BaseDamage":     "Base Damage",
    "BaseHealth":     "Base Health",
    "TotalDamage":    "Total Damage",
    "TotalHealth":    "Total Health",
}

# OCR typos that survive every other normalisation step.
_OCR_TYPOS = {
    "LiFesteal":  "Lifesteal",
    "LifFesteal": "Lifesteal",
    "Lifeste al": "Lifesteal",
    "LifeSteal":  "Lifesteal",
}


# ════════════════════════════════════════════════════════════
#  Known bracket labels — epochs + tier rarities
# ════════════════════════════════════════════════════════════
# Items in the game carry an "epoch" tag inside brackets
# (e.g. [Space] Saber, [Quantum] Black Gun). Skills / pets /
# mounts use the 6 tier rarities instead (e.g. [Ultimate]
# Stampede). Both share the same [Label] syntax, so we keep a
# single canonical list for OCR-typo correction.
#
# PaddleOCR is prone to mis-reading individual letters in these
# short labels (c→o, I→l, m→n …). `_fuzzy_bracket_label` below
# maps an OCR'd label back to its canonical spelling using a
# closest-match lookup against this list.

_KNOWN_EPOCHS = (
    "Primitive", "Medieval", "Early-Modern", "Modern",
    "Space", "Interstellar", "Multiverse", "Quantum",
    "Underworld", "Divine",
)
_KNOWN_TIERS = ("Common", "Rare", "Epic", "Legendary", "Ultimate", "Mythic")
_KNOWN_BRACKET_LABELS = _KNOWN_EPOCHS + _KNOWN_TIERS


def _bracket_norm(s: str) -> str:
    """Normalised form used for fuzzy matching: lowercase, no
    separators — so 'Early-Modern', 'Early Modern', 'early_modern'
    and 'earlymodern' all collapse to 'earlymodern'."""
    return re.sub(r"[\s\-_]", "", s).lower()


_KNOWN_BRACKET_NORM = {_bracket_norm(s): s for s in _KNOWN_BRACKET_LABELS}
# Pre-computed once — `difflib.get_close_matches` needs a sequence of
# candidates. Without this tuple we rebuilt `list(...keys())` on every
# _fuzzy_* call (which is hot — twice per OCR line).
_KNOWN_BRACKET_NORM_KEYS = tuple(_KNOWN_BRACKET_NORM.keys())


def _fuzzy_bracket_label(name: str) -> str:
    """Best-effort correction of OCR typos inside a [Label] bracket.

    Returns the canonical spelling when the input is close enough to a
    known epoch / tier rarity (ratio ≥ 0.75). Otherwise returns the
    input unchanged, so unrelated bracket contents (e.g. pet names in
    library files) pass through intact.
    """
    norm = _bracket_norm(name)
    if not norm:
        return name
    if norm in _KNOWN_BRACKET_NORM:
        return _KNOWN_BRACKET_NORM[norm]
    matches = difflib.get_close_matches(
        norm, _KNOWN_BRACKET_NORM_KEYS, n=1, cutoff=0.6)
    if matches:
        return _KNOWN_BRACKET_NORM[matches[0]]
    return name


def _fuzzy_bracket_label_strict(name: str) -> Optional[str]:
    """Same as _fuzzy_bracket_label but only returns a canonical label when
    the match is strong (ratio ≥ 0.8). Used by the "missing brackets"
    fallback below — we must NOT wrap arbitrary item words like 'Solar'
    or 'Saber' into [Space]/[Rare] by accident.
    """
    norm = _bracket_norm(name)
    if not norm:
        return None
    if norm in _KNOWN_BRACKET_NORM:
        return _KNOWN_BRACKET_NORM[norm]
    matches = difflib.get_close_matches(
        norm, _KNOWN_BRACKET_NORM_KEYS, n=1, cutoff=0.8)
    if matches:
        return _KNOWN_BRACKET_NORM[matches[0]]
    return None


# ════════════════════════════════════════════════════════════
#  Step 1 — Low-level normalisation
# ════════════════════════════════════════════════════════════

def _normalize_line(line: str) -> str:
    # Typos
    for wrong, right in _OCR_TYPOS.items():
        line = line.replace(wrong, right)

    # 1. LO / L0 → Lv.
    line = re.sub(r"\b[Ll][O0]\.?\s*(\d)", r"Lv. \1", line)

    # 2. Level prefix variants → "Lv. NN".
    line = re.sub(r"\b[Ll][Vv][.:\']?\s*(\d+)", r"Lv. \1", line)

    # 2bis. OCR 'o'/'O' mis-read as '0' inside a numeric token.
    #       Accepts a digit OR a decimal point on EITHER side so that
    #       both integer and fractional positions are covered:
    #         '23okDamage' → '230kDamage'
    #         '7.o4m'       → '7.04m'   (decimal-fraction zero)
    #         '1o.5'        → '10.5'    (units zero just before '.')
    #         '3ook'        → '300k'
    #         '1o2'         → '102'
    #       The neighbour character must be part of a numeric token
    #       (digit, '.', or k/m/b unit) so ordinary words like "Moo"
    #       or "foo" are never touched.
    line = re.sub(
        r"([\d.])([oO]+)(?=[\d.kmbKMB])",
        lambda m: m.group(1) + "0" * len(m.group(2)),
        line,
    )

    # 2ter. Parenthèses OCR → crochets : (Quantum] ou (Quantum) → [Quantum]
    line = re.sub(r"[\(\[]([A-Za-z][A-Za-z\s\-_]*?)[\)\]]", r"[\1]", line)

    # 3. Rarity bracket casing: [interstellar] → [Interstellar].
    line = re.sub(
        r"\[([a-z])([A-Za-z]*)\]",
        lambda m: "[" + m.group(1).upper() + m.group(2) + "]",
        line,
    )

    # 2quater. 'T' en début de mot suivi d'un label connu → crochet
    # TUltimate] → [Ultimate], TMedieval] → [Medieval]
    line = re.sub(
        r"(?<!\w)T([A-Za-z][A-Za-z\s\-_]*?\])",
        lambda m: "[" + _fuzzy_bracket_label(m.group(1).rstrip("]")) + "]",
        line,
    )

    # 3bis. Fuzzy-correct OCR typos inside [Label] brackets:
    #       [Spaoe] → [Space], [lnterstellar] → [Interstellar],
    #       [Quantun] → [Quantum], [Early Modern] → [Early-Modern].
    #       Unknown labels (pet names, skill names) pass through
    #       unchanged thanks to the 0.6 similarity cutoff.
    line = re.sub(
        r"\[\s*([A-Za-z][A-Za-z\s\-_]*?)\s*\]",
        lambda m: "[" + _fuzzy_bracket_label(m.group(1)) + "]",
        line,
    )

    # 3quater. Partial-bracket recovery. PaddleOCR sometimes keeps a
    #          MANGLED version of exactly one bracket while dropping
    #          (or garbling) the other:
    #              '(nterstellarj Adamantum'        → '[' dropped, ']' → 'j'
    #              'interstellarjimpactors'         → '[' dropped, ']' → 'j'
    #              'interstellar] PeluleSynchronizer' → '[' dropped, ']' kept
    #          Step 3bis needs BOTH brackets so those lines slip through,
    #          and step 3ter below bails out because a ']' / 'j' is still
    #          present.
    #
    #          We detect: optional broken-open char ( / l / I, a
    #          word (non-greedy), then a broken-close char ] / j / J / ).
    #          The word is fed to `_fuzzy_bracket_label_strict` (≥0.8
    #          cutoff) so random lines with incidental 'j' or ')' chars
    #          are never promoted — only true epoch/tier misreads are.
    if "[" not in line:
        m = re.match(r"^[\(lI]?([A-Za-z]+?)[\]jJ\)]\s*(.*)$", line)
        if m:
            canon = _fuzzy_bracket_label_strict(m.group(1))
            if canon:
                rest = m.group(2).strip()
                line = f"[{canon}] {rest}" if rest else f"[{canon}]"

    # 3ter. Bracket-LESS rarity fallback. PaddleOCR occasionally swallows
    #       the '[' and ']' glyphs entirely when the label is rendered
    #       in red on red-ish backgrounds (even after red→black). In
    #       that case the line arrives as 'Space Solarius Ring' or
    #       'Quantum Black Gun' — no brackets at all — and the parser
    #       drops it because it does not match _RE_RARITY.
    #
    #       If a line does NOT already contain '[' AND starts with a
    #       single word that is a STRONG (≥0.8) match for a known
    #       epoch or tier, we rebuild it as '[Epoch] Rest'. The strict
    #       cutoff prevents false positives on item names like
    #       'Solar Ring' or 'Diamond Saber' — only true misreads get
    #       promoted.
    if "[" not in line and "]" not in line:
        m = re.match(r"^([A-Za-z][A-Za-z\-]*)\s+(.+?)\s*$", line)
        if m:
            head_canon = _fuzzy_bracket_label_strict(m.group(1))
            rest = m.group(2).strip()
            # Only promote if the rest looks like an item / pet name
            # (starts with a capital letter), not a stat or number.
            if head_canon and rest and rest[0].isalpha() and rest[0].isupper():
                line = f"[{head_canon}] {rest}"

    # 4. Space after bracket glued to a word: "]Higgs" → "] Higgs".
    line = re.sub(r"\](\w)", r"] \1", line)

    # 5. Space between digit+unit and following letter:
    #    "210kDamage" → "210k Damage".
    line = re.sub(r"(\d[kmbKMB])([A-Za-z])", r"\1 \2", line)

    # 6. Space after % glued to a letter.
    line = re.sub(r"(%)([A-Za-z])", r"\1 \2", line)

    # 6bis. Space between digit and following letter (not k/m/b units).
    line = re.sub(r"(\d)([ac-jln-zAC-JLN-Z])", r"\1 \2", line)
    # And between lowercase letter and following digit.
    line = re.sub(r"([a-z])(\d)", r"\1 \2", line)

    # 6ter. Space after comma glued to next word.
    line = re.sub(r",([A-Za-z])", r", \1", line)

    # 7. Space before '(' glued to a word.
    line = re.sub(r"(\w)\(", r"\1 (", line)

    # 8. CamelCase whitelist (before generic split).
    for joined, spaced in _STAT_CAMEL_MAP.items():
        line = re.sub(r"\b" + joined + r"\b", spaced, line)

    # 9. Split passives glued by '+' or '-': "Damage+347k" → "Damage +347k",
    #    "Lifesteal-1.56%" → "Lifesteal -1.56%".
    line = re.sub(r"([A-Za-z])([+\-])(?=\d)", r"\1 \2", line)

    # 10. Generic CamelCase split for item / skill names.
    line = re.sub(r"([a-z])([A-Z])", r"\1 \2", line)

    # 11bis. Strip tout caractère parasite collé après une stat flat connue.
    # "1.84m Health A" → "1.84m Health"
    # "228k Damage/"   → "228k Damage"
    # "183k Damage V"  → "183k Damage"
    #
    # IMPORTANT: on doit préserver le qualifier "(ranged)" / "(melee)"
    # qui suit "Damage" pour les armes. On capture donc le qualifier
    # parenthésé optionnel et on le ré-injecte, puis on strippe les
    # parasites restants (y compris d'éventuels restes après le qualifier).
    line = re.sub(
        r"(\b(?:Health|Damage))(\s*\(\s*[A-Za-z]+\s*\))?\s*[^%\d\+\-\n\r\(\)]*$",
        lambda m: m.group(1) + (m.group(2) or ""),
        line,
    )

    # 12. Collapse whitespace and strip.
    line = re.sub(r"[ \t]+", " ", line).strip()
    return line


def _split_glued_stats(line: str) -> List[str]:
    """Split on internal '<space>[+-]<digit>' to separate glued stat
    pairs like '+43.4k Base Damage +347k Base Health' or
    '+15.5% Lifesteal -1.56% Skill Cooldown' into two sub-lines."""
    if not line:
        return []
    parts = re.split(r"\s+(?=[+\-]\d)", line)
    return [p.strip() for p in parts if p.strip()]


# ════════════════════════════════════════════════════════════
#  Step 2 — Pattern extraction
# ════════════════════════════════════════════════════════════

class Token(NamedTuple):
    kind: str
    text: str
    meta: dict


_RE_LV_FORGE  = re.compile(r"^Lv\.\s*(\d+)\s+Forge\s*$", re.IGNORECASE)
_RE_LV        = re.compile(r"^Lv\.\s*(\d+)\s*$", re.IGNORECASE)
_RE_RARITY    = re.compile(r"^\[\s*([A-Z][A-Za-z\-]*)\s*\]\s+(.+?)\s*$")
_RE_TOTAL_DMG = re.compile(r"^([\d.]+)\s*([kmb]?)\s+Total\s+Damage\s*$", re.IGNORECASE)
_RE_TOTAL_HP  = re.compile(r"^([\d.]+)\s*([kmb]?)\s+Total\s+Health\s*$", re.IGNORECASE)
_RE_FLAT_DMG  = re.compile(
    r"^([\d.]+)\s*([kmb]?)\s+Damage(?:\s*\(\s*([A-Za-z]+)\s*\))?\s*(?:\d+\s*)?$",
    re.IGNORECASE,
)
_RE_FLAT_HP   = re.compile(r"^([\d.]+)\s*([kmb]?)\s+Health\s*(?:\d+\s*)?$", re.IGNORECASE)
_RE_DEALING   = re.compile(r"^dealing\s+([\d.]+)\s*([kmb]?)\s+Damage\s*(?:to\b.*)?$", re.IGNORECASE)
_RE_BASE_DMG  = re.compile(r"^\+\s*([\d.]+)\s*([kmb]?)\s+Base\s+Damage\s*$", re.IGNORECASE)
_RE_BASE_HP   = re.compile(r"^\+\s*([\d.]+)\s*([kmb]?)\s+Base\s+Health\s*$", re.IGNORECASE)
_RE_SLASH     = re.compile(r"^(\d+)\s*/\s*(\d+)\s*$")
_RE_SUBSTAT   = re.compile(r"^([+\-])\s*([\d.]+)\s*%\s*(.+?)\s*$")
_RE_PASSIVE   = re.compile(r"^Passive\s*:\s*$", re.IGNORECASE)
_RE_NEW       = re.compile(r"^NEW\s*!\s*$", re.IGNORECASE)

# Keywords that are always dropped regardless of context.
_ALWAYS_DROP = {"equipped", "upgrade", "remove", "sell", "equip"}

# Noise patterns that disqualify a line from being kept as skill_text.
_RE_NOISE_SKILL = (
    re.compile(r"^\d+$"),
    re.compile(r"^[A-Za-z]$"),
    re.compile(r"^\d+\s*:\s*\d+$"),
)


def _fmt_unit(num: str, unit: str) -> str:
    return f"{num}{unit.lower()}" if unit else num


def _match_known_stat(tail: str) -> Optional[str]:
    tail_lower = tail.lower().strip().rstrip(" .,;:*")
    for stat in _KNOWN_STATS_SORTED:
        stat_lower = stat.lower()
        if tail_lower == stat_lower or tail_lower.startswith(stat_lower + " "):
            return stat
    return None


def _extract_tokens(lines: List[str], context: Optional[str]) -> List[Token]:
    tokens: List[Token] = []
    seen_rarity  = False
    seen_passive = False
    is_skill     = context == "skill"

    for line in lines:
        if not line:
            continue

        low = line.lower().strip()

        # Always-drop keywords (Equipped, Upgrade, Remove, Sell, Equip).
        if low in _ALWAYS_DROP:
            continue

        # NEW! — dropped everywhere (second item detected by second rarity).
        if _RE_NEW.match(line):
            continue

        # Passive: — skill context only.
        if _RE_PASSIVE.match(line):
            if is_skill:
                tokens.append(Token("passive", "Passive:", {}))
                seen_passive = True
            continue

        # Priority 1: "Lv. NN Forge" — dropped everywhere.
        m = _RE_LV_FORGE.match(line)
        if m:
            continue

        # Priority 2: "Lv. NN" — kept only in pet, mount, skill.
        m = _RE_LV.match(line)
        if m:
            if context in ("pet", "mount", "skill"):
                tokens.append(Token("lv", f"Lv. {m.group(1)}", {"level": int(m.group(1))}))
            continue

        # Priority 3: "[Rarity] Name".
        m = _RE_RARITY.match(line)
        if m:
            rarity = m.group(1).strip()
            name   = m.group(2).strip()
            tokens.append(Token("rarity_name", f"[{rarity}] {name}",
                                {"rarity": rarity, "name": name}))
            seen_rarity = True
            continue

        # Priority 4: "NN.N[kmb] Total Damage".
        m = _RE_TOTAL_DMG.match(line)
        if m:
            tokens.append(Token("total_dmg",
                                f"{_fmt_unit(m.group(1), m.group(2))} Total Damage", {}))
            continue

        # Priority 5: "NN.N[kmb] Total Health".
        m = _RE_TOTAL_HP.match(line)
        if m:
            tokens.append(Token("total_hp",
                                f"{_fmt_unit(m.group(1), m.group(2))} Total Health", {}))
            continue

        # Priority 11: "dealing NN.N[kmb] Damage" (before flat_dmg to avoid clash).
        m = _RE_DEALING.match(line)
        if m:
            tokens.append(Token("dealing",
                                f"dealing {_fmt_unit(m.group(1), m.group(2))} Damage", {}))
            continue

        # Priority 6: "NN.N[kmb] Damage [(ranged)]".
        m = _RE_FLAT_DMG.match(line)
        if m:
            base      = f"{_fmt_unit(m.group(1), m.group(2))} Damage"
            qualifier = m.group(3) or ""
            text      = f"{base} ({qualifier.lower()})" if qualifier else base
            tokens.append(Token("flat_dmg", text,
                                {"attack_type": qualifier.lower() or None}))
            continue

        # Priority 7: "NN.N[kmb] Health".
        m = _RE_FLAT_HP.match(line)
        if m:
            tokens.append(Token("flat_hp",
                                f"{_fmt_unit(m.group(1), m.group(2))} Health", {}))
            continue

        # Priority 9: "+NN.N[kmb] Base Damage".
        m = _RE_BASE_DMG.match(line)
        if m:
            tokens.append(Token("base_dmg",
                                f"+{_fmt_unit(m.group(1), m.group(2))} Base Damage", {}))
            continue

        # Priority 10: "+NN.N[kmb] Base Health".
        m = _RE_BASE_HP.match(line)
        if m:
            tokens.append(Token("base_hp",
                                f"+{_fmt_unit(m.group(1), m.group(2))} Base Health", {}))
            continue

        # Priority 12: "NN/NN" — dropped everywhere.
        m = _RE_SLASH.match(line)
        if m:
            continue

        # Priority 8: "+NN.N% <known stat>"  or  "-NN.N% <known stat>".
        m = _RE_SUBSTAT.match(line)
        if m:
            sign  = m.group(1)
            value = m.group(2)
            stat  = _match_known_stat(m.group(3))
            if stat:
                tokens.append(Token("substat", f"{sign}{value}% {stat}",
                                    {"stat": stat, "value": value, "sign": sign}))
            continue  # unknown stat tail → dropped silently

        # Priority 16: free skill text (skill context, before Passive:).
        if is_skill and seen_rarity and not seen_passive:
            if not any(p.match(line) for p in _RE_NOISE_SKILL):
                tokens.append(Token("skill_text", line, {}))

        # Anything else: silently dropped.

    return tokens


# ════════════════════════════════════════════════════════════
#  Step 3 — Context-specific post-processing
# ════════════════════════════════════════════════════════════

def _dedupe(tokens: List[Token]) -> List[Token]:
    seen: set = set()
    out: List[Token] = []
    for t in tokens:
        if t.text in seen:
            continue
        seen.add(t.text)
        out.append(t)
    return out


# -- profile / opponent -------------------------------------------------

def _post_profile(tokens: List[Token]) -> List[str]:
    kept = [t for t in tokens if t.kind in ("total_dmg", "total_hp", "substat")]
    kept = _dedupe(kept)
    totals   = [t for t in kept if t.kind in ("total_dmg", "total_hp")]
    substats = [t for t in kept if t.kind == "substat"]
    substats.sort(key=lambda t: _STAT_RANK.get(t.meta.get("stat", ""), 99))
    return [t.text for t in totals + substats]


# -- item ---------------------------------------------------------------

def _post_item(tokens: List[Token]) -> List[str]:
    """item layout (per item):
        [Rarity] Name
        flat value(s)
        +substats
    No Lv., no Equipped, no Sell, no Equip, no NEW!
    (all already dropped in _extract_tokens).
    """
    out: List[str] = []
    for t in tokens:
        if t.kind in ("rarity_name", "flat_dmg", "flat_hp", "substat"):
            out.append(t.text)
    return out


# -- pet / mount --------------------------------------------------------

def _post_companion(tokens: List[Token], default_lv: int = 1) -> List[str]:
    """pet/mount: Lv. → [Rarity] Name → flats → substats.
    Synthesises 'Lv. 1' if OCR missed the level badge."""
    out: List[str] = []
    lv     = next((t for t in tokens if t.kind == "lv"), None)
    rarity = next((t for t in tokens if t.kind == "rarity_name"), None)

    if rarity:
        out.append(lv.text if lv else f"Lv. {default_lv}")
        out.append(rarity.text)
    elif lv:
        out.append(lv.text)

    for t in tokens:
        if t.kind in ("flat_dmg", "flat_hp"):
            out.append(t.text)
    for t in tokens:
        if t.kind == "substat":
            out.append(t.text)

    return out


# -- skill --------------------------------------------------------------

def _post_skill(tokens: List[Token]) -> List[str]:
    """skill layout (strict — narrative/flavor text is dropped):
        Lv. NN
        [Rarity] Name
        dealing NN.N[kmb] Damage
        Passive:
        +Base Damage +Base Health   (combined on one line)
    """
    out: List[str] = []

    lv = next((t for t in tokens if t.kind == "lv"), None)
    if lv:
        out.append(lv.text)

    rarity = next((t for t in tokens if t.kind == "rarity_name"), None)
    if rarity:
        out.append(rarity.text)

    # Narrative "skill_text" tokens are intentionally NOT emitted.
    # The simulator only needs the structural lines below.

    for t in tokens:
        if t.kind == "dealing":
            out.append(t.text)

    passive = next((t for t in tokens if t.kind == "passive"), None)
    if passive:
        out.append(passive.text)

    base_d = next((t for t in tokens if t.kind == "base_dmg"), None)
    base_h = next((t for t in tokens if t.kind == "base_hp"),  None)
    if base_d and base_h:
        out.append(f"{base_d.text} {base_h.text}")
    elif base_d:
        out.append(base_d.text)
    elif base_h:
        out.append(base_h.text)

    return out


# -- default (no context) -----------------------------------------------

def _post_default(tokens: List[Token]) -> List[str]:
    """No reordering — emit tokens in original order.
    Recombines adjacent Base Damage / Base Health onto one line."""
    out: List[str] = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if (t.kind == "base_dmg"
                and i + 1 < len(tokens)
                and tokens[i+1].kind == "base_hp"):
            out.append(f"{t.text} {tokens[i+1].text}")
            i += 2
            continue
        out.append(t.text)
        i += 1
    return out


# ════════════════════════════════════════════════════════════
#  Public entry point
# ════════════════════════════════════════════════════════════

def fix_ocr(text: str, context: Optional[str] = None) -> str:
    """Extract known tokens from raw OCR output, reformat per context.

    `context` selects the post-processing strategy:
      - "profile" / "opponent" : keep only Total Damage/Health + known
        substats, dedupe, reorder substats into canonical in-game order.
      - "item"                 : [Rarity] Name → flats → substats,
        repeated for each item. No level, no UI keywords.
      - "pet" / "mount"        : Lv. → [Rarity] Name → flats → substats.
        Synthesises "Lv. 1" if OCR missed the level badge.
      - "skill"                : Lv. → [Rarity] Name → description →
        dealing → Passive: → +Base Damage +Base Health.
      - None / other           : generic passthrough (original order).

    The transform is idempotent on well-formed input.
    """
    if not text:
        return ""

    # Step 1: normalise each raw line, then split glued stat pairs.
    normalised: List[str] = []
    for raw in text.splitlines():
        line = _normalize_line(raw)
        normalised.extend(_split_glued_stats(line))

    # Step 2: extract typed tokens.
    tokens = _extract_tokens(normalised, context)

    # Step 3: context-specific post-processing.
    # Note: "equipment" is the zone-key used everywhere else in the
    # codebase (see ZONE_DEFAULTS in constants.py); it maps to the
    # same item-shaped output as "item".
    if context in ("profile", "opponent"):
        out_lines = _post_profile(tokens)
    elif context in ("item", "equipment"):
        out_lines = _post_item(tokens)
    elif context in ("pet", "mount"):
        out_lines = _post_companion(tokens, default_lv=1)
    elif context == "skill":
        out_lines = _post_skill(tokens)
    else:
        out_lines = _post_default(tokens)

    return "\n".join(out_lines)
