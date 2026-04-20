"""
============================================================
  FORGE MASTER UI — Skills
  Grille visuelle de tous les skills, sélection max 3.
============================================================
"""

import customtkinter as ctk
from PIL import Image
import os

# Chemin vers les icônes skills (relatif au dossier racine du projet)
_ICONS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "skill_icons")

def _load_icon(code: str, size: int = 48) -> ctk.CTkImage | None:
    """Charge l'icône d'un skill depuis le dossier skill_icons/."""
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
    "text":     "#E8E6DF",
    "muted":    "#7A7F96",
    "selected": "#1a2e1a",
    "win":      "#2ECC71",
    "lose":     "#E74C3C",
}

FONT_TITLE = ("Segoe UI", 20, "bold")
FONT_SUB   = ("Segoe UI", 12, "bold")
FONT_BODY  = ("Segoe UI", 13)
FONT_SMALL = ("Segoe UI", 10)
FONT_MONO  = ("Consolas", 11)

RARITY_ORDER = ["common", "rare", "epic", "legendary", "ultimate", "mythic"]


class SkillsView(ctk.CTkFrame):

    def __init__(self, parent, controller, app):
        super().__init__(parent, fg_color=C["bg"], corner_radius=0)
        self.controller    = controller
        self.app           = app
        self._selected     = {}   # code -> BooleanVar
        self._skill_frames = {}   # code -> CTkFrame (pour highlight)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build()

    def _build(self):
        # En-tête
        header = ctk.CTkFrame(self, fg_color=C["surface"], corner_radius=0, height=64)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(header, text="Skills",
                     font=FONT_TITLE, text_color=C["text"]).pack(
            side="left", padx=24, pady=16)

        self._lbl_count = ctk.CTkLabel(
            header, text="0 / 3 sélectionnés",
            font=FONT_BODY, text_color=C["muted"])
        self._lbl_count.pack(side="left", padx=16)

        ctk.CTkButton(
            header, text="💾  Sauvegarder la sélection",
            font=FONT_BODY, height=36, corner_radius=8,
            fg_color=C["accent"], hover_color="#c94828",
            command=self._sauvegarder,
        ).pack(side="right", padx=24, pady=14)

        self._lbl_status = ctk.CTkLabel(
            header, text="", font=FONT_SMALL, text_color=C["lose"])
        self._lbl_status.pack(side="right", padx=8)

        # Corps scrollable
        scroll = ctk.CTkScrollableFrame(self, fg_color=C["bg"], corner_radius=0)
        scroll.grid(row=1, column=0, sticky="nsew")

        tous    = self.controller.get_tous_skills()
        actifs  = [c for c, _ in self.controller.get_skills_actifs()]

        # Grouper par rareté
        par_rarete = {}
        for code, data in tous.items():
            r = str(data.get("rarity", "common")).lower()
            par_rarete.setdefault(r, []).append((code, data))

        row_idx = 0
        for rarity in RARITY_ORDER:
            items = par_rarete.get(rarity, [])
            if not items:
                continue

            color = self.controller.rarity_color(rarity)

            # Séparateur de rareté
            sep = ctk.CTkFrame(scroll, fg_color=C["surface"], corner_radius=8, height=36)
            sep.pack(fill="x", padx=16, pady=(16 if row_idx > 0 else 8, 4))
            ctk.CTkLabel(sep, text=f"  {rarity.upper()}",
                         font=("Segoe UI", 11, "bold"),
                         text_color=color).pack(side="left", padx=12, pady=6)
            ctk.CTkLabel(sep, text=f"{len(items)} skills",
                         font=FONT_SMALL, text_color=C["muted"]).pack(
                side="left", padx=4, pady=6)

            # Grille de skills
            grid_f = ctk.CTkFrame(scroll, fg_color="transparent")
            grid_f.pack(fill="x", padx=16, pady=0)

            cols = 3
            for i, (code, data) in enumerate(sorted(items, key=lambda x: x[0])):
                var = ctk.BooleanVar(value=(code in actifs))
                self._selected[code] = var

                card = self._make_skill_card(grid_f, code, data, var, color,
                                              row=i // cols, col=i % cols)
                self._skill_frames[code] = card
                self._update_card_style(code)

            row_idx += 1

        # Légende bas de page
        ctk.CTkLabel(scroll,
                     text="Cliquez sur un skill pour le sélectionner. Maximum 3 skills actifs.",
                     font=FONT_SMALL, text_color=C["muted"]).pack(pady=16)

    def _make_skill_card(self, parent, code, data, var, color, row, col):
        frame = ctk.CTkFrame(
            parent,
            fg_color=C["card"],
            corner_radius=10,
            border_width=1,
            border_color=C["border"],
        )
        frame.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
        parent.grid_columnconfigure(col, weight=1)

        # Clic sur toute la carte
        frame.bind("<Button-1>", lambda e, c=code: self._toggle(c))

        # Icône + badge rareté
        top_f = ctk.CTkFrame(frame, fg_color="transparent")
        top_f.pack(fill="x", padx=10, pady=(10, 0))
        top_f.bind("<Button-1>", lambda e, c=code: self._toggle(c))

        # Icône du skill
        icon_img = _load_icon(code, size=52)
        if icon_img:
            icon_lbl = ctk.CTkLabel(top_f, image=icon_img, text="",
                                     fg_color="transparent")
            icon_lbl.pack(side="left", padx=(0, 8))
            icon_lbl.bind("<Button-1>", lambda e, c=code: self._toggle(c))

        # Colonne droite : badge rareté + type
        right_f = ctk.CTkFrame(top_f, fg_color="transparent")
        right_f.pack(side="left", fill="both", expand=True)
        right_f.bind("<Button-1>", lambda e, c=code: self._toggle(c))

        badge = ctk.CTkLabel(right_f, text=data.get("rarity", "?").upper(),
                             font=("Segoe UI", 9, "bold"),
                             text_color=color,
                             fg_color="#0D0F14",
                             corner_radius=4, width=64, height=18)
        badge.pack(anchor="w")
        badge.bind("<Button-1>", lambda e, c=code: self._toggle(c))

        sk_type = data.get("type", "damage")
        type_icon = "⚡" if sk_type == "damage" else "🛡"
        type_lbl = ctk.CTkLabel(right_f, text=type_icon,
                                 font=("Segoe UI", 14), text_color=color)
        type_lbl.pack(anchor="w")
        type_lbl.bind("<Button-1>", lambda e, c=code: self._toggle(c))

        # Nom
        name_lbl = ctk.CTkLabel(frame,
                                 text=f"[{code.upper()}]  {data.get('name', '?')}",
                                 font=("Segoe UI", 12, "bold"),
                                 text_color=C["text"])
        name_lbl.pack(padx=12, pady=(4, 2))
        name_lbl.bind("<Button-1>", lambda e, c=code: self._toggle(c))

        # Stats
        cooldown = data.get("cooldown", 0)
        hits     = int(data.get("hits", 0))
        damage   = data.get("damage", 0)
        buff_atq = data.get("buff_atq", 0)
        buff_hp  = data.get("buff_hp", 0)
        buff_dur = data.get("buff_duration", 0)

        if sk_type == "damage":
            info = f"DMG: {self.controller.fmt_nombre(damage)} × {hits}  |  CD: {cooldown}s"
        else:
            parts = []
            if buff_atq:  parts.append(f"+ATQ {self.controller.fmt_nombre(buff_atq)}")
            if buff_hp:   parts.append(f"+HP {self.controller.fmt_nombre(buff_hp)}")
            info = f"Buff {buff_dur}s  —  " + ("  ".join(parts) if parts else "—")

        info_lbl = ctk.CTkLabel(frame, text=info,
                                 font=FONT_MONO, text_color=C["muted"],
                                 wraplength=200)
        info_lbl.pack(padx=12, pady=(0, 12))
        info_lbl.bind("<Button-1>", lambda e, c=code: self._toggle(c))

        return frame

    def _toggle(self, code):
        var      = self._selected[code]
        selected = [c for c, v in self._selected.items() if v.get()]

        if not var.get():
            # Tenter de sélectionner
            if len(selected) >= 3:
                self._lbl_status.configure(text="⚠ Maximum 3 skills actifs")
                return
            var.set(True)
        else:
            var.set(False)

        self._lbl_status.configure(text="")
        self._update_card_style(code)
        count = sum(1 for v in self._selected.values() if v.get())
        self._lbl_count.configure(text=f"{count} / 3 sélectionnés")

    def _update_card_style(self, code):
        frame = self._skill_frames.get(code)
        if not frame:
            return
        if self._selected[code].get():
            frame.configure(fg_color="#1a2e1a", border_color=C["win"], border_width=2)
        else:
            frame.configure(fg_color=C["card"], border_color=C["border"], border_width=1)

    def _sauvegarder(self):
        codes    = [c for c, v in self._selected.items() if v.get()]
        skills   = self.controller.get_skills_from_codes(codes)
        profil   = self.controller.get_profil()
        if not profil:
            self._lbl_status.configure(text="⚠ Aucun profil chargé")
            return
        self.controller.set_profil(profil, skills)
        self._lbl_status.configure(text=f"✅ {len(skills)} skill(s) sauvegardé(s)",
                                    text_color=C["win"])
        self.app.refresh_current()
