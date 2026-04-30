"""
============================================================
  FORGE MASTER UI — Zones (Phase 5 refactor)

  Calibrate the OCR capture regions (bboxes) used by every
  scanner pipeline (profile / opponent / equipment / ...).

  Layout (cf. UI_REFACTOR_PLAN §9 / §11 phase 5):

      ┌─────────────────────────────────────────────────┐
      │ Header                                          │
      ├──────────────┬──────────────────────────────────┤
      │ Sidebar      │ Detail card                      │
      │ (zone list,  │  - bboxes summary                │
      │  status chip │  - [Capture]                     │
      │  per row)    │  - [Test scan] -> raw OCR text   │
      │              │  - [Reset]                       │
      └──────────────┴──────────────────────────────────┘

  This view never imports backend/* — every operation goes
  through the GameController (cf. UI_REFACTOR_PLAN P1).
============================================================
"""

from __future__ import annotations

import logging
from typing import Dict, List, Tuple

import customtkinter as ctk

from ui.theme import (
    C,
    FONT_BODY,
    FONT_MONO,
    FONT_MONO_S,
    FONT_SMALL,
    FONT_SUB,
)
from ui.widgets import build_header, confirm
from ui.zone_picker import ZonePicker

log = logging.getLogger(__name__)

# ── Capture overlay region (screen-absolute) ──────────────
# Full 1920×1080 screen. Some zones (equipment popup, opponent profile)
# can sit anywhere on the display, so the overlay spans the full screen
# (it used to be limited to the BlueStacks panel).
_BLUESTACKS_REGION: Tuple[int, int, int, int] = (0, 0, 1920, 1080)

# ── Zone catalog (presentation order + per-zone metadata) ─
# Each entry: (zone_key, icon, label, hint shown to the user inside
# the picker overlay and on the detail card).
_ZONES: List[Tuple[str, str, str, str]] = [
    ("profile",          "📊", "Profile",
     "Trace the zone around your own stat panel"),
    ("opponent",         "⚔",  "Opponent",
     "Trace the zone around the opponent's stat panel"),
    ("equipment",        "🛡",  "Equipment",
     "Trace the zone around the equipment comparison popup"),
    ("skill",            "✨", "Skill",
     "Trace the zone around the skill description panel"),
    ("pet",              "🐾", "Pet",
     "Trace the zone around the pet stat panel"),
    ("mount",            "🐴", "Mount",
     "Trace the zone around the mount stat panel"),
    ("player_equipment", "🛡", "Player build",
     "Trace the zone around YOUR full character/equipment panel "
     "(same framing as the opponent profile)"),
    ("equipment_popup",  "🔍", "Equipment popup",
     "Trace the zone around the in-game item detail popup. "
     "Reused by every per-slot 📷 on the Build tab."),
]

_ZONE_META: Dict[str, Tuple[str, str, str]] = {
    k: (icon, label, hint) for (k, icon, label, hint) in _ZONES
}


class ZonesView(ctk.CTkFrame):
    """Sidebar (zone list) + detail card (bbox edition + Test scan)."""

    def __init__(self, parent, controller, app):
        super().__init__(parent, fg_color=C["bg"], corner_radius=0)
        self.controller = controller
        self.app        = app

        # sidebar row → {"frame", "chip", "btn"}
        self._sidebar_rows: Dict[str, Dict] = {}
        self._selected_key: str = _ZONES[0][0]

        # widgets owned by the detail panel — reset in _render_detail.
        self._detail_widgets: Dict[str, object] = {}

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build()

    # ── Layout ──────────────────────────────────────────────

    def _build(self) -> None:
        # Header (spans both columns).
        header = build_header(self, "Zones")
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        ctk.CTkLabel(
            header,
            text="Calibrate the screen regions used by the OCR scans.",
            font=FONT_BODY, text_color=C["muted"],
        ).pack(side="left", padx=12)

        # Left sidebar — fixed width, scrollable.
        sidebar = ctk.CTkScrollableFrame(
            self, fg_color=C["surface"], corner_radius=0, width=240,
        )
        sidebar.grid(row=1, column=0, sticky="nsew")
        sidebar.grid_columnconfigure(0, weight=1)
        # Prevent the scrollable frame from shrinking — fixed width.
        try:
            sidebar.configure(width=240)
        except Exception:
            pass

        for idx, (key, icon, label, _hint) in enumerate(_ZONES):
            row = self._build_sidebar_row(sidebar, key, icon, label)
            row.grid(row=idx, column=0, padx=8,
                     pady=(8 if idx == 0 else 4, 4), sticky="ew")

        # Right detail panel — flex.
        self._detail = ctk.CTkScrollableFrame(
            self, fg_color=C["bg"], corner_radius=0,
        )
        self._detail.grid(row=1, column=1, sticky="nsew")
        self._detail.grid_columnconfigure(0, weight=1)

        self._render_detail(self._selected_key)

    # ── Sidebar ─────────────────────────────────────────────

    def _build_sidebar_row(self, parent, key: str, icon: str,
                            label: str) -> ctk.CTkFrame:
        """One row in the sidebar — clickable + status chip."""
        row = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=8)
        row.grid_columnconfigure(1, weight=1)

        btn = ctk.CTkButton(
            row, text=f"{icon}  {label}",
            anchor="w", height=42, corner_radius=8,
            font=FONT_BODY,
            fg_color="transparent", hover_color=C["border"],
            text_color=C["text"],
            command=lambda k=key: self._on_select(k),
        )
        btn.grid(row=0, column=0, columnspan=2, sticky="ew",
                 padx=4, pady=(4, 0))

        chip = ctk.CTkLabel(
            row, text="", font=("Segoe UI", 10, "bold"),
            anchor="w", text_color=C["muted"],
        )
        chip.grid(row=1, column=0, columnspan=2, sticky="ew",
                  padx=12, pady=(0, 6))

        self._sidebar_rows[key] = {"frame": row, "chip": chip, "btn": btn}
        self._refresh_sidebar_row(key)
        return row

    def _refresh_sidebar_row(self, key: str) -> None:
        """Update the chip + selection styling for a single sidebar row."""
        row = self._sidebar_rows.get(key)
        if not row:
            return
        configured = self.controller.is_zone_configured(key)
        if configured:
            row["chip"].configure(text="✓ configured", text_color=C["win"])
        else:
            row["chip"].configure(text="⚠ pending",    text_color=C["draw"])

        # Selection highlight.
        if key == self._selected_key:
            row["frame"].configure(fg_color=C["card_alt"])
            row["btn"].configure(text_color=C["accent"])
        else:
            row["frame"].configure(fg_color=C["card"])
            row["btn"].configure(text_color=C["text"])

    def _on_select(self, key: str) -> None:
        if key == self._selected_key:
            return
        prev = self._selected_key
        self._selected_key = key
        self._refresh_sidebar_row(prev)
        self._refresh_sidebar_row(key)
        self._render_detail(key)

    # ── Detail panel ───────────────────────────────────────

    def _render_detail(self, key: str) -> None:
        """Wipe + rebuild the right-hand card for `key`."""
        for child in self._detail.winfo_children():
            child.destroy()
        self._detail_widgets = {}

        icon, label, hint = _ZONE_META.get(key, ("📐", key, ""))
        zone     = self.controller.get_zone(key)
        captures = max(1, int(zone.get("captures", 1)))

        card = ctk.CTkFrame(self._detail, fg_color=C["card"], corner_radius=12)
        card.grid(row=0, column=0, padx=16, pady=16, sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        # ── Card header: icon + name + status pill ──
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 6))
        head.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(head, text=icon,
                     font=("Segoe UI Emoji", 32)).grid(row=0, column=0,
                                                        rowspan=2,
                                                        padx=(0, 14),
                                                        sticky="w")
        ctk.CTkLabel(head, text=label, font=FONT_SUB,
                     text_color=C["text"]).grid(row=0, column=1, sticky="w")

        configured = self.controller.is_zone_configured(key)
        ctk.CTkLabel(
            head,
            text=("✓ configured" if configured else "⚠ pending"),
            font=("Segoe UI", 11, "bold"),
            text_color=(C["win"] if configured else C["draw"]),
        ).grid(row=0, column=2, sticky="e")

        ctk.CTkLabel(head, text=hint, font=FONT_SMALL, text_color=C["muted"],
                     anchor="w", justify="left", wraplength=520).grid(
            row=1, column=1, columnspan=2, sticky="w")

        # ── Bboxes section: one row per capture step ──
        bbox_frame = ctk.CTkFrame(card, fg_color=C["card_alt"],
                                   corner_radius=10)
        bbox_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(8, 8))
        bbox_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(bbox_frame, text="Capture bboxes",
                     font=FONT_SMALL, text_color=C["muted"]).grid(
            row=0, column=0, columnspan=3, padx=12, pady=(8, 4), sticky="w")

        bboxes = zone.get("bboxes") or []
        bbox_labels: List[ctk.CTkLabel] = []
        for i in range(captures):
            ctk.CTkLabel(
                bbox_frame, text=f"{i + 1}/{captures}",
                font=FONT_SMALL, text_color=C["muted"], width=40,
            ).grid(row=i + 1, column=0, padx=(12, 8), pady=2, sticky="w")
            bb_lbl = ctk.CTkLabel(
                bbox_frame, text="", font=FONT_MONO_S,
                text_color=C["text"], anchor="w",
            )
            bb_lbl.grid(row=i + 1, column=1, padx=(0, 8), pady=2, sticky="ew")
            bbox_labels.append(bb_lbl)
            # Per-capture "Recapture this step" button.
            ctk.CTkButton(
                bbox_frame, text="Capture", width=88, height=26,
                font=FONT_SMALL, corner_radius=6,
                fg_color=C["border"], hover_color=C["border_hl"],
                text_color=C["text"],
                command=lambda k=key, s=i: self._capture_single(k, s),
            ).grid(row=i + 1, column=2, padx=(0, 12), pady=2, sticky="e")

        ctk.CTkFrame(bbox_frame, fg_color="transparent",
                     height=8).grid(row=captures + 1, column=0)

        # ── Action row: Capture all / Test scan / Reset ──
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 8))

        cap_btn = ctk.CTkButton(
            actions,
            text=("Capture all" if captures > 1 else "Capture"),
            width=140, height=34, font=FONT_BODY, corner_radius=8,
            fg_color=C["accent"], hover_color=C["accent_hv"],
            command=lambda k=key: self._start_set_zone(k),
        )
        cap_btn.pack(side="left", padx=(0, 8))

        test_btn = ctk.CTkButton(
            actions, text="Test scan", width=120, height=34,
            font=FONT_BODY, corner_radius=8,
            fg_color=C["border"], hover_color=C["border_hl"],
            text_color=C["text"],
            command=lambda k=key: self._on_test_scan(k),
        )
        test_btn.pack(side="left", padx=(0, 8))

        reset_btn = ctk.CTkButton(
            actions, text="Reset", width=100, height=34,
            font=FONT_BODY, corner_radius=8,
            fg_color="transparent", hover_color=C["lose_hv"],
            border_width=1, border_color=C["border"],
            text_color=C["lose"],
            command=lambda k=key: self._on_reset(k),
        )
        reset_btn.pack(side="left")

        # ── Status line (inline, dynamic) ──
        status = ctk.CTkLabel(card, text="", font=FONT_SMALL,
                               text_color=C["muted"], anchor="w",
                               justify="left", wraplength=620)
        status.grid(row=3, column=0, sticky="ew", padx=20, pady=(4, 8))

        # ── Test scan output ──
        out_lbl = ctk.CTkLabel(
            card, text="OCR output (Test scan)",
            font=FONT_SMALL, text_color=C["muted"], anchor="w",
        )
        out_lbl.grid(row=4, column=0, sticky="w", padx=20, pady=(8, 4))
        out_box = ctk.CTkTextbox(
            card, height=200, font=FONT_MONO, fg_color=C["card_alt"],
            border_width=1, border_color=C["border"],
            text_color=C["text"], corner_radius=8,
        )
        out_box.grid(row=5, column=0, sticky="ew", padx=20, pady=(0, 16))
        out_box.configure(state="disabled")

        # Stash widgets so the action handlers can update them.
        self._detail_widgets = {
            "card":        card,
            "bbox_labels": bbox_labels,
            "captures":    captures,
            "cap_btn":     cap_btn,
            "test_btn":    test_btn,
            "reset_btn":   reset_btn,
            "status":      status,
            "out_box":     out_box,
        }
        self._refresh_bbox_labels(key)

    def _refresh_bbox_labels(self, key: str) -> None:
        """Update the bbox text rows of the currently rendered detail card."""
        if key != self._selected_key:
            return
        zone   = self.controller.get_zone(key)
        bboxes = zone.get("bboxes") or []
        labels = self._detail_widgets.get("bbox_labels") or []
        for i, lbl in enumerate(labels):
            if i < len(bboxes):
                bb = bboxes[i]
                if all(c == 0 for c in bb):
                    lbl.configure(text="⚠ not configured",
                                   text_color=C["lose"])
                else:
                    w = int(bb[2]) - int(bb[0])
                    h = int(bb[3]) - int(bb[1])
                    lbl.configure(
                        text=(f"({int(bb[0])}, {int(bb[1])}) → "
                              f"({int(bb[2])}, {int(bb[3])})   "
                              f"[{w}×{h}]"),
                        text_color=C["text"])
            else:
                lbl.configure(text="⚠ missing", text_color=C["lose"])

    def _set_status(self, text: str, color_key: str = "muted") -> None:
        if self._detail_widgets:
            self._detail_widgets["status"].configure(
                text=text, text_color=C.get(color_key, C["muted"]))

    def _set_buttons_enabled(self, enabled: bool) -> None:
        if not self._detail_widgets:
            return
        state = "normal" if enabled else "disabled"
        for k in ("cap_btn", "test_btn", "reset_btn"):
            try:
                self._detail_widgets[k].configure(state=state)
            except Exception:
                pass

    # ── Capture flow ───────────────────────────────────────

    def _start_set_zone(self, key: str) -> None:
        """Run an N-step picker sequence for `key`."""
        if key != self._selected_key:
            self._on_select(key)
        zone     = self.controller.get_zone(key)
        captures = max(1, int(zone.get("captures", 1)))
        _, _, hint = _ZONE_META.get(key, ("", "", "Click-drag to select"))
        collected: List[Tuple[int, int, int, int]] = []

        def do_step(step: int) -> None:
            self._set_buttons_enabled(False)
            if captures > 1:
                self._set_status(
                    f"Picker {step + 1}/{captures} — {hint}. Press Esc to cancel.",
                    "muted")
            else:
                self._set_status(
                    f"Picker — {hint}. Press Esc to cancel.", "muted")

            def on_done(bbox):
                if bbox is None:
                    self._set_status("Cancelled — no change saved.", "muted")
                    self._set_buttons_enabled(True)
                    return
                collected.append(bbox)
                if step + 1 < captures:
                    # Let the user scroll between captures.
                    self._set_status(
                        f"✓ Got capture {step + 1}/{captures}. "
                        f"Scroll in the game, then click « Continue ».",
                        "muted")
                    self._enter_continue_mode(key, step + 1, captures,
                                              collected, do_step)
                else:
                    self._save_collected(key, collected)

            # Small delay so Tk can flush the disabled state before the
            # overlay grabs focus.
            self.after(50, lambda: ZonePicker(
                self.app,
                hint=(f"{hint}  ({step + 1}/{captures})"
                      if captures > 1 else hint),
                on_done=on_done,
                region=_BLUESTACKS_REGION,
            ))

        do_step(0)

    def _enter_continue_mode(self, key: str, next_step: int, total: int,
                              collected: list, do_step) -> None:
        """Re-arm the Capture button as a 'Continue' button."""
        if not self._detail_widgets:
            return
        self._set_buttons_enabled(True)
        self._detail_widgets["cap_btn"].configure(
            text="Continue",
            command=lambda: self._continue_sequence(
                key, next_step, total, collected, do_step),
        )

    def _continue_sequence(self, key: str, next_step: int, total: int,
                            collected: list, do_step) -> None:
        if self._detail_widgets:
            self._detail_widgets["cap_btn"].configure(
                text="Capture all" if total > 1 else "Capture",
                command=lambda k=key: self._start_set_zone(k),
            )
        do_step(next_step)

    def _capture_single(self, key: str, step: int) -> None:
        """Recapture only one bbox slot of a multi-capture zone."""
        if key != self._selected_key:
            self._on_select(key)
        _, _, hint = _ZONE_META.get(key, ("", "", "Click-drag to select"))
        zone = self.controller.get_zone(key)
        existing = [tuple(b) for b in (zone.get("bboxes") or [])]
        captures = max(1, int(zone.get("captures", 1)))
        # Pad to `captures` length so we can replace step in place.
        while len(existing) < captures:
            existing.append((0, 0, 0, 0))

        self._set_buttons_enabled(False)
        self._set_status(
            f"Picker — {hint} (step {step + 1}/{captures}). "
            f"Press Esc to cancel.", "muted")

        def on_done(bbox):
            if bbox is None:
                self._set_status("Cancelled — no change saved.", "muted")
                self._set_buttons_enabled(True)
                return
            existing[step] = bbox
            self._save_collected(key, existing)

        self.after(50, lambda: ZonePicker(
            self.app,
            hint=(f"{hint}  ({step + 1}/{captures})"
                  if captures > 1 else hint),
            on_done=on_done,
            region=_BLUESTACKS_REGION,
        ))

    def _save_collected(self, key: str, bboxes) -> None:
        try:
            self.controller.set_zone_bboxes(key, list(bboxes))
        except Exception as e:
            log.exception("Failed to save zone %s", key)
            self._set_status(f"⚠ Save error: {e}", "lose")
            self._set_buttons_enabled(True)
            return
        self._set_buttons_enabled(True)
        self._refresh_bbox_labels(key)
        self._refresh_sidebar_row(key)
        self._set_status(f"✓ Zone « {key} » saved.", "win")

    # ── Test scan ───────────────────────────────────────────

    def _on_test_scan(self, key: str) -> None:
        """Run the OCR pipeline once and dump the result in the textbox."""
        if not self.controller.is_zone_configured(key):
            self._set_status(
                "⚠ Zone is not configured yet — capture a bbox first.",
                "lose")
            return

        self._set_buttons_enabled(False)
        self._set_status("Scanning…", "muted")
        self._write_output("")

        def cb(text: str, status: str) -> None:
            # Always re-enable buttons.
            self._set_buttons_enabled(True)
            if status == "ok":
                if text:
                    self._write_output(text)
                    self._set_status(
                        f"✓ Test scan complete ({len(text.splitlines())} "
                        f"lines).", "win")
                else:
                    self._write_output("(empty OCR result)")
                    self._set_status(
                        "⚠ OCR returned an empty string — bbox might be off.",
                        "draw")
            elif status == "ocr_unavailable":
                self._set_status(
                    "⚠ OCR engine unavailable. Install Pillow + a "
                    "PaddleOCR backend, then retry.", "lose")
            elif status == "zone_not_configured":
                self._set_status(
                    "⚠ Zone not configured — capture a bbox first.",
                    "lose")
            elif status == "ocr_error":
                self._set_status(
                    "⚠ OCR engine crashed mid-run — see logs/.",
                    "lose")
            else:
                # Partial results are still informative — show them.
                if text:
                    self._write_output(text)
                self._set_status(f"Status: {status}", "muted")

        try:
            self.controller.scan(key, cb)
        except Exception as e:
            log.exception("controller.scan(%s) raised", key)
            self._set_buttons_enabled(True)
            self._set_status(f"⚠ Scan failed: {e}", "lose")

    def _write_output(self, text: str) -> None:
        if not self._detail_widgets:
            return
        box: ctk.CTkTextbox = self._detail_widgets["out_box"]
        box.configure(state="normal")
        box.delete("1.0", "end")
        if text:
            box.insert("1.0", text)
        box.configure(state="disabled")

    # ── Reset ──────────────────────────────────────────────

    def _on_reset(self, key: str) -> None:
        if not confirm(self,
                       title="Reset zone",
                       message=(f"Clear all bboxes for « {key} » ?\n"
                                "You'll have to recapture them before "
                                "the next scan."),
                       ok_label="Reset", cancel_label="Cancel"):
            return
        self.controller.reset_zone(key)
        self._refresh_bbox_labels(key)
        self._refresh_sidebar_row(key)
        self._set_status(f"Zone « {key} » reset.", "muted")
        self._write_output("")
