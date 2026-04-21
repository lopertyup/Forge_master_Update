"""
============================================================
  FORGE MASTER UI — Thème partagé
  Source unique pour les couleurs, polices, labels et icônes.
  Toute vue doit importer d'ici plutôt que dupliquer les
  constantes. Si une valeur manque pour un usage ponctuel,
  ajoute-la ici au lieu de la redéfinir localement.
============================================================
"""

import logging
import os
from functools import lru_cache
from typing import Optional

import customtkinter as ctk
from PIL import Image

log = logging.getLogger(__name__)

# ── Chemin des icônes (relatif à ui/theme.py) ────────────────
_UI_DIR         = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR       = os.path.dirname(_UI_DIR)
ICONS_DIR       = os.path.join(_ROOT_DIR, "skill_icons")
PET_ICONS_DIR   = os.path.join(_ROOT_DIR, "pet_icons")
MOUNT_ICONS_DIR = os.path.join(_ROOT_DIR, "mount_icons")


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
    # raretés
    "rare":      "#2196F3",
    "epic":      "#9C27B0",
    "legendary": "#FF9800",
    "ultimate":  "#F44336",
    "mythic":    "#E91E63",
    "common":    "#9E9E9E",
}


# ── Polices ──────────────────────────────────────────────────

FONT_TITLE  = ("Segoe UI", 20, "bold")
FONT_H1     = ("Segoe UI", 22, "bold")  # titres de fenêtres/logos
FONT_BIG    = ("Segoe UI", 26, "bold")  # chiffres héros
FONT_HUGE   = ("Segoe UI", 28, "bold")  # compteurs simulateur
FONT_SUB    = ("Segoe UI", 13, "bold")
FONT_NAV    = ("Segoe UI", 13, "bold")
FONT_BODY   = ("Segoe UI", 13)
FONT_SMALL  = ("Segoe UI", 11)
FONT_TINY   = ("Segoe UI", 9, "bold")
FONT_MONO   = ("Consolas", 12)
FONT_MONO_S = ("Consolas", 11)


# ── Labels des stats (partagé partout) ──────────────────────

STAT_LABELS = {
    "hp_flat":         "❤  HP",
    "damage_flat":     "⚔  Damage",
    "hp_total":        "❤  HP Total",
    "attaque_total":   "⚔  ATQ Total",
    "hp_base":         "❤  HP Base",
    "attaque_base":    "⚔  ATQ Base",
    "health_pct":      "❤  Health %",
    "damage_pct":      "⚔  Damage %",
    "melee_pct":       "⚔  Melee %",
    "ranged_pct":      "⚔  Ranged %",
    "taux_crit":       "🎯 Crit Chance",
    "degat_crit":      "💥 Crit Damage",
    "health_regen":    "♻  Health Regen",
    "lifesteal":       "🩸 Lifesteal",
    "double_chance":   "✌  Double Chance",
    "vitesse_attaque": "⚡ Attack Speed",
    "skill_damage":    "✨ Skill Damage",
    "skill_cooldown":  "⏱  Skill CD",
    "chance_blocage":  "🛡  Block Chance",
}

FLAT_STAT_KEYS = ("hp_flat", "damage_flat", "hp_total", "attaque_total",
                  "hp_base", "attaque_base")


# ── Raretés (ordre d'affichage) ──────────────────────────────

RARITY_ORDER = ["common", "rare", "epic", "legendary", "ultimate", "mythic"]


def rarity_color(rarity: str) -> str:
    return C.get(str(rarity).lower(), C["common"])


# ── Icônes pets / mount ──────────────────────────────────────

PET_ICONS   = {"PET1": "🐉", "PET2": "🦅", "PET3": "🐺"}
MOUNT_ICON  = "🐴"


# ── Chargement d'icônes (cache) ──────────────────────────────

@lru_cache(maxsize=512)
def _load_icon_from(directory: str, code: str, size: int) -> Optional[ctk.CTkImage]:
    """Helper interne générique — cache par (directory, code, size)."""
    path = os.path.join(directory, f"{code}.png")
    if not os.path.isfile(path):
        return None
    try:
        img = Image.open(path).convert("RGBA").resize((size, size), Image.LANCZOS)
        return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
    except Exception as e:
        log.warning("load_icon(%r, %r, %d) a échoué : %s", directory, code, size, e)
        return None


def load_icon(code: str, size: int = 48) -> Optional[ctk.CTkImage]:
    """Charge une icône de skill depuis skill_icons/. None si absente."""
    return _load_icon_from(ICONS_DIR, code, size)


def load_pet_icon(name: str, size: int = 48) -> Optional[ctk.CTkImage]:
    """Charge une icône de pet depuis pet_icons/<Name>.png. None si absente."""
    return _load_icon_from(PET_ICONS_DIR, name, size)


def load_mount_icon(name: str, size: int = 48) -> Optional[ctk.CTkImage]:
    """Charge une icône de mount depuis mount_icons/<Name>.png. None si absente."""
    return _load_icon_from(MOUNT_ICONS_DIR, name, size)


# ── Helpers de formatage ─────────────────────────────────────

def fmt_nombre(n: float) -> str:
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return f"{n:.0f}"


def fmt_stat(key: str, value: float) -> str:
    """Formate une valeur de stat selon qu'elle est plate ou en pourcentage."""
    if key in FLAT_STAT_KEYS:
        return fmt_nombre(value)
    return f"+{value}%"
