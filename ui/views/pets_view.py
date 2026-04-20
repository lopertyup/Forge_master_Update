"""
============================================================
  FORGE MASTER UI — Gestion des Pets (réécriture complète)
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
}

FONT_TITLE = ("Segoe UI", 20, "bold")
FONT_SUB   = ("Segoe UI", 13, "bold")
FONT_BODY  = ("Segoe UI", 13)
FONT_SMALL = ("Segoe UI", 11)
FONT_BIG   = ("Segoe UI", 22, "bold")
FONT_MONO  = ("Consolas", 12)

PET_ICONS = {"PET1": "🐉", "PET2": "🦅", "PET3": "🐺"}

STAT_LABELS = {
    "hp_flat":         "❤  HP",
    "damage_flat":     "⚔  Damage",
    "health_pct":      "❤  Health %",
    "damage_pct":      "⚔  Damage %",
    "melee_pct":       "⚔  Melee %",
    "ranged_pct":      "⚔  Ranged %",
    "taux_crit":       "🎯 Crit Chance",
    "degat_crit":      "💥 Crit Damage",
    "health_regen":    "♻  Health Regen",
    "lifesteal":       "🩸 Lifesteal",
    "double_chance":   "✌  Double Chance",
    "vitesse_attaque": "⚡ Attack Speed",
    "skill_damage":    "✨ Skill Damage",
    "skill_cooldown":  "⏱  Skill CD",
    "chance_blocage":  "🛡  Block Chance",
}


class PetsView(ctk.CTkFrame):

    def __init__(self, parent, controller, app):
        super().__init__(parent, fg_color=C["bg"], corner_radius=0)
        self.controller = controller
        self.app        = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build()

    # ── Construction principale ───────────────────────────────

    def _build(self):
        # En-tête
        header = ctk.CTkFrame(self, fg_color=C["surface"], corner_radius=0, height=64)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        ctk.CTkLabel(header, text="Gestion des Pets",
                     font=FONT_TITLE, text_color=C["text"]).pack(
            side="left", padx=24, pady=16)

        # Scroll principal
        self.scroll = ctk.CTkScrollableFrame(self, fg_color=C["bg"], corner_radius=0)
        self.scroll.grid(row=1, column=0, sticky="nsew")
        self.scroll.grid_columnconfigure(0, weight=1)

        self._build_pets_cards()
        self._build_import_zone()
        self._build_result_zone()

    def _build_pets_cards(self):
        """Affiche les 3 cartes de pets actuels."""
        pets_frame = ctk.CTkFrame(self.scroll, fg_color="transparent")
        pets_frame.grid(row=0, column=0, padx=16, pady=16, sticky="ew")
        pets_frame.grid_columnconfigure((0, 1, 2), weight=1)

        pets = self.controller.get_pets()
        for col, nom in enumerate(["PET1", "PET2", "PET3"]):
            card = self._make_pet_card(pets_frame, nom, pets.get(nom, {}))
            card.grid(row=0, column=col, padx=6, pady=0, sticky="nsew")

    def _make_pet_card(self, parent, nom, pet):
        card = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=12)
        icon = PET_ICONS.get(nom, "🐾")
        ctk.CTkLabel(card, text=f"{icon}  {nom}",
                     font=FONT_SUB, text_color=C["text"]).pack(
            padx=16, pady=(14, 6), anchor="w")

        stats_non_nuls = [(k, v) for k, v in pet.items() if v != 0.0]
        if not stats_non_nuls:
            ctk.CTkLabel(card, text="(vide)",
                         font=FONT_BODY, text_color=C["muted"]).pack(padx=16, pady=20)
        else:
            for i, (k, v) in enumerate(stats_non_nuls):
                row_f = ctk.CTkFrame(card,
                                     fg_color="#232840" if i % 2 == 0 else C["card"],
                                     corner_radius=4)
                row_f.pack(padx=10, pady=1, fill="x")
                row_f.grid_columnconfigure(1, weight=1)
                label = STAT_LABELS.get(k, k)
                ctk.CTkLabel(row_f, text=label, font=FONT_SMALL,
                             text_color=C["muted"], anchor="w").grid(
                    row=0, column=0, padx=10, pady=4, sticky="w")
                unit = "" if k in ("hp_flat", "damage_flat") else "%"
                val_txt = self.controller.fmt_nombre(v) if k in ("hp_flat", "damage_flat") else f"+{v}{unit}"
                ctk.CTkLabel(row_f, text=val_txt, font=FONT_MONO,
                             text_color=C["text"], anchor="e").grid(
                    row=0, column=1, padx=10, pady=4, sticky="e")

        ctk.CTkFrame(card, fg_color="transparent", height=6).pack()
        return card

    def _build_import_zone(self):
        """Zone de saisie du nouveau pet."""
        card = ctk.CTkFrame(self.scroll, fg_color=C["card"], corner_radius=12)
        card.grid(row=1, column=0, padx=16, pady=(0, 8), sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card, text="Tester un nouveau pet",
                     font=FONT_SUB, text_color=C["text"]).grid(
            row=0, column=0, padx=20, pady=(16, 4), sticky="w")
        ctk.CTkLabel(card,
                     text="Collez les stats du pet depuis le jeu.",
                     font=FONT_SMALL, text_color=C["muted"]).grid(
            row=1, column=0, padx=20, pady=(0, 8), sticky="w")

        self.pet_textbox = ctk.CTkTextbox(
            card, height=130, font=("Consolas", 11),
            fg_color="#0D0F14", text_color=C["text"],
            border_color=C["border"], border_width=1)
        self.pet_textbox.grid(row=2, column=0, padx=16, pady=(0, 8), sticky="ew")

        btn_f = ctk.CTkFrame(card, fg_color="transparent")
        btn_f.grid(row=3, column=0, padx=16, pady=(0, 8), sticky="w")

        ctk.CTkButton(btn_f, text="🔬  Simuler le remplacement",
                      font=FONT_BODY, height=38, corner_radius=8,
                      fg_color=C["accent"], hover_color="#c94828",
                      command=self._tester_pet).pack(side="left", padx=(0, 8))

        ctk.CTkButton(btn_f, text="✏  Modifier directement un slot",
                      font=FONT_BODY, height=38, corner_radius=8,
                      fg_color="#2A2F45", hover_color="#3A3F55",
                      command=self._modifier_direct).pack(side="left")

        self._lbl_status = ctk.CTkLabel(card, text="",
                                         font=FONT_SMALL, text_color=C["muted"])
        self._lbl_status.grid(row=4, column=0, padx=20, pady=(0, 12))

    def _build_result_zone(self):
        """Zone de résultats — initialement vide."""
        self._result_outer = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self._result_outer.grid(row=2, column=0, padx=16, pady=(0, 16), sticky="ew")
        self._result_outer.grid_columnconfigure(0, weight=1)

    # ── Logique simulation ────────────────────────────────────

    def _tester_pet(self):
        if not self.controller.has_profil():
            self._lbl_status.configure(
                text="⚠ Aucun profil joueur. Allez dans Dashboard d'abord.",
                text_color=C["lose"])
            return

        texte = self.pet_textbox.get("1.0", "end").strip()
        if not texte:
            self._lbl_status.configure(text="⚠ Collez les stats du pet.",
                                        text_color=C["lose"])
            return

        nouveau_pet = self.controller.importer_texte_pet(texte)

        # Nettoyer la zone résultats
        for w in self._result_outer.winfo_children():
            w.destroy()

        self._lbl_status.configure(text="⏳ Simulation en cours…",
                                    text_color=C["muted"])
        self.update()

        def on_result(resultats):
            self._lbl_status.configure(text="", text_color=C["muted"])
            self._afficher_resultats(resultats, nouveau_pet)

        self.controller.tester_pet(nouveau_pet, on_result)

    def _afficher_resultats(self, resultats, nouveau_pet):
        """Affiche les résultats des 3 simulations."""
        # Nettoyer
        for w in self._result_outer.winfo_children():
            w.destroy()

        # Titre
        titre = ctk.CTkFrame(self._result_outer, fg_color=C["card"], corner_radius=12)
        titre.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(titre, text="Résultats — quel slot remplacer ?",
                     font=FONT_SUB, text_color=C["text"]).pack(
            padx=20, pady=(14, 4), anchor="w")
        ctk.CTkLabel(titre,
                     text="Nouveau moi (avec ce pet) vs Ancien moi (avec l'ancien pet dans ce slot).",
                     font=FONT_SMALL, text_color=C["muted"]).pack(
            padx=20, pady=(0, 12), anchor="w")

        # Trouver le meilleur slot
        meilleur = max(resultats, key=lambda k: resultats[k][0])
        wins_max = resultats[meilleur][0]

        # Cartes des 3 slots
        cards_frame = ctk.CTkFrame(self._result_outer, fg_color="transparent")
        cards_frame.pack(fill="x", pady=(0, 8))
        cards_frame.grid_columnconfigure((0, 1, 2), weight=1)

        for col, nom in enumerate(["PET1", "PET2", "PET3"]):
            wins, loses, draws = resultats[nom]
            is_best = (nom == meilleur and wins > loses)

            card = ctk.CTkFrame(
                cards_frame,
                fg_color="#1a2e1a" if is_best else C["card"],
                corner_radius=12,
                border_width=2 if is_best else 0,
                border_color=C["win"] if is_best else C["card"],
            )
            card.grid(row=0, column=col, padx=6, pady=0, sticky="nsew")

            icon = PET_ICONS.get(nom, "🐾")
            ctk.CTkLabel(card,
                         text=f"{icon} Remplacer {nom}",
                         font=FONT_SUB,
                         text_color=C["win"] if is_best else C["text"]).pack(
                padx=16, pady=(14, 2))

            if is_best:
                ctk.CTkLabel(card, text="★ MEILLEURE OPTION",
                             font=("Segoe UI", 9, "bold"),
                             text_color=C["win"]).pack()

            # Barres WIN / LOSE / DRAW
            for label, val, color in [
                ("WIN",  wins,  C["win"]),
                ("LOSE", loses, C["lose"]),
                ("DRAW", draws, C["draw"]),
            ]:
                row_f = ctk.CTkFrame(card, fg_color="transparent")
                row_f.pack(fill="x", padx=12, pady=2)
                ctk.CTkLabel(row_f, text=label, font=FONT_SMALL,
                             text_color=color, width=36).pack(side="left")
                bar = ctk.CTkProgressBar(row_f, height=8, corner_radius=4,
                                          progress_color=color)
                bar.pack(side="left", fill="x", expand=True, padx=6)
                bar.set(val / 1000)
                ctk.CTkLabel(row_f, text=f"{val/10:.0f}%",
                             font=FONT_SMALL, text_color=C["muted"],
                             width=36).pack(side="right")

            # Verdict
            if wins > loses:
                verdict_txt = f"✅ +{wins/10:.0f}% WIN"
                verdict_col = C["win"]
            elif loses > wins:
                verdict_txt = f"❌ {loses/10:.0f}% LOSE"
                verdict_col = C["lose"]
            else:
                verdict_txt = f"🤝 Égal"
                verdict_col = C["draw"]

            ctk.CTkLabel(card, text=verdict_txt,
                         font=FONT_SMALL, text_color=verdict_col).pack(pady=(4, 4))

            ctk.CTkButton(
                card,
                text=f"Remplacer {nom}",
                font=FONT_SMALL, height=32, corner_radius=6,
                fg_color=C["win"] if is_best else "#2A2F45",
                hover_color="#27ae60" if is_best else "#3A3F55",
                text_color="#0D0F14" if is_best else C["text"],
                command=lambda n=nom, p=nouveau_pet: self._remplacer_pet(n, p),
            ).pack(padx=12, pady=(0, 14), fill="x")

        # Recommandation globale
        reco = ctk.CTkFrame(self._result_outer, fg_color=C["card"], corner_radius=12)
        reco.pack(fill="x", pady=(0, 8))

        if wins_max > resultats[meilleur][1]:
            reco_txt  = f"✅  Remplacez {meilleur} — {wins_max/10:.0f}% de victoires avec ce pet."
            reco_col  = C["win"]
            show_btn  = True
        else:
            reco_txt  = "❌  Aucun remplacement n'est bénéfique. Gardez vos pets actuels."
            reco_col  = C["lose"]
            show_btn  = False

        ctk.CTkLabel(reco, text=reco_txt,
                     font=FONT_SUB, text_color=reco_col).pack(
            padx=20, pady=(16, 8 if show_btn else 16))

        if show_btn:
            ctk.CTkButton(
                reco,
                text=f"💾  Appliquer — remplacer {meilleur}",
                font=FONT_BODY, height=36, corner_radius=8,
                fg_color=C["win"], hover_color="#27ae60",
                text_color="#0D0F14",
                command=lambda n=meilleur, p=nouveau_pet: self._remplacer_pet(n, p),
            ).pack(padx=20, pady=(0, 16), fill="x")

    # ── Actions ───────────────────────────────────────────────

    def _remplacer_pet(self, nom, nouveau_pet):
        self.controller.set_pet(nom, nouveau_pet)
        self._lbl_status.configure(
            text=f"✅ {nom} mis à jour !", text_color=C["win"])
        self.app.refresh_current()

    def _modifier_direct(self):
        texte = self.pet_textbox.get("1.0", "end").strip()
        if not texte:
            self._lbl_status.configure(
                text="⚠ Collez d'abord les stats du pet.",
                text_color=C["lose"])
            return
        ModifyPetDialog(self, self.controller, self.app, texte)


# ════════════════════════════════════════════════════════════
#  Dialogue de modification directe
# ════════════════════════════════════════════════════════════

class ModifyPetDialog(ctk.CTkToplevel):

    def __init__(self, parent, controller, app, texte):
        super().__init__(parent)
        self.controller = controller
        self.app        = app
        self.texte      = texte
        self.title("Modifier un slot pet")
        self.geometry("400x280")
        self.resizable(False, False)
        self.configure(fg_color="#151820")
        self.grab_set()
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="Quel slot remplacer ?",
                     font=("Segoe UI", 15, "bold"),
                     text_color=C["text"]).pack(padx=24, pady=(24, 8))
        ctk.CTkLabel(self, text="Le pet sera enregistré sans simulation.",
                     font=("Segoe UI", 12),
                     text_color=C["muted"]).pack(padx=24)

        self.slot_var = ctk.StringVar(value="PET1")
        for nom in ["PET1", "PET2", "PET3"]:
            icon = PET_ICONS.get(nom, "🐾")
            ctk.CTkRadioButton(
                self, text=f"{icon}  {nom}",
                variable=self.slot_var, value=nom,
                text_color=C["text"], font=("Segoe UI", 13),
            ).pack(padx=40, pady=4, anchor="w")

        btn_f = ctk.CTkFrame(self, fg_color="transparent")
        btn_f.pack(padx=24, pady=20, fill="x")
        ctk.CTkButton(btn_f, text="Annuler",
                      fg_color="#2A2F45", hover_color="#3A3F55",
                      font=("Segoe UI", 13), width=100,
                      command=self.destroy).pack(side="right", padx=(8, 0))
        ctk.CTkButton(btn_f, text="✓  Enregistrer",
                      fg_color=C["accent"], hover_color="#c94828",
                      font=("Segoe UI", 13), width=140,
                      command=self._save).pack(side="right")

    def _save(self):
        nom     = self.slot_var.get()
        nouveau = self.controller.importer_texte_pet(self.texte)
        self.controller.set_pet(nom, nouveau)
        self.destroy()
        self.app.refresh_current()