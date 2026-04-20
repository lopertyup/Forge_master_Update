"""
============================================================
  FORGE MASTER UI — Optimizer View v6
  Compatible avec forge_optimizer v6
============================================================
"""

import threading
import sys
import os
import customtkinter as ctk

C = {
    "bg":      "#0D0F14",
    "surface": "#151820",
    "card":    "#1C2030",
    "border":  "#2A2F45",
    "accent":  "#E8593C",
    "accent2": "#F2A623",
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
FONT_MONO  = ("Consolas", 12)


class OptimizerView(ctk.CTkFrame):

    def __init__(self, parent, controller, app):
        super().__init__(parent, fg_color=C["bg"], corner_radius=0)
        self.controller = controller
        self.app        = app
        self._stop_flag = threading.Event()
        self._running   = False

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build()

    # ════════════════════════════════════════════════════════
    #  LAYOUT
    # ════════════════════════════════════════════════════════

    def _build(self):
        header = ctk.CTkFrame(self, fg_color=C["surface"], corner_radius=0, height=64)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)

        ctk.CTkLabel(header, text="🧬  Optimiseur de substats",
                     font=FONT_TITLE, text_color=C["text"]).pack(
            side="left", padx=24, pady=16)

        self._btn_stop = ctk.CTkButton(
            header, text="⏹  Arrêter",
            font=FONT_BODY, height=36, corner_radius=8,
            fg_color="#444", hover_color="#666",
            command=self._stop, state="disabled")
        self._btn_stop.pack(side="right", padx=8, pady=14)

        self._btn_start = ctk.CTkButton(
            header, text="▶  Lancer",
            font=FONT_BODY, height=36, corner_radius=8,
            fg_color=C["accent"], hover_color="#c94828",
            command=self._start)
        self._btn_start.pack(side="right", padx=8, pady=14)

        scroll = ctk.CTkScrollableFrame(self, fg_color=C["bg"], corner_radius=0)
        scroll.grid(row=1, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        self._build_config(scroll)
        self._build_progress(scroll)
        self._build_chart(scroll)
        self._build_best_build(scroll)
        self._build_log(scroll)

    # ════════════════════════════════════════════════════════
    #  SECTIONS
    # ════════════════════════════════════════════════════════

    def _build_config(self, parent):
        card = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=10)
        card.pack(fill="x", padx=20, pady=(16, 8))
        card.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(card, text="Configuration",
                     font=FONT_SUB, text_color=C["accent"]).grid(
            row=0, column=0, columnspan=2, padx=16, pady=(12, 8), sticky="w")

        params = [
            ("Générations",       "n_gen",  8,   1,  30,   1),
            ("Simulations/build", "n_sims", 100, 20, 500,  20),
        ]
        self._sliders = {}
        self._sld_lbl = {}

        for col, (label, key, default, lo, hi, step) in enumerate(params):
            fr = ctk.CTkFrame(card, fg_color="transparent")
            fr.grid(row=1, column=col, padx=16, pady=(0, 14), sticky="ew")

            ctk.CTkLabel(fr, text=label, font=FONT_SMALL,
                         text_color=C["muted"]).pack(anchor="w")
            val_lbl = ctk.CTkLabel(fr, text=str(default),
                                   font=("Segoe UI", 18, "bold"),
                                   text_color=C["text"])
            val_lbl.pack(anchor="w")
            self._sld_lbl[key] = val_lbl

            sl = ctk.CTkSlider(fr, from_=lo, to=hi,
                               number_of_steps=(hi - lo) // step,
                               command=lambda v, k=key: self._on_slider(k, v))
            sl.set(default)
            sl.pack(fill="x")
            self._sliders[key] = sl

        self._lbl_info = ctk.CTkLabel(card,
            text=self._info_estimation(8, 100),
            font=FONT_SMALL, text_color=C["muted"])
        self._lbl_info.grid(row=2, column=0, columnspan=2, padx=16, pady=(0, 12))

    def _info_estimation(self, n_gen, n_sims):
        total = 32 * n_sims * n_gen
        return (f"32 builds × {n_sims} sims × {n_gen} générations "
                f"= {total:,} simulations totales")

    def _build_progress(self, parent):
        card = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=10)
        card.pack(fill="x", padx=20, pady=8)
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card, text="Progression",
                     font=FONT_SUB, text_color=C["accent"]).grid(
            row=0, column=0, padx=16, pady=(12, 4), sticky="w")

        self._lbl_status = ctk.CTkLabel(card, text="En attente…",
                                         font=FONT_BODY, text_color=C["muted"])
        self._lbl_status.grid(row=1, column=0, padx=16, sticky="w")

        self._progressbar = ctk.CTkProgressBar(card, height=10, corner_radius=4,
                                                progress_color=C["accent"])
        self._progressbar.set(0)
        self._progressbar.grid(row=2, column=0, padx=16, pady=(6, 14), sticky="ew")

    def _build_chart(self, parent):
        card = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=10)
        card.pack(fill="x", padx=20, pady=8)
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card, text="Analyse des substats — top builds",
                     font=FONT_SUB, text_color=C["accent"]).grid(
            row=0, column=0, padx=16, pady=(12, 2), sticky="w")

        ctk.CTkLabel(card,
                     text="Barre = points investis en moyenne sur 24 possibles.  "
                          "🔒 variance faible = stat essentielle.  "
                          "🎲 variance haute = stat situationnelle.",
                     font=FONT_SMALL, text_color=C["muted"], wraplength=700).grid(
            row=1, column=0, padx=16, pady=(0, 8), sticky="w")

        self._chart_frame = ctk.CTkFrame(card, fg_color="transparent")
        self._chart_frame.grid(row=2, column=0, padx=16, pady=(0, 14), sticky="ew")
        self._chart_frame.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(self._chart_frame,
                     text="Lance l'optimiseur pour voir les résultats.",
                     font=FONT_SMALL, text_color=C["muted"]).grid(row=0, column=0)

    def _build_best_build(self, parent):
        card = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=10)
        card.pack(fill="x", padx=20, pady=8)
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card, text="🏆  Meilleur build trouvé",
                     font=FONT_SUB, text_color=C["accent"]).grid(
            row=0, column=0, padx=16, pady=(12, 2), sticky="w")

        ctk.CTkLabel(card,
                     text="Comparaison avec ton build actuel.  "
                          "🔺 à augmenter  🔻 à réduire  ✅ priorité haute.",
                     font=FONT_SMALL, text_color=C["muted"], wraplength=700).grid(
            row=1, column=0, padx=16, pady=(0, 8), sticky="w")

        self._best_frame = ctk.CTkFrame(card, fg_color="transparent")
        self._best_frame.grid(row=2, column=0, padx=16, pady=(0, 14), sticky="ew")
        self._best_frame.grid_columnconfigure((1, 2, 3), weight=1)

        ctk.CTkLabel(self._best_frame,
                     text="Lance l'optimiseur pour voir le meilleur build.",
                     font=FONT_SMALL, text_color=C["muted"]).grid(row=0, column=0)

    def _build_log(self, parent):
        card = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=10)
        card.pack(fill="x", padx=20, pady=(8, 20))
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card, text="Journal",
                     font=FONT_SUB, text_color=C["accent"]).grid(
            row=0, column=0, padx=16, pady=(12, 4), sticky="w")

        self._log_box = ctk.CTkTextbox(
            card, height=140, font=FONT_MONO,
            fg_color=C["surface"], text_color=C["text"],
            state="disabled")
        self._log_box.grid(row=1, column=0, padx=16, pady=(0, 14), sticky="ew")

    # ════════════════════════════════════════════════════════
    #  CONTRÔLES
    # ════════════════════════════════════════════════════════

    def _on_slider(self, key, value):
        self._sld_lbl[key].configure(text=str(int(round(value))))
        n_gen  = int(round(self._sliders["n_gen"].get()))
        n_sims = int(round(self._sliders["n_sims"].get()))
        self._lbl_info.configure(text=self._info_estimation(n_gen, n_sims))

    def _get_params(self):
        return {
            "n_generations": int(round(self._sliders["n_gen"].get())),
            "n_sims":        int(round(self._sliders["n_sims"].get())),
        }

    def _start(self):
        if self._running:
            return
        if not self.controller.has_profil():
            self._lbl_status.configure(
                text="⚠ Aucun profil joueur. Allez dans Dashboard d'abord.",
                text_color=C["lose"])
            return
        self._running = True
        self._stop_flag.clear()
        self._btn_start.configure(state="disabled")
        self._btn_stop.configure(state="normal")
        self._log_clear()
        self._lbl_status.configure(text="Initialisation…", text_color=C["muted"])
        self._progressbar.set(0)
        params = self._get_params()
        threading.Thread(target=self._run, kwargs=params, daemon=True).start()

    def _stop(self):
        self._stop_flag.set()
        self._lbl_status.configure(text="Arrêt demandé…", text_color=C["draw"])

    # ════════════════════════════════════════════════════════
    #  THREAD
    # ════════════════════════════════════════════════════════

    def _run(self, n_generations, n_sims):
        root = os.path.dirname(os.path.dirname(os.path.dirname(
                   os.path.abspath(__file__))))
        if root not in sys.path:
            sys.path.insert(0, root)

        try:
            from forge_optimizer import optimiser
        except ImportError as e:
            self.after(0, lambda: self._lbl_status.configure(
                text=f"Erreur import : {e}", text_color=C["lose"]))
            self.after(0, self._on_done)
            return

        profil  = self.controller.get_profil()
        skills  = self.controller.get_skills_actifs()
        n_total = n_generations * 32

        def on_generation(gen, top_builds, analyse, scores, wr_moyen, meilleur):
            top_wr = max(scores) * 100
            moy_wr = wr_moyen * 100
            msg = (f"Génération {gen}/{n_generations}  │  "
                   f"Meilleur : {top_wr:.1f}%  │  "
                   f"Moy. top 30% : {moy_wr:.1f}%\n")
            self.after(0, lambda m=msg: self._log_append(m))
            self.after(0, lambda a=analyse, g=gen: self._update_chart(a, g))
            self.after(0, lambda b=meilleur, w=top_wr: self._update_best_build(b, w))

        def on_progress(build_num, total_builds, gen):
            done = (gen - 1) * total_builds + build_num
            pct  = done / n_total
            lbl  = f"Génération {gen}/{n_generations} — Build {build_num}/{total_builds}"
            self.after(0, lambda p=pct: self._progressbar.set(p))
            self.after(0, lambda l=lbl: self._lbl_status.configure(
                text=l, text_color=C["muted"]))

        try:
            optimiser(
                profil=profil,
                skills=skills,
                n_generations=n_generations,
                n_sims=n_sims,
                generation_cb=on_generation,
                progress_cb=on_progress,
                stop_flag=self._stop_flag,
            )
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.after(0, lambda t=tb: self._log_append(f"\nERREUR :\n{t}\n"))
            self.after(0, lambda: self._lbl_status.configure(
                text=f"Erreur : {e}", text_color=C["lose"]))

        self.after(0, self._on_done)

    def _on_done(self):
        self._running = False
        self._btn_start.configure(state="normal")
        self._btn_stop.configure(state="disabled")
        if not self._stop_flag.is_set():
            self._lbl_status.configure(text="✅ Terminé !", text_color=C["win"])
            self._progressbar.set(1.0)
        else:
            self._lbl_status.configure(text="⏹ Arrêté", text_color=C["draw"])

    # ════════════════════════════════════════════════════════
    #  DIAGRAMME
    # ════════════════════════════════════════════════════════

    def _update_chart(self, analyse, gen):
        from forge_optimizer import N_SUBSTATS

        for w in self._chart_frame.winfo_children():
            w.destroy()
        self._chart_frame.grid_columnconfigure(2, weight=1)

        for row_idx, (pts_moy, pts_var, moyenne, variance, key, label) in enumerate(analyse):
            ratio = min(1.0, pts_moy / N_SUBSTATS)

            if ratio >= 0.25:
                color = C["win"]
            elif ratio >= 0.10:
                color = C["accent2"]
            else:
                color = C["muted"]

            var_icon = "🔒" if pts_var < 1.0 else ("🎲" if pts_var > 3.0 else "〰")

            ctk.CTkLabel(self._chart_frame, text=label,
                         font=FONT_SMALL, text_color=C["text"],
                         anchor="e", width=120).grid(
                row=row_idx, column=0, padx=(0, 8), pady=2, sticky="e")

            bar = ctk.CTkProgressBar(self._chart_frame, height=14,
                                      corner_radius=4, progress_color=color)
            bar.set(ratio)
            bar.grid(row=row_idx, column=2, pady=2, sticky="ew")

            ctk.CTkLabel(self._chart_frame,
                         text=f"{var_icon}  {pts_moy:.1f} / {N_SUBSTATS} pts  (±{pts_var:.1f})",
                         font=FONT_SMALL, text_color=C["muted"],
                         anchor="w", width=200).grid(
                row=row_idx, column=3, padx=(10, 0), pady=2, sticky="w")

        ctk.CTkLabel(self._chart_frame,
                     text=f"Génération {gen}  —  🔒 essentielle  🎲 situationnelle  〰 neutre",
                     font=("Segoe UI", 9), text_color=C["muted"]).grid(
            row=len(analyse), column=0, columnspan=4,
            padx=0, pady=(10, 0), sticky="w")

    # ════════════════════════════════════════════════════════
    #  MEILLEUR BUILD
    # ════════════════════════════════════════════════════════

    def _update_best_build(self, meilleur, winrate):
        for w in self._best_frame.winfo_children():
            w.destroy()
        self._best_frame.grid_columnconfigure((1, 2, 3), weight=1)

        profil = self.controller.get_profil()

        # Win rate
        ctk.CTkLabel(self._best_frame,
                     text=f"Win rate estimé : {winrate:.1f}%",
                     font=FONT_SUB, text_color=C["win"]).grid(
            row=0, column=0, columnspan=4, padx=8, pady=(0, 8), sticky="w")

        # En-têtes colonnes
        for col, txt in enumerate(["Stat", "Actuel", "Optimal", "Diff"]):
            ctk.CTkLabel(self._best_frame, text=txt,
                         font=FONT_SMALL, text_color=C["muted"],
                         anchor="center").grid(
                row=1, column=col, padx=8, pady=(0, 4), sticky="ew")

        stats_ordre = [
            "taux_crit", "degat_crit", "vitesse_attaque", "double_chance",
            "damage_pct", "skill_damage", "ranged_pct", "melee_pct",
            "chance_blocage", "lifesteal", "health_regen",
            "skill_cooldown", "health_pct",
        ]
        labels = {
            "taux_crit":       "Crit Chance",
            "degat_crit":      "Crit Damage",
            "vitesse_attaque": "Attack Speed",
            "double_chance":   "Double Chance",
            "damage_pct":      "Damage %",
            "skill_damage":    "Skill Damage",
            "ranged_pct":      "Ranged Dmg",
            "melee_pct":       "Melee Dmg",
            "chance_blocage":  "Block Chance",
            "lifesteal":       "Lifesteal",
            "health_regen":    "Health Regen",
            "skill_cooldown":  "Skill Cooldown",
            "health_pct":      "Health %",
        }

        # Calculer diffs et trier par diff absolue décroissante
        diffs = []
        for key in stats_ordre:
            val_actuel  = profil.get(key, 0.0)
            val_optimal = meilleur.get(key, 0.0)
            diff        = val_optimal - val_actuel
            diffs.append((abs(diff), diff, key, labels.get(key, key), val_actuel, val_optimal))
        diffs.sort(reverse=True)

        for row_idx, (_, diff, key, label, val_actuel, val_optimal) in enumerate(diffs):
            r = row_idx + 2  # décalage header + winrate

            if abs(diff) < 0.5:
                icone = "—"
                color = C["muted"]
            elif diff > 0:
                icone = "✅ 🔺" if abs(diff) > 5 else "🔺"
                color = C["win"]
            else:
                icone = "🔻"
                color = C["lose"]

            fg = "#232840" if row_idx % 2 == 0 else C["card"]
            row_f = ctk.CTkFrame(self._best_frame, fg_color=fg, corner_radius=4)
            row_f.grid(row=r, column=0, columnspan=4, padx=0, pady=1, sticky="ew")
            row_f.grid_columnconfigure((1, 2, 3), weight=1)

            ctk.CTkLabel(row_f, text=label,
                         font=FONT_SMALL, text_color=C["text"],
                         anchor="w", width=120).grid(
                row=0, column=0, padx=10, pady=4, sticky="w")
            ctk.CTkLabel(row_f, text=f"{val_actuel:.1f}",
                         font=FONT_MONO, text_color=C["muted"],
                         anchor="center").grid(row=0, column=1, padx=4, pady=4)
            ctk.CTkLabel(row_f, text=f"{val_optimal:.1f}",
                         font=FONT_MONO, text_color=C["text"],
                         anchor="center").grid(row=0, column=2, padx=4, pady=4)
            sign = "+" if diff >= 0 else ""
            ctk.CTkLabel(row_f, text=f"{icone}  {sign}{diff:.1f}",
                         font=FONT_SMALL, text_color=color,
                         anchor="center").grid(row=0, column=3, padx=4, pady=4)

    # ════════════════════════════════════════════════════════
    #  LOG
    # ════════════════════════════════════════════════════════

    def _log_clear(self):
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.configure(state="disabled")

    def _log_append(self, msg):
        self._log_box.configure(state="normal")
        self._log_box.insert("end", msg)
        self._log_box.see("end")
        self._log_box.configure(state="disabled")