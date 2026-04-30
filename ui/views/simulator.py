"""
============================================================
  FORGE MASTER UI — Combat Simulator

  Phase-4 refactor (UI_REFACTOR_PLAN §4 / §11).

  Two-panel layout (no tabs):

      ┌── Header — title + [📷 Scan opponent] [📷 Scan weapon] ─┐
      │                                                        │
      ├── Left: player mini-fiche  ──── Right: opponent mini-fiche ──┤
      │                                                        │
      ├── [▶  Run 1000 fights]   (disabled while incomplete)   │
      │                                                        │
      └── ResultDelta (W/L/D bars + verdict)                   │

  All shared widgets come from ui/cards.py (Phase-2 module).
  No imports from backend/* here — Plan §11 D1 / Plan P1.

  The opponent panel is populated from controller.get_last_enemy_stats() /
  controller.get_last_enemy_profile() — peek, not consume — so a second
  click on Run reuses the same scan (Plan §11 D2).
============================================================
"""

import logging
from typing import Dict, Optional

import customtkinter as ctk

from ui.theme import (
    C,
    FONT_BIG,
    FONT_BODY,
    FONT_MONO,
    FONT_SMALL,
    FONT_SUB,
    FONT_TINY,
    FONT_TITLE,
    MOUNT_ICON,
    PET_ICONS,
    fmt_number,
    load_mount_icon,
    load_pet_icon,
    load_skill_icon_by_name,
    rarity_color,
)
from ui.widgets import (
    attach_scan_button,
    build_header,
)
from ui.cards import ResultDelta

log = logging.getLogger(__name__)

# Default total used for the result panel when a sim hasn't run yet.
# Plan §4 keeps the historical 1000-fight contract.
_N_SIMULATIONS_DEFAULT = 1000

# Substats shown in the mini-fiche (filtered to non-zero entries).
_SUBSTAT_ROWS = (
    ("crit_chance",    "Crit Chance"),
    ("crit_damage",    "Crit Damage"),
    ("block_chance",   "Block Chance"),
    ("lifesteal",      "Lifesteal"),
    ("double_chance",  "Double Chance"),
    ("damage_pct",     "Damage %"),
    ("attack_speed",   "Attack Speed"),
    ("skill_damage",   "Skill Damage"),
)

_PET_SLOTS = ("PET1", "PET2", "PET3")


class SimulatorView(ctk.CTkFrame):

    def __init__(self, parent, controller, app):
        super().__init__(parent, fg_color=C["bg"], corner_radius=0)
        self.controller = controller
        self.app        = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build()

    # ── Build ─────────────────────────────────────────────────

    def _build(self) -> None:
        build_header(self, "⚔  Combat Simulator")

        body = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        body.grid(row=1, column=0, sticky="nsew", padx=16, pady=16)
        body.grid_columnconfigure((0, 1), weight=1)
        body.grid_rowconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=0)
        body.grid_rowconfigure(2, weight=0)
        body.grid_rowconfigure(3, weight=0)

        # Row 0 — left/right mini-fiches.
        self._left_panel = ctk.CTkFrame(body, fg_color=C["card"], corner_radius=12)
        self._left_panel.grid(row=0, column=0, padx=(0, 8), pady=(0, 8),
                                sticky="nsew")
        self._right_panel = ctk.CTkFrame(body, fg_color=C["card"], corner_radius=12)
        self._right_panel.grid(row=0, column=1, padx=(8, 0), pady=(0, 8),
                                 sticky="nsew")

        # Row 1 — header status line shared by Scan / Run actions.
        self._lbl_status = ctk.CTkLabel(
            body, text="", font=FONT_SMALL, text_color=C["muted"],
        )
        self._lbl_status.grid(row=1, column=0, columnspan=2,
                                padx=4, pady=(0, 6), sticky="w")

        # Row 2 — central Run button.
        self._btn_run = ctk.CTkButton(
            body,
            text=f"▶  Run {_N_SIMULATIONS_DEFAULT} fights",
            font=FONT_SUB, height=44, corner_radius=10,
            fg_color=C["accent"], hover_color=C["accent_hv"],
            command=self._on_run,
        )
        self._btn_run.grid(row=2, column=0, columnspan=2,
                            padx=0, pady=(0, 8), sticky="ew")

        # Row 3 — result slot (ResultDelta dropped here once we have data).
        self._result_slot = ctk.CTkFrame(body, fg_color="transparent",
                                           corner_radius=0)
        self._result_slot.grid(row=3, column=0, columnspan=2,
                                padx=0, pady=(0, 0), sticky="nsew")
        self._result_slot.grid_columnconfigure(0, weight=1)

        self._refresh_panels()

    def _refresh_panels(self) -> None:
        """Wipe + redraw both mini-fiches based on the current controller
        state. Cheap — called on every Scan callback and Run completion."""
        for panel in (self._left_panel, self._right_panel):
            for child in panel.winfo_children():
                child.destroy()

        self._build_player_panel(self._left_panel)
        self._build_opponent_panel(self._right_panel)
        self._refresh_run_button()

    def _refresh_run_button(self) -> None:
        """Plan §4 step 3: disable Run while either side is missing."""
        ready = (
            self.controller.has_profile()
            and self.controller.get_last_enemy_stats() is not None
        )
        self._btn_run.configure(state="normal" if ready else "disabled")

    # ── Player mini-fiche (left panel) ───────────────────────

    def _build_player_panel(self, parent: ctk.CTkFrame) -> None:
        ctk.CTkLabel(parent, text="⚔  Your character",
                     font=FONT_SUB, text_color=C["text"]).pack(
            padx=16, pady=(14, 6), anchor="w")

        profile = self.controller.get_profile()
        if not profile:
            ctk.CTkLabel(
                parent,
                text="No profile loaded.\nGo to the Dashboard to import\nyour stats first.",
                font=FONT_BODY, text_color=C["muted"], justify="center",
            ).pack(padx=16, pady=24)
            # Quick nav.
            ctk.CTkButton(
                parent, text="Open Dashboard →",
                font=FONT_SMALL, height=32, corner_radius=8,
                fg_color="transparent",
                border_color=C["card_alt"], border_width=1,
                hover_color=C["border"], text_color=C["text"],
                command=lambda: self.app.show_view("dashboard"),
            ).pack(padx=24, pady=(0, 16))
            return

        # ── Hero stats: HP / ATK ─────────────────────────────
        hero = ctk.CTkFrame(parent, fg_color=C["card_alt"], corner_radius=10)
        hero.pack(fill="x", padx=12, pady=(0, 6))
        for label, key, color in (
            ("❤  Total HP", "hp_total",     C["lose"]),
            ("⚔  Total ATK", "attack_total", C["accent2"]),
        ):
            row = ctk.CTkFrame(hero, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=4)
            ctk.CTkLabel(row, text=label, font=FONT_SMALL,
                         text_color=C["muted"], width=100, anchor="w").pack(
                side="left")
            ctk.CTkLabel(row, text=fmt_number(profile.get(key, 0)),
                         font=FONT_SUB, text_color=color, anchor="e").pack(
                side="right")

        atk_type = profile.get("attack_type", "?")
        ctk.CTkLabel(
            hero,
            text=f"Type: {'🏹 Ranged' if atk_type == 'ranged' else '⚔ Melee'}",
            font=FONT_SMALL, text_color=C["muted"],
        ).pack(padx=12, pady=(0, 8), anchor="w")

        # ── Substats summary ─────────────────────────────────
        self._build_substats_block(parent, profile)

        # ── Skills row ───────────────────────────────────────
        skills = self.controller.get_active_skills()
        if skills:
            sk_outer = ctk.CTkFrame(parent, fg_color=C["card_alt"], corner_radius=10)
            sk_outer.pack(fill="x", padx=12, pady=(0, 6))
            ctk.CTkLabel(sk_outer, text="Skills",
                         font=FONT_SMALL, text_color=C["muted"]).pack(
                padx=12, pady=(8, 4), anchor="w")
            for code, data in skills:
                rar  = str(data.get("rarity", "common")).lower()
                col  = rarity_color(rar)
                name = data.get("name", code)
                ctk.CTkLabel(
                    sk_outer, text=f"  [{code.upper()}] {name}",
                    font=FONT_SMALL, text_color=col,
                ).pack(padx=12, anchor="w")
            ctk.CTkFrame(sk_outer, fg_color="transparent", height=8).pack()

        # ── Companions row (3 pets + 1 mount, mini-icons) ────
        comp_outer = ctk.CTkFrame(parent, fg_color=C["card_alt"], corner_radius=10)
        comp_outer.pack(fill="x", padx=12, pady=(0, 6))
        ctk.CTkLabel(comp_outer, text="Companions",
                     font=FONT_SMALL, text_color=C["muted"]).pack(
            padx=12, pady=(8, 4), anchor="w")

        comp_row = ctk.CTkFrame(comp_outer, fg_color="transparent")
        comp_row.pack(padx=12, pady=(0, 8), anchor="w", fill="x")
        pets = self.controller.get_pets() or {}
        for slot in _PET_SLOTS:
            pet  = pets.get(slot, {}) or {}
            name = pet.get("__name__")
            icon = load_pet_icon(name, size=28) if name else None
            self._mini_icon(comp_row, icon, PET_ICONS.get(slot, "🐾"),
                            tooltip=name or "(empty)").pack(
                side="left", padx=2)
        mount = self.controller.get_mount() or {}
        m_name = mount.get("__name__")
        m_icon = load_mount_icon(m_name, size=28) if m_name else None
        self._mini_icon(comp_row, m_icon, MOUNT_ICON,
                        tooltip=m_name or "(no mount)").pack(
            side="left", padx=(10, 2))

        # Phase 5 — the legacy "Scan weapon" row was removed: the player's
        # weapon timing now lives on self._equipment["EQUIP_WEAPON"], populated
        # by the Build view's per-slot 📷 (or the full Build scan). The
        # simulator reads windup / recovery / range from the persisted build
        # at fight time — no per-fight consume.

    # ── Opponent mini-fiche (right panel) ────────────────────

    def _build_opponent_panel(self, parent: ctk.CTkFrame) -> None:
        ctk.CTkLabel(parent, text="🎯  Opponent",
                     font=FONT_SUB, text_color=C["text"]).pack(
            padx=16, pady=(14, 6), anchor="w")

        rec  = self.controller.get_last_enemy_stats()
        prof = self.controller.get_last_enemy_profile()

        if rec is None:
            # CTA path — Plan §4 step 1 right column.
            ctk.CTkLabel(
                parent,
                text="No opponent scanned yet.\nUse 📷 Scan opponent below.",
                font=FONT_BODY, text_color=C["muted"], justify="center",
            ).pack(padx=16, pady=20)
            self._build_opponent_scan_row(parent)
            return

        # ── Hero stats from EnemyComputedStats ───────────────
        hero = ctk.CTkFrame(parent, fg_color=C["card_alt"], corner_radius=10)
        hero.pack(fill="x", padx=12, pady=(0, 6))
        for label, value, color in (
            ("❤  Total HP", float(rec.total_health),  C["lose"]),
            ("⚔  Total ATK", float(rec.total_damage), C["accent2"]),
        ):
            row = ctk.CTkFrame(hero, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=4)
            ctk.CTkLabel(row, text=label, font=FONT_SMALL,
                         text_color=C["muted"], width=100, anchor="w").pack(
                side="left")
            ctk.CTkLabel(row, text=fmt_number(value),
                         font=FONT_SUB, text_color=color, anchor="e").pack(
                side="right")

        atk_type = "ranged" if rec.is_ranged_weapon else "melee"
        ctk.CTkLabel(
            hero,
            text=f"Type: {'🏹 Ranged' if atk_type == 'ranged' else '⚔ Melee'}",
            font=FONT_SMALL, text_color=C["muted"],
        ).pack(padx=12, pady=(0, 8), anchor="w")

        # ── Substats from EnemyComputedStats (decimals → %) ──
        opp_substats = {
            "crit_chance":    float(rec.critical_chance) * 100.0,
            "crit_damage":    (float(rec.critical_damage) - 1.0) * 100.0,
            "block_chance":   float(rec.block_chance) * 100.0,
            "lifesteal":      float(rec.life_steal) * 100.0,
            "double_chance":  float(rec.double_damage_chance) * 100.0,
            "attack_speed":   (float(rec.attack_speed_multiplier) - 1.0) * 100.0,
            "skill_damage":   (float(rec.skill_damage_multiplier) - 1.0) * 100.0,
        }
        self._build_substats_block(parent, opp_substats)

        # ── Identified gear summary ───────────────────────────
        if prof is not None:
            self._build_opp_gear_block(parent, prof)

        # ── Re-scan row (replaces textbox + skill picker) ────
        self._build_opponent_scan_row(parent)

    def _build_opponent_scan_row(self, parent: ctk.CTkFrame) -> None:
        bar = ctk.CTkFrame(parent, fg_color="transparent")
        bar.pack(padx=12, pady=(0, 12), fill="x")
        self._lbl_scan_opp = ctk.CTkLabel(
            bar, text="", font=FONT_SMALL, text_color=C["muted"])
        self._lbl_scan_opp.pack(side="right", padx=(8, 0))
        attach_scan_button(
            parent_btn_frame=bar,
            textbox=None,                         # the controller persists
                                                  # the recompute internally
            status_lbl=self._lbl_scan_opp,
            scan_key="opponent",
            scan_fn=self.controller.scan,
            captures_fn=self.controller.get_zone_captures,
            on_scan_ready=self._on_opponent_scanned,
            label="📷  Scan opponent",
        )

    def _on_opponent_scanned(self) -> None:
        """The OCR pipeline has stashed a fresh _last_enemy_stats. Refresh
        the right panel so the user can see the new opponent before
        clicking Run."""
        self._refresh_panels()
        self._lbl_status.configure(
            text="✓ Opponent ready — click « Run » to simulate.",
            text_color=C["win"])

    # ── Shared sub-widgets ────────────────────────────────────

    def _build_substats_block(self, parent: ctk.CTkFrame,
                                stats: Dict) -> None:
        """Mini list of non-zero substats. Same style on both panels."""
        non_zero = [
            (k, lab, float(stats.get(k, 0.0) or 0.0))
            for k, lab in _SUBSTAT_ROWS
            if float(stats.get(k, 0.0) or 0.0)
        ]
        if not non_zero:
            return

        outer = ctk.CTkFrame(parent, fg_color=C["card_alt"], corner_radius=10)
        outer.pack(fill="x", padx=12, pady=(0, 6))
        ctk.CTkLabel(outer, text="Substats",
                     font=FONT_SMALL, text_color=C["muted"]).pack(
            padx=12, pady=(8, 4), anchor="w")
        for i, (_k, label, val) in enumerate(non_zero):
            bg  = C["card"] if i % 2 == 0 else C["card_alt"]
            row = ctk.CTkFrame(outer, fg_color=bg, corner_radius=4)
            row.pack(fill="x", padx=8, pady=1)
            row.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(row, text=label, font=FONT_SMALL,
                         text_color=C["muted"], anchor="w").grid(
                row=0, column=0, padx=10, pady=3, sticky="w")
            ctk.CTkLabel(row, text=f"{val:+.1f}%", font=FONT_MONO,
                         text_color=C["text"], anchor="e").grid(
                row=0, column=1, padx=10, pady=3, sticky="e")
        ctk.CTkFrame(outer, fg_color="transparent", height=4).pack()

    def _build_opp_gear_block(self, parent: ctk.CTkFrame, prof) -> None:
        """Show a compact gear summary from EnemyIdentifiedProfile."""
        n_items  = len(getattr(prof, "items", []) or [])
        n_pets   = len(getattr(prof, "pets",  []) or [])
        n_mount  = 1 if getattr(prof, "mount", None) is not None else 0
        n_skills = len(getattr(prof, "skills", []) or [])
        flv      = int(getattr(prof, "forge_level", 0) or 0)

        outer = ctk.CTkFrame(parent, fg_color=C["card_alt"], corner_radius=10)
        outer.pack(fill="x", padx=12, pady=(0, 6))
        ctk.CTkLabel(outer, text="Identified gear",
                     font=FONT_SMALL, text_color=C["muted"]).pack(
            padx=12, pady=(8, 4), anchor="w")

        bits = []
        if flv:      bits.append(f"Forge Lv.{flv}")
        bits.append(f"🛡 {n_items}/8 items")
        bits.append(f"🐾 {n_pets} pets")
        if n_mount:  bits.append(f"{MOUNT_ICON} mount")
        if n_skills: bits.append(f"✨ {n_skills} skills")
        ctk.CTkLabel(outer, text="   ".join(bits),
                     font=FONT_SMALL, text_color=C["text"]).pack(
            padx=12, pady=(0, 8), anchor="w")

    def _mini_icon(self, parent: ctk.CTkBaseClass, icon, fallback_emoji: str,
                    tooltip: str = "") -> ctk.CTkLabel:
        """Small (28 px) icon block with emoji fallback."""
        if icon is not None:
            lbl = ctk.CTkLabel(parent, image=icon, text="",
                                fg_color="transparent")
        else:
            lbl = ctk.CTkLabel(parent, text=fallback_emoji,
                                font=("Segoe UI", 18))
        # Lightweight hover hint using the existing label text.
        if tooltip:
            def _enter(_e, n=tooltip, w=lbl, ic=icon, fb=fallback_emoji):
                w.configure(image=None, text=n[:14])
            def _leave(_e, w=lbl, ic=icon, fb=fallback_emoji):
                w.configure(image=ic if ic else None,
                            text="" if ic else fb)
            lbl.bind("<Enter>", _enter)
            lbl.bind("<Leave>", _leave)
        return lbl

    # ── Run flow ─────────────────────────────────────────────

    def _on_run(self) -> None:
        if not self.controller.has_profile():
            self._lbl_status.configure(
                text="⚠ No player profile. Go to Dashboard first.",
                text_color=C["lose"])
            return
        if self.controller.get_last_enemy_stats() is None:
            self._lbl_status.configure(
                text="⚠ No opponent scanned yet.",
                text_color=C["lose"])
            return

        self._lbl_status.configure(
            text=f"⏳  Simulating {_N_SIMULATIONS_DEFAULT} fights…",
            text_color=C["muted"])
        self._btn_run.configure(state="disabled",
                                 text="⏳  Simulating…")
        self._clear_result_slot()
        self.update_idletasks()

        # Plan §11 D2: the controller peeks (does NOT consume) the cached
        # enemy, so a second click on Run reuses the same scan.
        self.controller.simulate_vs_last_enemy(self._display_results)

    def _display_results(self, wins: int, loses: int, draws: int) -> None:
        self._refresh_run_button()
        self._btn_run.configure(text=f"▶  Run {_N_SIMULATIONS_DEFAULT} fights")
        self._lbl_status.configure(
            text=f"✅  Done — {wins}W / {loses}L / {draws}D",
            text_color=C["muted"])
        self._render_result(wins, loses, draws)

    def _render_result(self, wins: int, loses: int, draws: int) -> None:
        self._clear_result_slot()
        ResultDelta(
            self._result_slot,
            wins, loses, draws,
            total=wins + loses + draws or _N_SIMULATIONS_DEFAULT,
            title=f"Result — {_N_SIMULATIONS_DEFAULT} fights",
            subtitle=None,
            on_apply=None,
            on_discard=None,
        ).pack(fill="x")

    def _clear_result_slot(self) -> None:
        for w in self._result_slot.winfo_children():
            w.destroy()
      # enemy, so a second click on Run reuses the same scan.
        self.controller.simulate_vs_last_enemy(self._display_results)

    def _display_results(self, wins: int, loses: int, draws: int) -> None:
        self._refresh_run_button()
        self._btn_run.configure(text=f"▶  Run {_N_SIMULATIONS_DEFAULT} fights")
        self._lbl_status.configure(
            text=f"✅  Done — {wins}W / {loses}L / {draws}D",
            text_color=C["muted"])
        self._render_result(wins, loses, draws)

    def _render_result(self, wins: int, loses: int, draws: int) -> None:
        self._clear_result_slot()
        ResultDelta(
            self._result_slot,
            wins, loses, draws,
            total=wins + loses + draws or _N_SIMULATIONS_DEFAULT,
            title=f"Result — {_N_SIMULATIONS_DEFAULT} fights",
            subtitle=None,
            on_apply=None,
            on_discard=None,
        ).pack(fill="x")

    def _clear_result_slot(self) -> None:
        for w in self._result_slot.winfo_children():
            w.destroy()
