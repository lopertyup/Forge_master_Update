"""
============================================================
  FORGE MASTER UI — Gestion du Mount
  Un seul slot ; nouveau_moi (avec mount) vs ancien_moi.
============================================================
"""

from typing import Dict

import customtkinter as ctk

from ui.theme import (
    C, FONT_BODY, FONT_MONO_S, FONT_SMALL, FONT_SUB, FONT_TINY,
    MOUNT_ICON, RARITY_ORDER, fmt_nombre, load_mount_icon, rarity_color,
)
from ui.widgets import (
    build_header,
    build_import_zone,
    build_wld_bars,
    companion_slot_card,
    confirmer,
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

    # ── Construction ─────────────────────────────────────────

    def _build(self) -> None:
        build_header(self, f"{MOUNT_ICON}  Gestion du Mount")

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
        nom   = mount.get("__name__")
        rar   = mount.get("__rarity__")
        icon  = load_mount_icon(nom, size=48) if nom else None

        card = companion_slot_card(
            self._scroll,
            slot_label=f"{MOUNT_ICON}  Mount actuel",
            name=nom,
            rarity=rar,
            stats=mount,
            icon_image=icon,
            fallback_emoji=MOUNT_ICON,
            empty_text="(aucun mount enregistré)",
        )
        card.grid(row=0, column=0, padx=16, pady=16, sticky="ew")

    def _build_import(self) -> None:
        card, self._textbox, self._lbl_status = build_import_zone(
            self._scroll,
            title="Tester un nouveau mount",
            hint="Collez les stats du mount depuis le jeu.",
            primary_label="🔬  Simuler le remplacement",
            primary_cmd=self._tester_mount,
            secondary_label="💾  Enregistrer directement",
            secondary_cmd=self._enregistrer_direct,
        )
        card.grid(row=1, column=0, padx=16, pady=(0, 8), sticky="ew")

    def _build_result_zone(self) -> None:
        self._result_outer = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._result_outer.grid(row=2, column=0, padx=16, pady=(0, 16),
                                sticky="ew")
        self._result_outer.grid_columnconfigure(0, weight=1)

    def _build_library(self) -> None:
        """Bibliothèque des mounts (stats Lv.1, indexées par nom)."""
        card = ctk.CTkFrame(self._scroll, fg_color=C["card"], corner_radius=12)
        card.grid(row=3, column=0, padx=16, pady=(0, 16), sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card, text="📚  Bibliothèque des mounts",
                     font=FONT_SUB, text_color=C["text"]).grid(
            row=0, column=0, sticky="w", padx=20, pady=(16, 2))
        ctk.CTkLabel(card,
                     text="Les stats flat (HP/Damage) au Lv.1 servent de référence pour toutes les comparaisons.",
                     font=FONT_SMALL, text_color=C["muted"],
                     wraplength=700, justify="left").grid(
            row=1, column=0, sticky="w", padx=20, pady=(0, 4))

        library = self.controller.get_mount_library()

        if not library:
            ctk.CTkLabel(
                card,
                text="Aucun mount en bibliothèque. Collez un mount Lv.1 ci-dessus puis cliquez sur « Simuler » — il sera ajouté automatiquement.",
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

        for i, nom in enumerate(sorted(library.keys(), key=_sort_key)):
            entry = library[nom]
            bg = C["card_alt"] if i % 2 == 0 else C["card"]
            row = ctk.CTkFrame(lst, fg_color=bg, corner_radius=6)
            row.grid(row=i, column=0, columnspan=5, sticky="ew", padx=4, pady=2)
            row.grid_columnconfigure(2, weight=1)

            icon_img = load_mount_icon(nom, size=40)
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
            ctk.CTkLabel(row, text=nom, font=FONT_BODY,
                         text_color=C["text"], anchor="w").grid(
                row=0, column=2, padx=6, pady=6, sticky="w")

            stats_txt = (f"⚔ {fmt_nombre(entry.get('damage_flat', 0))}   "
                         f"❤ {fmt_nombre(entry.get('hp_flat', 0))}")
            ctk.CTkLabel(row, text=stats_txt, font=FONT_MONO_S,
                         text_color=C["muted"]).grid(
                row=0, column=3, padx=6, pady=6)

            ctk.CTkButton(
                row, text="🗑", width=32, height=26,
                font=FONT_SMALL, corner_radius=6,
                fg_color="transparent", hover_color=C["lose"],
                text_color=C["muted"],
                command=lambda n=nom: self._supprimer_library(n),
            ).grid(row=0, column=4, padx=(4, 10), pady=4)

    def _supprimer_library(self, nom: str) -> None:
        if not confirmer(
            self.app, "Supprimer de la bibliothèque",
            f"Supprimer « {nom} » de la bibliothèque des mounts ?",
            ok_label="Supprimer", danger=True,
        ):
            return
        if self.controller.supprimer_mount_library(nom):
            self.app.refresh_current()

    def _refresh_library_only(self) -> None:
        for child in self._scroll.winfo_children():
            info = child.grid_info()
            if info.get("row") == 3:
                child.destroy()
        self._build_library()

    # ── Actions ──────────────────────────────────────────────

    def _tester_mount(self) -> None:
        if not self.controller.has_profil():
            self._lbl_status.configure(
                text="⚠ Aucun profil joueur. Allez dans Dashboard d'abord.",
                text_color=C["lose"])
            return

        texte = self._textbox.get("1.0", "end").strip()
        if not texte:
            self._lbl_status.configure(text="⚠ Collez les stats du mount.",
                                        text_color=C["lose"])
            return

        nouveau, statut, meta = self.controller.resoudre_mount(texte)

        if statut == "no_name":
            self._lbl_status.configure(
                text="⚠ Impossible de lire le nom du mount (attendu : « [Rareté] Nom »).",
                text_color=C["lose"])
            return

        if statut == "unknown_not_lvl1":
            nom = meta.get("name") if meta else "?"
            self._lbl_status.configure(
                text=f"⚠ « {nom} » n'est pas en bibliothèque. Importez-le d'abord en Lv.1 pour enregistrer ses stats de référence.",
                text_color=C["lose"])
            return

        for w in self._result_outer.winfo_children():
            w.destroy()

        if statut == "added":
            nom = meta.get("name") if meta else ""
            self._lbl_status.configure(
                text=f"✅ « {nom} » ajouté à la bibliothèque (Lv.1) — simulation en cours…",
                text_color=C["win"])
            self.update_idletasks()
            self.app.after(50, self._refresh_library_only)
        else:
            self._lbl_status.configure(text="⏳ Simulation en cours…",
                                        text_color=C["muted"])
            self.update_idletasks()

        def on_result(w: int, l: int, d: int) -> None:
            self._lbl_status.configure(text="", text_color=C["muted"])
            self._afficher_resultats(w, l, d, nouveau)

        self.controller.tester_mount(nouveau, on_result)

    def _afficher_resultats(self, wins: int, loses: int, draws: int,
                             nouveau_mount: Dict) -> None:
        for w in self._result_outer.winfo_children():
            w.destroy()

        card = ctk.CTkFrame(self._result_outer, fg_color=C["card"],
                             corner_radius=12)
        card.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(card, text="Résultat — Nouveau mount vs Ancien mount",
                     font=FONT_SUB, text_color=C["text"]).pack(
            padx=20, pady=(16, 4), anchor="w")
        ctk.CTkLabel(card,
                     text="Nouveau moi (avec ce mount) vs Ancien moi (avec l'ancien mount).",
                     font=("Segoe UI", 11), text_color=C["muted"]).pack(
            padx=20, pady=(0, 12), anchor="w")

        bars = build_wld_bars(card, wins, loses, draws, total=N_SIMULATIONS)
        bars.pack(fill="x", padx=20, pady=(0, 8))

        if wins > loses:
            verdict_txt = f"✅  Ce mount est meilleur — {100 * wins / N_SIMULATIONS:.0f}% de victoires."
            verdict_col = C["win"]
            show_btn    = True
        elif loses > wins:
            verdict_txt = "❌  Ce mount est moins bon. Gardez l'actuel."
            verdict_col = C["lose"]
            show_btn    = False
        else:
            verdict_txt = "🤝  Égalité — les deux mounts se valent."
            verdict_col = C["draw"]
            show_btn    = False

        ctk.CTkLabel(card, text=verdict_txt, font=FONT_SUB,
                     text_color=verdict_col).pack(
            padx=20, pady=(8, 8 if show_btn else 16))

        if show_btn:
            ctk.CTkButton(
                card, text="💾  Appliquer ce mount",
                font=FONT_BODY, height=36, corner_radius=8,
                fg_color=C["win"], hover_color=C["win_hv"],
                text_color=C["bg"],
                command=lambda m=nouveau_mount: self._appliquer_mount(m),
            ).pack(padx=20, pady=(0, 16), fill="x")

    def _appliquer_mount(self, mount: Dict) -> None:
        if not confirmer(
            self.app, "Confirmer le remplacement",
            "Remplacer le mount actuel par ce nouveau mount ?",
            ok_label="Remplacer", danger=False,
        ):
            return
        self.controller.set_mount(mount)
        self._lbl_status.configure(text="✅ Mount mis à jour !",
                                    text_color=C["win"])
        self.app.refresh_current()

    def _enregistrer_direct(self) -> None:
        texte = self._textbox.get("1.0", "end").strip()
        if not texte:
            self._lbl_status.configure(
                text="⚠ Collez d'abord les stats du mount.",
                text_color=C["lose"])
            return

        mount, statut, meta = self.controller.resoudre_mount(texte)
        if statut == "no_name":
            self._lbl_status.configure(
                text="⚠ Impossible de lire le nom du mount.",
                text_color=C["lose"])
            return
        if statut == "unknown_not_lvl1":
            nom = meta.get("name") if meta else "?"
            self._lbl_status.configure(
                text=f"⚠ « {nom} » n'est pas en bibliothèque. Importez-le d'abord en Lv.1.",
                text_color=C["lose"])
            return

        if not confirmer(
            self.app, "Enregistrer sans simuler",
            "Enregistrer ce mount sans tester s'il est meilleur que l'actuel ?",
            ok_label="Enregistrer", danger=False,
        ):
            return
        self.controller.set_mount(mount)
        self._lbl_status.configure(text="✅ Mount enregistré !",
                                    text_color=C["win"])
        self.app.refresh_current()
