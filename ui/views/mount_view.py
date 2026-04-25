"""
============================================================
  FORGE MASTER UI — Mount Management
  Single slot; new_me (with mount) vs old_me.
============================================================
"""

from typing import Dict

import customtkinter as ctk

from ui.theme import (
    C, FONT_BODY, FONT_MONO_S, FONT_SMALL, FONT_SUB, FONT_TINY,
    MOUNT_ICON, RARITY_ORDER, fmt_number, load_mount_icon, rarity_color,
)
from ui.widgets import (
    build_header,
    build_import_zone,
    build_wld_bars,
    companion_slot_card,
    confirm,
)
from backend.constants import N_SIMULATIONS


class MountView(ctk.CTkFrame):

    def __init__(self, parent, controller, app):
        super().__init__(parent, fg_color=C["bg"], corner_radius=0)
        self.controller = controller
        self.app        = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build()

    # ── Build ─────────────────────────────────────────────────

    def _build(self) -> None:
        build_header(self, f"{MOUNT_ICON}  Mount Management")

        self._scroll = ctk.CTkScrollableFrame(self, fg_color=C["bg"],
                                               corner_radius=0)
        self._scroll.grid(row=1, column=0, sticky="nsew")
        self._scroll.grid_columnconfigure(0, weight=1)

        self._build_mount_card()
        self._build_import()
        self._build_result_zone()
        self._build_library()

    def _build_mount_card(self) -> None:
        mount = self.controller.get_mount() or {}
        name  = mount.get("__name__")
        rar   = mount.get("__rarity__")
        icon  = load_mount_icon(name, size=48) if name else None

        card = companion_slot_card(
            self._scroll,
            slot_label=f"{MOUNT_ICON}  Current mount",
            name=name,
            rarity=rar,
            stats=mount,
            icon_image=icon,
            fallback_emoji=MOUNT_ICON,
            empty_text="(no mount registered)",
        )
        card.grid(row=0, column=0, padx=16, pady=16, sticky="ew")

    def _build_import(self) -> None:
        card, self._textbox, self._lbl_status = build_import_zone(
            self._scroll,
            title="Test a new mount",
            hint="Paste the mount stats from the game.",
            primary_label="🔬  Simulate replacement",
            primary_cmd=self._test_mount,
            secondary_label="💾  Save directly",
            secondary_cmd=self._save_direct,
            scan_key="mount",
            scan_fn=self.controller.scan,
            captures_fn=self.controller.get_zone_captures,
            on_scan_ready=self._test_mount,
        )
        card.grid(row=1, column=0, padx=16, pady=(0, 8), sticky="ew")

    def _build_result_zone(self) -> None:
        self._result_outer = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._result_outer.grid(row=2, column=0, padx=16, pady=(0, 16),
                                sticky="ew")
        self._result_outer.grid_columnconfigure(0, weight=1)

    def _build_library(self) -> None:
        """Mount library (Lv.1 stats, indexed by name)."""
        card = ctk.CTkFrame(self._scroll, fg_color=C["card"], corner_radius=12)
        card.grid(row=3, column=0, padx=16, pady=(0, 16), sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card, text="📚  Mount Library",
                     font=FONT_SUB, text_color=C["text"]).grid(
            row=0, column=0, sticky="w", padx=20, pady=(16, 2))
        ctk.CTkLabel(card,
                     text="Flat stats (HP/Damage) at Lv.1 are used as reference for all comparisons.",
                     font=FONT_SMALL, text_color=C["muted"],
                     wraplength=700, justify="left").grid(
            row=1, column=0, sticky="w", padx=20, pady=(0, 4))

        library = self.controller.get_mount_library()

        if not library:
            ctk.CTkLabel(
                card,
                text="No mounts in library. Paste a Lv.1 mount above and click « Simulate » — it will be added automatically.",
                font=FONT_SMALL, text_color=C["muted"],
                wraplength=700, justify="left").grid(
                row=2, column=0, padx=20, pady=(0, 16), sticky="w")
            return

        lst = ctk.CTkFrame(card, fg_color="transparent")
        lst.grid(row=2, column=0, padx=10, pady=(4, 12), sticky="ew")
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

            icon_img = load_mount_icon(name, size=40)
            if icon_img:
                ctk.CTkLabel(row, image=icon_img, text="",
                             fg_color="transparent").grid(
                    row=0, column=0, padx=(8, 2), pady=4)
            else:
                ctk.CTkLabel(row, text=MOUNT_ICON,
                             font=("Segoe UI", 24), width=48).grid(
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
            f"Remove « {name} » from the mount library?",
            ok_label="Remove", danger=True,
        ):
            return
        if self.controller.remove_mount_library(name):
            self.app.refresh_current()

    # ── Actions ───────────────────────────────────────────────

    def _test_mount(self) -> None:
        if not self.controller.has_profile():
            self._lbl_status.configure(
                text="⚠ No player profile. Go to Dashboard first.",
                text_color=C["lose"])
            return

        text = self._textbox.get("1.0", "end").strip()
        if not text:
            self._lbl_status.configure(text="⚠ Paste the mount stats.",
                                        text_color=C["lose"])
            return

        new_mount, status, meta = self.controller.resolve_mount(text)

        if status == "no_name":
            self._lbl_status.configure(
                text="⚠ Could not read the mount name (expected: « [Rarity] Name »).",
                text_color=C["lose"])
            return

        if status == "unknown":
            name = meta.get("name") if meta else "?"
            self._lbl_status.configure(
                text=f"⚠ « {name} » is not in the library — check the spelling or add it manually to mount_library.txt.",
                text_color=C["lose"])
            return

        for w in self._result_outer.winfo_children():
            w.destroy()

        self._lbl_status.configure(text="⏳ Simulation running…",
                                    text_color=C["muted"])
        self.update_idletasks()

        def on_result(w: int, l: int, d: int) -> None:
            self._lbl_status.configure(text="", text_color=C["muted"])
            self._display_results(w, l, d, new_mount)

        self.controller.test_mount(new_mount, on_result)

    def _display_results(self, wins: int, loses: int, draws: int,
                          new_mount: Dict) -> None:
        for w in self._result_outer.winfo_children():
            w.destroy()

        card = ctk.CTkFrame(self._result_outer, fg_color=C["card"],
                             corner_radius=12)
        card.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(card, text="Result — New mount vs Old mount",
                     font=FONT_SUB, text_color=C["text"]).pack(
            padx=20, pady=(16, 4), anchor="w")
        ctk.CTkLabel(card,
                     text="New me (with this mount) vs Old me (with the old mount).",
                     font=("Segoe UI", 11), text_color=C["muted"]).pack(
            padx=20, pady=(0, 12), anchor="w")

        bars = build_wld_bars(card, wins, loses, draws, total=N_SIMULATIONS)
        bars.pack(fill="x", padx=20, pady=(0, 8))

        if wins > loses:
            verdict_txt = f"✅  This mount is better — {100 * wins / N_SIMULATIONS:.0f}% wins."
            verdict_col = C["win"]
            show_btn    = True
        elif loses > wins:
            verdict_txt = "❌  This mount is worse. Keep the current one."
            verdict_col = C["lose"]
            show_btn    = False
        else:
            verdict_txt = "🤝  Tie — both mounts are equivalent."
            verdict_col = C["draw"]
            show_btn    = False

        ctk.CTkLabel(card, text=verdict_txt, font=FONT_SUB,
                     text_color=verdict_col).pack(
            padx=20, pady=(8, 8 if show_btn else 16))

        if show_btn:
            ctk.CTkButton(
                card, text="💾  Apply this mount",
                font=FONT_BODY, height=36, corner_radius=8,
                fg_color=C["win"], hover_color=C["win_hv"],
                text_color=C["bg"],
                command=lambda m=new_mount: self._apply_mount(m),
            ).pack(padx=20, pady=(0, 16), fill="x")

    def _apply_mount(self, mount: Dict) -> None:
        if not confirm(
            self.app, "Confirm replacement",
            "Replace the current mount with this new one?",
            ok_label="Replace", danger=False,
        ):
            return
        self.controller.set_mount(mount)
        self._lbl_status.configure(text="✅ Mount updated!",
                                    text_color=C["win"])
        self.app.refresh_current()

    def _save_direct(self) -> None:
        text = self._textbox.get("1.0", "end").strip()
        if not text:
            self._lbl_status.configure(
                text="⚠ Paste the mount stats first.",
                text_color=C["lose"])
            return

        mount, status, meta = self.controller.resolve_mount(text)
        if status == "no_name":
            self._lbl_status.configure(
                text="⚠ Could not read the mount name.",
                text_color=C["lose"])
            return
        if status == "unknown":
            name = meta.get("name") if meta else "?"
            self._lbl_status.configure(
                text=f"⚠ « {name} » is not in the library — check the spelling.",
                text_color=C["lose"])
            return

        if not confirm(
            self.app, "Save without simulating",
            "Save this mount without testing if it's better than the current one?",
            ok_label="Save", danger=False,
        ):
            return
        self.controller.set_mount(mount)
        self._lbl_status.configure(text="✅ Mount saved!",
                                    text_color=C["win"])
        self.app.refresh_current()