"""
============================================================
  FORGE MASTER UI — Pet Management
  3 slots (PET1, PET2, PET3). Tests the new pet against
  each existing one to find the best slot to replace.
============================================================
"""

from typing import Dict, Tuple

import customtkinter as ctk

from ui.theme import (
    C,
    FONT_BODY,
    FONT_MONO_S,
    FONT_SMALL,
    FONT_SUB,
    FONT_TINY,
    PET_ICONS,
    RARITY_ORDER,
    fmt_number,
    load_pet_icon,
    rarity_color,
)
from ui.widgets import (
    build_header,
    build_import_zone,
    build_wld_bars,
    companion_slot_card,
    confirm,
)
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

        self._scroll = ctk.CTkScrollableFrame(self, fg_color=C["bg"],
                                               corner_radius=0)
        self._scroll.grid(row=1, column=0, sticky="nsew")
        self._scroll.grid_columnconfigure(0, weight=1)

        self._build_pet_cards()
        self._build_import()
        self._build_result_zone()
        self._build_library()

    def _build_pet_cards(self) -> None:
        pets_frame = ctk.CTkFrame(self._scroll, fg_color="transparent")
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

    def _build_import(self) -> None:
        card, self._textbox, self._lbl_status = build_import_zone(
            self._scroll,
            title="Test a new pet",
            hint="Paste the pet stats from the game.",
            primary_label="🔬  Simulate replacement",
            primary_cmd=self._test_pet,
            secondary_label="✏  Directly edit a slot",
            secondary_cmd=self._edit_direct,
            scan_key="pet",
            scan_fn=self.controller.scan,
            captures_fn=self.controller.get_zone_captures,
            on_scan_ready=self._test_pet,
        )
        card.grid(row=1, column=0, padx=16, pady=(0, 8), sticky="ew")

    def _build_result_zone(self) -> None:
        self._result_outer = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._result_outer.grid(row=2, column=0, padx=16, pady=(0, 16),
                                sticky="ew")
        self._result_outer.grid_columnconfigure(0, weight=1)

    def _build_library(self) -> None:
        """Library section: list of known pets (Lv.1 stats)."""
        card = ctk.CTkFrame(self._scroll, fg_color=C["card"], corner_radius=12)
        card.grid(row=3, column=0, padx=16, pady=(0, 16), sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(card, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 4))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="📚  Pet Library",
                     font=FONT_SUB, text_color=C["text"]).grid(
            row=0, column=0, sticky="w")
        ctk.CTkLabel(header,
                     text="Flat stats (HP/Damage) at Lv.1 are used for all comparisons, regardless of the imported pet's level.",
                     font=FONT_SMALL, text_color=C["muted"],
                     wraplength=700, justify="left").grid(
            row=1, column=0, sticky="w", pady=(2, 0))

        library = self.controller.get_pets_library()

        if not library:
            ctk.CTkLabel(
                card,
                text="No pets in library. Paste a Lv.1 pet in the zone above and click « Simulate » — it will be added automatically.",
                font=FONT_SMALL, text_color=C["muted"],
                wraplength=700, justify="left").grid(
                row=1, column=0, padx=20, pady=(0, 16), sticky="w")
            return

        lst = ctk.CTkFrame(card, fg_color="transparent")
        lst.grid(row=1, column=0, padx=10, pady=(4, 12), sticky="ew")
        lst.grid_columnconfigure(1, weight=1)

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

            # Icon (or emoji fallback)
            icon_img = load_pet_icon(name, size=40)
            if icon_img:
                ctk.CTkLabel(row, image=icon_img, text="",
                             fg_color="transparent").grid(
                    row=0, column=0, padx=(8, 2), pady=4)
            else:
                ctk.CTkLabel(row, text="🐾", font=("Segoe UI", 24),
                             width=48).grid(
                    row=0, column=0, padx=(8, 2), pady=4)

            rar = str(entry.get("rarity", "common")).lower()
            ctk.CTkLabel(row, text=rar.upper(),
                         font=FONT_TINY, text_color=rarity_color(rar),
                         width=80).grid(row=0, column=1, padx=(6, 6), pady=6)
            ctk.CTkLabel(row, text=name, font=FONT_BODY,
                         text_color=C["text"], anchor="w").grid(
                row=0, column=2, padx=6, pady=6, sticky="w")

            stats_txt = (f"⚔ {fmt_number(entry.get('damage_flat', 0))}   "
                         f"❤ {fmt_number(entry.get('hp_flat', 0))}")
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

    def _delete_from_library(self, name: str) -> None:
        if not confirm(
            self.app, "Remove from library",
            f"Remove « {name} » from the pet library?\n"
            "Future imports of this name will need to be re-done at Lv.1.",
            ok_label="Remove", danger=True,
        ):
            return
        if self.controller.remove_pet_library(name):
            self.app.refresh_current()

    # ── Actions ───────────────────────────────────────────────

    def _test_pet(self) -> None:
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

        if status == "unknown":
            name = meta.get("name") if meta else "?"
            self._lbl_status.configure(
                text=f"⚠ « {name} » is not in the library — check the spelling or add it manually to pets_library.txt.",
                text_color=C["lose"])
            return

        for w in self._result_outer.winfo_children():
            w.destroy()

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
        if status == "unknown":
            name = meta.get("name") if meta else "?"
            self._lbl_status.configure(
                text=f"⚠ « {name} » is not in the library — check the spelling.",
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