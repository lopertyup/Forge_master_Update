"""
============================================================
  FORGE MASTER UI — Shared theme
  Single source for colors, fonts, labels and icons.
  Every view should import from here rather than duplicate
  the constants. If a value is missing for a one-off use,
  add it here instead of redefining it locally.
============================================================
"""

import logging
import os
from functools import lru_cache
from typing import Optional

import customtkinter as ctk
from PIL import Image

from data.canonical import AGE_INT_TO_NAME, EQUIPMENT_SLOT_TO_ICON_FOLDER

log = logging.getLogger(__name__)

# ── Icon paths (relative to ui/theme.py) ─────────────────────
# All icons live under data/icons/ (cf. data/README-DATA.txt §2.E):
#     data/icons/skills/<SpriteName>.png
#     data/icons/pets/<SpriteName>.png
#     data/icons/mount/<SpriteName>.png
#     data/icons/equipment/<Age>/<Slot>/<SpriteName>.png
# The SpriteName used for lookup MUST match the value stored in
# Auto{Skill,Pet,Mount,Item}Mapping.json. Display names with spaces
# and capitalised words are preserved verbatim (e.g. "Saber Tooth.png",
# "Cannon Barrage.png", "Brown Horse.png"). No name normalisation.
_UI_DIR             = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR           = os.path.dirname(_UI_DIR)
_DATA_ICONS_DIR     = os.path.join(_ROOT_DIR, "data", "icons")
SKILL_ICONS_DIR     = os.path.join(_DATA_ICONS_DIR, "skills")
PET_ICONS_DIR       = os.path.join(_DATA_ICONS_DIR, "pets")
MOUNT_ICONS_DIR     = os.path.join(_DATA_ICONS_DIR, "mount")
EQUIPMENT_ICONS_DIR = os.path.join(_DATA_ICONS_DIR, "equipment")
# Backwards-compatible alias used historically by load_icon().
ICONS_DIR           = SKILL_ICONS_DIR


# ── Palette ──────────────────────────────────────────────────

C = {
    "bg":        "#0D0F14",
    "surface":   "#151820",
    "card":      "#1C2030",
    "card_alt":  "#232840",
    "border":    "#2A2F45",
    "border_hl": "#3A3F55",
    "accent":    "#E8593C",
    "accent_hv": "#c94828",
    "accent2":   "#F2A623",
    "text":      "#E8E6DF",
    "muted":     "#7A7F96",
    "disabled":  "#3A3F55",
    "selected":  "#1a2e1a",
    "win":       "#2ECC71",
    "win_hv":    "#27ae60",
    "lose":      "#E74C3C",
    "lose_hv":   "#c0392b",
    "draw":      "#F39C12",
    # rarities
    "rare":      "#2196F3",
    "epic":      "#9C27B0",
    "legendary": "#FF9800",
    "ultimate":  "#F44336",
    "mythic":    "#E91E63",
    "common":    "#9E9E9E",
}


# ── Fonts ────────────────────────────────────────────────────

FONT_TITLE  = ("Segoe UI", 20, "bold")
FONT_H1     = ("Segoe UI", 22, "bold")  # window / logo titles
FONT_BIG    = ("Segoe UI", 26, "bold")  # hero numbers
FONT_HUGE   = ("Segoe UI", 28, "bold")  # simulator counters
FONT_SUB    = ("Segoe UI", 13, "bold")
FONT_NAV    = ("Segoe UI", 13, "bold")
FONT_BODY   = ("Segoe UI", 13)
FONT_SMALL  = ("Segoe UI", 11)
FONT_TINY   = ("Segoe UI", 9, "bold")
FONT_MONO   = ("Consolas", 12)
FONT_MONO_S = ("Consolas", 11)


# ── Stat labels (shared everywhere) ──────────────────────────

STAT_LABELS = {
    # Flat stats (shown first on profile / equipment / pet / mount cards)
    "hp_flat":         "❤  HP",
    "damage_flat":     "⚔  Damage",
    "hp_total":        "❤  Total HP",
    "attack_total":    "⚔  Total ATK",
    "hp_base":         "❤  Base HP",
    "attack_base":     "⚔  Base ATK",
    # Substats — canonical in-game order
    "crit_chance":     "🎯 Crit Chance",
    "crit_damage":     "💥 Crit Damage",
    "block_chance":    "🛡  Block Chance",
    "health_regen":    "♻  Health Regen",
    "lifesteal":       "🩸 Lifesteal",
    "double_chance":   "✌  Double Chance",
    "damage_pct":      "⚔  Damage %",
    "melee_pct":       "⚔  Melee %",
    "ranged_pct":      "⚔  Ranged %",
    "attack_speed":    "⚡ Attack Speed",
    "skill_damage":    "✨ Skill Damage",
    "skill_cooldown":  "⏱  Skill CD",
    "health_pct":      "❤  Health %",
}

FLAT_STAT_KEYS = ("hp_flat", "damage_flat", "hp_total", "attack_total",
                  "hp_base", "attack_base")


# ── Canonical stat display order (used everywhere we render stats) ──
# Flat stats first (in their natural order), then substats in the
# exact order the game uses in its stat panel. Any key not listed
# here sorts after, alphabetically — a safety net for new stats.
STAT_DISPLAY_ORDER = (
    # Flat / totals
    "hp_flat", "damage_flat",
    "hp_total", "attack_total",
    "hp_base",  "attack_base",
    # Substats — canonical in-game order
    "crit_chance",
    "crit_damage",
    "block_chance",
    "health_regen",
    "lifesteal",
    "double_chance",
    "damage_pct",
    "melee_pct",
    "ranged_pct",
    "attack_speed",
    "skill_damage",
    "skill_cooldown",
    "health_pct",
)

_STAT_ORDER_INDEX = {k: i for i, k in enumerate(STAT_DISPLAY_ORDER)}


def stat_sort_key(key: str) -> tuple:
    """Sort key for stat dicts → canonical in-game display order.

    Unknown keys go last, alphabetically, so a typo never hides a stat.
    """
    idx = _STAT_ORDER_INDEX.get(key)
    if idx is None:
        return (len(STAT_DISPLAY_ORDER), str(key))
    return (idx, str(key))


def sorted_stats(stats):
    """Yield ``(key, value)`` from a stat dict in canonical order.

    Keeps identity keys (leading ``__``) out. Doesn't filter zero values
    — caller decides whether to skip those.
    """
    for k, v in sorted(stats.items(), key=lambda kv: stat_sort_key(kv[0])):
        if isinstance(k, str) and k.startswith("__"):
            continue
        yield k, v


# ── Rarities (display order) ─────────────────────────────────

RARITY_ORDER = ["common", "rare", "epic", "legendary", "ultimate", "mythic"]


def rarity_color(rarity: str) -> str:
    return C.get(str(rarity).lower(), C["common"])


# ── Pet / mount icons ────────────────────────────────────────

PET_ICONS   = {"PET1": "🐉", "PET2": "🦅", "PET3": "🐺"}
MOUNT_ICON  = "🐴"


# ── Icon loading (cached) ────────────────────────────────────

@lru_cache(maxsize=512)
def _load_icon_from(directory: str, code: str, size: int) -> Optional[ctk.CTkImage]:
    """Generic internal helper — cached by (directory, code, size)."""
    path = os.path.join(directory, f"{code}.png")
    if not os.path.isfile(path):
        return None
    try:
        img = Image.open(path).convert("RGBA").resize((size, size), Image.LANCZOS)
        return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
    except Exception as e:
        log.warning("load_icon(%r, %r, %d) failed: %s", directory, code, size, e)
        return None


def load_icon(code: str, size: int = 48) -> Optional[ctk.CTkImage]:
    """Load a skill icon from data/icons/skills/. None if absent.

    Back-compat shim — prefer load_skill_icon_by_name in new code.
    """
    return _load_icon_from(SKILL_ICONS_DIR, code, size)


def load_skill_icon_by_name(name: str, size: int = 48) -> Optional[ctk.CTkImage]:
    """
    Load a skill icon by its display NAME from
    ``data/icons/skills/<Name>.png``. The name must match the
    SpriteName field in ``data/AutoSkillMapping.json`` (display name
    with spaces). Returns None if the file is absent.
    """
    if not name:
        return None
    return _load_icon_from(SKILL_ICONS_DIR, name.strip(), size)


def load_pet_icon(name: str, size: int = 48) -> Optional[ctk.CTkImage]:
    """Load a pet icon from ``data/icons/pets/<Name>.png``.

    The name must match the SpriteName field in
    ``data/AutoPetMapping.json`` (display name with spaces, e.g.
    ``"Saber Tooth"``). Returns None if absent.
    """
    if not name:
        return None
    return _load_icon_from(PET_ICONS_DIR, name.strip(), size)


def load_mount_icon(name: str, size: int = 48) -> Optional[ctk.CTkImage]:
    """Load a mount icon from ``data/icons/mount/<Name>.png``.

    The name must match the SpriteName field in
    ``data/AutoMountMapping.json`` (display name with spaces, e.g.
    ``"Brown Horse"``). Returns None if absent.
    """
    if not name:
        return None
    return _load_icon_from(MOUNT_ICONS_DIR, name.strip(), size)


# Internal age-int → folder name map (mirror of
# data.libraries.AGE_INT_TO_FOLDER — duplicated here so the UI
# stays decoupled from the backend, cf. UI_REFACTOR_PLAN P1).
_AGE_INT_TO_FOLDER = dict(AGE_INT_TO_NAME)

# Two slot vocabularies are accepted:
#  - the canonical EQUIPMENT_SLOTS keys used by the backend
#    (Helmet / Body / Gloves / Necklace / Ring / Weapon / Shoe / Belt),
#  - the TypeName values used by data/AutoItemMapping.json
#    (Helmet / Armour / Gloves / Necklace / Ring / Weapon / Shoes / Belt).
# Both must resolve to the actual folder names under
# data/icons/equipment/<Age>/.
_SLOT_TO_FOLDER = dict(EQUIPMENT_SLOT_TO_ICON_FOLDER)


def load_equipment_icon(age, slot: str, sprite_name: str,
                         size: int = 48) -> Optional[ctk.CTkImage]:
    """Load an equipment icon from
    ``data/icons/equipment/<Age>/<Slot>/<SpriteName>.png``.

    `age` may be an int (0-9) or the folder name directly.
    `slot` is the canonical equipment slot key (Helmet / Body / ...).
    `sprite_name` must match the SpriteName field in
    ``data/AutoItemMapping.json``. Returns None if absent.
    """
    if not sprite_name:
        return None
    age_folder = _AGE_INT_TO_FOLDER.get(age, str(age)) if isinstance(age, int) \
        else str(age)
    slot_folder = _SLOT_TO_FOLDER.get(slot, str(slot))
    directory = os.path.join(EQUIPMENT_ICONS_DIR, age_folder, slot_folder)
    return _load_icon_from(directory, sprite_name.strip(), size)


# ── Formatting helpers ───────────────────────────────────────

def fmt_number(n: float) -> str:
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return f"{n:.0f}"


def fmt_stat(key: str, value: float) -> str:
    """Format a stat value depending on whether it is flat or a percentage."""
    if key in FLAT_STAT_KEYS:
        return fmt_number(value)
    return f"+{value}%"


# Back-compat alias
fmt_nombre = fmt_number
