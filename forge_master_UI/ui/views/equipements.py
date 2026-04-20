"""
============================================================
  FORGE MASTER UI — Comparateur d'équipements
  Coller texte avec NEW! → calcul + simulation automatique.
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
        self.controller = controller
        self.app        = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._result_data = None
        self._build()

    def _build(self):
        # En-tête
        header = ctk.CTkFrame(self, fg_color=C["surface"], corner_radius=0, height=64)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        ctk.CTkLabel(header, text="Comparateur d'équipements",
                     font=FONT_TITLE, text_color=C["text"]).pack(
            side="left", padx=24, pady=16)

        # Scrollable body
        scroll = ctk.CTkScrollableFrame(self, fg_color=C["bg"], corner_radius=0)
        scroll.grid(row=1, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        # ── Zone de saisie ────────────────────────────────────
        input_card = ctk.CTkFrame(scroll, fg_color=C["card"], corner_radius=12)
        input_card.grid(row=0, column=0, padx=16, pady=16, sticky="ew")
        input_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(input_card, text="Texte de comparaison",
                     font=FONT_SUB, text_color=C["text"]).grid(
            row=0, column=0, padx=20, pady=(16, 4), sticky="w")

        ctk.CTkLabel(input_card,
                     text="Collez le texte de comparaison depuis le jeu (doit contenir « NEW! »).",
                     font=FONT_SMALL, text_color=C["muted"]).grid(
            row=1, column=0, padx=20, pady=(0, 8), sticky="w")

        self.text_box = ctk.CTkTextbox(
            input_card, height=180, font=("Consolas", 11),
            fg_color="#0D0F14", text_color=C["text"],
            border_color=C["border"], border_width=1,
        )
        self.text_box.grid(row=2, column=0, padx=16, pady=(0, 8), sticky="ew")

        # Type arme (optionnel si détecté)
        type_f = ctk.CTkFrame(input_card, fg_color="transparent")
        type_f.grid(row=3, column=0, padx=16, pady=(0, 8), sticky="w")
        ctk.CTkLabel(type_f, text="Type arme (si non détecté) :",
                     font=FONT_SMALL, text_color=C["muted"]).pack(side="left")
        self.weapon_type = ctk.StringVar(value="auto")
        for val, lbl in [("auto", "Auto"), ("corps_a_corps", "⚔ Mêlée"), ("distance", "🏹 Distance")]:
            ctk.CTkRadioButton(type_f, text=lbl, variable=self.weapon_type,
                               value=val, text_color=C["text"],
                               font=FONT_SMALL).pack(side="left", padx=10)

        self._lbl_err = ctk.CTkLabel(input_card, text="",
                                      font=FONT_SMALL, text_color=C["lose"])
        self._lbl_err.grid(row=4, column=0, padx=20)

        ctk.CTkButton(
            input_card, text="🔍  Analyser et simuler",
            font=FONT_SUB, height=40, corner_radius=8,
            fg_color=C["accent"], hover_color="#c94828",
            command=self._analyser,
        ).grid(row=5, column=0, padx=16, pady=(0, 16), sticky="ew")

        # ── Zone résultats ────────────────────────────────────
        self.result_container = ctk.CTkFrame(scroll, fg_color="transparent")
        self.result_container.grid(row=1, column=0, padx=16, pady=(0, 16), sticky="ew")
        self.result_container.grid_columnconfigure((0, 1), weight=1)

    def _analyser(self):
        if not self.controller.has_profil():
            self._lbl_err.configure(
                text="⚠ Aucun profil joueur. Allez dans Dashboard d'abord.")
            return

        texte = self.text_box.get("1.0", "end").strip()
        if not texte:
            self._lbl_err.configure(text="⚠ Collez le texte de comparaison.")
            return

        result = self.controller.comparer_equipement(texte)
        if result is None:
            self._lbl_err.configure(
                text="⚠ Texte invalide : assurez-vous que « NEW! » est présent.")
            return

        eq_ancien, eq_nouveau, profil_nouveau = result

        # Appliquer le type si forcé
        if self.weapon_type.get() != "auto" and eq_nouveau.get("type_attaque") is None:
            eq_nouveau["type_attaque"] = self.weapon_type.get()

        self._lbl_err.configure(text="")
        self._result_data = (eq_ancien, eq_nouveau, profil_nouveau)

        # Afficher comparaison stats immédiatement
        self._afficher_stats(eq_ancien, eq_nouveau, profil_nouveau)

        # Lancer simulation en arrière-plan
        self._lbl_verdict = ctk.CTkLabel(
            self.result_container,
            text="⏳ Simulation en cours (1000 combats)…",
            font=FONT_BODY, text_color=C["muted"])
        self._lbl_verdict.grid(row=2, column=0, columnspan=2, pady=8)
        self.update()

        from backend.forge_master import stats_combat
        # FIX : adversaire = profil actuel, joueur = profil avec nouvel équipement
        se_ancien = stats_combat(self.controller.get_profil())
        skills    = self.controller.get_skills_actifs()

        # FIX : callback thread-safe via after()
        def on_result(wins, loses, draws):
            self.after(0, lambda: self._on_sim_done(wins, loses, draws, profil_nouveau))

        self.controller.simuler(
            se_ancien,          # adversaire = profil actuel (sans le nouvel équip)
            skills,
            on_result,
            profil_override=profil_nouveau,   # joueur = avec le nouvel équip
            skills_override=skills,
        )

    def _on_sim_done(self, wins, loses, draws, profil_nouveau):
        if self._lbl_verdict and self._lbl_verdict.winfo_exists():
            self._lbl_verdict.destroy()
        self._afficher_simulation(wins, loses, draws, profil_nouveau)

    def _afficher_stats(self, eq_ancien, eq_nouveau, profil_nouveau):
        # Nettoyer les anciens résultats
        for w in self.result_container.winfo_children():
            w.destroy()

        profil_actuel = self.controller.get_profil()

        # Colonne Ancien
        col_a = ctk.CTkFrame(self.result_container, fg_color=C["card"], corner_radius=12)
        col_a.grid(row=0, column=0, padx=(0, 8), pady=(0, 8), sticky="nsew")
        ctk.CTkLabel(col_a, text="Équipement actuel",
                     font=FONT_SUB, text_color=C["muted"]).pack(padx=16, pady=(14, 6))
        self._render_eq_stats(col_a, eq_ancien)

        # Colonne Nouveau
        col_n = ctk.CTkFrame(self.result_container, fg_color=C["card"], corner_radius=12)
        col_n.grid(row=0, column=1, padx=(8, 0), pady=(0, 8), sticky="nsew")
        ctk.CTkLabel(col_n, text="Nouvel équipement",
                     font=FONT_SUB, text_color=C["accent"]).pack(padx=16, pady=(14, 6))
        self._render_eq_stats(col_n, eq_nouveau)

        # Comparaison HP / ATQ
        delta_frame = ctk.CTkFrame(self.result_container, fg_color=C["card"], corner_radius=12)
        delta_frame.grid(row=1, column=0, columnspan=2, padx=0, pady=(0, 8), sticky="ew")
        delta_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        ctk.CTkLabel(delta_frame, text="Impact sur le profil",
                     font=FONT_SUB, text_color=C["text"]).grid(
            row=0, column=0, columnspan=4, padx=20, pady=(14, 8), sticky="w")

        for col, (label, key, is_big) in enumerate([
            ("HP Total",  "hp_total",       True),
            ("ATQ Total", "attaque_total",   True),
            ("HP Base",   "hp_base",        False),
            ("ATQ Base",  "attaque_base",   False),
        ]):
            v_old = profil_actuel.get(key, 0)
            v_new = profil_nouveau.get(key, 0)
            delta = v_new - v_old
            color = C["up"] if delta > 0 else (C["down"] if delta < 0 else C["neutral"])
            sign  = "+" if delta >= 0 else ""

            f = ctk.CTkFrame(delta_frame, fg_color="#232840", corner_radius=8)
            f.grid(row=1, column=col, padx=8, pady=(0, 14), sticky="ew")
            ctk.CTkLabel(f, text=label, font=FONT_SMALL,
                         text_color=C["muted"]).pack(pady=(8, 0))
            ctk.CTkLabel(f, text=self.controller.fmt_nombre(v_new),
                         font=("Segoe UI", 16, "bold"),
                         text_color=C["text"]).pack()
            ctk.CTkLabel(f,
                         text=f"{sign}{self.controller.fmt_nombre(delta)}",
                         font=FONT_SMALL, text_color=color).pack(pady=(0, 8))

    def _render_eq_stats(self, parent, eq):
        stat_labels = [
            ("hp_flat",         "Health (flat)"),
            ("damage_flat",     "Damage (flat)"),
            ("health_pct",      "Health %"),
            ("damage_pct",      "Damage %"),
            ("melee_pct",       "Melee %"),
            ("ranged_pct",      "Ranged %"),
            ("taux_crit",       "Crit Chance"),
            ("degat_crit",      "Crit Damage"),
            ("health_regen",    "Health Regen"),
            ("lifesteal",       "Lifesteal"),
            ("double_chance",   "Double Chance"),
            ("vitesse_attaque", "Attack Speed"),
            ("skill_damage",    "Skill Damage"),
            ("skill_cooldown",  "Skill Cooldown"),
            ("chance_blocage",  "Block Chance"),
        ]
        any_shown = False
        for i, (key, label) in enumerate(stat_labels):
            val = eq.get(key, 0.0)
            if not val:
                continue
            any_shown = True
            row_f = ctk.CTkFrame(
                parent,
                fg_color="#232840" if i % 2 == 0 else C["card"],
                corner_radius=4,
            )
            row_f.pack(padx=10, pady=1, fill="x")
            row_f.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(row_f, text=label, font=FONT_SMALL,
                         text_color=C["muted"], anchor="w").grid(
                row=0, column=0, padx=12, pady=5, sticky="w")
            unit = "" if key in ("hp_flat", "damage_flat") else "%"
            ctk.CTkLabel(row_f,
                         text=self.controller.fmt_nombre(val) if key in ("hp_flat", "damage_flat") else f"+{val}{unit}",
                         font=FONT_MONO, text_color=C["text"],
                         anchor="e").grid(row=0, column=1, padx=12, pady=5, sticky="e")

        t = eq.get("type_attaque")
        if t:
            ctk.CTkLabel(parent,
                         text=f"Type : {'🏹 Distance' if t == 'distance' else '⚔ Mêlée'}",
                         font=FONT_SMALL, text_color=C["muted"]).pack(
                padx=12, pady=(4, 10), anchor="w")

        if not any_shown and not t:
            ctk.CTkLabel(parent, text="Aucune stat détectée",
                         font=FONT_SMALL, text_color=C["muted"]).pack(pady=20)

    def _afficher_simulation(self, wins, loses, draws, profil_nouveau):
        sim_frame = ctk.CTkFrame(self.result_container, fg_color=C["card"], corner_radius=12)
        sim_frame.grid(row=2, column=0, columnspan=2, padx=0, pady=(0, 16), sticky="ew")
        sim_frame.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkLabel(sim_frame, text="Résultat simulation (1000 combats)",
                     font=FONT_SUB, text_color=C["text"]).grid(
            row=0, column=0, columnspan=3, padx=20, pady=(14, 8), sticky="w")

        # Compteurs
        for col, (label, val, color) in enumerate([
            ("WIN",  wins,  C["win"]),
            ("LOSE", loses, C["lose"]),
            ("DRAW", draws, C["draw"]),
        ]):
            f = ctk.CTkFrame(sim_frame, fg_color="#232840", corner_radius=10)
            f.grid(row=1, column=col, padx=10, pady=(0, 8), sticky="ew")
            ctk.CTkLabel(f, text=label, font=FONT_SMALL,
                         text_color=C["muted"]).pack(pady=(8, 0))
            ctk.CTkLabel(f, text=str(val), font=FONT_BIG,
                         text_color=color).pack()
            ctk.CTkLabel(f, text=f"{val/10:.1f}%", font=FONT_SMALL,
                         text_color=C["muted"]).pack(pady=(0, 8))

        # Barre win rate
        bar = ctk.CTkProgressBar(sim_frame, height=10, corner_radius=5,
                                  progress_color=C["win"] if wins >= loses else C["lose"])
        bar.grid(row=2, column=0, columnspan=3, padx=20, pady=(4, 8), sticky="ew")
        bar.set(wins / 1000)

        # Verdict + bouton sauvegarder
        if wins > loses:
            verdict = f"✅  Le nouvel équipement est meilleur ! ({wins/10:.1f}% WIN)"
            color   = C["win"]
        elif loses > wins:
            verdict = f"❌  L'ancien équipement reste meilleur. ({loses/10:.1f}% LOSE)"
            color   = C["lose"]
        else:
            verdict = "🤝  Équivalents — aucun changement nécessaire."
            color   = C["draw"]

        ctk.CTkLabel(sim_frame, text=verdict,
                     font=FONT_SUB, text_color=color).grid(
            row=3, column=0, columnspan=3, padx=20, pady=(0, 8))

        if wins > loses:
            ctk.CTkButton(
                sim_frame,
                text="💾  Appliquer ce nouvel équipement",
                font=FONT_BODY, height=36, corner_radius=8,
                fg_color=C["win"], hover_color="#27ae60", text_color="#0D0F14",
                command=lambda: self._appliquer(profil_nouveau),
            ).grid(row=4, column=0, columnspan=3, padx=20, pady=(0, 14), sticky="ew")

    def _appliquer(self, profil_nouveau):
        self.controller.appliquer_equipement(profil_nouveau)
        self.app.refresh_current()
