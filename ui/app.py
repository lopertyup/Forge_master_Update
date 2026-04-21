"""
============================================================
  FORGE MASTER UI — app.py
  Main window + side navigation.
  Theme/colors/fonts centralized in ui.theme.
============================================================
"""

import logging

import customtkinter as ctk

from game_controller import GameController
from ui.theme import C, FONT_H1, FONT_NAV, FONT_SMALL
from ui.views.dashboard    import DashboardView
from ui.views.equipment  import EquipmentView
from ui.views.mount_view   import MountView
from ui.views.optimizer_view import OptimizerView
from ui.views.pets_view    import PetsView
from ui.views.simulator  import SimulatorView
from ui.views.skills_view  import SkillsView

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

log = logging.getLogger(__name__)

_NAV_ITEMS = [
    ("dashboard",   "  📊  Dashboard",   DashboardView),
    ("simulator",   "  ⚔   Simulator",   SimulatorView),
    ("equipment",   "  🛡   Equipment",  EquipmentView),
    ("skills",      "  ✨  Skills",      SkillsView),
    ("pets",        "  🐾  Pets",        PetsView),
    ("optimizer",   "  🧬  Optimizer",   OptimizerView),
    ("mount",       "  🐴  Mount",       MountView),
]


class ForgeMasterApp(ctk.CTk):
    """Forge Master main window."""

    def __init__(self):
        super().__init__()
        self.controller = GameController()
        self.controller.set_tk_root(self)

        self.title("Forge Master")
        self.geometry("1100x700")
        self.minsize(900, 600)
        self.configure(fg_color=C["bg"])

        self._active_view_id: str = "dashboard"
        self._view_map = {vid: cls for vid, _, cls in _NAV_ITEMS}

        self._build_layout()
        self._build_nav()
        self._build_content_area()
        self.show_view("dashboard")

    # ── Layout ───────────────────────────────────────────────

    def _build_layout(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

    def _build_nav(self) -> None:
        self.nav_frame = ctk.CTkFrame(
            self, width=200, corner_radius=0,
            fg_color=C["surface"], border_width=0,
        )
        self.nav_frame.grid(row=0, column=0, sticky="nsew")
        self.nav_frame.grid_propagate(False)
        self.nav_frame.grid_rowconfigure(10, weight=1)
        self.nav_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self.nav_frame, text="⚒ FORGE\nMASTER",
            font=FONT_H1, text_color=C["accent"], justify="center",
        ).grid(row=0, column=0, padx=20, pady=(28, 20))

        ctk.CTkFrame(self.nav_frame, height=1, fg_color=C["border"]).grid(
            row=1, column=0, sticky="ew", padx=16, pady=(0, 16))

        self._nav_buttons = {}
        for idx, (view_id, label, _cls) in enumerate(_NAV_ITEMS):
            btn = ctk.CTkButton(
                self.nav_frame, text=label, anchor="w",
                font=FONT_NAV, height=44, corner_radius=10,
                fg_color="transparent", hover_color=C["border"],
                text_color=C["muted"],
                command=lambda v=view_id: self.show_view(v),
            )
            btn.grid(row=idx + 2, column=0, padx=10, pady=3, sticky="ew")
            self._nav_buttons[view_id] = btn

        ctk.CTkLabel(
            self.nav_frame, text="v1.0 — GUI Edition",
            font=FONT_SMALL, text_color=C["muted"],
        ).grid(row=11, column=0, pady=16)

    def _build_content_area(self) -> None:
        self.content_frame = ctk.CTkFrame(
            self, corner_radius=0, fg_color=C["bg"])
        self.content_frame.grid(row=0, column=1, sticky="nsew")
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)
        self._current_view = None

    # ── Navigation ───────────────────────────────────────────

    def show_view(self, view_id: str) -> None:
        """Show the `view_id` view, destroying the previous one."""
        self._active_view_id = view_id

        for vid, btn in self._nav_buttons.items():
            if vid == view_id:
                btn.configure(fg_color=C["accent"], text_color=C["text"],
                              hover_color=C["accent"])
            else:
                btn.configure(fg_color="transparent",
                              text_color=C["muted"],
                              hover_color=C["border"])

        if self._current_view is not None:
            self._current_view.destroy()
            self._current_view = None

        ViewClass = self._view_map.get(view_id)
        if ViewClass is None:
            log.warning("show_view: unknown view_id %r", view_id)
            return

        self._current_view = ViewClass(self.content_frame, self.controller, self)
        self._current_view.grid(row=0, column=0, sticky="nsew")

    def refresh_current(self) -> None:
        """Reload data and rebuild the active view."""
        self.controller.reload()
        self.show_view(self._active_view_id)


def run() -> None:
    app = ForgeMasterApp()
    app.mainloop()
