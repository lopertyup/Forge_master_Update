"""
============================================================
  FORGE MASTER UI — Equipment Comparator
  Layout: text on the left | old/new stacked on the right
  Auto-simulation (debounce 600 ms) on two-item detection.
============================================================
"""

from typing import Dict
import re

import customtkinter as ctk

from backend.constants import N_SIMULATIONS
from backend.stats import combat_stats

from ui.theme import (
    C,
    FONT_BIG,
    FONT_BODY,
    FONT_MONO,
    FONT_MONO_S,
    FONT_SMALL,
    FONT_SUB,
    fmt_number,
)
from ui.widgets import attach_scan_button, build_header, confirm


# Stats displayed on equipment — canonical in-game order.
# Flat stats first, then substats in the order the game shows them.
_STAT_ROWS = [
    ("hp_flat",        "Health (flat)",  True),
    ("damage_flat",    "Damage (flat)",  True),
    ("crit_chance",    "Crit Chance",    False),
    ("crit_damage",    "Crit Damage",    False),
    ("block_chance",   "Block Chance",   False),
    ("health_regen",   "Health Regen",   False),
    ("lifesteal",      "Lifesteal",      False),
    ("double_chance",  "Double Chance",  False),
    ("damage_pct",     "Damage %",       False),
    ("melee_pct",      "Melee %",        False),
    ("ranged_pct",     "Ranged %",       False),
    ("attack_speed",   "Attack Speed",   False),
    ("skill_damage",   "Skill Damage",   False),
    ("skill_cooldown", "Skill Cooldown", False),
    ("health_pct",     "Health %",       False),
]


def _has_two_items(text: str) -> bool:
    """True when the text contains at least two '[Rarity] Name' lines."""
    return len(re.findall(r'^\[', text, re.MULTILINE)) >= 2


class EquipmentView(ctk.CTkFrame):

    def __init__(self, parent, controller, app):
        super().__init__(parent, fg_color=C["bg"], corner_radius=0)
        self.controller   = controller
        self.app          = app
        self._new_profile = None
        self._after_id    = None  # debounce auto-analysis
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build()

    # ── Build ─────────────────────────────────────────────────

    def _build(self) -> None:
        build_header(self, "Equipment Comparator")

        body = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        body.grid(row=1, column=0, sticky="nsew", padx=16, pady=12)
        body.grid_columnconfigure(0, weight=2)   # text column
        body.grid_columnconfigure(1, weight=3)   # equipment column
        body.grid_rowconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=0)

        # ── Left: input ───────────────────────────────────────
        left = ctk.CTkFrame(body, fg_color=C["card"], corner_radius=12)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 8))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(left, text="Paste text here",
                     font=FONT_SUB, text_color=C["text"]).grid(
            row=0, column=0, padx=16, pady=(14, 4), sticky="w")

        self.text_box = ctk.CTkTextbox(
            left, font=FONT_MONO_S,
            fg_color=C["bg"], text_color=C["text"],
            border_color=C["border"], border_width=1,
        )
        self.text_box.grid(row=1, column=0, padx=12, pady=(0, 6), sticky="nsew")
        self.text_box.bind("<KeyRelease>", self._on_text_change)

        # ── Scan button row (OCR — equipment has 2 bboxes) ──
        self._scan_row = ctk.CTkFrame(left, fg_color="transparent")
        self._scan_row.grid(row=2, column=0, padx=12, pady=(0, 6), sticky="ew")

        self._lbl_err = ctk.CTkLabel(left, text="", font=FONT_SMALL,
                                      text_color=C["lose"], wraplength=260)
        self._lbl_err.grid(row=3, column=0, padx=12, pady=(0, 4))

        self._lbl_status = ctk.CTkLabel(left, text="Waiting for text…",
                                         font=FONT_SMALL, text_color=C["muted"],
                                         wraplength=260)
        self._lbl_status.grid(row=4, column=0, padx=12, pady=(0, 12))

        # Scan button — wired AFTER _lbl_status is created so it can write
        # its progress / errors into the same status label the analyzer uses.
        attach_scan_button(
            parent_btn_frame=self._scan_row,
            textbox=self.text_box,
            status_lbl=self._lbl_status,
            scan_key="equipment",
            scan_fn=self.controller.scan,
            captures_fn=self.controller.get_zone_captures,
            on_scan_ready=self._on_scan_ready,
        )

        # ── Right: old + new ──────────────────────────────────
        right = ctk.CTkFrame(body, fg_color="transparent", corner_radius=0)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=(0, 8))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure((0, 1), weight=1)

        self.card_old = ctk.CTkFrame(right, fg_color=C["card"], corner_radius=12)
        self.card_old.grid(row=0, column=0, sticky="nsew", pady=(0, 6))
        self.card_old.grid_columnconfigure(0, weight=1)
        self._lbl_title_old = ctk.CTkLabel(
            self.card_old, text="Current equipment",
            font=FONT_SUB, text_color=C["muted"])
        self._lbl_title_old.pack(padx=16, pady=(12, 4), anchor="w")
        self._inner_old = ctk.CTkScrollableFrame(
            self.card_old, fg_color="transparent", height=120)
        self._inner_old.pack(fill="both", expand=True, padx=8, pady=(0, 10))

        self.card_new = ctk.CTkFrame(right, fg_color=C["card"], corner_radius=12)
        self.card_new.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        self.card_new.grid_columnconfigure(0, weight=1)
        self._lbl_title_new = ctk.CTkLabel(
            self.card_new, text="New equipment",
            font=FONT_SUB, text_color=C["accent"])
        self._lbl_title_new.pack(padx=16, pady=(12, 4), anchor="w")
        self._inner_new = ctk.CTkScrollableFrame(
            self.card_new, fg_color="transparent", height=120)
        self._inner_new.pack(fill="both", expand=True, padx=8, pady=(0, 10))

        # ── Bottom: results ───────────────────────────────────
        self.bottom = ctk.CTkFrame(body, fg_color=C["card"], corner_radius=12)
        self.bottom.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.bottom.grid_columnconfigure((0, 1, 2), weight=1)
        self._build_bottom_empty()

    def _build_bottom_empty(self) -> None:
        for w in self.bottom.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.bottom,
                     text="Simulation results will appear here.",
                     font=FONT_SMALL, text_color=C["muted"]).pack(pady=18)

    # ── OCR callback ──────────────────────────────────────────

    def _on_scan_ready(self) -> None:
        """Called once the OCR finished writing both captures into the
        textbox. Equipment auto-runs the analyzer when two items are
        detected — check for that and trigger the same pipeline used by
        the KeyRelease handler."""
        text = self.text_box.get("1.0", "end").strip()
        if _has_two_items(text):
            if self._after_id:
                self.after_cancel(self._after_id)
            self._after_id = self.after(50, self._analyze)
        else:
            self._lbl_status.configure(
                text="✓ OCR complete. Waiting for two items…",
                text_color=C["muted"])

    # ── Auto-analysis (debounce 600 ms) ───────────────────────

    def _on_text_change(self, _event=None) -> None:
        if self._after_id:
            self.after_cancel(self._after_id)
        text = self.text_box.get("1.0", "end").strip()
        if _has_two_items(text):
            self._after_id = self.after(600, self._analyze)
        else:
            self._lbl_status.configure(
                text="Waiting for two items in the text…")
            self._lbl_err.configure(text="")

    # ── Analysis + simulation ─────────────────────────────────

    def _analyze(self) -> None:
        self._after_id = None

        if not self.controller.has_profile():
            self._lbl_err.configure(
                text="⚠ No player profile. Go to the Dashboard first.")
            return

        text   = self.text_box.get("1.0", "end").strip()
        result = self.controller.compare_equipment(text)
        if result is None:
            self._lbl_err.configure(
                text="⚠ Invalid text: make sure two items are present.")
            return

        self._lbl_err.configure(text="")
        eq_old, eq_new, new_profile = result
        self._new_profile = new_profile

        self._render_eq(self._inner_old, eq_old)
        self._render_eq(self._inner_new, eq_new)

        lbl_old = "Current equipment"
        lbl_new = "New equipment"
        t_old   = eq_old.get("attack_type")
        t_new   = eq_new.get("attack_type")
        if t_old:
            lbl_old += f"  {'🏹 Ranged' if t_old == 'ranged' else '⚔ Melee'}"
        if t_new:
            lbl_new += f"  {'🏹 Ranged' if t_new == 'ranged' else '⚔ Melee'}"
        self._lbl_title_old.configure(text=lbl_old)
        self._lbl_title_new.configure(text=lbl_new)

        self._lbl_status.configure(text="⏳ Simulation running…")
        self._build_bottom_loading()

        se_old = combat_stats(self.controller.get_profile())
        skills = self.controller.get_active_skills()

        self.controller.simulate(
            se_old, skills, self._on_sim_done,
            profile_override=new_profile,
            skills_override=skills,
        )

    def _build_bottom_loading(self) -> None:
        for w in self.bottom.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self.bottom,
            text=f"⏳ Simulation running ({N_SIMULATIONS} fights)…",
            font=FONT_BODY, text_color=C["muted"]).pack(pady=18)

    def _on_sim_done(self, wins: int, loses: int, draws: int) -> None:
        self._lbl_status.configure(text="✅ Analysis complete.")
        self._display_results(wins, loses, draws)

    # ── Equipment rendering ───────────────────────────────────

    def _render_eq(self, parent: ctk.CTkScrollableFrame, eq: Dict) -> None:
        for w in parent.winfo_children():
            w.destroy()

        # Tout équipement avec "damage_flat" est une arme — on doit donc
        # afficher son type d'attaque (ranged / melee) pour que l'utilisateur
        # puisse vérifier que le parser l'a bien détecté.
        atk_type = eq.get("attack_type")
        has_flat = bool(eq.get("damage_flat", 0.0))

        any_shown = False
        for i, (key, label, is_flat) in enumerate(_STAT_ROWS):
            val = eq.get(key, 0.0)
            if not val:
                continue
            any_shown = True
            row_f = ctk.CTkFrame(
                parent,
                fg_color=C["card_alt"] if i % 2 == 0 else C["card"],
                corner_radius=4,
            )
            row_f.pack(padx=4, pady=1, fill="x")
            row_f.grid_columnconfigure(1, weight=1)

            # Pour la ligne "Damage (flat)" d'une arme, on accole
            # un badge ranged / melee au label.
            row_label = label
            if key == "damage_flat" and has_flat:
                badge = "🏹 Ranged" if atk_type == "ranged" else "⚔ Melee"
                row_label = f"{label}  ({badge})"

            ctk.CTkLabel(row_f, text=row_label, font=FONT_SMALL,
                         text_color=C["muted"], anchor="w").grid(
                row=0, column=0, padx=10, pady=4, sticky="w")
            val_str = fmt_number(val) if is_flat else f"+{val}%"
            ctk.CTkLabel(row_f, text=val_str, font=FONT_MONO,
                         text_color=C["text"], anchor="e").grid(
                row=0, column=1, padx=10, pady=4, sticky="e")

        if not any_shown:
            ctk.CTkLabel(parent, text="No stats detected",
                         font=FONT_SMALL, text_color=C["muted"]).pack(pady=10)

    # ── Results rendering ─────────────────────────────────────

    def _display_results(self, wins: int, loses: int, draws: int) -> None:
        for w in self.bottom.winfo_children():
            w.destroy()

        total = wins + loses + draws or 1
        pct   = 100.0 / total

        # WIN / LOSE / DRAW counters
        for col, (label, val, color) in enumerate([
            ("WIN",  wins,  C["win"]),
            ("LOSE", loses, C["lose"]),
            ("DRAW", draws, C["draw"]),
        ]):
            f = ctk.CTkFrame(self.bottom, fg_color=C["card_alt"],
                              corner_radius=10)
            f.grid(row=0, column=col, padx=10, pady=(12, 6), sticky="ew")
            ctk.CTkLabel(f, text=label, font=FONT_SMALL,
                         text_color=C["muted"]).pack(pady=(6, 0))
            ctk.CTkLabel(f, text=str(val), font=FONT_BIG,
                         text_color=color).pack()
            ctk.CTkLabel(f, text=f"{val * pct:.1f}%", font=FONT_SMALL,
                         text_color=C["muted"]).pack(pady=(0, 6))

        bar = ctk.CTkProgressBar(
            self.bottom, height=8, corner_radius=4,
            progress_color=C["win"] if wins >= loses else C["lose"])
        bar.grid(row=1, column=0, columnspan=3, padx=16, pady=(0, 6),
                  sticky="ew")
        bar.set(wins / total)

        # Verdict
        is_better = wins > loses
        if is_better:
            verdict       = f"✅  Better equipment! ({wins * pct:.1f}% WIN)"
            verdict_color = C["win"]
        elif loses > wins:
            verdict       = f"❌  Worse equipment. ({loses * pct:.1f}% LOSE)"
            verdict_color = C["lose"]
        else:
            verdict       = "🤝  Equivalent."
            verdict_color = C["draw"]

        ctk.CTkLabel(self.bottom, text=verdict, font=FONT_SUB,
                     text_color=verdict_color).grid(
            row=2, column=0, columnspan=3, padx=16, pady=(0, 8))

        # Buttons
        btn_frame = ctk.CTkFrame(self.bottom, fg_color="transparent")
        btn_frame.grid(row=3, column=0, columnspan=3, padx=16, pady=(0, 12),
                        sticky="ew")
        btn_frame.grid_columnconfigure((0, 1), weight=1)

        if is_better:
            ctk.CTkButton(
                btn_frame, text="💾  Apply new equipment",
                font=FONT_BODY, height=36, corner_radius=8,
                fg_color=C["win"], hover_color=C["win_hv"],
                text_color=C["bg"],
                command=self._apply,
            ).grid(row=0, column=0, padx=(0, 6), sticky="ew")

            ctk.CTkButton(
                btn_frame, text="✖  Do not apply",
                font=FONT_BODY, height=36, corner_radius=8,
                fg_color=C["lose"], hover_color=C["lose_hv"],
                text_color=C["text"],
                command=self._clear,
            ).grid(row=0, column=1, padx=(6, 0), sticky="ew")
        else:
            ctk.CTkButton(
                btn_frame, text="💾  Apply anyway",
                font=FONT_BODY, height=36, corner_radius=8,
                fg_color=C["lose"], hover_color=C["lose_hv"],
                text_color=C["text"],
                command=self._apply_anyway,
            ).grid(row=0, column=0, padx=(0, 6), sticky="ew")

            ctk.CTkButton(
                btn_frame, text="✔  Keep current equipment",
                font=FONT_BODY, height=36, corner_radius=8,
                fg_color=C["win"], hover_color=C["win_hv"],
                text_color=C["bg"],
                command=self._clear,
            ).grid(row=0, column=1, padx=(6, 0), sticky="ew")

    # ── Actions ───────────────────────────────────────────────

    def _apply(self) -> None:
        if self._new_profile:
            self.controller.apply_equipment(self._new_profile)
            self.app.refresh_current()
        self._clear()

    def _apply_anyway(self) -> None:
        """Applies a worse equipment — asks for confirmation."""
        if not confirm(
            self.app, "Apply worse equipment",
            "Simulations indicate this new equipment performs worse.\n\n"
            "Do you really want to replace your current equipment?",
            ok_label="Apply anyway",
            cancel_label="Cancel",
            danger=True,
        ):
            return
        self._apply()

    def _clear(self) -> None:
        self.text_box.delete("1.0", "end")
        self._new_profile = None
        self._lbl_err.configure(text="")
        self._lbl_status.configure(text="Waiting for text…")
        self._render_eq(self._inner_old, {})
        self._render_eq(self._inner_new, {})
        self._build_bottom_empty()