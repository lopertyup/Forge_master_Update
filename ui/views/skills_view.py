"""
============================================================
  FORGE MASTER UI — Skills
  Visual grid of all skills (grouped by rarity),
  max 3 selection.
============================================================
"""

from typing import Dict

import customtkinter as ctk

from ui.theme import (
    C,
    FONT_BODY,
    FONT_MONO_S,
    FONT_SMALL,
    FONT_SUB,
    FONT_TINY,
    FONT_TITLE,
    RARITY_ORDER,
    fmt_number,
    load_icon,
    rarity_color,
)


class SkillsView(ctk.CTkFrame):

    def __init__(self, parent, controller, app):
        super().__init__(parent, fg_color=C["bg"], corner_radius=0)
        self.controller    = controller
        self.app           = app
        self._selected: Dict[str, ctk.BooleanVar] = {}
        self._skill_frames: Dict[str, ctk.CTkFrame] = {}
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build()

    def _build(self) -> None:
        # Header (custom: count + button + status on the right)
        header = ctk.CTkFrame(self, fg_color=C["surface"], corner_radius=0,
                               height=64)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(header, text="Skills",
                     font=FONT_TITLE, text_color=C["text"]).pack(
            side="left", padx=24, pady=16)

        self._lbl_count = ctk.CTkLabel(
            header, text="0 / 3 selected",
            font=FONT_BODY, text_color=C["muted"])
        self._lbl_count.pack(side="left", padx=16)

        ctk.CTkButton(
            header, text="💾  Save selection",
            font=FONT_BODY, height=36, corner_radius=8,
            fg_color=C["accent"], hover_color=C["accent_hv"],
            command=self._save,
        ).pack(side="right", padx=24, pady=14)

        self._lbl_status = ctk.CTkLabel(
            header, text="", font=FONT_SMALL, text_color=C["lose"])
        self._lbl_status.pack(side="right", padx=8)

        # Scrollable body
        scroll = ctk.CTkScrollableFrame(self, fg_color=C["bg"],
                                         corner_radius=0)
        scroll.grid(row=1, column=0, sticky="nsew")

        all_skills = self.controller.get_all_skills()
        active     = {c for c, _ in self.controller.get_active_skills()}

        # Group by rarity
        by_rarity: Dict[str, list] = {}
        for code, data in all_skills.items():
            r = str(data.get("rarity", "common")).lower()
            by_rarity.setdefault(r, []).append((code, data))

        row_idx = 0
        for rarity in RARITY_ORDER:
            items = by_rarity.get(rarity, [])
            if not items:
                continue

            color = rarity_color(rarity)

            sep = ctk.CTkFrame(scroll, fg_color=C["surface"],
                                corner_radius=8, height=36)
            sep.pack(fill="x", padx=16, pady=(16 if row_idx > 0 else 8, 4))
            ctk.CTkLabel(sep, text=f"  {rarity.upper()}",
                         font=("Segoe UI", 11, "bold"),
                         text_color=color).pack(side="left", padx=12, pady=6)
            ctk.CTkLabel(sep, text=f"{len(items)} skills",
                         font=FONT_SMALL, text_color=C["muted"]).pack(
                side="left", padx=4, pady=6)

            grid_f = ctk.CTkFrame(scroll, fg_color="transparent")
            grid_f.pack(fill="x", padx=16, pady=0)

            cols = 3
            for i, (code, data) in enumerate(sorted(items, key=lambda x: x[0])):
                var = ctk.BooleanVar(value=(code in active))
                self._selected[code] = var
                card = self._make_skill_card(grid_f, code, data, color,
                                              row=i // cols, col=i % cols)
                self._skill_frames[code] = card
                self._update_card_style(code)

            row_idx += 1

        # Legend + initial count
        ctk.CTkLabel(scroll,
                     text="Click on a skill to select it. Maximum 3 active skills.",
                     font=FONT_SMALL, text_color=C["muted"]).pack(pady=16)

        count = sum(1 for v in self._selected.values() if v.get())
        self._lbl_count.configure(text=f"{count} / 3 selected")

    def _make_skill_card(self, parent: ctk.CTkFrame, code: str, data: Dict,
                          color: str, row: int, col: int) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(
            parent, fg_color=C["card"], corner_radius=10,
            border_width=1, border_color=C["border"],
        )
        frame.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
        parent.grid_columnconfigure(col, weight=1)

        # Make the entire card clickable (propagate to root frame)
        def _bind_all(widget: ctk.CTkBaseClass) -> None:
            widget.bind("<Button-1>", lambda _e, c=code: self._toggle(c))

        _bind_all(frame)

        top_f = ctk.CTkFrame(frame, fg_color="transparent")
        top_f.pack(fill="x", padx=10, pady=(10, 0))
        _bind_all(top_f)

        icon_img = load_icon(code, size=52)
        if icon_img:
            icon_lbl = ctk.CTkLabel(top_f, image=icon_img, text="",
                                     fg_color="transparent")
            icon_lbl.pack(side="left", padx=(0, 8))
            _bind_all(icon_lbl)

        right_f = ctk.CTkFrame(top_f, fg_color="transparent")
        right_f.pack(side="left", fill="both", expand=True)
        _bind_all(right_f)

        badge = ctk.CTkLabel(right_f, text=data.get("rarity", "?").upper(),
                             font=FONT_TINY, text_color=color,
                             fg_color=C["bg"], corner_radius=4,
                             width=64, height=18)
        badge.pack(anchor="w")
        _bind_all(badge)

        sk_type   = data.get("type", "damage")
        type_icon = "⚡" if sk_type == "damage" else "🛡"
        type_lbl  = ctk.CTkLabel(right_f, text=type_icon,
                                  font=("Segoe UI", 14), text_color=color)
        type_lbl.pack(anchor="w")
        _bind_all(type_lbl)

        name_lbl = ctk.CTkLabel(
            frame, text=f"[{code.upper()}]  {data.get('name', '?')}",
            font=("Segoe UI", 12, "bold"), text_color=C["text"])
        name_lbl.pack(padx=12, pady=(4, 2))
        _bind_all(name_lbl)

        cooldown = data.get("cooldown", 0)
        hits     = int(data.get("hits", 0))
        damage   = data.get("damage", 0)
        buff_atk = data.get("buff_atk", data.get("buff_atq", 0))
        buff_hp  = data.get("buff_hp", 0)
        buff_dur = data.get("buff_duration", 0)

        if sk_type == "damage":
            info = f"DMG: {fmt_number(damage)} × {hits}  |  CD: {cooldown}s"
        else:
            parts = []
            if buff_atk: parts.append(f"+ATK {fmt_number(buff_atk)}")
            if buff_hp:  parts.append(f"+HP {fmt_number(buff_hp)}")
            info = f"Buff {buff_dur}s  —  " + ("  ".join(parts) if parts else "—")

        info_lbl = ctk.CTkLabel(frame, text=info, font=FONT_MONO_S,
                                 text_color=C["muted"], wraplength=200)
        info_lbl.pack(padx=12, pady=(0, 12))
        _bind_all(info_lbl)

        return frame

    def _toggle(self, code: str) -> None:
        var      = self._selected[code]
        selected = [c for c, v in self._selected.items() if v.get()]

        if not var.get():
            if len(selected) >= 3:
                self._lbl_status.configure(text="⚠ Maximum 3 active skills")
                return
            var.set(True)
        else:
            var.set(False)

        self._lbl_status.configure(text="")
        self._update_card_style(code)
        count = sum(1 for v in self._selected.values() if v.get())
        self._lbl_count.configure(text=f"{count} / 3 selected")

    def _update_card_style(self, code: str) -> None:
        frame = self._skill_frames.get(code)
        if not frame:
            return
        if self._selected[code].get():
            frame.configure(fg_color=C["selected"],
                            border_color=C["win"], border_width=2)
        else:
            frame.configure(fg_color=C["card"],
                            border_color=C["border"], border_width=1)

    def _save(self) -> None:
        codes   = [c for c, v in self._selected.items() if v.get()]
        skills  = self.controller.get_skills_from_codes(codes)
        profile = self.controller.get_profile()
        if not profile:
            self._lbl_status.configure(text="⚠ No profile loaded")
            return
        self.controller.set_profile(profile, skills)
        self._lbl_status.configure(text=f"✅ {len(skills)} skill(s) saved",
                                    text_color=C["win"])
        self.app.refresh_current()