"""
============================================================
  FORGE MASTER UI — Pet Management

  Phase-3 refactor (UI_REFACTOR_PLAN §11):
  3-tab layout — same flow as Mount / Skills / Equipment > Comparer:

      [Équipés]   [Comparer]   [Librairie]

    * Équipés   : 3 slot cards (PET1 / PET2 / PET3) side-by-side.
    * Comparer  : paste / scan a candidate, run test_pet()
                  against ALL 3 slots, render one result per
                  slot + recommend the best replacement.
    * Librairie : LibraryList with rarity / type filters,
                  per-row Compare and Delete.

  All shared widgets come from ui/cards.py.
============================================================
"""

from typing import Dict, Tuple

import customtkinter as ctk

from ui.theme import (
    C,
    FONT_BODY,
    FONT_SMALL,
    FONT_SUB,
    FONT_TINY,
    PET_ICONS,
    load_pet_icon,
)
from ui.widgets import (
    build_header,
    build_import_zone,
    build_wld_bars,
    companion_slot_card,
    confirm,
)
from ui.cards import LibraryList
from backend.constants import N_SIMULATIONS

_SLOTS = ("PET1", "PET2", "PET3")


class PetsView(ctk.CTkFrame):

    def __init__(self, parent, controller, app):
        super().__init__(parent, fg_color=C["bg"], corner_radius=0)
        self.controller = controller
        self.app        = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build()

    # ── Build ─────────────────────────────────────────────────

    def _build(self) -> None:
        build_header(self, "Pet Management")

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

        pets_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        pets_frame.grid(row=0, column=0, padx=16, pady=16, sticky="ew")
        pets_frame.grid_columnconfigure((0, 1, 2), weight=1)

        pets = self.controller.get_pets()
        for col, slot in enumerate(_SLOTS):
            pet  = pets.get(slot, {}) or {}
            name = pet.get("__name__")
            rar  = pet.get("__rarity__")
            icon = load_pet_icon(name, size=44) if name else None

            card = companion_slot_card(
                pets_frame,
                slot_label=f"{PET_ICONS.get(slot, '🐾')}  {slot}",
                name=name,
                rarity=rar,
                stats=pet,
                icon_image=icon,
                fallback_emoji="🐾",
                empty_text="(empty slot)",
            )
            card.grid(row=0, column=col, padx=6, pady=0, sticky="nsew")

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

    # ── Tab 2 — Comparer ─────────────────────────────────────

    def _build_compare_tab(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        import_card, self._textbox, self._lbl_status = build_import_zone(
            parent,
            title="Test a new pet",
            hint="Paste the pet stats from the game, or scan with the camera button.",
            primary_label="🔬  Compare against 3 slots",
            primary_cmd=self._test_pet,
            secondary_label="✏  Edit a slot directly",
            secondary_cmd=self._edit_direct,
            scan_key="pet",
            scan_fn=self.controller.scan,
            captures_fn=self.controller.get_zone_captures,
            on_scan_ready=self._test_pet,
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
            text="📚  Pet Library",
            font=FONT_SUB, text_color=C["text"],
        ).pack(padx=16, pady=(12, 2), anchor="w")
        ctk.CTkLabel(
            hint,
            text=("Flat stats (HP / Damage) at Lv.1 are used for all "
                  "comparisons, regardless of the imported pet's level."),
            font=FONT_SMALL, text_color=C["muted"],
            wraplength=700, justify="left",
        ).pack(padx=16, pady=(0, 12), anchor="w")

        library = self.controller.get_pets_library() or {}
        items   = self._library_items(library)

        filters = {}
        if items:
            filters["rarity"] = self._distinct(items, "rarity")
            type_vals = self._distinct(items, "type")
            if type_vals:
                filters["type"] = type_vals

        list_frame, _ctrl = LibraryList(
            parent,
            items,
            title="Collected pets",
            hint=None,
            filters=filters or None,
            on_action=self._library_use_as_candidate,
            on_delete=self._library_delete,
            icon_loader=lambda name: load_pet_icon(name, size=40),
            fallback_emoji="🐾",
            max_height=420,
        )
        list_frame.grid(row=1, column=0, padx=16, pady=(0, 16), sticky="nsew")

    @staticmethod
    def _library_items(library: Dict[str, Dict]) -> list:
        rows = []
        for name, entry in library.items():
            rows.append({
                "key":         name,
                "name":        name,
                "rarity":      str(entry.get("rarity", "common")).lower(),
                "type":        str(entry.get("type", "")).lower(),
                "hp_flat":     entry.get("hp_flat", 0),
                "damage_flat": entry.get("damage_flat", 0),
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
        """Drop a library row into the Comparer tab as a candidate."""
        name   = item.get("name", "?")
        rarity = str(item.get("rarity", "common")).title()
        hp     = item.get("hp_flat") or 0
        dmg    = item.get("damage_flat") or 0
        text = (f"[{rarity}] {name}\n"
                f"Lv.1\n"
                f"+{int(dmg)} Damage\n"
                f"+{int(hp)} Health\n")

        try:
            self._tabs.set("Comparer")
        except Exception:
            pass
        self._textbox.delete("1.0", "end")
        self._textbox.insert("1.0", text)
        self._test_pet()

    def _library_delete(self, item: Dict) -> None:
        name = item.get("name") or item.get("key")
        if not name:
            return
        if not confirm(
            self.app, "Remove from library",
            f"Remove « {name} » from the pet library?\n"
            "Future imports of this name will need to be re-done at Lv.1.",
            ok_label="Remove", danger=True,
        ):
            return
        if self.controller.remove_pet_library(name):
            self.app.refresh_current()

    # ── Compare actions (logic preserved from legacy view) ────

    def _test_pet(self) -> None:
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
            self._lbl_status.configure(text="⚠ Paste the pet stats.",
                                        text_color=C["lose"])
            return

        new_pet, status, meta = self.controller.resolve_pet(text)

        if status == "no_name":
            self._lbl_status.configure(
                text="⚠ Could not read the pet name (expected: « [Rarity] Name »).",
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
            self._display_results(results, new_pet)

        self.controller.test_pet(new_pet, on_result)

    def _display_results(self, results: Dict[str, Tuple[int, int, int]],
                          new_pet: Dict) -> None:
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
                     text="New me (with this pet) vs Old me (with the old pet in that slot).",
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

            icon = PET_ICONS.get(slot, "🐾")
            ctk.CTkLabel(card, text=f"{icon} Replace {slot}",
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
                command=lambda n=slot, p=new_pet: self._replace_pet(n, p),
            ).pack(padx=12, pady=(0, 14), fill="x")

        reco = ctk.CTkFrame(self._result_outer, fg_color=C["card"],
                             corner_radius=12)
        reco.pack(fill="x", pady=(0, 8))

        if wins_max > loses_max:
            reco_txt = f"✅  Replace {best} — {100 * wins_max / N_SIMULATIONS:.0f}% wins with this pet."
            reco_col = C["win"]
            show_btn = True
        else:
            reco_txt = "❌  No replacement is beneficial. Keep your current pets."
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
                command=lambda n=best, p=new_pet: self._replace_pet(n, p),
            ).pack(padx=20, pady=(0, 16), fill="x")

    def _replace_pet(self, slot: str, new_pet: Dict) -> None:
        if not confirm(
            self.app, f"Replace {slot}",
            f"Replace the pet in slot {slot}?",
            ok_label="Replace", danger=False,
        ):
            return
        self.controller.set_pet(slot, new_pet)
        self._lbl_status.configure(text=f"✅ {slot} updated!",
                                    text_color=C["win"])
        self.app.refresh_current()

    def _edit_direct(self) -> None:
        text = self._textbox.get("1.0", "end").strip()
        if not text:
            self._lbl_status.configure(
                text="⚠ Paste the pet stats first.",
                text_color=C["lose"])
            return

        pet, status, meta = self.controller.resolve_pet(text)
        if status == "no_name":
            self._lbl_status.configure(
                text="⚠ Could not read the pet name.",
                text_color=C["lose"])
            return
        if status == "unknown_not_lvl1":
            name = meta.get("name") if meta else "?"
            self._lbl_status.configure(
                text=f"⚠ « {name} » is not in the library — paste at Lv.1 to auto-add it.",
                text_color=C["lose"])
            return

        EditPetDialog(self, self.controller, self.app, pet)


# ════════════════════════════════════════════════════════════
#  Direct edit dialog
# ════════════════════════════════════════════════════════════

class EditPetDialog(ctk.CTkToplevel):

    def __init__(self, parent, controller, app, pet: Dict):
        super().__init__(parent)
        self.controller = controller
        self.app        = app
        self.pet        = pet
        self.title("Edit a pet slot")
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
        ctk.CTkLabel(self, text="The pet will be saved without simulation.",
                     font=FONT_BODY, text_color=C["muted"]).pack(padx=24)

        self.slot_var = ctk.StringVar(value="PET1")
        for slot in _SLOTS:
            icon = PET_ICONS.get(slot, "🐾")
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
        self.controller.set_pet(slot, self.pet)
        self.destroy()
        self.app.refresh_current()
