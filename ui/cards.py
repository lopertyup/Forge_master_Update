"""
============================================================
  FORGE MASTER UI — Reusable swap-flow cards
  (Plan §11 Phase 2)

  Components shared by the four "swap-style" sections:
  Mount, Pet, Skills, and Equipment > Comparer.

  Two of the five components called for in the plan are
  already implemented in ui.widgets — we re-export them here
  under the plan's nomenclature so that the views to be
  refactored in Phase 3 can use a single, uniform import:

      from ui.cards import (
          ItemCard,        # = widgets.companion_slot_card
          StatBlock,       # = widgets.stats_card
          ResultDelta,     # NEW
          SwapPanel,       # NEW
          LibraryList,     # NEW
      )

  Each NEW component is built on top of existing ui.widgets
  helpers (build_wld_bars, stat_row, …) so we don't reinvent
  layout primitives. Functions return a CTkFrame and never
  call .pack/.grid themselves — the caller chooses placement.
============================================================
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

import customtkinter as ctk

from .theme import (
    C,
    FONT_BODY,
    FONT_MONO_S,
    FONT_SMALL,
    FONT_SUB,
    FONT_TINY,
    RARITY_ORDER,
    fmt_number,
    rarity_color,
)
from .widgets import (
    build_wld_bars,
    companion_slot_card,
    stat_row,
    stats_card,
)


# ════════════════════════════════════════════════════════════
#  ITEM CARD  (alias)
# ════════════════════════════════════════════════════════════
# The plan calls it "ItemCard" — it's the same widget as
# companion_slot_card. We re-export rather than duplicate so
# any visual tweak applied in widgets.py propagates here.

ItemCard = companion_slot_card


# ════════════════════════════════════════════════════════════
#  STAT BLOCK  (alias)
# ════════════════════════════════════════════════════════════

StatBlock = stats_card


# ════════════════════════════════════════════════════════════
#  RESULT DELTA  (W/L/D bars + verdict + Apply / Discard)
# ════════════════════════════════════════════════════════════

def ResultDelta(parent: ctk.CTkBaseClass,
                wins: int,
                loses: int,
                draws: int,
                *,
                total: Optional[int] = None,
                title: str = "Result",
                subtitle: Optional[str] = None,
                on_apply: Optional[Callable[[], None]] = None,
                on_discard: Optional[Callable[[], None]] = None,
                apply_label: str = "💾  Apply",
                discard_label: str = "✖  Discard",
                always_show_apply: bool = False,
                better_only_apply: bool = True,
                ) -> ctk.CTkFrame:
    """
    Boxed result panel for a swap simulation.

    Layout:
        Title                                                 (FONT_SUB)
        Subtitle (optional)                                   (FONT_SMALL)
        ────────────────────────────────────────────────────
        WIN  ▰▰▰▰▱▱▱▱▱▱  62%
        LOSE ▰▰▱▱▱▱▱▱▱▱  18%
        DRAW ▰▰▱▱▱▱▱▱▱▱  20%
        Verdict text (colored by win/lose/tie)
        [Apply]   [Discard]   ← optional, see flags below

    Behaviour rules:

      * `total` defaults to wins + loses + draws.
      * Verdict color follows wins ↔ loses ↔ tie.
      * Apply button visibility:
          - shown if `on_apply` is set AND
              (`always_show_apply`
               OR (wins > loses)
               OR not `better_only_apply`)
        Use `always_show_apply=True` for the equipment
        "apply worse anyway" path (after a confirm dialog).
      * Discard button shown whenever `on_discard` is set.

    Returns the outer card frame (caller chooses placement).
    """
    total = total or max(1, wins + loses + draws)

    card = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=12)

    ctk.CTkLabel(
        card, text=title, font=FONT_SUB, text_color=C["text"],
    ).pack(padx=20, pady=(16, 2), anchor="w")

    if subtitle:
        ctk.CTkLabel(
            card, text=subtitle, font=FONT_SMALL, text_color=C["muted"],
        ).pack(padx=20, pady=(0, 8), anchor="w")
    else:
        ctk.CTkFrame(card, fg_color="transparent", height=4).pack()

    bars = build_wld_bars(card, wins, loses, draws, total=total)
    bars.pack(fill="x", padx=20, pady=(0, 8))

    if wins > loses:
        verdict_txt = (
            f"✅  Better — {100 * wins / total:.0f}% wins / "
            f"{100 * loses / total:.0f}% losses."
        )
        verdict_col = C["win"]
        is_better   = True
    elif loses > wins:
        verdict_txt = (
            f"❌  Worse — {100 * loses / total:.0f}% losses."
        )
        verdict_col = C["lose"]
        is_better   = False
    else:
        verdict_txt = "🤝  Tie — equivalent."
        verdict_col = C["draw"]
        is_better   = False

    ctk.CTkLabel(
        card, text=verdict_txt, font=FONT_SUB, text_color=verdict_col,
    ).pack(padx=20, pady=(8, 8), anchor="w")

    show_apply = bool(on_apply) and (
        always_show_apply or is_better or not better_only_apply
    )
    show_discard = bool(on_discard)

    if show_apply or show_discard:
        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(0, 16))
        if show_apply and show_discard:
            btn_row.grid_columnconfigure((0, 1), weight=1)
        else:
            btn_row.grid_columnconfigure(0, weight=1)

        col = 0
        if show_apply:
            ctk.CTkButton(
                btn_row, text=apply_label,
                font=FONT_BODY, height=36, corner_radius=8,
                fg_color=C["win"] if is_better else C["lose"],
                hover_color=C["win_hv"] if is_better else C["lose_hv"],
                text_color=C["bg"] if is_better else C["text"],
                command=on_apply,
            ).grid(row=0, column=col, padx=(0, 4) if show_discard else 0,
                    sticky="ew")
            col += 1
        if show_discard:
            ctk.CTkButton(
                btn_row, text=discard_label,
                font=FONT_BODY, height=36, corner_radius=8,
                fg_color="transparent",
                border_color=C["card_alt"], border_width=1,
                hover_color=C["border"],
                text_color=C["muted"],
                command=on_discard,
            ).grid(row=0, column=col,
                    padx=(4, 0) if col == 1 else 0, sticky="ew")
    else:
        ctk.CTkFrame(card, fg_color="transparent", height=8).pack()

    return card


# ════════════════════════════════════════════════════════════
#  SWAP PANEL  (Current | Candidate + Compare button + result slot)
# ════════════════════════════════════════════════════════════

class SwapPanel:
    """
    Side-by-side "Current vs Candidate" panel with a Compare button
    and a result slot below it.

    Usage:

        sp = SwapPanel(parent,
                       left_title="Equipped pet",
                       right_title="Candidate pet",
                       on_compare=self._test_pet,
                       compare_label="🔬  Compare (1000 fights)")
        sp.outer.grid(row=2, column=0, sticky="nsew")

        # Drop the equipped item card on the left:
        ItemCard(sp.left_slot, ...).pack(fill="both", expand=True)

        # Drop the candidate card on the right:
        ItemCard(sp.right_slot, ...).pack(fill="both", expand=True)

        # When the simulation finishes, drop a ResultDelta:
        sp.clear_result()
        ResultDelta(sp.result_slot, w, l, d,
                    on_apply=self._apply).pack(fill="x")

    Attributes (exposed for the caller):
        outer        — outer CTkFrame to be placed by the caller
        left_slot    — empty frame for the "current" content
        right_slot   — empty frame for the "candidate" content
        result_slot  — empty frame where the caller injects ResultDelta
        compare_btn  — the Compare button (if on_compare was set)

    Helpers:
        clear_result()  — wipe the result_slot before re-rendering
        clear_left()    — wipe the left content
        clear_right()   — wipe the right content
        set_compare_state(enabled, label=None)  — toggle the button
    """

    def __init__(self,
                 parent: ctk.CTkBaseClass,
                 *,
                 left_title: str = "Current",
                 right_title: str = "Candidate",
                 on_compare: Optional[Callable[[], None]] = None,
                 compare_label: str = "🔬  Compare (1000 fights)",
                 fg_color: Optional[str] = None,
                 ):
        self.outer = ctk.CTkFrame(
            parent,
            fg_color=fg_color if fg_color is not None else "transparent",
            corner_radius=0,
        )
        self.outer.grid_columnconfigure((0, 1), weight=1)
        self.outer.grid_rowconfigure(1, weight=1)

        # Title row.
        ctk.CTkLabel(self.outer, text=left_title,
                     font=FONT_SMALL, text_color=C["muted"],
                     anchor="w").grid(
            row=0, column=0, sticky="w", padx=(8, 4), pady=(4, 2))
        ctk.CTkLabel(self.outer, text=right_title,
                     font=FONT_SMALL, text_color=C["accent"],
                     anchor="w").grid(
            row=0, column=1, sticky="w", padx=(4, 8), pady=(4, 2))

        # Content slots.
        self.left_slot = ctk.CTkFrame(
            self.outer, fg_color="transparent", corner_radius=0)
        self.left_slot.grid(row=1, column=0, sticky="nsew", padx=(8, 4))
        self.right_slot = ctk.CTkFrame(
            self.outer, fg_color="transparent", corner_radius=0)
        self.right_slot.grid(row=1, column=1, sticky="nsew", padx=(4, 8))

        # Compare button.
        if on_compare is not None:
            self.compare_btn = ctk.CTkButton(
                self.outer, text=compare_label,
                font=FONT_BODY, height=40, corner_radius=8,
                fg_color=C["accent"], hover_color=C["accent_hv"],
                command=on_compare,
            )
            self.compare_btn.grid(
                row=2, column=0, columnspan=2,
                padx=8, pady=(10, 6), sticky="ew")
        else:
            self.compare_btn = None

        # Result slot (where the caller drops a ResultDelta).
        self.result_slot = ctk.CTkFrame(
            self.outer, fg_color="transparent", corner_radius=0)
        self.result_slot.grid(
            row=3, column=0, columnspan=2,
            padx=8, pady=(0, 8), sticky="ew")

    # ── Helpers ──────────────────────────────────────────────

    def clear_left(self) -> None:
        for w in self.left_slot.winfo_children():
            w.destroy()

    def clear_right(self) -> None:
        for w in self.right_slot.winfo_children():
            w.destroy()

    def clear_result(self) -> None:
        for w in self.result_slot.winfo_children():
            w.destroy()

    def set_compare_state(self, enabled: bool,
                          label: Optional[str] = None) -> None:
        if self.compare_btn is None:
            return
        self.compare_btn.configure(state="normal" if enabled else "disabled")
        if label is not None:
            self.compare_btn.configure(text=label)


# ════════════════════════════════════════════════════════════
#  LIBRARY LIST  (filter chips + scrollable rows + per-row actions)
# ════════════════════════════════════════════════════════════

# A library row is a dict with at least:
#   "key"          — unique id (typically the item name)
#   "name"         — display name
#   "rarity"       — one of RARITY_ORDER (lower-cased)
# Optional:
#   "hp_flat", "damage_flat"   — shown in the stats column
#   "type"                     — extra tag (e.g. pet "Balanced/Damage/Health")
#   "icon"                     — pre-loaded CTkImage (skip icon_loader)


def library_list(parent: ctk.CTkBaseClass,
                 items: List[Dict[str, Any]],
                 *,
                 title: str = "📚  Library",
                 hint: Optional[str] = None,
                 filters: Optional[Dict[str, List[str]]] = None,
                 on_action: Optional[Callable[[Dict[str, Any]], None]] = None,
                 action_label: str = "🔬  Compare",
                 on_delete: Optional[Callable[[Dict[str, Any]], None]] = None,
                 icon_loader: Optional[Callable[[str], Any]] = None,
                 fallback_emoji: str = "📦",
                 max_height: int = 360,
                 ) -> Tuple[ctk.CTkFrame, "LibraryListController"]:
    """
    Scrollable, optionally filtered list of library entries.

    Each row shows: icon · rarity badge · name · stats summary ·
    [Compare] [Delete] (only if the corresponding callback is set).

    Filters are passed as a dict ``{filter_key: [allowed_values]}``
    where ``filter_key`` is a key on the item dict (e.g. "rarity",
    "type", "age"). For each filter we render a chip strip with an
    "All" chip at index 0 plus one chip per allowed value. Multiple
    filters AND together.

    Returns ``(outer_frame, controller)``. The controller exposes
    ``set_items(new_list)`` and ``set_filter(filter_key, value)``
    so the caller can refresh the list without rebuilding the
    surrounding container.
    """

    outer = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=12)
    outer.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(
        outer, text=title, font=FONT_SUB, text_color=C["text"],
    ).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 2))

    if hint:
        ctk.CTkLabel(
            outer, text=hint, font=FONT_SMALL, text_color=C["muted"],
            wraplength=700, justify="left",
        ).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 6))

    # ── Filter chips (one row per filter key) ───────────────
    chip_rows: Dict[str, ctk.CTkFrame] = {}
    active_filters: Dict[str, Optional[str]] = {}

    if filters:
        for fkey, values in filters.items():
            chip_row = ctk.CTkFrame(outer, fg_color="transparent")
            chip_row.grid(row=2 + len(chip_rows), column=0,
                           sticky="w", padx=14, pady=(0, 4))
            chip_rows[fkey] = chip_row
            active_filters[fkey] = None  # None ⇒ "All"

    # ── Scrollable list ─────────────────────────────────────
    list_row_idx = 2 + len(chip_rows)
    list_frame = ctk.CTkScrollableFrame(
        outer, fg_color=C["bg"], corner_radius=8,
        height=max_height,
    )
    list_frame.grid(row=list_row_idx, column=0, sticky="nsew",
                     padx=14, pady=(4, 14))
    list_frame.grid_columnconfigure(0, weight=1)
    outer.grid_rowconfigure(list_row_idx, weight=1)

    state = {"items": list(items)}

    def _row_sort_key(it: Dict[str, Any]) -> Tuple[int, str]:
        rar = str(it.get("rarity", "common")).lower()
        idx = RARITY_ORDER.index(rar) if rar in RARITY_ORDER else 0
        return (idx, str(it.get("name", "")).lower())

    def _matches_filters(it: Dict[str, Any]) -> bool:
        for fkey, fval in active_filters.items():
            if fval is None:
                continue
            if str(it.get(fkey, "")).lower() != str(fval).lower():
                return False
        return True

    def _render_rows() -> None:
        for w in list_frame.winfo_children():
            w.destroy()

        visible = [it for it in state["items"] if _matches_filters(it)]
        visible.sort(key=_row_sort_key)

        if not visible:
            ctk.CTkLabel(
                list_frame, text="(no matching items)",
                font=FONT_SMALL, text_color=C["muted"],
            ).pack(padx=12, pady=18)
            return

        for i, it in enumerate(visible):
            bg  = C["card_alt"] if i % 2 == 0 else C["card"]
            row = ctk.CTkFrame(list_frame, fg_color=bg, corner_radius=6)
            row.pack(fill="x", padx=4, pady=2)
            row.grid_columnconfigure(2, weight=1)

            # Column 0: icon (loaded image or fallback emoji)
            icon_img = it.get("icon")
            if icon_img is None and icon_loader is not None:
                try:
                    icon_img = icon_loader(it.get("name", ""))
                except Exception:
                    icon_img = None
            if icon_img is not None:
                ctk.CTkLabel(row, image=icon_img, text="",
                             fg_color="transparent").grid(
                    row=0, column=0, padx=(8, 2), pady=4)
            else:
                ctk.CTkLabel(row, text=fallback_emoji,
                             font=("Segoe UI", 22), width=44).grid(
                    row=0, column=0, padx=(8, 2), pady=4)

            # Column 1: rarity badge
            rar = str(it.get("rarity", "common")).lower()
            ctk.CTkLabel(
                row, text=rar.upper(), font=FONT_TINY,
                text_color=rarity_color(rar), width=72,
            ).grid(row=0, column=1, padx=(6, 6), pady=6)

            # Column 2: name (+ optional type chip)
            name = str(it.get("name", "?"))
            ctk.CTkLabel(row, text=name, font=FONT_BODY,
                         text_color=C["text"], anchor="w").grid(
                row=0, column=2, padx=6, pady=6, sticky="w")

            # Column 3: stats summary (HP / DMG)
            hp_flat  = it.get("hp_flat") or 0
            dmg_flat = it.get("damage_flat") or 0
            stats_bits: List[str] = []
            if dmg_flat:
                stats_bits.append(f"⚔ {fmt_number(dmg_flat)}")
            if hp_flat:
                stats_bits.append(f"❤ {fmt_number(hp_flat)}")
            if stats_bits:
                ctk.CTkLabel(
                    row, text="   ".join(stats_bits),
                    font=FONT_MONO_S, text_color=C["muted"],
                ).grid(row=0, column=3, padx=6, pady=6)

            # Columns 4/5: per-row actions
            col = 4
            if on_action is not None:
                ctk.CTkButton(
                    row, text=action_label,
                    font=FONT_SMALL, height=26, width=100,
                    corner_radius=6,
                    fg_color=C["accent"], hover_color=C["accent_hv"],
                    command=lambda x=it: on_action(x),
                ).grid(row=0, column=col, padx=(4, 4), pady=4)
                col += 1
            if on_delete is not None:
                ctk.CTkButton(
                    row, text="🗑", width=32, height=26,
                    font=FONT_SMALL, corner_radius=6,
                    fg_color="transparent",
                    hover_color=C["lose"], text_color=C["muted"],
                    command=lambda x=it: on_delete(x),
                ).grid(row=0, column=col, padx=(4, 10), pady=4)

    def _make_chip(parent_row: ctk.CTkFrame, fkey: str,
                   label: str, value: Optional[str]) -> ctk.CTkButton:
        def _click():
            active_filters[fkey] = value
            _refresh_chips(fkey)
            _render_rows()
        btn = ctk.CTkButton(
            parent_row, text=label,
            font=FONT_TINY, height=24, width=70, corner_radius=12,
            fg_color="transparent",
            border_color=C["card_alt"], border_width=1,
            hover_color=C["border"], text_color=C["muted"],
            command=_click,
        )
        btn._chip_value = value  # type: ignore[attr-defined]
        return btn

    def _refresh_chips(fkey: str) -> None:
        row = chip_rows.get(fkey)
        if row is None:
            return
        for child in row.winfo_children():
            value = getattr(child, "_chip_value", None)
            is_on = value == active_filters[fkey]
            child.configure(
                fg_color=C["accent"] if is_on else "transparent",
                text_color=C["bg"] if is_on else C["muted"],
            )

    if filters:
        for fkey, values in filters.items():
            row = chip_rows[fkey]
            ctk.CTkLabel(
                row, text=f"{fkey}:", font=FONT_TINY,
                text_color=C["muted"],
            ).pack(side="left", padx=(6, 4))
            chip = _make_chip(row, fkey, "All", None)
            chip.pack(side="left", padx=2)
            for v in values:
                chip = _make_chip(row, fkey, str(v).title(), str(v).lower())
                chip.pack(side="left", padx=2)
            _refresh_chips(fkey)

    _render_rows()

    # ── Lightweight controller for live updates ─────────────
    class LibraryListController:
        """Returned alongside the outer frame so the caller can
        push fresh data or change the active filter without
        rebuilding the whole list."""

        @staticmethod
        def set_items(new_items: List[Dict[str, Any]]) -> None:
            state["items"] = list(new_items)
            _render_rows()

        @staticmethod
        def set_filter(fkey: str, value: Optional[str]) -> None:
            if fkey not in active_filters:
                return
            active_filters[fkey] = value
            _refresh_chips(fkey)
            _render_rows()

    return outer, LibraryListController()


# Plan nomenclature alias.
LibraryList = library_list


__all__ = [
    "ItemCard",
    "StatBlock",
    "ResultDelta",
    "SwapPanel",
    "LibraryList",
    "library_list",
]
