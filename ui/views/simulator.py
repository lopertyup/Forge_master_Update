"""
============================================================
  FORGE MASTER UI — Combat Simulator
  N_SIMULATIONS fights with graphical display.
  Thread-safe callbacks (via controller.set_tk_root → after()).
============================================================
"""

from typing import Dict

import logging
import customtkinter as ctk

from backend.constants import N_SIMULATIONS
from backend.parser import parse_profile_text
from backend.stats import finalize_bases, combat_stats

from ui.theme import (
    C,
    FONT_BIG,
    FONT_BODY,
    FONT_SMALL,
    FONT_SUB,
    FONT_TITLE,
    fmt_number,
    rarity_color,
)
from ui.widgets import (
    attach_scan_button,
    big_counter,
    build_header,
    skill_icon_grid,
)

log = logging.getLogger(__name__)


class SimulatorView(ctk.CTkFrame):

    def __init__(self, parent, controller, app):
        super().__init__(parent, fg_color=C["bg"], corner_radius=0)
        self.controller = controller
        self.app        = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._opp_profile = None
        self._opp_skills  = []
        self._build()

    def _build(self) -> None:
        build_header(self, "Combat Simulator")

        body = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        body.grid(row=1, column=0, sticky="nsew", padx=16, pady=16)
        body.grid_columnconfigure((0, 1), weight=1)
        body.grid_rowconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=0)

        player_card = ctk.CTkFrame(body, fg_color=C["card"], corner_radius=12)
        player_card.grid(row=0, column=0, padx=(0, 8), pady=(0, 8), sticky="nsew")
        self._build_player_panel(player_card)

        opp_outer = ctk.CTkFrame(body, fg_color=C["card"], corner_radius=12)
        opp_outer.grid(row=0, column=1, padx=(8, 0), pady=(0, 8), sticky="nsew")
        opp_outer.grid_rowconfigure(0, weight=1)
        opp_outer.grid_rowconfigure(1, weight=0)
        opp_outer.grid_columnconfigure(0, weight=1)
        self._build_opponent_panel(opp_outer)

        self.result_frame = ctk.CTkFrame(body, fg_color=C["card"], corner_radius=12)
        self.result_frame.grid(row=1, column=0, columnspan=2,
                               padx=0, pady=(0, 0), sticky="nsew")
        self._build_result_panel(self.result_frame)

    # ── Player panel ──────────────────────────────────────────

    def _build_player_panel(self, parent: ctk.CTkFrame) -> None:
        ctk.CTkLabel(parent, text="⚔  Your character",
                     font=FONT_SUB, text_color=C["text"]).pack(
            padx=16, pady=(14, 6), anchor="w")

        profile = self.controller.get_profile()
        if not profile:
            ctk.CTkLabel(parent,
                         text="No profile loaded.\nGo to the Dashboard\nto import your stats.",
                         font=FONT_BODY, text_color=C["muted"],
                         justify="center").pack(pady=20)
            return

        stats_f = ctk.CTkFrame(parent, fg_color=C["card_alt"], corner_radius=8)
        stats_f.pack(padx=12, pady=(0, 8), fill="x")
        for label, key in (("HP", "hp_total"), ("ATK", "attack_total")):
            row = ctk.CTkFrame(stats_f, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=2)
            ctk.CTkLabel(row, text=label, font=FONT_SMALL,
                         text_color=C["muted"], width=40,
                         anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=fmt_number(profile.get(key, 0)),
                         font=FONT_SUB, text_color=C["text"]).pack(
                side="left", padx=8)

        atk_type = profile.get("attack_type", "?")
        ctk.CTkLabel(stats_f,
                     text=f"Type: {'🏹 Ranged' if atk_type == 'ranged' else '⚔ Melee'}",
                     font=FONT_SMALL, text_color=C["muted"]).pack(
            padx=12, pady=(0, 8), anchor="w")

        skills = self.controller.get_active_skills()
        if skills:
            sk_f = ctk.CTkFrame(parent, fg_color=C["card_alt"], corner_radius=8)
            sk_f.pack(padx=12, pady=(0, 12), fill="x")
            ctk.CTkLabel(sk_f, text="Skills:", font=FONT_SMALL,
                         text_color=C["muted"]).pack(padx=12, pady=(8, 2), anchor="w")
            for code, data in skills:
                color = rarity_color(data.get("rarity", "common"))
                ctk.CTkLabel(sk_f,
                             text=f"  [{code.upper()}] {data.get('name', '?')}",
                             font=FONT_SMALL, text_color=color).pack(
                    padx=12, anchor="w")
            ctk.CTkFrame(sk_f, fg_color="transparent", height=8).pack()

    # ── Opponent panel ────────────────────────────────────────

    def _build_opponent_panel(self, parent: ctk.CTkFrame) -> None:
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent",
                                         corner_radius=0)
        scroll.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        scroll.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(scroll, text="🎯  Opponent",
                     font=FONT_SUB, text_color=C["text"]).pack(
            padx=16, pady=(14, 6), anchor="w")

        ctk.CTkLabel(scroll, text="Opponent stats:",
                     font=FONT_SMALL, text_color=C["muted"]).pack(
            padx=16, anchor="w")

        self.opp_textbox = ctk.CTkTextbox(
            scroll, height=120, font=("Consolas", 11),
            fg_color=C["bg"], text_color=C["text"],
            border_color=C["border"], border_width=1,
        )
        self.opp_textbox.pack(padx=12, pady=(4, 4), fill="x")

        # ── Scan row (OCR capture for opponent) ────────────
        scan_row = ctk.CTkFrame(scroll, fg_color="transparent")
        scan_row.pack(padx=12, pady=(0, 6), fill="x")
        self._lbl_scan_status = ctk.CTkLabel(
            scan_row, text="", font=FONT_SMALL, text_color=C["muted"])
        self._lbl_scan_status.pack(side="right", padx=(8, 0))
        attach_scan_button(
            parent_btn_frame=scan_row,
            textbox=self.opp_textbox,
            status_lbl=self._lbl_scan_status,
            scan_key="opponent",
            scan_fn=self.controller.scan,
            captures_fn=self.controller.get_zone_captures,
            on_scan_ready=self._auto_run_if_ready,
        )

        type_f = ctk.CTkFrame(scroll, fg_color="transparent")
        type_f.pack(padx=12, fill="x")
        ctk.CTkLabel(type_f, text="Type:", font=FONT_SMALL,
                     text_color=C["muted"]).pack(side="left")
        self.opp_type = ctk.StringVar(value="ranged")
        ctk.CTkRadioButton(type_f, text="🏹 Ranged",
                           variable=self.opp_type, value="ranged",
                           text_color=C["text"], font=FONT_SMALL).pack(
            side="left", padx=10)
        ctk.CTkRadioButton(type_f, text="⚔ Melee",
                           variable=self.opp_type, value="melee",
                           text_color=C["text"], font=FONT_SMALL).pack(
            side="left", padx=4)

        ctk.CTkLabel(scroll, text="Opponent skills:",
                     font=FONT_SMALL, text_color=C["muted"]).pack(
            padx=16, pady=(8, 2), anchor="w")

        all_skills = self.controller.get_all_skills()
        self._opp_skill_vars: Dict[str, ctk.BooleanVar] = {
            code: ctk.BooleanVar(value=False) for code in all_skills
        }

        grid, _btns = skill_icon_grid(
            scroll, all_skills, self._opp_skill_vars,
            cols=5, icon_size=38,
            on_toggle=self._toggle_opp_skill,
        )
        grid.pack(padx=12, pady=(0, 4), fill="x")

        self._opp_limit_lbl = ctk.CTkLabel(
            scroll, text="", font=FONT_SMALL, text_color=C["lose"])
        self._opp_limit_lbl.pack(pady=(2, 4))

        ctk.CTkFrame(scroll, fg_color=C["border"], height=1).pack(
            fill="x", padx=12, pady=(0, 4))

        # Fixed button outside the scroll
        btn_frame = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=0)
        btn_frame.grid(row=1, column=0, sticky="ew", padx=0, pady=0)
        btn_frame.grid_columnconfigure(0, weight=1)

        self._lbl_status_opp = ctk.CTkLabel(
            btn_frame, text="", font=FONT_SMALL, text_color=C["lose"])
        self._lbl_status_opp.grid(row=0, column=0, padx=12, pady=(6, 0))

        ctk.CTkButton(
            btn_frame, text=f"▶  Run {N_SIMULATIONS} simulations",
            font=FONT_SUB, height=40, corner_radius=8,
            fg_color=C["accent"], hover_color=C["accent_hv"],
            command=self._run,
        ).grid(row=1, column=0, padx=12, pady=(4, 12), sticky="ew")

    def _toggle_opp_skill(self, code: str) -> None:
        """Toggle an opponent skill with a limit of 3."""
        var      = self._opp_skill_vars[code]
        selected = [c for c, v in self._opp_skill_vars.items() if v.get()]
        if not var.get():
            if len(selected) >= 3:
                self._opp_limit_lbl.configure(text="⚠ Maximum 3 skills")
                return
            var.set(True)
        else:
            var.set(False)
        self._opp_limit_lbl.configure(text="")

    # ── Result panel ──────────────────────────────────────────

    def _build_result_panel(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure((0, 1, 2), weight=1)

        self._lbl_status = ctk.CTkLabel(
            parent,
            text="Fill in the opponent stats and run the simulation.",
            font=FONT_BODY, text_color=C["muted"],
        )
        self._lbl_status.grid(row=0, column=0, columnspan=3, pady=20)

        total_txt = f"/ {N_SIMULATIONS}"
        self._lbl_win  = big_counter(parent, "WIN",  C["win"],  total_text=total_txt)
        self._lbl_lose = big_counter(parent, "LOSE", C["lose"], total_text=total_txt)
        self._lbl_draw = big_counter(parent, "DRAW", C["draw"], total_text=total_txt)
        self._lbl_win._counter_frame.grid(row=1, column=0, padx=12, pady=8, sticky="ew")
        self._lbl_lose._counter_frame.grid(row=1, column=1, padx=12, pady=8, sticky="ew")
        self._lbl_draw._counter_frame.grid(row=1, column=2, padx=12, pady=8, sticky="ew")

        self._progress = ctk.CTkProgressBar(parent, height=12, corner_radius=6,
                                             progress_color=C["win"])
        self._progress.grid(row=2, column=0, columnspan=3,
                            padx=24, pady=(8, 0), sticky="ew")
        self._progress.set(0)

        self._lbl_verdict = ctk.CTkLabel(
            parent, text="", font=FONT_SUB, text_color=C["text"])
        self._lbl_verdict.grid(row=3, column=0, columnspan=3, pady=(8, 16))

    # ── Logic ─────────────────────────────────────────────────

    def _auto_run_if_ready(self) -> None:
        """After an OCR capture fills the opponent textbox, auto-run the
        simulation — but ONLY if at least one opponent skill is selected.
        Otherwise keep the textbox populated and wait for the user to
        pick the skills and click Run."""
        selected = [c for c, v in self._opp_skill_vars.items() if v.get()]
        if selected:
            self._run()
        else:
            self._lbl_scan_status.configure(
                text="✓ OCR complete — select opponent skills, then Run.",
                text_color=C["muted"])

    def _run(self) -> None:
        if not self.controller.has_profile():
            self._lbl_status_opp.configure(
                text="⚠ No player profile. Go to the Dashboard.")
            return

        text = self.opp_textbox.get("1.0", "end").strip()
        if not text:
            self._lbl_status_opp.configure(text="⚠ Paste the opponent stats.")
            return

        opp_selected = [c for c, v in self._opp_skill_vars.items() if v.get()]
        if len(opp_selected) > 3:
            self._lbl_status_opp.configure(text="⚠ Maximum 3 skills for the opponent.")
            return

        self._lbl_status_opp.configure(text="")

        opp_stats = parse_profile_text(text)
        opp_stats["attack_type"] = self.opp_type.get()
        opp_stats  = finalize_bases(opp_stats)
        opp_combat = combat_stats(opp_stats)

        # ── Phase 3 — prefer recomputed stats when available ──
        # The controller stashes EnemyComputedStats whenever the
        # opponent zone was scanned via OCR. Override the OCR
        # text-derived totals with the values rebuilt from the
        # identified gear; the substats (crit, lifesteal, etc.)
        # already came from the same OCR text so we leave them.
        recomputed, _ = self.controller.consume_enemy_recompute()
        if recomputed is not None:
            opp_combat["hp_total"]     = float(recomputed.total_health)
            opp_combat["attack_total"] = float(recomputed.total_damage)
            opp_combat["attack_type"]  = (
                "ranged" if recomputed.is_ranged_weapon else "melee"
            )
            # Discrete attack-speed model: thread the weapon's wind-up
            # and recovery (recovery = AttackDuration − WindupTime)
            # into the simulator so it floors swing/recovery to the
            # nearest 0.1 s instead of using the legacy linear curve.
            wu = float(recomputed.weapon_windup_time)
            ad = float(recomputed.weapon_attack_duration)
            opp_combat["weapon_windup"]   = wu
            opp_combat["weapon_recovery"] = max(ad - wu, 0.0)
            # Projectile travel time: 0 for melee, range/speed for
            # ranged. The simulator queues a deferred impact when
            # this is > 0 so a slow projectile (e.g. Tomahawk ~0.47s)
            # doesn't apply damage instantly like a melee weapon.
            travel = 0.0
            if recomputed.is_ranged_weapon:
                speed = float(recomputed.projectile_speed or 0.0)
                rng = float(recomputed.weapon_attack_range or 0.0)
                if speed > 0.0 and rng > 0.0:
                    travel = rng / speed
            opp_combat["projectile_travel_time"] = travel
            log.info(
                "simulator: using recomputed enemy stats — "
                "HP=%.0f Dmg=%.0f (text-OCR overridden); "
                "weapon W=%.2fs R=%.2fs travel=%.3fs",
                recomputed.total_health, recomputed.total_damage,
                wu, max(ad - wu, 0.0), travel,
            )
        opp_skills = self.controller.get_skills_from_codes(opp_selected)

        self._lbl_status.configure(text="⏳ Simulation running…",
                                    text_color=C["muted"])
        self._lbl_win.configure(text="…")
        self._lbl_lose.configure(text="…")
        self._lbl_draw.configure(text="…")
        self._progress.set(0)
        self._lbl_verdict.configure(text="")
        self.update_idletasks()

        # ── Player weapon scan -- enrich the player profile with the
        # ── windup / recovery / projectile_travel_time derived from
        # ── the user's last "scan player_weapon" capture. We pass the
        # ── enriched profile via profile_override so the controller's
        # ── existing combat_stats() picks the new fields up.
        player_profile = None
        pw_scan = self.controller.consume_player_weapon()
        if pw_scan is not None:
            base = self.controller.get_profile() or {}
            player_profile = dict(base)
            player_profile["weapon_windup"]          = pw_scan.get("weapon_windup")
            player_profile["weapon_recovery"]        = pw_scan.get("weapon_recovery")
            player_profile["projectile_travel_time"] = pw_scan.get(
                "projectile_travel_time", 0.0)
            # Only override attack_type if the profile didn't already
            # have one (preserves the explicit ranged/melee toggle the
            # user may have set on the dashboard).
            if not player_profile.get("attack_type"):
                player_profile["attack_type"] = pw_scan.get("attack_type", "melee")
            log.info(
                "simulator: applying player weapon scan W=%.2fs R=%.2fs "
                "travel=%.3fs (type=%s)",
                pw_scan.get("weapon_windup", 0.0),
                pw_scan.get("weapon_recovery", 0.0),
                pw_scan.get("projectile_travel_time", 0.0),
                pw_scan.get("attack_type", "?"),
            )

        # Controller already dispatches on the Tk thread; no need for after()
        self.controller.simulate(opp_combat, opp_skills, self._display_results,
                                 profile_override=player_profile)

    def _display_results(self, wins: int, loses: int, draws: int) -> None:
        self._lbl_win.configure(text=str(wins))
        self._lbl_lose.configure(text=str(loses))
        self._lbl_draw.configure(text=str(draws))
        win_rate = wins / N_SIMULATIONS if N_SIMULATIONS else 0.0
        self._progress.set(win_rate)
        self._progress.configure(
            progress_color=C["win"] if win_rate >= 0.5 else C["lose"])

        pct = 100.0 / N_SIMULATIONS if N_SIMULATIONS else 0.0
        if wins > loses:
            verdict = f"✅  You win {wins * pct:.1f}% of the time"
            color   = C["win"]
        elif loses > wins:
            verdict = f"❌  You lose {loses * pct:.1f}% of the time"
            color   = C["lose"]
        else:
            verdict = f"🤝  Perfect tie ({draws * pct:.1f}% draws)"
            color   = C["draw"]

        self._lbl_verdict.configure(text=verdict, text_color=color)
        self._lbl_status.configure(text="Simulation complete.",
                                    text_color=C["muted"])
