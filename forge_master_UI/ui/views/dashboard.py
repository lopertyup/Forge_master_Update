"""
============================================================
  FORGE MASTER UI — Dashboard
  Affiche toutes les stats du joueur + skills actifs.
============================================================
"""

import customtkinter as ctk
from PIL import Image
import os

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
    "bg":       "#0D0F14",
    "surface":  "#151820",
    "card":     "#1C2030",
    "border":   "#2A2F45",
    "accent":   "#E8593C",
    "accent2":  "#F2A623",
    "text":     "#E8E6DF",
    "muted":    "#7A7F96",
    "win":      "#2ECC71",
    "lose":     "#E74C3C",
}

FONT_TITLE  = ("Segoe UI", 20, "bold")
FONT_SUB    = ("Segoe UI", 13, "bold")
FONT_BODY   = ("Segoe UI", 13)
FONT_SMALL  = ("Segoe UI", 11)
FONT_BIG    = ("Segoe UI", 26, "bold")
FONT_MONO   = ("Consolas", 13)


class DashboardView(ctk.CTkFrame):

    def __init__(self, parent, controller, app):
        super().__init__(parent, fg_color="#0D0F14", corner_radius=0)
        self.controller = controller
        self.app        = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build()

    def _build(self):
        # ── En-tête ──────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color="#151820", corner_radius=0, height=64)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            header, text="Dashboard",
            font=FONT_TITLE, text_color="#E8E6DF",
        ).grid(row=0, column=0, padx=24, pady=16, sticky="w")

        btn_update = ctk.CTkButton(
            header, text="⟳  Mettre à jour le profil",
            font=FONT_BODY, height=36, corner_radius=8,
            fg_color="#E8593C", hover_color="#c94828",
            command=self._open_import,
        )
        btn_update.grid(row=0, column=2, padx=24, pady=14, sticky="e")

        # ── Corps scrollable ──────────────────────────────────
        scroll = ctk.CTkScrollableFrame(self, fg_color="#0D0F14", corner_radius=0)
        scroll.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        scroll.grid_columnconfigure((0, 1), weight=1)

        profil = self.controller.get_profil()

        if not profil:
            self._empty_state(scroll)
            return

        # ── Cartes HP & ATQ ──────────────────────────────────
        self._stat_hero_card(scroll, "❤  HP Total",
                             self.controller.fmt_nombre(profil.get("hp_total", 0)),
                             "HP Base : " + self.controller.fmt_nombre(profil.get("hp_base", 0)),
                             "#E74C3C", row=0, col=0)

        self._stat_hero_card(scroll, "⚔  ATQ Total",
                             self.controller.fmt_nombre(profil.get("attaque_total", 0)),
                             "ATQ Base : " + self.controller.fmt_nombre(profil.get("attaque_base", 0)),
                             "#F2A623", row=0, col=1)

        # ── Type d'attaque ────────────────────────────────────
        type_atq = profil.get("type_attaque", "?")
        type_label = "🏹 Distance" if type_atq == "distance" else "⚔ Corps à Corps"
        type_card = ctk.CTkFrame(scroll, fg_color="#1C2030", corner_radius=12)
        type_card.grid(row=1, column=0, columnspan=2, padx=16, pady=(0, 8), sticky="ew")
        ctk.CTkLabel(type_card, text=f"Type d'attaque : {type_label}",
                     font=FONT_SUB, text_color="#7A7F96").pack(padx=20, pady=10)

        # ── Grille stats secondaires ──────────────────────────
        stats_frame = ctk.CTkFrame(scroll, fg_color="#1C2030", corner_radius=12)
        stats_frame.grid(row=2, column=0, columnspan=2, padx=16, pady=(0, 8), sticky="ew")
        stats_frame.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkLabel(stats_frame, text="Stats détaillées",
                     font=FONT_SUB, text_color="#E8E6DF").grid(
            row=0, column=0, columnspan=3, padx=20, pady=(16, 8), sticky="w")

        stat_rows = [
            ("health_pct",      "Health %",         "%"),
            ("damage_pct",      "Damage %",          "%"),
            ("melee_pct",       "Melee %",           "%"),
            ("ranged_pct",      "Ranged %",          "%"),
            ("taux_crit",       "Crit Chance",       "%"),
            ("degat_crit",      "Crit Damage",       "%"),
            ("health_regen",    "Health Regen",      "%"),
            ("lifesteal",       "Lifesteal",         "%"),
            ("double_chance",   "Double Chance",     "%"),
            ("vitesse_attaque", "Attack Speed",      "%"),
            ("skill_damage",    "Skill Damage",      "%"),
            ("skill_cooldown",  "Skill Cooldown",    "%"),
            ("chance_blocage",  "Block Chance",      "%"),
        ]

        for i, (key, label, unit) in enumerate(stat_rows):
            val = profil.get(key, 0.0)
            row_f = ctk.CTkFrame(
                stats_frame,
                fg_color="#232840" if i % 2 == 0 else "#1C2030",
                corner_radius=6,
            )
            row_f.grid(row=i + 1, column=0, columnspan=3,
                       padx=12, pady=1, sticky="ew")
            row_f.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(row_f, text=label,
                         font=FONT_BODY, text_color="#7A7F96",
                         anchor="w").grid(row=0, column=0, padx=16, pady=6, sticky="w")

            color = "#E8E6DF" if val else "#3A3F55"
            ctk.CTkLabel(row_f,
                         text=f"{val:+.2f}{unit}" if val else "—",
                         font=FONT_MONO, text_color=color,
                         anchor="e").grid(row=0, column=2, padx=16, pady=6, sticky="e")

        # Padding bas
        ctk.CTkFrame(stats_frame, fg_color="transparent", height=8).grid(
            row=len(stat_rows) + 1, column=0)

        # ── Skills actifs ─────────────────────────────────────
        skills = self.controller.get_skills_actifs()
        sk_frame = ctk.CTkFrame(scroll, fg_color="#1C2030", corner_radius=12)
        sk_frame.grid(row=3, column=0, columnspan=2, padx=16, pady=(0, 16), sticky="ew")
        sk_frame.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkLabel(sk_frame, text="Skills actifs",
                     font=FONT_SUB, text_color="#E8E6DF").grid(
            row=0, column=0, columnspan=3, padx=20, pady=(16, 8), sticky="w")

        if not skills:
            ctk.CTkLabel(sk_frame, text="Aucun skill équipé",
                         font=FONT_BODY, text_color="#3A3F55").grid(
                row=1, column=0, columnspan=3, padx=20, pady=16)
        else:
            for idx, (code, data) in enumerate(skills):
                self._skill_card(sk_frame, code, data, row=1, col=idx)

        ctk.CTkFrame(sk_frame, fg_color="transparent", height=8).grid(
            row=2, column=0)

    # ── Widgets helpers ───────────────────────────────────────

    def _stat_hero_card(self, parent, title, value, sub, color, row, col):
        card = ctk.CTkFrame(parent, fg_color="#1C2030", corner_radius=12)
        card.grid(row=row, column=col, padx=(16 if col == 0 else 8, 16 if col == 1 else 8),
                  pady=(16, 8), sticky="ew")

        ctk.CTkLabel(card, text=title, font=FONT_SMALL,
                     text_color="#7A7F96").pack(anchor="w", padx=20, pady=(16, 0))
        ctk.CTkLabel(card, text=value, font=FONT_BIG,
                     text_color=color).pack(anchor="w", padx=20, pady=(2, 0))
        ctk.CTkLabel(card, text=sub, font=FONT_SMALL,
                     text_color="#7A7F96").pack(anchor="w", padx=20, pady=(0, 16))

    def _skill_card(self, parent, code, data, row, col):
        rarity  = str(data.get("rarity", "common")).lower()
        color   = self.controller.rarity_color(rarity)
        sk_type = data.get("type", "damage")

        card = ctk.CTkFrame(parent, fg_color="#232840", corner_radius=10)
        card.grid(row=row, column=col, padx=10, pady=(0, 12), sticky="ew")

        # Badge rareté
        badge = ctk.CTkLabel(card, text=rarity.upper(),
                             font=("Segoe UI", 9, "bold"),
                             text_color=color,
                             fg_color="#0D0F14",
                             corner_radius=4,
                             width=60, height=18)
        badge.pack(anchor="ne", padx=10, pady=(10, 0))

        ctk.CTkLabel(card, text=f"[{code.upper()}]  {data.get('name', '?')}",
                     font=FONT_SUB, text_color="#E8E6DF").pack(padx=14, pady=(0, 2))

        icon = "⚡" if sk_type == "damage" else "🛡"
        ctk.CTkLabel(card,
                     text=f"{icon} {sk_type.title()}  |  CD: {data.get('cooldown', 0):.1f}s  |  x{int(data.get('hits', 1))} hits",
                     font=FONT_SMALL, text_color="#7A7F96").pack(padx=14, pady=(0, 12))

    def _empty_state(self, parent):
        ctk.CTkLabel(
            parent,
            text="Aucun profil trouvé\n\nCliquez sur « Mettre à jour le profil »\npour importer vos stats depuis le jeu.",
            font=FONT_BODY, text_color="#3A3F55",
            justify="center",
        ).pack(expand=True, pady=80)

    def _open_import(self):
        """Ouvre la boîte de dialogue d'import de profil."""
        ImportDialog(self, self.controller, self.app)


# ════════════════════════════════════════════════════════════
#  Dialogue d'import de profil
# ════════════════════════════════════════════════════════════

class ImportDialog(ctk.CTkToplevel):

    def __init__(self, parent, controller, app):
        super().__init__(parent)
        self.controller = controller
        self.app        = app
        self.title("Mettre à jour le profil")
        self.geometry("660x700")
        self.minsize(600, 500)
        self.resizable(True, True)
        self.configure(fg_color="#151820")
        self.grab_set()
        self._build()

    def _build(self):
        # Layout : zone scrollable (row 0, weight=1) + barre boutons fixe (row 1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_columnconfigure(0, weight=1)

        # ── Zone scrollable ───────────────────────────────────
        scroll = ctk.CTkScrollableFrame(self, fg_color="#151820", corner_radius=0)
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(scroll, text="Coller le texte du profil",
                     font=("Segoe UI", 16, "bold"),
                     text_color="#E8E6DF").pack(padx=24, pady=(20, 4), anchor="w")

        ctk.CTkLabel(scroll,
                     text="Copiez le résumé de stats depuis le jeu et collez-le ci-dessous.",
                     font=("Segoe UI", 12), text_color="#7A7F96").pack(
            padx=24, pady=(0, 8), anchor="w")

        self.text_box = ctk.CTkTextbox(
            scroll, height=180, font=("Consolas", 12),
            fg_color="#0D0F14", text_color="#E8E6DF",
            border_color="#2A2F45", border_width=1,
        )
        self.text_box.pack(padx=24, pady=(0, 12), fill="x")

        # Type d'attaque
        type_frame = ctk.CTkFrame(scroll, fg_color="#1C2030", corner_radius=8)
        type_frame.pack(padx=24, pady=(0, 12), fill="x")
        ctk.CTkLabel(type_frame, text="Type d'attaque :",
                     font=FONT_BODY, text_color="#E8E6DF").pack(
            side="left", padx=16, pady=10)
        self.type_var = ctk.StringVar(value="distance")
        ctk.CTkRadioButton(type_frame, text="🏹 Distance",
                           variable=self.type_var, value="distance",
                           text_color="#E8E6DF").pack(side="left", padx=16, pady=10)
        ctk.CTkRadioButton(type_frame, text="⚔ Corps à Corps",
                           variable=self.type_var, value="corps_a_corps",
                           text_color="#E8E6DF").pack(side="left", padx=8, pady=10)

        # Skills — grille 3 colonnes sans scroll imbriqué
        ctk.CTkLabel(scroll, text="Skills actifs — sélectionnez jusqu'à 3",
                     font=FONT_BODY, text_color="#E8E6DF").pack(
            padx=24, pady=(0, 6), anchor="w")

        tous           = self.controller.get_tous_skills()
        self._skill_vars = {}
        current_skills = [c for c, _ in self.controller.get_skills_actifs()]

        sk_frame = ctk.CTkFrame(scroll, fg_color="#0D0F14", corner_radius=8,
                                border_width=1, border_color="#2A2F45")
        sk_frame.pack(padx=24, pady=(0, 8), fill="x")

        self._skill_btns = {}
        cols = 6
        for i, (code, data) in enumerate(sorted(tous.items())):
            color = self.controller.rarity_color(str(data.get("rarity", "common")).lower())
            var   = ctk.BooleanVar(value=(code in current_skills))
            self._skill_vars[code] = var

            icon_img = _load_icon(code, size=44)
            name     = data.get("name", code)

            btn_frame = ctk.CTkFrame(sk_frame, fg_color="transparent", corner_radius=8)
            btn_frame.grid(row=i // cols, column=i % cols, padx=6, pady=6)

            # Bouton icône cliquable
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
            lbl.bind("<Button-1>", lambda e, c=code: self._toggle_skill(c))
            self._skill_btns[code] = (lbl, btn_frame)
            self._update_skill_btn(code)

            # Tooltip nom au survol
            lbl.bind("<Enter>", lambda e, n=name, col=color, l=lbl: l.configure(text=n[:8], text_color=col))
            lbl.bind("<Leave>", lambda e, img=icon_img, l=lbl: l.configure(
                text="" if img else code.upper(), image=img if img else None))

        for c in range(cols):
            sk_frame.grid_columnconfigure(c, weight=1)

        self._skill_limit_label = ctk.CTkLabel(
            scroll, text="", font=FONT_SMALL, text_color="#E74C3C")
        self._skill_limit_label.pack(padx=24, pady=(0, 8))

        # ── Barre boutons fixe en bas ─────────────────────────
        btn_bar = ctk.CTkFrame(self, fg_color="#1C2030", corner_radius=0, height=64)
        btn_bar.grid(row=1, column=0, sticky="ew")
        btn_bar.grid_propagate(False)
        btn_bar.grid_columnconfigure(0, weight=1)

        self._lbl_btn_status = ctk.CTkLabel(
            btn_bar, text="", font=FONT_SMALL, text_color="#E74C3C")
        self._lbl_btn_status.pack(side="left", padx=24)

        ctk.CTkButton(btn_bar, text="Annuler", fg_color="#2A2F45",
                      hover_color="#3A3F55", font=FONT_BODY, width=120,
                      command=self.destroy).pack(
            side="right", padx=(8, 24), pady=14)
        ctk.CTkButton(btn_bar, text="✓  Sauvegarder",
                      fg_color="#E8593C", hover_color="#c94828",
                      font=FONT_BODY, width=160,
                      command=self._save).pack(side="right", pady=14)

    def _toggle_skill(self, code):
        var      = self._skill_vars[code]
        selected = [c for c, v in self._skill_vars.items() if v.get()]
        if not var.get():
            if len(selected) >= 3:
                self._skill_limit_label.configure(text="⚠ Maximum 3 skills actifs")
                return
            var.set(True)
        else:
            var.set(False)
        self._skill_limit_label.configure(text="")
        self._update_skill_btn(code)

    def _update_skill_btn(self, code):
        if code not in self._skill_btns:
            return
        lbl, frame = self._skill_btns[code]
        if self._skill_vars[code].get():
            frame.configure(fg_color="#1a2e1a", corner_radius=8,
                            border_width=2, border_color="#2ECC71")
        else:
            frame.configure(fg_color="transparent", border_width=0)

    def _check_max_skills(self):
        selected = [c for c, v in self._skill_vars.items() if v.get()]
        if len(selected) > 3:
            self._skill_limit_label.configure(text="⚠ Maximum 3 skills actifs")
        else:
            self._skill_limit_label.configure(text="")

    def _save(self):
        texte = self.text_box.get("1.0", "end").strip()
        if not texte:
            self._lbl_btn_status.configure(text="⚠ Collez d'abord le texte du profil")
            return

        selected = [c for c, v in self._skill_vars.items() if v.get()]
        if len(selected) > 3:
            self._lbl_btn_status.configure(text="⚠ Maximum 3 skills actifs")
            return

        type_atq = self.type_var.get()
        profil   = self.controller.importer_texte_profil(texte, type_atq)
        skills   = self.controller.get_skills_from_codes(selected)
        self.controller.set_profil(profil, skills)

        self.destroy()
        self.app.refresh_current()