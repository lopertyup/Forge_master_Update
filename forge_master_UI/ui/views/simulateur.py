"""
============================================================
  FORGE MASTER UI — Simulateur de combat
  1000 simulations avec affichage graphique des résultats.
  FIX : panneau adversaire scrollable + bouton toujours visible
        + callback thread-safe via after()
============================================================
"""

import customtkinter as ctk
from PIL import Image
import os
from backend.forge_master import parser_texte, finaliser_bases, stats_combat

_ICONS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "skill_icons")

def _load_icon(code: str, size: int = 40):
    path = os.path.join(_ICONS_DIR, f"{code}.png")
    if not os.path.isfile(path):
        return None
    try:
        img = Image.open(path).convert("RGBA").resize((size, size), Image.LANCZOS)
        return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
    except Exception:
        return None

C = {
    "bg":      "#0D0F14",
    "surface": "#151820",
    "card":    "#1C2030",
    "border":  "#2A2F45",
    "accent":  "#E8593C",
    "text":    "#E8E6DF",
    "muted":   "#7A7F96",
    "win":     "#2ECC71",
    "lose":    "#E74C3C",
    "draw":    "#F39C12",
}

FONT_TITLE = ("Segoe UI", 20, "bold")
FONT_SUB   = ("Segoe UI", 13, "bold")
FONT_BODY  = ("Segoe UI", 13)
FONT_SMALL = ("Segoe UI", 11)
FONT_BIG   = ("Segoe UI", 28, "bold")
FONT_MONO  = ("Consolas", 12)


class SimulateurView(ctk.CTkFrame):

    def __init__(self, parent, controller, app):
        super().__init__(parent, fg_color=C["bg"], corner_radius=0)
        self.controller  = controller
        self.app         = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._adv_profil = None
        self._adv_skills = []
        self._build()

    def _build(self):
        # En-tête
        header = ctk.CTkFrame(self, fg_color=C["surface"], corner_radius=0, height=64)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        ctk.CTkLabel(header, text="Simulateur de combat",
                     font=FONT_TITLE, text_color=C["text"]).pack(
            side="left", padx=24, pady=16)

        # Corps principal : colonnes gauche/droite + résultats en bas
        body = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        body.grid(row=1, column=0, sticky="nsew", padx=16, pady=16)
        body.grid_columnconfigure((0, 1), weight=1)
        body.grid_rowconfigure(1, weight=1)

        # ── Colonne gauche : Joueur ───────────────────────────
        joueur_card = ctk.CTkFrame(body, fg_color=C["card"], corner_radius=12)
        joueur_card.grid(row=0, column=0, padx=(0, 8), pady=(0, 8), sticky="nsew")
        self._build_joueur_panel(joueur_card)

        # ── Colonne droite : Adversaire (scrollable + bouton fixe en bas) ──
        adv_outer = ctk.CTkFrame(body, fg_color=C["card"], corner_radius=12)
        adv_outer.grid(row=0, column=1, padx=(8, 0), pady=(0, 8), sticky="nsew")
        adv_outer.grid_rowconfigure(0, weight=1)
        adv_outer.grid_rowconfigure(1, weight=0)
        adv_outer.grid_columnconfigure(0, weight=1)
        self._build_adversaire_panel(adv_outer)

        # ── Résultats (toute la largeur) ──────────────────────
        self.result_frame = ctk.CTkFrame(body, fg_color=C["card"], corner_radius=12)
        self.result_frame.grid(row=1, column=0, columnspan=2,
                               padx=0, pady=(0, 0), sticky="nsew")
        self._build_result_panel(self.result_frame)

    # ── Panneau joueur ────────────────────────────────────────

    def _build_joueur_panel(self, parent):
        ctk.CTkLabel(parent, text="⚔  Votre personnage",
                     font=FONT_SUB, text_color=C["text"]).pack(
            padx=16, pady=(14, 6), anchor="w")

        profil = self.controller.get_profil()
        if not profil:
            ctk.CTkLabel(parent,
                         text="Aucun profil chargé.\nAllez dans Dashboard\npour importer vos stats.",
                         font=FONT_BODY, text_color=C["muted"],
                         justify="center").pack(pady=20)
            return

        stats_f = ctk.CTkFrame(parent, fg_color="#232840", corner_radius=8)
        stats_f.pack(padx=12, pady=(0, 8), fill="x")
        for label, key in [("HP", "hp_total"), ("ATQ", "attaque_total")]:
            row = ctk.CTkFrame(stats_f, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=2)
            ctk.CTkLabel(row, text=label, font=FONT_SMALL,
                         text_color=C["muted"], width=40, anchor="w").pack(side="left")
            ctk.CTkLabel(row,
                         text=self.controller.fmt_nombre(profil.get(key, 0)),
                         font=FONT_SUB, text_color=C["text"]).pack(side="left", padx=8)

        type_atq = profil.get("type_attaque", "?")
        ctk.CTkLabel(stats_f,
                     text=f"Type : {'🏹 Distance' if type_atq == 'distance' else '⚔ Corps à Corps'}",
                     font=FONT_SMALL, text_color=C["muted"]).pack(
            padx=12, pady=(0, 8), anchor="w")

        skills = self.controller.get_skills_actifs()
        if skills:
            sk_f = ctk.CTkFrame(parent, fg_color="#232840", corner_radius=8)
            sk_f.pack(padx=12, pady=(0, 12), fill="x")
            ctk.CTkLabel(sk_f, text="Skills :", font=FONT_SMALL,
                         text_color=C["muted"]).pack(padx=12, pady=(8, 2), anchor="w")
            for code, data in skills:
                color = self.controller.rarity_color(data.get("rarity", "common"))
                ctk.CTkLabel(sk_f,
                             text=f"  [{code.upper()}] {data.get('name', '?')}",
                             font=FONT_SMALL, text_color=color).pack(padx=12, anchor="w")
            ctk.CTkFrame(sk_f, fg_color="transparent", height=8).pack()

    # ── Panneau adversaire ────────────────────────────────────
    # Structure : zone scrollable (stats/type/skills) + bouton fixe en bas

    def _build_adversaire_panel(self, parent):
        # Zone scrollable — contient tout sauf le bouton
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent", corner_radius=0)
        scroll.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        scroll.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(scroll, text="🎯  Adversaire",
                     font=FONT_SUB, text_color=C["text"]).pack(
            padx=16, pady=(14, 6), anchor="w")

        ctk.CTkLabel(scroll, text="Stats de l'adversaire :",
                     font=FONT_SMALL, text_color=C["muted"]).pack(padx=16, anchor="w")

        self.adv_textbox = ctk.CTkTextbox(
            scroll, height=120, font=("Consolas", 11),
            fg_color="#0D0F14", text_color=C["text"],
            border_color=C["border"], border_width=1,
        )
        self.adv_textbox.pack(padx=12, pady=(4, 8), fill="x")

        # Type adversaire
        type_f = ctk.CTkFrame(scroll, fg_color="transparent")
        type_f.pack(padx=12, fill="x")
        ctk.CTkLabel(type_f, text="Type :", font=FONT_SMALL,
                     text_color=C["muted"]).pack(side="left")
        self.adv_type = ctk.StringVar(value="distance")
        ctk.CTkRadioButton(type_f, text="🏹 Distance",
                           variable=self.adv_type, value="distance",
                           text_color=C["text"], font=FONT_SMALL).pack(side="left", padx=10)
        ctk.CTkRadioButton(type_f, text="⚔ C-à-C",
                           variable=self.adv_type, value="corps_a_corps",
                           text_color=C["text"], font=FONT_SMALL).pack(side="left", padx=4)

        # Skills adversaire
        ctk.CTkLabel(scroll, text="Skills adversaire :",
                     font=FONT_SMALL, text_color=C["muted"]).pack(
            padx=16, pady=(8, 2), anchor="w")

        tous = self.controller.get_tous_skills()
        self._adv_skill_vars = {}
        self._adv_skill_btns = {}

        sk_grid = ctk.CTkFrame(scroll, fg_color="#0D0F14",
                                border_color=C["border"], border_width=1,
                                corner_radius=8)
        sk_grid.pack(padx=12, pady=(0, 4), fill="x")

        cols = 6
        for i, (code, data) in enumerate(sorted(tous.items())):
            color    = self.controller.rarity_color(data.get("rarity", "common"))
            var      = ctk.BooleanVar(value=False)
            self._adv_skill_vars[code] = var
            icon_img = _load_icon(code, size=44)
            name     = data.get("name", code)

            btn_frame = ctk.CTkFrame(sk_grid, fg_color="transparent", corner_radius=8)
            btn_frame.grid(row=i // cols, column=i % cols, padx=6, pady=6)

            lbl = ctk.CTkLabel(
                btn_frame,
                image=icon_img if icon_img else None,
                text="" if icon_img else code.upper(),
                font=("Segoe UI", 9, "bold"),
                text_color=color,
                fg_color="transparent",
                corner_radius=8,
                width=52, height=52,
            )
            lbl.pack()
            lbl.bind("<Button-1>", lambda e, c=code: self._toggle_adv_skill(c))
            self._adv_skill_btns[code] = (lbl, btn_frame)

            lbl.bind("<Enter>", lambda e, n=name, col=color, l=lbl: l.configure(text=n[:8], text_color=col))
            lbl.bind("<Leave>", lambda e, img=icon_img, l=lbl: l.configure(
                text="" if img else code.upper(), image=img if img else None))

        for c in range(cols):
            sk_grid.grid_columnconfigure(c, weight=1)

        self._adv_limit_lbl = ctk.CTkLabel(
            scroll, text="", font=FONT_SMALL, text_color=C["lose"])
        self._adv_limit_lbl.pack(pady=(2, 4))

        # Séparateur visuel
        ctk.CTkFrame(scroll, fg_color=C["border"], height=1).pack(
            fill="x", padx=12, pady=(0, 4))

        # ── Bouton fixe en bas (hors du scroll) ──────────────
        btn_frame = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=0)
        btn_frame.grid(row=1, column=0, sticky="ew", padx=0, pady=0)
        btn_frame.grid_columnconfigure(0, weight=1)

        self._lbl_status_adv = ctk.CTkLabel(
            btn_frame, text="", font=FONT_SMALL, text_color=C["lose"])
        self._lbl_status_adv.grid(row=0, column=0, padx=12, pady=(6, 0))

        ctk.CTkButton(
            btn_frame, text="▶  Lancer 1000 simulations",
            font=FONT_SUB, height=40, corner_radius=8,
            fg_color=C["accent"], hover_color="#c94828",
            command=self._lancer,
        ).grid(row=1, column=0, padx=12, pady=(4, 12), sticky="ew")

    def _toggle_adv_skill(self, code):
        var      = self._adv_skill_vars[code]
        selected = [c for c, v in self._adv_skill_vars.items() if v.get()]
        if not var.get():
            if len(selected) >= 3:
                self._adv_limit_lbl.configure(text="⚠ Maximum 3 skills")
                return
            var.set(True)
        else:
            var.set(False)
        self._adv_limit_lbl.configure(text="")
        # Mettre à jour le style du bouton
        lbl, frame = self._adv_skill_btns[code]
        if var.get():
            frame.configure(fg_color="#1a2e1a", corner_radius=8,
                            border_width=2, border_color=C["win"])
        else:
            frame.configure(fg_color="transparent", border_width=0)

    def _check_adv_skills(self):
        selected = [c for c, v in self._adv_skill_vars.items() if v.get()]
        if len(selected) > 3:
            self._adv_limit_lbl.configure(text="⚠ Maximum 3 skills")
        else:
            self._adv_limit_lbl.configure(text="")

    # ── Panneau résultats ─────────────────────────────────────

    def _build_result_panel(self, parent):
        parent.grid_columnconfigure((0, 1, 2), weight=1)

        self._lbl_status = ctk.CTkLabel(
            parent,
            text="Remplissez les stats adversaire et lancez la simulation.",
            font=FONT_BODY, text_color=C["muted"],
        )
        self._lbl_status.grid(row=0, column=0, columnspan=3, pady=20)

        self._lbl_win  = self._big_counter(parent, "WIN",  C["win"],  row=1, col=0)
        self._lbl_lose = self._big_counter(parent, "LOSE", C["lose"], row=1, col=1)
        self._lbl_draw = self._big_counter(parent, "DRAW", C["draw"], row=1, col=2)

        self._progress = ctk.CTkProgressBar(parent, height=12, corner_radius=6,
                                             progress_color=C["win"])
        self._progress.grid(row=2, column=0, columnspan=3,
                            padx=24, pady=(8, 0), sticky="ew")
        self._progress.set(0)

        self._lbl_verdict = ctk.CTkLabel(
            parent, text="", font=FONT_SUB, text_color=C["text"])
        self._lbl_verdict.grid(row=3, column=0, columnspan=3, pady=(8, 16))

    def _big_counter(self, parent, label, color, row, col):
        frame = ctk.CTkFrame(parent, fg_color="#232840", corner_radius=10)
        frame.grid(row=row, column=col, padx=12, pady=8, sticky="ew")
        ctk.CTkLabel(frame, text=label, font=FONT_SMALL,
                     text_color=C["muted"]).pack(pady=(10, 0))
        lbl = ctk.CTkLabel(frame, text="—", font=FONT_BIG, text_color=color)
        lbl.pack()
        ctk.CTkLabel(frame, text="/ 1000", font=FONT_SMALL,
                     text_color=C["muted"]).pack(pady=(0, 10))
        return lbl

    # ── Logique ───────────────────────────────────────────────

    def _lancer(self):
        if not self.controller.has_profil():
            self._lbl_status_adv.configure(
                text="⚠ Aucun profil joueur. Allez dans Dashboard.")
            return

        texte = self.adv_textbox.get("1.0", "end").strip()
        if not texte:
            self._lbl_status_adv.configure(text="⚠ Collez les stats de l'adversaire.")
            return

        adv_selected = [c for c, v in self._adv_skill_vars.items() if v.get()]
        if len(adv_selected) > 3:
            self._lbl_status_adv.configure(text="⚠ Maximum 3 skills pour l'adversaire.")
            return

        self._lbl_status_adv.configure(text="")

        adv_stats          = parser_texte(texte)
        adv_stats["type_attaque"] = self.adv_type.get()
        adv_stats          = finaliser_bases(adv_stats)
        adv_combat         = stats_combat(adv_stats)
        adv_skills         = self.controller.get_skills_from_codes(adv_selected)

        self._lbl_status.configure(text="⏳ Simulation en cours…", text_color=C["muted"])
        self._lbl_win.configure(text="…")
        self._lbl_lose.configure(text="…")
        self._lbl_draw.configure(text="…")
        self._progress.set(0)
        self._lbl_verdict.configure(text="")
        self.update()

        # Callback thread-safe via after()
        def on_result(wins, loses, draws):
            self.after(0, lambda: self._afficher_resultats(wins, loses, draws))

        self.controller.simuler(adv_combat, adv_skills, on_result)

    def _afficher_resultats(self, wins, loses, draws):
        self._lbl_win.configure(text=str(wins))
        self._lbl_lose.configure(text=str(loses))
        self._lbl_draw.configure(text=str(draws))
        win_rate = wins / 1000
        self._progress.set(win_rate)
        self._progress.configure(
            progress_color=C["win"] if win_rate >= 0.5 else C["lose"])

        if wins > loses:
            verdict = f"✅  Vous gagnez {wins/10:.1f}% du temps"
            color   = C["win"]
        elif loses > wins:
            verdict = f"❌  Vous perdez {loses/10:.1f}% du temps"
            color   = C["lose"]
        else:
            verdict = f"🤝  Égalité parfaite ({draws/10:.1f}% draws)"
            color   = C["draw"]

        self._lbl_verdict.configure(text=verdict, text_color=color)
        self._lbl_status.configure(text="Simulation terminée.", text_color=C["muted"])
