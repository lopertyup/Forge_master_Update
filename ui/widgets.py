"""
============================================================
  FORGE MASTER UI — Reusable widgets

  Small components built on top of customtkinter to replace
  the duplicated blocks in the views.

  Historically this module held everything UI-related that
  wasn't a full view. It has been split into three focused
  modules while keeping a stable import surface:

      ui.widgets      — pure widgets (this file): header,
                        stat_row, WLD bars, hero/stat cards,
                        companion card, skill icon grid.
      ui.dialogs      — ConfirmDialog + confirm() helpers.
      ui.import_zone  — build_import_zone + attach_scan_button
                        (OCR-driven scan FSM).

  The three submodules are re-exported here so every existing
  `from ui.widgets import X` keeps working with no churn in
  the 7 view modules that import from this file.
============================================================
"""

from __future__ import annotations

from typing import Callable, Dict, Optional, Tuple

import customtkinter as ctk

from .theme import (
    C,
    FLAT_STAT_KEYS,
    FONT_BIG,
    FONT_BODY,
    FONT_HUGE,
    FONT_MONO,
    FONT_SMALL,
    FONT_SUB,
    FONT_TINY,
    STAT_LABELS,
    fmt_number,
    rarity_color,
    stat_sort_key,
)

# ─── Re-exports for back-compat ─────────────────────────────
# Imported at module load so old `from ui.widgets import X`
# callers continue to work without touching the 7 views.
from .dialogs import ConfirmDialog, confirm, confirmer  # noqa: F401
from .import_zone import (  # noqa: F401
    attach_scan_button,
    build_import_zone,
)


# ════════════════════════════════════════════════════════════
#  VIEW HEADER (top 64px band)
# ════════════════════════════════════════════════════════════

def build_header(parent: ctk.CTkBaseClass, title: str,
                 font=None, height: int = 64) -> ctk.CTkFrame:
    """Build the standard view header. Returns the frame."""
    from .theme import FONT_TITLE
    header = ctk.CTkFrame(parent, fg_color=C["surface"], corner_radius=0, height=height)
    header.grid(row=0, column=0, sticky="ew")
    header.grid_propagate(False)
    header.grid_columnconfigure(1, weight=1)
    ctk.CTkLabel(header, text=title,
                 font=font or FONT_TITLE, text_color=C["text"]).pack(
        side="left", padx=24, pady=16)
    return header


# ════════════════════════════════════════════════════════════
#  STAT ROW (label on the left, value on the right)
# ════════════════════════════════════════════════════════════

def stat_row(parent: ctk.CTkBaseClass, key: str, value: float,
             row_index: int = 0, label: Optional[str] = None,
             is_flat: Optional[bool] = None) -> ctk.CTkFrame:
    """A 'Label  ────  Value' row with alternating zebra stripes."""
    bg = C["card_alt"] if row_index % 2 == 0 else C["card"]
    row = ctk.CTkFrame(parent, fg_color=bg, corner_radius=4)
    row.grid_columnconfigure(1, weight=1)

    ctk.CTkLabel(row, text=label or STAT_LABELS.get(key, key),
                 font=FONT_SMALL, text_color=C["muted"], anchor="w").grid(
        row=0, column=0, padx=10, pady=4, sticky="w")

    if is_flat is None:
        is_flat = key in FLAT_STAT_KEYS
    val_txt = fmt_number(value) if is_flat else f"+{value}%"
    ctk.CTkLabel(row, text=val_txt, font=FONT_MONO,
                 text_color=C["text"], anchor="e").grid(
        row=0, column=1, padx=10, pady=4, sticky="e")
    return row


# ════════════════════════════════════════════════════════════
#  WIN / LOSE / DRAW BARS
# ════════════════════════════════════════════════════════════

def build_wld_bars(parent: ctk.CTkBaseClass, wins: int, loses: int, draws: int,
                   total: Optional[int] = None, bar_height: int = 10,
                   compact: bool = False) -> ctk.CTkFrame:
    """
    Display 3 horizontal bars WIN / LOSE / DRAW.
    `total` defaults to wins + loses + draws.
    """
    total = total or max(1, wins + loses + draws)
    frame = ctk.CTkFrame(parent, fg_color="transparent")

    for label, val, color in (
        ("WIN",  wins,  C["win"]),
        ("LOSE", loses, C["lose"]),
        ("DRAW", draws, C["draw"]),
    ):
        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(fill="x", pady=2 if compact else 3)
        ctk.CTkLabel(row, text=label, font=FONT_SMALL,
                     text_color=color, width=36 if compact else 40).pack(side="left")
        bar = ctk.CTkProgressBar(row, height=bar_height, corner_radius=4,
                                  progress_color=color)
        bar.pack(side="left", fill="x", expand=True, padx=6 if compact else 8)
        bar.set(val / total)
        ctk.CTkLabel(row, text=f"{100 * val / total:.0f}%",
                     font=FONT_SMALL, text_color=C["muted"],
                     width=36 if compact else 40).pack(side="right")
    return frame


# ════════════════════════════════════════════════════════════
#  BIG "—" COUNTER (used by the simulator)
# ════════════════════════════════════════════════════════════

def big_counter(parent: ctk.CTkBaseClass, label: str, color: str,
                total_text: str = "/ 1000") -> ctk.CTkLabel:
    """Boxed 'LABEL / number / total'. Returns the number's label."""
    frame = ctk.CTkFrame(parent, fg_color=C["card_alt"], corner_radius=10)
    ctk.CTkLabel(frame, text=label, font=FONT_SMALL,
                 text_color=C["muted"]).pack(pady=(10, 0))
    value_lbl = ctk.CTkLabel(frame, text="—", font=FONT_HUGE, text_color=color)
    value_lbl.pack()
    ctk.CTkLabel(frame, text=total_text, font=FONT_SMALL,
                 text_color=C["muted"]).pack(pady=(0, 10))
    value_lbl._counter_frame = frame  # for callers that want to .grid() the frame
    return value_lbl


# ════════════════════════════════════════════════════════════
#  "HERO STAT" CARD (HP / ATK in the dashboard)
# ════════════════════════════════════════════════════════════

def stat_hero_card(parent: ctk.CTkBaseClass, title: str, value: str,
                   subtitle: str, color: str) -> ctk.CTkFrame:
    card = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=12)
    ctk.CTkLabel(card, text=title, font=FONT_SMALL,
                 text_color=C["muted"]).pack(anchor="w", padx=20, pady=(16, 0))
    ctk.CTkLabel(card, text=value, font=FONT_BIG,
                 text_color=color).pack(anchor="w", padx=20, pady=(2, 0))
    ctk.CTkLabel(card, text=subtitle, font=FONT_SMALL,
                 text_color=C["muted"]).pack(anchor="w", padx=20, pady=(0, 16))
    return card


# ════════════════════════════════════════════════════════════
#  "STATS" CARD (pet / mount / equipment summary)
# ════════════════════════════════════════════════════════════

def stats_card(parent: ctk.CTkBaseClass, title: str, stats: Dict[str, float],
               empty_text: str = "(empty)",
               title_color: Optional[str] = None) -> ctk.CTkFrame:
    """
    Card with a title and stat_rows for every non-zero stat.
    Shows `empty_text` if every stat is zero.
    """
    card = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=12)
    ctk.CTkLabel(card, text=title, font=FONT_SUB,
                 text_color=title_color or C["text"]).pack(
        padx=16, pady=(14, 6), anchor="w")

    non_zero = [(k, v) for k, v in stats.items()
                if not k.startswith("__") and v]
    # Canonical in-game order (flat stats first, then substats)
    non_zero.sort(key=lambda kv: stat_sort_key(kv[0]))

    if not non_zero:
        ctk.CTkLabel(card, text=empty_text, font=FONT_BODY,
                     text_color=C["muted"]).pack(padx=16, pady=20)
    else:
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=10, pady=(0, 10))
        for i, (k, v) in enumerate(non_zero):
            stat_row(inner, k, v, row_index=i).pack(fill="x", pady=1)

    ctk.CTkFrame(card, fg_color="transparent", height=6).pack()
    return card


# ════════════════════════════════════════════════════════════
#  "COMPANION SLOT" CARD (equipped pet / equipped mount)
#  Header with icon + name + rarity badge, then stats.
# ════════════════════════════════════════════════════════════

def companion_slot_card(parent: ctk.CTkBaseClass, slot_label: str,
                         name: Optional[str], rarity: Optional[str],
                         stats: Dict[str, float],
                         icon_image=None, fallback_emoji: str = "🐾",
                         empty_text: str = "(empty)") -> ctk.CTkFrame:
    """
    Card for an equipped slot: slot label, icon + name + rarity,
    then list of non-zero stats. If `name` is None → "empty" state.
    """
    card = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=12)

    # Top band: slot label (e.g. "🐾 PET1" / "🐴 Current mount")
    ctk.CTkLabel(card, text=slot_label, font=FONT_SUB,
                 text_color=C["muted"]).pack(
        padx=16, pady=(12, 4), anchor="w")

    # Identity band: icon + name + rarity
    head = ctk.CTkFrame(card, fg_color="transparent")
    head.pack(fill="x", padx=12, pady=(0, 6))

    if icon_image is not None:
        ctk.CTkLabel(head, image=icon_image, text="",
                     fg_color="transparent", width=48).pack(side="left",
                                                             padx=(2, 8))
    else:
        ctk.CTkLabel(head, text=fallback_emoji,
                     font=("Segoe UI", 26), width=48).pack(side="left",
                                                            padx=(2, 8))

    info = ctk.CTkFrame(head, fg_color="transparent")
    info.pack(side="left", fill="x", expand=True)

    if name:
        ctk.CTkLabel(info, text=name, font=FONT_SUB,
                     text_color=C["text"], anchor="w").pack(anchor="w")
        # Rarity badge + (optional) level badge on the same row
        meta_row = ctk.CTkFrame(info, fg_color="transparent")
        meta_row.pack(anchor="w", fill="x")
        if rarity:
            rar = str(rarity).lower()
            ctk.CTkLabel(meta_row, text=rar.upper(), font=FONT_TINY,
                         text_color=rarity_color(rar), anchor="w").pack(
                side="left")
        lvl = stats.get("__level__")
        if lvl:
            ctk.CTkLabel(meta_row, text=f"Lv.{int(lvl)}", font=FONT_TINY,
                         text_color=C["accent"], anchor="w").pack(
                side="left", padx=(8, 0))
    else:
        ctk.CTkLabel(info, text="— free —", font=FONT_BODY,
                     text_color=C["muted"], anchor="w").pack(anchor="w")

    # Stats (filter out non-numeric identity keys)
    non_zero = [(k, v) for k, v in stats.items()
                if not k.startswith("__") and v]
    # Canonical in-game order (flat stats first, then substats)
    non_zero.sort(key=lambda kv: stat_sort_key(kv[0]))

    if not non_zero:
        ctk.CTkLabel(card, text=empty_text, font=FONT_BODY,
                     text_color=C["muted"]).pack(padx=16, pady=(4, 14))
    else:
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=10, pady=(0, 10))
        for i, (k, v) in enumerate(non_zero):
            stat_row(inner, k, v, row_index=i).pack(fill="x", pady=1)

    ctk.CTkFrame(card, fg_color="transparent", height=6).pack()
    return card


# ════════════════════════════════════════════════════════════
#  SKILL ICON GRID (with toggle)
# ════════════════════════════════════════════════════════════

def skill_icon_grid(parent: ctk.CTkBaseClass,
                    all_skills: Dict,
                    selected: Dict[str, "ctk.BooleanVar"],
                    cols: int = 6,
                    icon_size: int = 44,
                    on_toggle: Optional[Callable[[str], None]] = None
                    ) -> Tuple[ctk.CTkFrame, Dict]:
    """
    Build a clickable icon grid for `all_skills`.
    `selected` is a {code: BooleanVar} dict injected by the caller.
    Returns (frame, widgets) where widgets = {code: (label, frame)} so the
    caller can refresh things visually.
    """
    from .theme import RARITY_ORDER, load_icon, rarity_color

    grid = ctk.CTkFrame(parent, fg_color=C["bg"],
                        border_color=C["border"], border_width=1,
                        corner_radius=8)

    widgets: Dict[str, Tuple[ctk.CTkLabel, ctk.CTkFrame]] = {}

    def _rarity_sort_key(item: Tuple[str, Dict]) -> Tuple[int, str]:
        code, data = item
        rar = str(data.get("rarity", "common")).lower()
        idx = RARITY_ORDER.index(rar) if rar in RARITY_ORDER else 0
        return (idx, str(data.get("name", code)).lower())

    def _refresh(code: str) -> None:
        lbl, frame = widgets[code]
        if selected[code].get():
            frame.configure(fg_color=C["selected"], corner_radius=8,
                            border_width=2, border_color=C["win"])
        else:
            frame.configure(fg_color="transparent", border_width=0)

    def _make_toggle(code: str) -> Callable:
        def _click(_evt=None) -> None:
            if on_toggle is not None:
                on_toggle(code)
            _refresh(code)
        return _click

    for i, (code, data) in enumerate(sorted(all_skills.items(),
                                              key=_rarity_sort_key)):
        color    = rarity_color(str(data.get("rarity", "common")).lower())
        icon_img = load_icon(code, size=icon_size)
        name     = data.get("name", code)

        btn_frame = ctk.CTkFrame(grid, fg_color="transparent",
                                  corner_radius=8)
        btn_frame.grid(row=i // cols, column=i % cols, padx=6, pady=6)

        lbl = ctk.CTkLabel(
            btn_frame,
            image=icon_img if icon_img else None,
            text="" if icon_img else code.upper(),
            font=("Segoe UI", 9, "bold"),
            text_color=color,
            fg_color="transparent",
            corner_radius=8,
            width=icon_size + 8, height=icon_size + 8,
        )
        lbl.pack()
        lbl.bind("<Button-1>", _make_toggle(code))
        widgets[code] = (lbl, btn_frame)

        # Hover tooltip: replace the icon with the short name
        def _enter(_e, n=name, col=color, w=lbl) -> None:
            w.configure(text=n[:8], text_color=col, image=None)

        def _leave(_e, img=icon_img, w=lbl, c=code) -> None:
            w.configure(text="" if img else c.upper(),
                        image=img if img else None)

        lbl.bind("<Enter>", _enter)
        lbl.bind("<Leave>", _leave)

        _refresh(code)

    for c in range(cols):
        grid.grid_columnconfigure(c, weight=1)

    return grid, widgets
