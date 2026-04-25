"""
============================================================
  FORGE MASTER UI — Skills Management
  3 slots (S1, S2, S3) — same pattern as pets/mount.
  Tests a new skill against each equipped slot to find the
  best one to replace.
============================================================
"""

from typing import Dict, Optional, Tuple

import customtkinter as ctk

from ui.theme import (
    C,
    FONT_BODY,
    FONT_MONO_S,
    FONT_SMALL,
    FONT_SUB,
    FONT_TINY,
    RARITY_ORDER,
    fmt_number,
    load_skill_icon_by_name,
    rarity_color,
)
from ui.widgets import (
    build_header,
    build_import_zone,
    build_wld_bars,
    confirm,
)
from backend.constants import N_SIMULATIONS

# Slot identity (same pattern as PET_ICONS / MOUNT_ICON in theme.py)
_SLOTS      = ("S1", "S2", "S3")
_SLOT_ICONS = {"S1": "✨", "S2": "💫", "S3": "⚡"}


class SkillsView(ctk.CTkFrame):

    def __init__(self, parent, controller, app):
        super().__init__(parent, fg_color=C["bg"], corner_radius=0)
        self.controller = controller
        self.app        = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build()

    # ── Build ─────────────────────────────────────────────────

    def _build(self) -> None:
        build_header(self, "Skills Management")

        self._scroll = ctk.CTkScrollableFrame(self, fg_color=C["bg"],
                                               corner_radius=0)
        self._scroll.grid(row=1, column=0, sticky="nsew")
        self._scroll.grid_columnconfigure(0, weight=1)

        self._build_skill_cards()
        self._build_import()
        self._build_result_zone()
        self._build_library()

    def _build_skill_cards(self) -> None:
        skills_frame = ctk.CTkFrame(self._scroll, fg_color="transparent")
        skills_frame.grid(row=0, column=0, padx=16, pady=16, sticky="ew")
        skills_frame.grid_columnconfigure((0, 1, 2), weight=1)

        slots = self.controller.get_skill_slots()
        for col, slot in enumerate(_SLOTS):
            data = slots.get(slot) or {}
            card = self._skill_slot_card(skills_frame, slot, data)
            card.grid(row=0, column=col, padx=6, pady=0, sticky="nsew")

    def _build_import(self) -> None:
        card, self._textbox, self._lbl_status = build_import_zone(
            self._scroll,
            title="Test a new skill",
            hint="Paste the skill stats from the game "
                 "(including the « Passive: +xx Base Damage +xx Base Health » line).",
            primary_label="🔬  Simulate replacement",
            primary_cmd=self._test_skill,
            secondary_label="✏  Directly edit a slot",
            secondary_cmd=self._edit_direct,
            scan_key="skill",
            scan_fn=self.controller.scan,
            captures_fn=self.controller.get_zone_captures,
            on_scan_ready=self._test_skill,
        )
        card.grid(row=1, column=0, padx=16, pady=(0, 8), sticky="ew")

    def _build_result_zone(self) -> None:
        self._result_outer = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._result_outer.grid(row=2, column=0, padx=16, pady=(0, 16),
                                sticky="ew")
        self._result_outer.grid_columnconfigure(0, weight=1)

    def _build_library(self) -> None:
        """Skills library (Lv.1 reference stats)."""
        card = ctk.CTkFrame(self._scroll, fg_color=C["card"], corner_radius=12)
        card.grid(row=3, column=0, padx=16, pady=(0, 16), sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(card, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 4))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="📚  Skills Library",
                     font=FONT_SUB, text_color=C["text"]).grid(
            row=0, column=0, sticky="w")
        ctk.CTkLabel(header,
                     text="Lv.1 reference stats are used only for swap comparisons. "
                          "Equipped skills keep their current-level stats.",
                     font=FONT_SMALL, text_color=C["muted"],
                     wraplength=700, justify="left").grid(
            row=1, column=0, sticky="w", pady=(2, 0))

        library = self.controller.get_skills_library()

        if not library:
            ctk.CTkLabel(
                card,
                text="No skills in library. Paste a Lv.1 skill in the zone above "
                     "and click « Simulate » — it will be added automatically.",
                font=FONT_SMALL, text_color=C["muted"],
                wraplength=700, justify="left").grid(
                row=1, column=0, padx=20, pady=(0, 16), sticky="w")
            return

        lst = ctk.CTkFrame(card, fg_color="transparent")
        lst.grid(row=1, column=0, padx=10, pady=(4, 12), sticky="ew")
        lst.grid_columnconfigure(2, weight=1)

        def _sort_key(n: str):
            rar = str(library[n].get("rarity", "common")).lower()
            idx = RARITY_ORDER.index(rar) if rar in RARITY_ORDER else 0
            return (idx, n.lower())

        for i, name in enumerate(sorted(library.keys(), key=_sort_key)):
            entry = library[name]
            bg = C["card_alt"] if i % 2 == 0 else C["card"]
            row = ctk.CTkFrame(lst, fg_color=bg, corner_radius=6)
            row.grid(row=i, column=0, columnspan=5, sticky="ew", padx=4, pady=2)
            row.grid_columnconfigure(2, weight=1)

            # Skill icon — PNG when available, else the type glyph.
            sk_type   = str(entry.get("type", "damage"))
            type_icon = "⚔" if sk_type == "damage" else "🛡"
            icon_img  = load_skill_icon_by_name(name, size=36)
            ctk.CTkLabel(
                row,
                image=icon_img if icon_img else None,
                text="" if icon_img else type_icon,
                font=("Segoe UI", 22),
                width=44, height=44,
            ).grid(row=0, column=0, padx=(8, 2), pady=4)

            rar = str(entry.get("rarity", "common")).lower()
            ctk.CTkLabel(row, text=rar.upper(),
                         font=FONT_TINY, text_color=rarity_color(rar),
                         width=80).grid(row=0, column=1, padx=(6, 6), pady=6)
            ctk.CTkLabel(row, text=name, font=FONT_BODY,
                         text_color=C["text"], anchor="w").grid(
                row=0, column=2, padx=6, pady=6, sticky="w")

            stats_txt = self._library_stat_line(entry)
            ctk.CTkLabel(row, text=stats_txt, font=FONT_MONO_S,
                         text_color=C["muted"]).grid(
                row=0, column=3, padx=6, pady=6)

            ctk.CTkButton(
                row, text="🗑", width=32, height=26,
                font=FONT_SMALL, corner_radius=6,
                fg_color="transparent", hover_color=C["lose"],
                text_color=C["muted"],
                command=lambda n=name: self._delete_from_library(n),
            ).grid(row=0, column=4, padx=(4, 10), pady=4)

    @staticmethod
    def _library_stat_line(entry: Dict) -> str:
        """Summarize a library entry in one line."""
        sk_type = str(entry.get("type", "damage"))
        if sk_type == "damage":
            dmg  = entry.get("damage", 0) or 0
            hits = int(entry.get("hits", 1) or 1)
            cd   = entry.get("cooldown", 0) or 0
            core = f"⚔ {fmt_number(dmg)} × {hits}  CD {cd:g}s"
        else:
            dur = entry.get("buff_duration", 0) or 0
            atk = entry.get("buff_atk", 0) or 0
            hp  = entry.get("buff_hp",  0) or 0
            bits = []
            if atk: bits.append(f"+ATK {fmt_number(atk)}")
            if hp:  bits.append(f"+HP {fmt_number(hp)}")
            core = f"🛡 {dur:g}s  " + ("  ".join(bits) if bits else "—")
        # Passive bonuses
        pd = entry.get("passive_damage", 0) or 0
        ph = entry.get("passive_hp",     0) or 0
        passive = f"   Passive: ⚔+{fmt_number(pd)}  ❤+{fmt_number(ph)}"
        return core + passive

    def _delete_from_library(self, name: str) -> None:
        if not confirm(
            self.app, "Remove from library",
            f"Remove « {name} » from the skills library?\n"
            "Future imports of this name will need to be re-done at Lv.1.",
            ok_label="Remove", danger=True,
        ):
            return
        if self.controller.remove_skill_library(name):
            self.app.refresh_current()

    # ── Skill slot card (equipped skill display) ─────────────

    def _skill_slot_card(self, parent: ctk.CTkBaseClass,
                          slot: str, data: Dict) -> ctk.CTkFrame:
        """
        Build a 'S1/S2/S3' card showing the equipped skill with its
        current-level stats + passive bonuses + rarity / level badges.
        If the slot is empty (no __name__), show the empty state.
        """
        card = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=12)

        # Top band: slot label
        slot_icon = _SLOT_ICONS.get(slot, "✨")
        ctk.CTkLabel(card, text=f"{slot_icon}  {slot}", font=FONT_SUB,
                     text_color=C["muted"]).pack(
            padx=16, pady=(12, 4), anchor="w")

        name = data.get("__name__")
        if not name:
            # Empty state
            ctk.CTkLabel(card, text="— empty slot —", font=FONT_BODY,
                         text_color=C["muted"]).pack(padx=16, pady=(4, 20))
            return card

        # Identity band: skill icon (PNG if available, else type glyph) +
        # name + rarity/level badges.
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=12, pady=(0, 6))

        sk_type   = str(data.get("type", "damage"))
        type_icon = "⚔" if sk_type == "damage" else "🛡"
        rar       = str(data.get("__rarity__", "common")).lower()

        icon_img = load_skill_icon_by_name(name, size=48)
        ctk.CTkLabel(
            head,
            image=icon_img if icon_img else None,
            text="" if icon_img else type_icon,
            font=("Segoe UI", 26),
            text_color=rarity_color(rar),
            width=56, height=56,
        ).pack(side="left", padx=(2, 8))

        info = ctk.CTkFrame(head, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(info, text=name, font=FONT_SUB,
                     text_color=C["text"], anchor="w").pack(anchor="w")

        meta_row = ctk.CTkFrame(info, fg_color="transparent")
        meta_row.pack(anchor="w", fill="x")
        ctk.CTkLabel(meta_row, text=rar.upper(), font=FONT_TINY,
                     text_color=rarity_color(rar), anchor="w").pack(side="left")
        lvl = data.get("__level__")
        if lvl:
            ctk.CTkLabel(meta_row, text=f"Lv.{int(lvl)}", font=FONT_TINY,
                         text_color=C["accent"], anchor="w").pack(
                side="left", padx=(8, 0))

        # Stats block
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=10, pady=(0, 10))
        i = 0
        for label, value in self._active_stat_rows(data):
            self._stat_row(inner, label, value, row_index=i).pack(fill="x", pady=1)
            i += 1
        # Passive bonuses — always shown if non-zero
        pd = float(data.get("passive_damage", 0) or 0)
        ph = float(data.get("passive_hp",     0) or 0)
        if pd:
            self._stat_row(inner, "⚔  Passive Dmg", fmt_number(pd),
                            row_index=i).pack(fill="x", pady=1); i += 1
        if ph:
            self._stat_row(inner, "❤  Passive HP",  fmt_number(ph),
                            row_index=i).pack(fill="x", pady=1); i += 1

        ctk.CTkFrame(card, fg_color="transparent", height=6).pack()
        return card

    @staticmethod
    def _active_stat_rows(data: Dict):
        """Yield (label, pre-formatted value) pairs for the active part of a skill."""
        sk_type = str(data.get("type", "damage"))
        if sk_type == "damage":
            dmg  = float(data.get("damage", 0) or 0)
            hits = int(data.get("hits", 1) or 1)
            cd   = float(data.get("cooldown", 0) or 0)
            if dmg:  yield ("⚔  Damage / hit", fmt_number(dmg))
            if hits: yield ("🔢 Hits",          str(hits))
            if cd:   yield ("⏱  Cooldown",      f"{cd:g}s")
        else:
            dur = float(data.get("buff_duration", 0) or 0)
            atk = float(data.get("buff_atk",      0) or 0)
            hp  = float(data.get("buff_hp",       0) or 0)
            cd  = float(data.get("cooldown",      0) or 0)
            if dur: yield ("⏳ Buff duration", f"{dur:g}s")
            if atk: yield ("⚔  Buff ATK",     fmt_number(atk))
            if hp:  yield ("❤  Buff HP",      fmt_number(hp))
            if cd:  yield ("⏱  Cooldown",     f"{cd:g}s")

    @staticmethod
    def _stat_row(parent: ctk.CTkBaseClass, label: str, value: str,
                   row_index: int = 0) -> ctk.CTkFrame:
        """Zebra-striped row: label on the left, pre-formatted value on the right."""
        bg = C["card_alt"] if row_index % 2 == 0 else C["card"]
        row = ctk.CTkFrame(parent, fg_color=bg, corner_radius=4)
        row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(row, text=label, font=FONT_SMALL,
                     text_color=C["muted"], anchor="w").grid(
            row=0, column=0, padx=10, pady=4, sticky="w")
        ctk.CTkLabel(row, text=value, font=("Consolas", 12),
                     text_color=C["text"], anchor="e").grid(
            row=0, column=1, padx=10, pady=4, sticky="e")
        return row

    # ── Actions ───────────────────────────────────────────────

    def _test_skill(self) -> None:
        if not self.controller.has_profile():
            self._lbl_status.configure(
                text="⚠ No player profile. Go to Dashboard first.",
                text_color=C["lose"])
            return

        text = self._textbox.get("1.0", "end").strip()
        if not text:
            self._lbl_status.configure(text="⚠ Paste the skill stats.",
                                        text_color=C["lose"])
            return

        new_skill, status, meta = self.controller.resolve_skill(text)

        if status == "no_name":
            self._lbl_status.configure(
                text="⚠ Could not read the skill name (expected: « [Rarity] Name »).",
                text_color=C["lose"])
            return

        if status == "unknown":
            name = meta.get("name") if meta else "?"
            self._lbl_status.configure(
                text=f"⚠ « {name} » is not in the library — "
                     "check the spelling or add it manually to skills_library.txt.",
                text_color=C["lose"])
            return

        for w in self._result_outer.winfo_children():
            w.destroy()

        self._lbl_status.configure(text="⏳ Simulation running…",
                                    text_color=C["muted"])
        self.update_idletasks()

        def on_result(results: Dict[str, Tuple[int, int, int]]) -> None:
            self._lbl_status.configure(text="", text_color=C["muted"])
            self._display_results(results, new_skill)

        self.controller.test_skill(new_skill, on_result)

    def _display_results(self, results: Dict[str, Tuple[int, int, int]],
                          new_skill: Dict) -> None:
        for w in self._result_outer.winfo_children():
            w.destroy()

        if not results:
            return

        title = ctk.CTkFrame(self._result_outer, fg_color=C["card"],
                              corner_radius=12)
        title.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(title, text="Results — which slot to replace?",
                     font=FONT_SUB, text_color=C["text"]).pack(
            padx=20, pady=(14, 4), anchor="w")
        ctk.CTkLabel(title,
                     text="New me (with this skill) vs Old me (with the old skill in that slot).",
                     font=FONT_SMALL, text_color=C["muted"]).pack(
            padx=20, pady=(0, 12), anchor="w")

        best = max(results, key=lambda k: results[k][0])
        wins_max, loses_max, _ = results[best]

        cards = ctk.CTkFrame(self._result_outer, fg_color="transparent")
        cards.pack(fill="x", pady=(0, 8))
        cards.grid_columnconfigure((0, 1, 2), weight=1)

        for col, slot in enumerate(_SLOTS):
            wins, loses, draws = results[slot]
            is_best = (slot == best and wins > loses)

            card = ctk.CTkFrame(
                cards,
                fg_color=C["selected"] if is_best else C["card"],
                corner_radius=12,
                border_width=2 if is_best else 0,
                border_color=C["win"] if is_best else C["card"],
            )
            card.grid(row=0, column=col, padx=6, pady=0, sticky="nsew")

            slot_icon = _SLOT_ICONS.get(slot, "✨")
            ctk.CTkLabel(card, text=f"{slot_icon} Replace {slot}",
                         font=FONT_SUB,
                         text_color=C["win"] if is_best else C["text"]).pack(
                padx=16, pady=(14, 2))

            if is_best:
                ctk.CTkLabel(card, text="★ BEST OPTION",
                             font=FONT_TINY, text_color=C["win"]).pack()

            bars = build_wld_bars(card, wins, loses, draws,
                                   total=N_SIMULATIONS, compact=True,
                                   bar_height=8)
            bars.pack(fill="x", padx=12, pady=(4, 2))

            if wins > loses:
                v_txt = f"✅ +{100 * wins / N_SIMULATIONS:.0f}% WIN"
                v_col = C["win"]
            elif loses > wins:
                v_txt = f"❌ {100 * loses / N_SIMULATIONS:.0f}% LOSE"
                v_col = C["lose"]
            else:
                v_txt = "🤝 Tie"
                v_col = C["draw"]
            ctk.CTkLabel(card, text=v_txt, font=FONT_SMALL,
                         text_color=v_col).pack(pady=(4, 4))

            ctk.CTkButton(
                card, text=f"Replace {slot}",
                font=FONT_SMALL, height=32, corner_radius=6,
                fg_color=C["win"] if is_best else C["border"],
                hover_color=C["win_hv"] if is_best else C["border_hl"],
                text_color=C["bg"] if is_best else C["text"],
                command=lambda n=slot, s=new_skill: self._replace_skill(n, s),
            ).pack(padx=12, pady=(0, 14), fill="x")

        reco = ctk.CTkFrame(self._result_outer, fg_color=C["card"],
                             corner_radius=12)
        reco.pack(fill="x", pady=(0, 8))

        if wins_max > loses_max:
            reco_txt = f"✅  Replace {best} — {100 * wins_max / N_SIMULATIONS:.0f}% wins with this skill."
            reco_col = C["win"]
            show_btn = True
        else:
            reco_txt = "❌  No replacement is beneficial. Keep your current skills."
            reco_col = C["lose"]
            show_btn = False

        ctk.CTkLabel(reco, text=reco_txt, font=FONT_SUB,
                     text_color=reco_col).pack(
            padx=20, pady=(16, 8 if show_btn else 16))

        if show_btn:
            ctk.CTkButton(
                reco, text=f"💾  Apply — replace {best}",
                font=FONT_BODY, height=36, corner_radius=8,
                fg_color=C["win"], hover_color=C["win_hv"],
                text_color=C["bg"],
                command=lambda n=best, s=new_skill: self._replace_skill(n, s),
            ).pack(padx=20, pady=(0, 16), fill="x")

    def _replace_skill(self, slot: str, new_skill: Dict) -> None:
        if not confirm(
            self.app, f"Replace {slot}",
            f"Replace the skill in slot {slot}?",
            ok_label="Replace", danger=False,
        ):
            return
        self.controller.set_skill(slot, new_skill)
        self._lbl_status.configure(text=f"✅ {slot} updated!",
                                    text_color=C["win"])
        self.app.refresh_current()

    def _edit_direct(self) -> None:
        text = self._textbox.get("1.0", "end").strip()
        if not text:
            self._lbl_status.configure(
                text="⚠ Paste the skill stats first.",
                text_color=C["lose"])
            return

        skill, status, meta = self.controller.resolve_skill(text)
        if status == "no_name":
            self._lbl_status.configure(
                text="⚠ Could not read the skill name.",
                text_color=C["lose"])
            return
        if status == "unknown":
            name = meta.get("name") if meta else "?"
            self._lbl_status.configure(
                text=f"⚠ « {name} » is not in the library — check the spelling.",
                text_color=C["lose"])
            return

        EditSkillDialog(self, self.controller, self.app, skill)


# ════════════════════════════════════════════════════════════
#  Direct edit dialog
# ════════════════════════════════════════════════════════════

class EditSkillDialog(ctk.CTkToplevel):

    def __init__(self, parent, controller, app, skill: Dict):
        super().__init__(parent)
        self.controller = controller
        self.app        = app
        self.skill      = skill
        self.title("Edit a skill slot")
        self.geometry("400x280")
        self.resizable(False, False)
        self.configure(fg_color=C["surface"])
        self.grab_set()
        self.transient(parent)
        self._build()

    def _build(self) -> None:
        ctk.CTkLabel(self, text="Which slot to replace?",
                     font=("Segoe UI", 15, "bold"),
                     text_color=C["text"]).pack(padx=24, pady=(24, 8))
        ctk.CTkLabel(self, text="The skill will be saved without simulation.",
                     font=FONT_BODY, text_color=C["muted"]).pack(padx=24)

        self.slot_var = ctk.StringVar(value="S1")
        for slot in _SLOTS:
            icon = _SLOT_ICONS.get(slot, "✨")
            ctk.CTkRadioButton(
                self, text=f"{icon}  {slot}",
                variable=self.slot_var, value=slot,
                text_color=C["text"], font=FONT_BODY,
            ).pack(padx=40, pady=4, anchor="w")

        btn_f = ctk.CTkFrame(self, fg_color="transparent")
        btn_f.pack(padx=24, pady=20, fill="x")
        ctk.CTkButton(btn_f, text="Cancel", fg_color=C["border"],
                      hover_color=C["border_hl"], font=FONT_BODY, width=100,
                      command=self.destroy).pack(side="right", padx=(8, 0))
        ctk.CTkButton(btn_f, text="✓  Save",
                      fg_color=C["accent"], hover_color=C["accent_hv"],
                      font=FONT_BODY, width=140,
                      command=self._save).pack(side="right")

    def _save(self) -> None:
        slot = self.slot_var.get()
        self.controller.set_skill(slot, self.skill)
        self.destroy()
        self.app.refresh_current()
