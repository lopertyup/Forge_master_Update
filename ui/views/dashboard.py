"""
============================================================
  FORGE MASTER UI — Dashboard
  Show all the player's stats + active skills.
============================================================
"""

from typing import Dict

import customtkinter as ctk

from ui.theme import (
    C,
    FONT_BIG,
    FONT_BODY,
    FONT_MONO,
    FONT_SMALL,
    FONT_SUB,
    FONT_TITLE,
    FONT_TINY,
    fmt_number,
    rarity_color,
)
from ui.widgets import build_header, skill_icon_grid, stat_hero_card


class DashboardView(ctk.CTkFrame):

    def __init__(self, parent, controller, app):
        super().__init__(parent, fg_color=C["bg"], corner_radius=0)
        self.controller = controller
        self.app        = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build()

    def _build(self) -> None:
        # ── Header with import button ───────────────────────
        header = ctk.CTkFrame(self, fg_color=C["surface"], corner_radius=0,
                               height=64)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(header, text="Dashboard",
                     font=FONT_TITLE, text_color=C["text"]).grid(
            row=0, column=0, padx=24, pady=16, sticky="w")

        ctk.CTkButton(
            header, text="⟳ Update profile",
            font=FONT_BODY, height=36, corner_radius=8,
            fg_color=C["accent"], hover_color=C["accent_hv"],
            command=self._open_import,
        ).grid(row=0, column=2, padx=24, pady=14, sticky="e")

        # ── Scrollable body ─────────────────────────────────
        scroll = ctk.CTkScrollableFrame(self, fg_color=C["bg"],
                                         corner_radius=0)
        scroll.grid(row=1, column=0, sticky="nsew")
        scroll.grid_columnconfigure((0, 1), weight=1)

        profile = self.controller.get_profile()
        if not profile:
            self._empty_state(scroll)
            return

        # ── HP & ATK cards ─────────────────────────────────
        hp_card = stat_hero_card(
            scroll, "❤  Total HP",
            fmt_number(profile.get("hp_total", 0)),
            "Base HP: " + fmt_number(profile.get("hp_base", 0)),
            C["lose"])
        hp_card.grid(row=0, column=0, padx=(16, 8), pady=(16, 8), sticky="ew")

        atk_card = stat_hero_card(
            scroll, "⚔  Total ATK",
            fmt_number(profile.get("attack_total", 0)),
            "Base ATK: " + fmt_number(profile.get("attack_base", 0)),
            C["accent2"])
        atk_card.grid(row=0, column=1, padx=(8, 16), pady=(16, 8), sticky="ew")

        # ── Attack type ────────────────────────────────────
        atk_type   = profile.get("attack_type", "?")
        type_label = "🏹 Ranged" if atk_type == "ranged" else "⚔ Melee"
        type_card  = ctk.CTkFrame(scroll, fg_color=C["card"], corner_radius=12)
        type_card.grid(row=1, column=0, columnspan=2, padx=16, pady=(0, 8),
                        sticky="ew")
        ctk.CTkLabel(type_card, text=f"Attack type: {type_label}",
                     font=FONT_SUB, text_color=C["muted"]).pack(
            padx=20, pady=10)

        # ── Secondary stats ────────────────────────────────
        stats_frame = ctk.CTkFrame(scroll, fg_color=C["card"], corner_radius=12)
        stats_frame.grid(row=2, column=0, columnspan=2, padx=16, pady=(0, 8),
                          sticky="ew")
        stats_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(stats_frame, text="Detailed stats",
                     font=FONT_SUB, text_color=C["text"]).grid(
            row=0, column=0, padx=20, pady=(16, 8), sticky="w")

        stat_rows = [
            ("health_pct",     "Health %"),
            ("damage_pct",     "Damage %"),
            ("melee_pct",      "Melee %"),
            ("ranged_pct",     "Ranged %"),
            ("crit_chance",    "Crit Chance"),
            ("crit_damage",    "Crit Damage"),
            ("health_regen",   "Health Regen"),
            ("lifesteal",      "Lifesteal"),
            ("double_chance",  "Double Chance"),
            ("attack_speed",   "Attack Speed"),
            ("skill_damage",   "Skill Damage"),
            ("skill_cooldown", "Skill Cooldown"),
            ("block_chance",   "Block Chance"),
        ]

        for i, (key, label) in enumerate(stat_rows):
            val = profile.get(key, 0.0)
            row_f = ctk.CTkFrame(
                stats_frame,
                fg_color=C["card_alt"] if i % 2 == 0 else C["card"],
                corner_radius=6,
            )
            row_f.grid(row=i + 1, column=0, padx=12, pady=1, sticky="ew")
            row_f.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(row_f, text=label, font=FONT_BODY,
                         text_color=C["muted"], anchor="w").grid(
                row=0, column=0, padx=16, pady=6, sticky="w")

            color = C["text"] if val else C["disabled"]
            ctk.CTkLabel(
                row_f,
                text=f"{val:+.2f}%" if val else "—",
                font=FONT_MONO, text_color=color, anchor="e",
            ).grid(row=0, column=2, padx=16, pady=6, sticky="e")

        ctk.CTkFrame(stats_frame, fg_color="transparent", height=8).grid(
            row=len(stat_rows) + 1, column=0)

        # ── Active skills ───────────────────────────────────
        skills   = self.controller.get_active_skills()
        sk_frame = ctk.CTkFrame(scroll, fg_color=C["card"], corner_radius=12)
        sk_frame.grid(row=3, column=0, columnspan=2, padx=16, pady=(0, 16),
                       sticky="ew")
        sk_frame.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkLabel(sk_frame, text="Active skills",
                     font=FONT_SUB, text_color=C["text"]).grid(
            row=0, column=0, columnspan=3, padx=20, pady=(16, 8), sticky="w")

        if not skills:
            ctk.CTkLabel(sk_frame, text="No skill equipped",
                         font=FONT_BODY, text_color=C["disabled"]).grid(
                row=1, column=0, columnspan=3, padx=20, pady=16)
        else:
            for idx, (code, data) in enumerate(skills):
                self._skill_card(sk_frame, code, data, row=1, col=idx)

        ctk.CTkFrame(sk_frame, fg_color="transparent", height=8).grid(
            row=2, column=0)

    # ── Sub-widgets ─────────────────────────────────────────

    def _skill_card(self, parent, code: str, data: Dict,
                    row: int, col: int) -> None:
        rarity  = str(data.get("rarity", "common")).lower()
        color   = rarity_color(rarity)
        sk_type = data.get("type", "damage")

        card = ctk.CTkFrame(parent, fg_color=C["card_alt"], corner_radius=10)
        card.grid(row=row, column=col, padx=10, pady=(0, 12), sticky="ew")

        ctk.CTkLabel(card, text=rarity.upper(), font=FONT_TINY,
                     text_color=color, fg_color=C["bg"],
                     corner_radius=4, width=60, height=18).pack(
            anchor="ne", padx=10, pady=(10, 0))

        ctk.CTkLabel(card, text=f"[{code.upper()}]  {data.get('name', '?')}",
                     font=FONT_SUB, text_color=C["text"]).pack(
            padx=14, pady=(0, 2))

        icon = "⚡" if sk_type == "damage" else "🛡"
        ctk.CTkLabel(
            card,
            text=f"{icon} {sk_type.title()}  |  CD: {data.get('cooldown', 0):.1f}s  |  x{int(data.get('hits', 1))} hits",
            font=FONT_SMALL, text_color=C["muted"],
        ).pack(padx=14, pady=(0, 12))

    def _empty_state(self, parent: ctk.CTkBaseClass) -> None:
        ctk.CTkLabel(
            parent,
            text="No profile found\n\nClick « Update profile »\nto import your stats from the game",
            font=FONT_BODY, text_color=C["disabled"], justify="center",
        ).pack(expand=True, pady=80)

    def _open_import(self) -> None:
        ImportDialog(self, self.controller, self.app)


# ════════════════════════════════════════════════════════════
#  Profile import dialog
# ════════════════════════════════════════════════════════════

class ImportDialog(ctk.CTkToplevel):

    def __init__(self, parent, controller, app):
        super().__init__(parent)
        self.controller = controller
        self.app        = app
        self.title("Update profile")
        self.geometry("660x700")
        self.minsize(600, 500)
        self.resizable(True, True)
        self.configure(fg_color=C["surface"])
        self.grab_set()
        self.transient(parent)
        self._build()

    def _build(self) -> None:
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_columnconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(self, fg_color=C["surface"],
                                         corner_radius=0)
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(scroll, text="Paste the profile text",
                     font=("Segoe UI", 16, "bold"),
                     text_color=C["text"]).pack(padx=24, pady=(20, 4),
                                                 anchor="w")

        ctk.CTkLabel(scroll,
                     text="Copy the stat summary from the game and paste it below",
                     font=FONT_BODY, text_color=C["muted"]).pack(
            padx=24, pady=(0, 8), anchor="w")

        self.text_box = ctk.CTkTextbox(
            scroll, height=180, font=FONT_MONO,
            fg_color=C["bg"], text_color=C["text"],
            border_color=C["border"], border_width=1,
        )
        self.text_box.pack(padx=24, pady=(0, 12), fill="x")

        # Attack type
        type_frame = ctk.CTkFrame(scroll, fg_color=C["card"], corner_radius=8)
        type_frame.pack(padx=24, pady=(0, 12), fill="x")
        ctk.CTkLabel(type_frame, text="Attack type:",
                     font=FONT_BODY, text_color=C["text"]).pack(
            side="left", padx=16, pady=10)
        self.type_var = ctk.StringVar(value="ranged")
        ctk.CTkRadioButton(type_frame, text="🏹 Ranged",
                           variable=self.type_var, value="ranged",
                           text_color=C["text"]).pack(side="left", padx=16,
                                                       pady=10)
        ctk.CTkRadioButton(type_frame, text="⚔ Melee",
                           variable=self.type_var, value="melee",
                           text_color=C["text"]).pack(side="left", padx=8,
                                                       pady=10)

        # Skills
        ctk.CTkLabel(scroll, text="Active skills — select up to 3",
                     font=FONT_BODY, text_color=C["text"]).pack(
            padx=24, pady=(0, 6), anchor="w")

        all_skills     = self.controller.get_all_skills()
        current_codes  = {c for c, _ in self.controller.get_active_skills()}
        self._skill_vars = {
            code: ctk.BooleanVar(value=(code in current_codes))
            for code in all_skills
        }

        sk_frame, _btns = skill_icon_grid(
            scroll, all_skills, self._skill_vars, on_toggle=self._toggle_skill,
        )
        sk_frame.pack(padx=24, pady=(0, 8), fill="x")

        self._skill_limit_label = ctk.CTkLabel(
            scroll, text="", font=FONT_SMALL, text_color=C["lose"])
        self._skill_limit_label.pack(padx=24, pady=(0, 8))

        # Fixed button bar
        btn_bar = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=0,
                                height=64)
        btn_bar.grid(row=1, column=0, sticky="ew")
        btn_bar.grid_propagate(False)
        btn_bar.grid_columnconfigure(0, weight=1)

        self._lbl_btn_status = ctk.CTkLabel(
            btn_bar, text="", font=FONT_SMALL, text_color=C["lose"])
        self._lbl_btn_status.pack(side="left", padx=24)

        ctk.CTkButton(btn_bar, text="Cancel", fg_color=C["border"],
                      hover_color=C["border_hl"], font=FONT_BODY, width=120,
                      command=self.destroy).pack(side="right", padx=(8, 24),
                                                  pady=14)
        ctk.CTkButton(btn_bar, text="✓  Save",
                      fg_color=C["accent"], hover_color=C["accent_hv"],
                      font=FONT_BODY, width=160,
                      command=self._save).pack(side="right", pady=14)

    def _toggle_skill(self, code: str) -> None:
        var      = self._skill_vars[code]
        selected = [c for c, v in self._skill_vars.items() if v.get()]
        if not var.get():
            if len(selected) >= 3:
                self._skill_limit_label.configure(text="⚠ Maximum of 3 active skills")
                return
            var.set(True)
        else:
            var.set(False)
        self._skill_limit_label.configure(text="")

    def _save(self) -> None:
        text = self.text_box.get("1.0", "end").strip()
        if not text:
            self._lbl_btn_status.configure(text="⚠ Paste the profile text first")
            return

        selected = [c for c, v in self._skill_vars.items() if v.get()]
        if len(selected) > 3:
            self._lbl_btn_status.configure(text="⚠ Maximum of 3 active skills")
            return

        attack_type = self.type_var.get()
        profile     = self.controller.import_profile_text(text, attack_type)
        skills      = self.controller.get_skills_from_codes(selected)
        self.controller.set_profile(profile, skills)

        self.destroy()
        self.app.refresh_current()
