"""
============================================================
  FORGE MASTER UI — app.py
  FIX : set_tk_root pour callbacks thread-safe
        + refresh_current robuste (ne dépend plus de cget couleur)
============================================================
"""

import customtkinter as ctk
from game_controller import GameController

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

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
    "draw":     "#F39C12",
    "rare":     "#2196F3",
    "epic":     "#9C27B0",
    "legendary":"#FF9800",
    "ultimate": "#F44336",
    "mythic":   "#E91E63",
}

FONT_TITLE  = ("Segoe UI", 22, "bold")
FONT_NAV    = ("Segoe UI", 13, "bold")
FONT_BODY   = ("Segoe UI", 13)
FONT_SMALL  = ("Segoe UI", 11)
FONT_MONO   = ("Consolas", 12)


class ForgeMasterApp(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.controller = GameController()
        # Donner la référence root au controller pour les callbacks thread-safe
        self.controller.set_tk_root(self)

        self.title("Forge Master")
        self.geometry("1100x700")
        self.minsize(900, 600)
        self.configure(fg_color=C["bg"])

        self._active_view_id = "dashboard"   # FIX : suivi de la vue active

        self._build_layout()
        self._build_nav()
        self._build_content_area()
        self.show_view("dashboard")

    # ── Layout principal ─────────────────────────────────────

    def _build_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

    def _build_nav(self):
        self.nav_frame = ctk.CTkFrame(
            self, width=200, corner_radius=0,
            fg_color=C["surface"], border_width=0,
        )
        self.nav_frame.grid(row=0, column=0, sticky="nsew")
        self.nav_frame.grid_propagate(False)
        self.nav_frame.grid_rowconfigure(10, weight=1)

        logo = ctk.CTkLabel(
            self.nav_frame,
            text="⚒ FORGE\nMASTER",
            font=("Segoe UI", 18, "bold"),
            text_color=C["accent"],
            justify="center",
        )
        logo.grid(row=0, column=0, padx=20, pady=(28, 20))

        sep = ctk.CTkFrame(self.nav_frame, height=1, fg_color=C["border"])
        sep.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 16))

        self._nav_buttons = {}
        nav_items = [
            ("dashboard",   "  📊  Dashboard"),
            ("simulateur",  "  ⚔   Simulateur"),
            ("equipements", "  🛡   Équipements"),
            ("skills",      "  ✨  Skills"),
            ("pets",        "  🐾  Pets"),
        ]
        for idx, (view_id, label) in enumerate(nav_items):
            btn = ctk.CTkButton(
                self.nav_frame,
                text=label,
                anchor="w",
                font=FONT_NAV,
                height=44,
                corner_radius=10,
                fg_color="transparent",
                hover_color=C["border"],
                text_color=C["muted"],
                command=lambda v=view_id: self.show_view(v),
            )
            btn.grid(row=idx + 2, column=0, padx=10, pady=3, sticky="ew")
            self._nav_buttons[view_id] = btn

        self.nav_frame.grid_columnconfigure(0, weight=1)

        ver = ctk.CTkLabel(
            self.nav_frame, text="v1.0 — GUI Edition",
            font=FONT_SMALL, text_color=C["muted"],
        )
        ver.grid(row=11, column=0, pady=16)

    def _build_content_area(self):
        self.content_frame = ctk.CTkFrame(
            self, corner_radius=0, fg_color=C["bg"],
        )
        self.content_frame.grid(row=0, column=1, sticky="nsew")
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)
        self._current_view = None

    # ── Navigation ───────────────────────────────────────────

    def show_view(self, view_id: str):
        from ui.views.dashboard   import DashboardView
        from ui.views.simulateur  import SimulateurView
        from ui.views.equipements import EquipementsView
        from ui.views.skills_view import SkillsView
        from ui.views.pets_view   import PetsView

        VIEW_MAP = {
            "dashboard":   DashboardView,
            "simulateur":  SimulateurView,
            "equipements": EquipementsView,
            "skills":      SkillsView,
            "pets":        PetsView,
        }

        # FIX : stocker la vue active par son id (pas via cget couleur)
        self._active_view_id = view_id

        for vid, btn in self._nav_buttons.items():
            if vid == view_id:
                btn.configure(fg_color=C["accent"], text_color=C["text"],
                              hover_color=C["accent"])
            else:
                btn.configure(fg_color="transparent", text_color=C["muted"],
                              hover_color=C["border"])

        if self._current_view:
            self._current_view.destroy()

        ViewClass = VIEW_MAP.get(view_id)
        if ViewClass:
            self._current_view = ViewClass(self.content_frame, self.controller, self)
            self._current_view.grid(row=0, column=0, sticky="nsew")

    def refresh_current(self):
        """Recharge les données et rafraîchit la vue active."""
        self.controller.reload()
        # FIX : utilise l'id stocké, plus de comparaison de couleur fragile
        self.show_view(self._active_view_id)


def run():
    app = ForgeMasterApp()
    app.mainloop()
