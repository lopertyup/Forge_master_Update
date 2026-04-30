"""
============================================================
  FORGE MASTER UI — Skills Management

  Phase-3 refactor (UI_REFACTOR_PLAN §11):
  3-tab layout — same flow as Mount / Pet / Equipment > Comparer:

      [Équipés]   [Comparer]   [Librairie]

    * Équipés   : 3 slot cards (S1 / S2 / S3) side-by-side.
    * Comparer  : paste / scan a candidate, run the
                  test_skill() simulation against ALL 3 slots,
                  show one result per slot + recommend the
                  best replacement (existing logic preserved).
    * Librairie : LibraryList with rarity / type filters,
                  per-row delete.

  All shared widgets come from ui/cards.py.
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
from ui.cards import LibraryList
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

        self._tabs = ctk.CTkTabview(
            self,
            fg_color=C["bg"],
            segmented_button_fg_color=C["card"],
            segmented_button_selected_color=C["accent"],
            segmented_button_selected_hover_color=C["accent"],
        )
        self._tabs.grid(row=1, column=0, sticky="nsew", padx=8, pady=(8, 8))

        self._build_equipped_tab(self._tabs.add("Équipés"))
        self._build_compare_tab(self._tabs.add("Comparer"))
        self._build_library_tab(self._tabs.add("Librairie"))

    # ── Tab 1 — Équipés ──────────────────────────────────────

    def _build_equipped_tab(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(parent, fg_color=C["bg"],
                                         corner_radius=0)
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        skills_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        skills_frame.grid(row=0, column=0, padx=16, pady=16, sticky="ew")
        skills_frame.grid_columnconfigure((0, 1, 2), weight=1)

        slots = self.controller.get_skill_slots()
        for col, slot in enumerate(_SLOTS):
            data = slots.get(slot) or {}
            card = self._skill_slot_card(skills_frame, slot, data)
            card.grid(row=0, column=col, padx=6, pady=0, sticky="nsew")

        # Quick-actions row.
        bar = ctk.CTkFrame(scroll, fg_color="transparent")
        bar.grid(row=1, column=0, padx=16, pady=(0, 16), sticky="ew")
        bar.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            bar, text="↪  Go to « Comparer »",
            font=FONT_SMALL, height=34, corner_radius=8,
            fg_color=C["accent"], hover_color=C["accent_hv"],
            command=lambda: self._tabs.set("Comparer"),
        ).grid(row=0, column=0, padx=(0, 4), sticky="ew")

        ctk.CTkButton(
            bar, text="📚  Open library",
            font=FONT_SMALL, height=34, corner_radius=8,
            fg_color="transparent", border_color=C["card"], border_width=1,
            hover_color=C["border"], text_color=C["text"],
            command=lambda: self._tabs.set("Librairie"),
        ).grid(row=0, column=1, padx=(4, 0), sticky="ew")

    # ── Skill slot card (equipped skill display) ─────────────

    def _skill_slot_card(self, parent: ctk.CTkBaseClass,
                          slot: str, data: Dict) -> ctk.CTkFrame:
        card = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=12)

        slot_icon = _SLOT_ICONS.get(slot, "✨")
        ctk.CTkLabel(card, text=f"{slot_icon}  {slot}", font=FONT_SUB,
                     text_color=C["muted"]).pack(
            padx=16, pady=(12, 4), anchor="w")

        name = data.get("__name__")
        if not name:
            ctk.CTkLabel(card, text="— empty slot —", font=FONT_BODY,
                         text_color=C["muted"]).pack(padx=16, pady=(4, 20))
            return card

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

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=10, pady=(0, 10))
        i = 0
        for label, value in self._active_stat_rows(data):
            self._stat_row(inner, label, value, row_index=i).pack(fill="x", pady=1)
            i += 1
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

    # ── Tab 2 — Comparer ─────────────────────────────────────
    # Tests the candidate against all 3 equipped slots and renders
    # one result card per slot — the "best slot to replace" output
    # is preserved verbatim from the legacy view.

    def _build_compare_tab(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        import_card, self._textbox, self._lbl_status = build_import_zone(
            parent,
            title="Test a new skill",
            hint="Paste the skill stats from the game (including the « Passive: +xx Base Damage +xx Base Health » line).",
            primary_label="🔬  Compare against 3 slots",
            primary_cmd=self._test_skill,
            secondary_label="✏  Edit a slot directly",
            secondary_cmd=self._edit_direct,
            scan_key="skill",
            scan_fn=self.controller.scan,
            captures_fn=self.controller.get_zone_captures,
            on_scan_ready=self._test_skill,
        )
        import_card.grid(row=0, column=0, padx=16, pady=(12, 8), sticky="ew")

        self._result_outer = ctk.CTkScrollableFrame(
            parent, fg_color=C["bg"], corner_radius=0)
        self._result_outer.grid(row=1, column=0, padx=16, pady=(0, 16),
                                sticky="nsew")
        self._result_outer.grid_columnconfigure(0, weight=1)

        self._compare_placeholder()

    def _compare_placeholder(self) -> None:
        for w in self._result_outer.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self._result_outer,
            text="Paste or scan a candidate above, then hit « Compare ».\n"
                 "We'll test it against each of your 3 active slots.",
            font=FONT_SMALL, text_color=C["muted"],
        ).pack(pady=24)

    # ── Tab 3 — Librairie ────────────────────────────────────

    def _build_library_tab(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        hint = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=12)
        hint.grid(row=0, column=0, padx=16, pady=(12, 6), sticky="ew")
        ctk.CTkLabel(
            hint,
            text="📚  Skills Library",
            font=FONT_SUB, text_color=C["text"],
        ).pack(padx=16, pady=(12, 2), anchor="w")
        ctk.CTkLabel(
            hint,
            text=("Lv.1 reference stats — used only as the structural "
                  "template when you paste a skill. Equipped skills keep "
                  "their current-level stats."),
            font=FONT_SMALL, text_color=C["muted"],
            wraplength=700, justify="left",
        ).pack(padx=16, pady=(0, 12), anchor="w")

        library = self.controller.get_skills_library() or {}
        items   = self._library_items(library)

        filters = {}
        if items:
            filters["rarity"] = self._distinct(items, "rarity")
            filters["type"]   = self._distinct(items, "type")

        list_frame, _ctrl = LibraryList(
            parent,
            items,
            title="Collected skills",
            hint=None,
            filters=filters or None,
            on_action=self._library_use_as_candidate,
            on_delete=self._library_delete,
            icon_loader=lambda name: load_skill_icon_by_name(name, size=40),
            fallback_emoji="✨",
            max_height=420,
        )
        list_frame.grid(row=1, column=0, padx=16, pady=(0, 16), sticky="nsew")

    def _library_items(self, library: Dict[str, Dict]) -> list:
        rows = []
        for name, entry in library.items():
            rows.append({
                "key":         name,
                "name":        name,
                "rarity":      str(entry.get("rarity", "common")).lower(),
                "type":        str(entry.get("type", "damage")).lower(),
                "hp_flat":     entry.get("passive_hp", 0),
                "damage_flat": entry.get("damage", 0) or entry.get("passive_damage", 0),
                "_lib_entry":  entry,
            })
        return rows

    @staticmethod
    def _distinct(items: list, key: str) -> list:
        seen = []
        for it in items:
            v = it.get(key)
            if v and v not in seen:
                seen.append(v)
        return seen

    def _library_use_as_candidate(self, item: Dict) -> None:
        """Push a library row into the Comparer tab as a candidate.
        Re-builds a paste-like text so resolve_skill() can normalise it."""
        name   = item.get("name", "?")
        rarity = str(item.get("rarity", "common")).title()
        entry  = item.get("_lib_entry") or {}
        sk_type = str(entry.get("type", "damage"))

        # Minimal paste: name + Lv.1 + the line resolve_skill needs.
        # For damage skills, "total_damage" is parsed from a "Damage: X x N hits" pattern.
        total_dmg = float(entry.get("damage", 0) or 0) * float(entry.get("hits", 1) or 1)
        hits      = int(entry.get("hits", 1) or 1)
        cd        = float(entry.get("cooldown", 0) or 0)
        pd        = float(entry.get("passive_damage", 0) or 0)
        ph        = float(entry.get("passive_hp", 0) or 0)

        if sk_type == "damage":
            lines = [
                f"[{rarity}] {name}",
                "Lv.1",
                f"Damage: {int(total_dmg)} x {hits} hits",
                f"Cooldown: {cd:g}s",
                f"Passive: +{int(pd)} Base Damage  +{int(ph)} Base Health",
            ]
        else:
            atk = float(entry.get("buff_atk", 0) or 0)
            hp  = float(entry.get("buff_hp", 0) or 0)
            dur = float(entry.get("buff_duration", 0) or 0)
            lines = [
                f"[{rarity}] {name}",
                "Lv.1",
                f"Buff: +{int(atk)} ATK  +{int(hp)} HP for {dur:g}s",
                f"Cooldown: {cd:g}s",
                f"Passive: +{int(pd)} Base Damage  +{int(ph)} Base Health",
            ]

        try:
            self._tabs.set("Comparer")
        except Exception:
            pass
        self._textbox.delete("1.0", "end")
        self._textbox.insert("1.0", "\n".join(lines) + "\n")
        self._test_skill()

    def _library_delete(self, item: Dict) -> None:
        name = item.get("name") or item.get("key")
        if not name:
            return
        if not confirm(
            self.app, "Remove from library",
            f"Remove « {name} » from the skills library?\n"
            "Future imports of this name will need to be re-done at Lv.1.",
            ok_label="Remove", danger=True,
        ):
            return
        if self.controller.remove_skill_library(name):
            self.app.refresh_current()

    # ── Compare actions (existing logic, unchanged) ──────────

    def _test_skill(self) -> None:
        try:
            self._tabs.set("Comparer")
        except Exception:
            pass

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

        if status == "unknown_not_lvl1":
            name = meta.get("name") if meta else "?"
            self._lbl_status.configure(
                text=f"⚠ « {name} » is not in the library — paste at Lv.1 to auto-add it.",
                text_color=C["lose"])
            return

        self._compare_placeholder()
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
        if status == "unknown_not_lvl1":
            name = meta.get("name") if meta else "?"
            self._lbl_status.configure(
                text=f"⚠ « {name} » is not in the library — paste at Lv.1 to auto-add it.",
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
