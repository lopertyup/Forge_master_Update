"""
============================================================
  FORGE MASTER UI -- Build view (P2.7)
  Player's 8 equipment slots in a 4x2 grid. Reads from the
  controller's persisted equipment dict (loaded from
  equipment.txt at startup) and offers a "Scan Build" button
  that triggers the player_equipment OCR pipeline.
============================================================
"""

from typing import Dict

import customtkinter as ctk

from backend.constants import EQUIPMENT_SLOTS, EQUIPMENT_SLOT_NAMES
from ui.theme import (
    C, FONT_BODY, FONT_SMALL, FONT_SUB, FONT_TINY,
    fmt_number, rarity_color,
)
from ui.widgets import build_header, companion_slot_card


# Slot label: "🛡  Helmet". The eight icons match the in-game order
# (Helmet, Body, Gloves, Necklace, Ring, Weapon, Shoe, Belt).
_SLOT_EMOJI = {
    "EQUIP_HELMET":   "🪖",
    "EQUIP_BODY":     "🦺",
    "EQUIP_GLOVES":   "🧤",
    "EQUIP_NECKLACE": "📿",
    "EQUIP_RING":     "💍",
    "EQUIP_WEAPON":   "⚔",
    "EQUIP_SHOE":     "👢",
    "EQUIP_BELT":     "🎗",
}


class BuildView(ctk.CTkFrame):
    """8 equipment slots in a 4-column grid, plus a scan button."""

    def __init__(self, parent, controller, app):
        super().__init__(parent, fg_color=C["bg"], corner_radius=0)
        self.controller = controller
        self.app        = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build()

    def _build(self) -> None:
        build_header(self, "🛡  Build (8 slots)")

        self._scroll = ctk.CTkScrollableFrame(self, fg_color=C["bg"],
                                               corner_radius=0)
        self._scroll.grid(row=1, column=0, sticky="nsew")
        self._scroll.grid_columnconfigure(0, weight=1)

        self._build_actions()
        self._build_slots()

    # ── Actions row ────────────────────────────────────────────

    def _build_actions(self) -> None:
        bar = ctk.CTkFrame(self._scroll, fg_color="transparent")
        bar.grid(row=0, column=0, padx=16, pady=(12, 6), sticky="ew")
        bar.grid_columnconfigure(2, weight=1)

        ctk.CTkButton(
            bar, text="📷  Scan Build",
            font=FONT_SMALL, width=160,
            command=self._on_scan_clicked,
        ).grid(row=0, column=0, padx=(0, 8))

        ctk.CTkButton(
            bar, text="🔄  Reload",
            font=FONT_SMALL, width=120,
            fg_color="transparent",
            border_color=C["card"], border_width=1,
            command=self._refresh_slots,
        ).grid(row=0, column=1, padx=(0, 8))

        self._status_lbl = ctk.CTkLabel(
            bar, text="", font=FONT_SMALL,
            text_color=C["muted"], anchor="w",
        )
        self._status_lbl.grid(row=0, column=2, sticky="ew")

    # ── 4x2 slot grid ──────────────────────────────────────────

    def _build_slots(self) -> None:
        self._grid_frame = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._grid_frame.grid(row=1, column=0, padx=16, pady=8, sticky="ew")
        for c in range(4):
            self._grid_frame.grid_columnconfigure(c, weight=1)
        self._refresh_slots()

    def _refresh_slots(self) -> None:
        # Wipe + redraw -- cheap, only 8 cards.
        for child in self._grid_frame.winfo_children():
            child.destroy()

        equipment = self.controller.get_equipment()
        for i, slot_key in enumerate(EQUIPMENT_SLOTS):
            slot_name = EQUIPMENT_SLOT_NAMES[i]
            data = equipment.get(slot_key, {}) or {}
            name = data.get("__name__")
            rar  = data.get("__rarity__")

            stats = {}
            if data.get("__level__") is not None:
                stats["__level__"] = data.get("__level__")
            hp_flat = data.get("hp_flat")
            dmg_flat = data.get("damage_flat")
            if hp_flat:
                stats["hp_flat"] = float(hp_flat)
            if dmg_flat:
                stats["damage_flat"] = float(dmg_flat)
            atype = data.get("attack_type")
            if atype:
                stats["attack_type"] = atype

            card = companion_slot_card(
                self._grid_frame,
                slot_label=f"{_SLOT_EMOJI.get(slot_key, '🛡')}  {slot_name}",
                name=name,
                rarity=rar,
                stats=stats,
                fallback_emoji=_SLOT_EMOJI.get(slot_key, "🛡"),
                empty_text="(unscanned)",
            )
            row, col = divmod(i, 4)
            card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")

        # Status line: count of populated slots.
        n_filled = sum(1 for v in equipment.values()
                       if isinstance(v, dict) and v.get("__name__"))
        self._status_lbl.configure(
            text=f"{n_filled}/8 slots populated",
            text_color=C["muted"],
        )

    # ── Scan trigger ───────────────────────────────────────────

    def _on_scan_clicked(self) -> None:
        """Call controller.scan('player_equipment') asynchronously and
        refresh the grid once the scan persisted the new pieces."""
        self._status_lbl.configure(text="📷  Scanning ...",
                                    text_color=C["accent"])

        def _on_done(text: str, status: str) -> None:
            # Callback dispatched on the Tk thread by the controller.
            if status == "ocr_unavailable":
                self._status_lbl.configure(
                    text="⚠  OCR unavailable -- install rapidocr_onnxruntime",
                    text_color=C["lose"])
                return
            if status == "zone_not_configured":
                self._status_lbl.configure(
                    text="⚠  Zone player_equipment not configured -- "
                         "set the bbox in the Zones tab first",
                    text_color=C["lose"])
                return
            if status == "ocr_error":
                self._status_lbl.configure(
                    text="⚠  OCR failed", text_color=C["lose"])
                return
            # Success path: equipment.txt has been overwritten by the
            # controller. Reload the grid from disk.
            self._refresh_slots()
            self._status_lbl.configure(
                text="✅  Scan applied",
                text_color=C["win"])

        try:
            self.controller.scan(zone_key="player_equipment", callback=_on_done)
        except Exception as e:
            self._status_lbl.configure(
                text=f"⚠  scan() raised: {e}",
                text_color=C["lose"])

    # ── App-level reload hook ──────────────────────────────────

    def refresh(self) -> None:
        """Called by the app shell when global state may have changed."""
        self._refresh_slots()
