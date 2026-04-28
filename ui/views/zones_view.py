"""
============================================================
  FORGE MASTER UI — Zones
  Calibrate the OCR capture regions (bboxes) for each zone:
  profile / opponent / equipment / pet / mount / skill.

  For each zone the user clicks "Set zone" → an overlay opens
  over the whole screen, the user drags a rectangle, and the
  coordinates are saved to zones.json via the GameController.
  Zones that need multiple captures (e.g. profile, which the
  user scrolls between) chain the overlays automatically.
============================================================
"""

from __future__ import annotations

import logging
from typing import List, Tuple

import customtkinter as ctk

from backend.zone_store import is_bbox_valid
from ui.theme import C, FONT_BODY, FONT_MONO_S, FONT_SMALL, FONT_SUB, FONT_TITLE
from ui.zone_picker import ZonePicker

log = logging.getLogger(__name__)

# ── Capture overlay region (screen-absolute) ──────────────
# Full 1920×1080 screen. We previously constrained the overlay to the
# BlueStacks panel (x≥1350) so the simulator stayed clickable, but the
# new wiki-grid zone needs the user to trace over the wiki popup which
# may sit anywhere on the display — so the overlay now spans full screen.
_BLUESTACKS_REGION: Tuple[int, int, int, int] = (0, 0, 1920, 1080)

# ── Zone catalog (order & presentation) ───────────────────
# Each entry: (zone_key, icon, label, hint for user)
_ZONES: List[Tuple[str, str, str, str]] = [
    ("profile",   "📊", "Profile",
     "Trace the zone around your own stat panel"),
    ("opponent",  "⚔",  "Opponent",
     "Trace the zone around the opponent's stat panel"),
    ("equipment", "🛡",  "Equipment",
     "Trace the zone around the equipment comparison popup"),
    ("skill",     "✨", "Skill",
     "Trace the zone around the skill description panel"),
    ("pet",       "🐾", "Pet",
     "Trace the zone around the pet stat panel"),
    ("mount",     "🐴", "Mount",
     "Trace the zone around the mount stat panel"),
    ("player_weapon", "🗡", "Player weapon",
     "Trace a tight box around YOUR equipped weapon icon"),
    ("player_equipment", "🛡", "Player build (8 slots)",
     "Trace the zone around YOUR full character/equipment panel "
     "(same framing as the opponent profile)"),
    ("wiki_grid", "📚", "Wiki grid",
     "Trace the zone around the in-game wiki popup (4×2 item grid). "
     "Used by Equipment Comparator → Calibrate icons."),
]


class ZonesView(ctk.CTkFrame):
    """Zones calibration view."""

    def __init__(self, parent, controller, app):
        super().__init__(parent, fg_color=C["bg"], corner_radius=0)
        self.controller = controller
        self.app        = app
        self._rows: dict = {}  # zone_key → {"bbox_labels": [...], "status": lbl}

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build()

    # ── Layout ──────────────────────────────────────────────

    def _build(self) -> None:
        # Header
        header = ctk.CTkFrame(self, fg_color=C["surface"], corner_radius=0,
                               height=64)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(header, text="Zones",
                     font=FONT_TITLE, text_color=C["text"]).grid(
            row=0, column=0, padx=24, pady=16, sticky="w")

        ctk.CTkLabel(
            header,
            text="Calibrate the screen regions used by the OCR scans.",
            font=FONT_BODY, text_color=C["muted"],
        ).grid(row=0, column=1, padx=12, pady=16, sticky="w")

        # Scrollable body
        scroll = ctk.CTkScrollableFrame(self, fg_color=C["bg"],
                                         corner_radius=0)
        scroll.grid(row=1, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        for idx, (key, icon, label, hint) in enumerate(_ZONES):
            card = self._build_zone_card(scroll, key, icon, label, hint)
            card.grid(row=idx, column=0, padx=16, pady=(16 if idx == 0 else 8, 8),
                       sticky="ew")

        # Footer with global status.
        self._global_status = ctk.CTkLabel(
            scroll, text="", font=FONT_SMALL, text_color=C["muted"])
        self._global_status.grid(row=len(_ZONES), column=0, pady=(8, 16))

    def _build_zone_card(self, parent, key: str, icon: str,
                         label: str, hint: str) -> ctk.CTkFrame:
        card = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=12)
        card.grid_columnconfigure(1, weight=1)

        # Left: big icon + label.
        left = ctk.CTkFrame(card, fg_color="transparent")
        left.grid(row=0, column=0, rowspan=2, padx=(20, 12), pady=16, sticky="nw")
        ctk.CTkLabel(left, text=icon,
                     font=("Segoe UI Emoji", 28)).pack()
        ctk.CTkLabel(left, text=label,
                     font=FONT_SUB, text_color=C["text"]).pack(pady=(4, 0))

        # Middle: hint + current bboxes.
        mid = ctk.CTkFrame(card, fg_color="transparent")
        mid.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=(14, 4))
        mid.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(mid, text=hint,
                     font=FONT_SMALL, text_color=C["muted"],
                     anchor="w", justify="left").grid(
            row=0, column=0, sticky="ew")

        bbox_frame = ctk.CTkFrame(mid, fg_color="transparent")
        bbox_frame.grid(row=1, column=0, sticky="ew", pady=(6, 0))

        bbox_labels: List[ctk.CTkLabel] = []
        zone = self.controller.get_zone(key)
        for i in range(int(zone.get("captures", 1))):
            lbl = ctk.CTkLabel(
                bbox_frame, text="", font=FONT_MONO_S,
                text_color=C["muted"], anchor="w",
            )
            lbl.pack(anchor="w")
            bbox_labels.append(lbl)

        # Right: action buttons.
        right = ctk.CTkFrame(card, fg_color="transparent")
        right.grid(row=0, column=2, rowspan=2, padx=(0, 20), pady=14, sticky="e")

        btn_set = ctk.CTkButton(
            right, text="Set zone", width=120, height=34,
            font=FONT_BODY, corner_radius=8,
            fg_color=C["accent"], hover_color=C["accent_hv"],
            command=lambda k=key: self._start_set_zone(k),
        )
        btn_set.pack(padx=0, pady=(0, 6))

        btn_reset = ctk.CTkButton(
            right, text="Reset", width=120, height=30,
            font=FONT_SMALL, corner_radius=8,
            fg_color=C["border"], hover_color=C["border_hl"],
            text_color=C["text"],
            command=lambda k=key: self._on_reset(k),
        )
        btn_reset.pack(padx=0)

        # Inline status (row 1, spans mid area only).
        status = ctk.CTkLabel(card, text="", font=FONT_SMALL,
                               text_color=C["muted"], anchor="w")
        status.grid(row=1, column=1, sticky="ew", padx=(0, 12), pady=(0, 12))

        # Remember references so we can refresh this row later.
        self._rows[key] = {
            "card":        card,
            "bbox_labels": bbox_labels,
            "status":      status,
            "btn_set":     btn_set,
        }
        self._refresh_row(key)
        return card

    # ── Row refresh ─────────────────────────────────────────

    def _refresh_row(self, key: str) -> None:
        row = self._rows.get(key)
        if not row:
            return
        zone = self.controller.get_zone(key)
        bboxes = zone.get("bboxes") or []
        total  = int(zone.get("captures", 1))

        for i, lbl in enumerate(row["bbox_labels"]):
            if i < len(bboxes):
                bb = bboxes[i]
                if is_bbox_valid(bb):
                    w = int(bb[2]) - int(bb[0])
                    h = int(bb[3]) - int(bb[1])
                    txt = (f"Capture {i+1}/{total}:  "
                           f"({int(bb[0])}, {int(bb[1])}) → "
                           f"({int(bb[2])}, {int(bb[3])})   [{w}×{h}]")
                    lbl.configure(text=txt, text_color=C["text"])
                else:
                    lbl.configure(
                        text=f"Capture {i+1}/{total}:  ⚠ not configured",
                        text_color=C["lose"])
            else:
                lbl.configure(text=f"Capture {i+1}/{total}:  ⚠ missing",
                              text_color=C["lose"])

        configured = self.controller.is_zone_configured(key)
        if configured:
            row["status"].configure(text="✓ Zone configured.",
                                     text_color=C["win"])
        else:
            row["status"].configure(
                text="⚠ Not configured — click « Set zone ».",
                text_color=C["lose"])

    # ── Actions ─────────────────────────────────────────────

    def _start_set_zone(self, key: str) -> None:
        """Kick off an N-step picker sequence for `key`."""
        row = self._rows.get(key)
        zone = self.controller.get_zone(key)
        total = int(zone.get("captures", 1))
        hint_for_zone = next(
            (h for (k, _i, _l, h) in _ZONES if k == key),
            "Click-drag to select the zone")

        collected: List[Tuple[int, int, int, int]] = []

        def do_step(step: int) -> None:
            if row:
                if total > 1:
                    row["status"].configure(
                        text=f"Picker {step+1}/{total} — {hint_for_zone}. "
                             f"Press Esc to cancel.",
                        text_color=C["muted"])
                else:
                    row["status"].configure(
                        text=f"Picker — {hint_for_zone}. Press Esc to cancel.",
                        text_color=C["muted"])
                row["btn_set"].configure(state="disabled")

            # NOTE: we deliberately keep the main window (simulator) visible
            # on the left — the overlay only covers the BlueStacks region on
            # the right, so the user can still see the simulator while
            # tracing zones.

            def on_done(bbox):
                if bbox is None:
                    if row:
                        row["status"].configure(
                            text="Cancelled — no change saved.",
                            text_color=C["muted"])
                        row["btn_set"].configure(state="normal")
                    return

                collected.append(bbox)
                if step + 1 < total:
                    # Let the user scroll before the next capture.
                    self.after(200, lambda: self._prompt_next_step(
                        key, step + 1, total, collected, do_step))
                else:
                    self._save_collected(key, collected)

            # Small delay so Tkinter can flush pending UI updates (button
            # state, status label) before the overlay grabs focus.
            self.after(50, lambda: ZonePicker(
                self.app,
                hint=f"{hint_for_zone}  ({step+1}/{total})"
                     if total > 1 else hint_for_zone,
                on_done=on_done,
                region=_BLUESTACKS_REGION,
            ))

        do_step(0)

    def _prompt_next_step(self, key: str, next_step: int, total: int,
                          collected: list, do_step) -> None:
        row = self._rows.get(key)
        if row:
            row["status"].configure(
                text=(f"✓ Got capture {next_step}/{total}. "
                      f"Scroll in the game, then click « Continue »."),
                text_color=C["muted"])
            row["btn_set"].configure(state="normal", text="Continue",
                                      command=lambda: self._continue_sequence(
                                          key, next_step, total, collected, do_step))

    def _continue_sequence(self, key: str, next_step: int, total: int,
                            collected: list, do_step) -> None:
        # Reset the button text/command for future use and advance.
        row = self._rows.get(key)
        if row:
            row["btn_set"].configure(
                text="Set zone",
                command=lambda k=key: self._start_set_zone(k),
            )
        do_step(next_step)

    def _save_collected(self, key: str, bboxes) -> None:
        try:
            self.controller.set_zone_bboxes(key, bboxes)
        except Exception as e:
            log.exception("Failed to save zone %s", key)
            row = self._rows.get(key)
            if row:
                row["status"].configure(
                    text=f"⚠ Save error: {e}",
                    text_color=C["lose"])
                row["btn_set"].configure(state="normal", text="Set zone",
                                          command=lambda k=key: self._start_set_zone(k))
            return

        row = self._rows.get(key)
        if row:
            row["btn_set"].configure(state="normal", text="Set zone",
                                      command=lambda k=key: self._start_set_zone(k))
        self._refresh_row(key)
        self._global_status.configure(
            text=f"✓ Zone « {key} » saved.", text_color=C["win"])

    def _on_reset(self, key: str) -> None:
        self.controller.reset_zone(key)
        self._refresh_row(key)
        self._global_status.configure(
            text=f"Zone « {key} » reset.", text_color=C["muted"])
