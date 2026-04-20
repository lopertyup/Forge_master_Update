"""
============================================================
  FORGE MASTER UI — Comparateur d'équipements
  Disposition : texte à gauche | ancien/nouveau empilés à droite
  Simulation auto dès détection de NEW!
============================================================
"""

import customtkinter as ctk

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
    "up":      "#2ECC71",
    "down":    "#E74C3C",
    "neutral": "#7A7F96",
}

FONT_TITLE = ("Segoe UI", 20, "bold")
FONT_SUB   = ("Segoe UI", 13, "bold")
FONT_BODY  = ("Segoe UI", 13)
FONT_SMALL = ("Segoe UI", 11)
FONT_BIG   = ("Segoe UI", 26, "bold")
FONT_MONO  = ("Consolas", 12)


class EquipementsView(ctk.CTkFrame):

    def __init__(self, parent, controller, app):
        super().__init__(parent, fg_color=C["bg"], corner_radius=0)
        self.controller    = controller
        self.app           = app
        self._result_data  = None
        self._profil_nouveau = None
        self._after_id     = None  # pour debounce auto-analyse
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build()

    # ════════════════════════════════════════════════════════
    #  CONSTRUCTION UI
    # ════════════════════════════════════════════════════════

    def _build(self):
        # ── En-tête ──────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color=C["surface"], corner_radius=0, height=64)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        ctk.CTkLabel(header, text="Comparateur d'équipements",
                     font=FONT_TITLE, text_color=C["text"]).pack(
            side="left", padx=24, pady=16)

        # ── Corps principal (pas scrollable — tout doit tenir à l'écran) ──
        body = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        body.grid(row=1, column=0, sticky="nsew", padx=16, pady=12)
        body.grid_columnconfigure(0, weight=2)   # colonne texte
        body.grid_columnconfigure(1, weight=3)   # colonne équipements
        body.grid_rowconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=0)

        # ── Colonne gauche : saisie ──────────────────────────
        left = ctk.CTkFrame(body, fg_color=C["card"], corner_radius=12)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 8))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(left, text="Coller le texte ici",
                     font=FONT_SUB, text_color=C["text"]).grid(
            row=0, column=0, padx=16, pady=(14, 4), sticky="w")

        self.text_box = ctk.CTkTextbox(
            left, font=("Consolas", 11),
            fg_color="#0D0F14", text_color=C["text"],
            border_color=C["border"], border_width=1,
        )
        self.text_box.grid(row=1, column=0, padx=12, pady=(0, 8), sticky="nsew")
        self.text_box.bind("<KeyRelease>", self._on_text_change)

        self._lbl_err = ctk.CTkLabel(left, text="",
                                      font=FONT_SMALL, text_color=C["lose"],
                                      wraplength=260)
        self._lbl_err.grid(row=2, column=0, padx=12, pady=(0, 4))

        self._lbl_status = ctk.CTkLabel(left, text="En attente du texte…",
                                         font=FONT_SMALL, text_color=C["muted"],
                                         wraplength=260)
        self._lbl_status.grid(row=3, column=0, padx=12, pady=(0, 12))

        # ── Colonne droite : ancien + nouveau empilés ────────
        right = ctk.CTkFrame(body, fg_color="transparent", corner_radius=0)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=(0, 8))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)

        # Carte équipement actuel
        self.card_ancien = ctk.CTkFrame(right, fg_color=C["card"], corner_radius=12)
        self.card_ancien.grid(row=0, column=0, sticky="nsew", pady=(0, 6))
        self.card_ancien.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.card_ancien, text="Équipement actuel",
                     font=FONT_SUB, text_color=C["muted"]).pack(
            padx=16, pady=(12, 4), anchor="w")
        self._inner_ancien = ctk.CTkFrame(self.card_ancien, fg_color="transparent")
        self._inner_ancien.pack(fill="both", expand=True, padx=8, pady=(0, 10))

        # Carte nouvel équipement
        self.card_nouveau = ctk.CTkFrame(right, fg_color=C["card"], corner_radius=12)
        self.card_nouveau.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        self.card_nouveau.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.card_nouveau, text="Nouvel équipement",
                     font=FONT_SUB, text_color=C["accent"]).pack(
            padx=16, pady=(12, 4), anchor="w")
        self._inner_nouveau = ctk.CTkFrame(self.card_nouveau, fg_color="transparent")
        self._inner_nouveau.pack(fill="both", expand=True, padx=8, pady=(0, 10))

        # ── Bas : résultats simulation ───────────────────────
        self.bottom = ctk.CTkFrame(body, fg_color=C["card"], corner_radius=12)
        self.bottom.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.bottom.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)
        self._build_bottom_empty()

    def _build_bottom_empty(self):
        for w in self.bottom.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.bottom,
                     text="Les résultats de simulation apparaîtront ici.",
                     font=FONT_SMALL, text_color=C["muted"]).pack(pady=18)

    # ════════════════════════════════════════════════════════
    #  AUTO-ANALYSE (debounce 600 ms)
    # ════════════════════════════════════════════════════════

    def _on_text_change(self, event=None):
        if self._after_id:
            self.after_cancel(self._after_id)
        texte = self.text_box.get("1.0", "end").strip()
        if "NEW!" in texte.upper():
            self._after_id = self.after(600, self._analyser)
        else:
            self._lbl_status.configure(text="En attente de « NEW! » dans le texte…")
            self._lbl_err.configure(text="")

    # ════════════════════════════════════════════════════════
    #  ANALYSE + SIMULATION
    # ════════════════════════════════════════════════════════

    def _analyser(self):
        self._after_id = None

        if not self.controller.has_profil():
            self._lbl_err.configure(
                text="⚠ Aucun profil joueur. Allez dans Dashboard d'abord.")
            return

        texte = self.text_box.get("1.0", "end").strip()
        result = self.controller.comparer_equipement(texte)
        if result is None:
            self._lbl_err.configure(
                text="⚠ Texte invalide : assurez-vous que « NEW! » est présent.")
            return

        self._lbl_err.configure(text="")
        eq_ancien, eq_nouveau, profil_nouveau = result
        self._profil_nouveau = profil_nouveau

        # Afficher les équipements
        self._render_eq(self._inner_ancien, eq_ancien)
        self._render_eq(self._inner_nouveau, eq_nouveau)

        # Lancer simulation
        self._lbl_status.configure(text="⏳ Simulation en cours…")
        self._build_bottom_loading()

        from backend.forge_master import stats_combat
        se_ancien = stats_combat(self.controller.get_profil())
        skills    = self.controller.get_skills_actifs()

        def on_result(wins, loses, draws):
            self.after(0, lambda: self._on_sim_done(wins, loses, draws))

        self.controller.simuler(
            se_ancien,
            skills,
            on_result,
            profil_override=profil_nouveau,
            skills_override=skills,
        )

    def _build_bottom_loading(self):
        for w in self.bottom.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.bottom,
                     text="⏳ Simulation en cours (1000 combats)…",
                     font=FONT_BODY, text_color=C["muted"]).pack(pady=18)

    def _on_sim_done(self, wins, loses, draws):
        self._lbl_status.configure(text="✅ Analyse terminée.")
        self._afficher_resultats(wins, loses, draws)

    # ════════════════════════════════════════════════════════
    #  RENDU ÉQUIPEMENT
    # ════════════════════════════════════════════════════════

    def _render_eq(self, parent, eq):
        for w in parent.winfo_children():
            w.destroy()

        stat_labels = [
            ("hp_flat",         "Health (flat)",  True),
            ("damage_flat",     "Damage (flat)",  True),
            ("health_pct",      "Health %",       False),
            ("damage_pct",      "Damage %",       False),
            ("melee_pct",       "Melee %",        False),
            ("ranged_pct",      "Ranged %",       False),
            ("taux_crit",       "Crit Chance",    False),
            ("degat_crit",      "Crit Damage",    False),
            ("health_regen",    "Health Regen",   False),
            ("lifesteal",       "Lifesteal",      False),
            ("double_chance",   "Double Chance",  False),
            ("vitesse_attaque", "Attack Speed",   False),
            ("skill_damage",    "Skill Damage",   False),
            ("skill_cooldown",  "Skill Cooldown", False),
            ("chance_blocage",  "Block Chance",   False),
        ]

        any_shown = False
        for i, (key, label, is_flat) in enumerate(stat_labels):
            val = eq.get(key, 0.0)
            if not val:
                continue
            any_shown = True
            row_f = ctk.CTkFrame(
                parent,
                fg_color="#232840" if i % 2 == 0 else C["card"],
                corner_radius=4,
            )
            row_f.pack(padx=4, pady=1, fill="x")
            row_f.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(row_f, text=label, font=FONT_SMALL,
                         text_color=C["muted"], anchor="w").grid(
                row=0, column=0, padx=10, pady=4, sticky="w")
            val_str = self.controller.fmt_nombre(val) if is_flat else f"+{val}%"
            ctk.CTkLabel(row_f, text=val_str,
                         font=FONT_MONO, text_color=C["text"],
                         anchor="e").grid(row=0, column=1, padx=10, pady=4, sticky="e")

        t = eq.get("type_attaque")
        if t:
            ctk.CTkLabel(parent,
                         text=f"Type : {'🏹 Distance' if t == 'distance' else '⚔ Mêlée'}",
                         font=FONT_SMALL, text_color=C["muted"]).pack(
                padx=10, pady=(4, 4), anchor="w")

        if not any_shown and not t:
            ctk.CTkLabel(parent, text="Aucune stat détectée",
                         font=FONT_SMALL, text_color=C["muted"]).pack(pady=10)

    # ════════════════════════════════════════════════════════
    #  RÉSULTATS SIMULATION
    # ════════════════════════════════════════════════════════

    def _afficher_resultats(self, wins, loses, draws):
        for w in self.bottom.winfo_children():
            w.destroy()

        total = wins + loses + draws

        # ── Compteurs WIN / LOSE / DRAW ──────────────────────
        for col, (label, val, color) in enumerate([
            ("WIN",  wins,  C["win"]),
            ("LOSE", loses, C["lose"]),
            ("DRAW", draws, C["draw"]),
        ]):
            f = ctk.CTkFrame(self.bottom, fg_color="#232840", corner_radius=10)
            f.grid(row=0, column=col, padx=10, pady=(12, 6), sticky="ew")
            ctk.CTkLabel(f, text=label, font=FONT_SMALL,
                         text_color=C["muted"]).pack(pady=(6, 0))
            ctk.CTkLabel(f, text=str(val), font=FONT_BIG,
                         text_color=color).pack()
            ctk.CTkLabel(f, text=f"{val/10:.1f}%", font=FONT_SMALL,
                         text_color=C["muted"]).pack(pady=(0, 6))

        # ── Barre win rate ───────────────────────────────────
        bar = ctk.CTkProgressBar(self.bottom, height=8, corner_radius=4,
                                  progress_color=C["win"] if wins >= loses else C["lose"])
        bar.grid(row=1, column=0, columnspan=3, padx=16, pady=(0, 6), sticky="ew")
        bar.set(wins / total if total else 0)

        # ── Verdict ──────────────────────────────────────────
        amelioration = wins > loses
        if amelioration:
            verdict = f"✅  Meilleur équipement ! ({wins/10:.1f}% WIN)"
            verdict_color = C["win"]
        elif loses > wins:
            verdict = f"❌  Moins bon équipement. ({loses/10:.1f}% LOSE)"
            verdict_color = C["lose"]
        else:
            verdict = "🤝  Équivalents."
            verdict_color = C["draw"]

        ctk.CTkLabel(self.bottom, text=verdict,
                     font=FONT_SUB, text_color=verdict_color).grid(
            row=2, column=0, columnspan=3, padx=16, pady=(0, 8))

        # ── Boutons ──────────────────────────────────────────
        btn_frame = ctk.CTkFrame(self.bottom, fg_color="transparent")
        btn_frame.grid(row=3, column=0, columnspan=3, padx=16, pady=(0, 12), sticky="ew")
        btn_frame.grid_columnconfigure((0, 1), weight=1)

        if amelioration:
            # Amélioration → Appliquer en vert, Ne pas appliquer en rouge
            ctk.CTkButton(
                btn_frame,
                text="💾  Appliquer le nouvel équipement",
                font=FONT_BODY, height=36, corner_radius=8,
                fg_color=C["win"], hover_color="#27ae60", text_color="#0D0F14",
                command=self._appliquer,
            ).grid(row=0, column=0, padx=(0, 6), sticky="ew")

            ctk.CTkButton(
                btn_frame,
                text="✖  Ne pas appliquer",
                font=FONT_BODY, height=36, corner_radius=8,
                fg_color=C["lose"], hover_color="#c0392b", text_color=C["text"],
                command=self._clear,
            ).grid(row=0, column=1, padx=(6, 0), sticky="ew")
        else:
            # Pas d'amélioration → Appliquer en rouge, Ne pas appliquer en vert
            ctk.CTkButton(
                btn_frame,
                text="💾  Appliquer quand même",
                font=FONT_BODY, height=36, corner_radius=8,
                fg_color=C["lose"], hover_color="#c0392b", text_color=C["text"],
                command=self._appliquer,
            ).grid(row=0, column=0, padx=(0, 6), sticky="ew")

            ctk.CTkButton(
                btn_frame,
                text="✔  Garder l'équipement actuel",
                font=FONT_BODY, height=36, corner_radius=8,
                fg_color=C["win"], hover_color="#27ae60", text_color="#0D0F14",
                command=self._clear,
            ).grid(row=0, column=1, padx=(6, 0), sticky="ew")

    # ════════════════════════════════════════════════════════
    #  ACTIONS
    # ════════════════════════════════════════════════════════

    def _appliquer(self):
        if self._profil_nouveau:
            self.controller.appliquer_equipement(self._profil_nouveau)
            self.app.refresh_current()
        self._clear()

    def _clear(self):
        self.text_box.delete("1.0", "end")
        self._profil_nouveau = None
        self._result_data    = None
        self._lbl_err.configure(text="")
        self._lbl_status.configure(text="En attente du texte…")
        self._render_eq(self._inner_ancien, {})
        self._render_eq(self._inner_nouveau, {})
        self._build_bottom_empty()