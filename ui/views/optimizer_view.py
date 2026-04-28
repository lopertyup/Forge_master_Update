"""
============================================================
  FORGE MASTER UI — Stats Optimizer v7

  Bidirectional marginal analysis:
    for each stat, simulate "add Δ pts" and "remove Δ pts"
    against the current profile, and classify:
      🔺 INCREASE  – underinvested stat, should be pushed
      🟢 KEEP      – useful stat, level OK
      🔻 DECREASE  – wasted stat, should be reduced
      —  NEUTRAL   – stat with no effect at this level

  Directly answers: "what should I increase and what can I lower?"
============================================================
"""

import threading
import traceback
from typing import Dict, List

import customtkinter as ctk

from backend.calculator.optimizer import (
    SUBSTATS_POOL,
    VERDICT_DECREASE,
    VERDICT_INCREASE,
    VERDICT_KEEP,
    VERDICT_NEUTRAL,
    analyze_profile,
)
from ui.theme import (
    C,
    FONT_BODY,
    FONT_MONO,
    FONT_MONO_S,
    FONT_SMALL,
    FONT_SUB,
    FONT_TINY,
    FONT_TITLE,
)
from ui.widgets import build_header


# Default display order (before sorting by impact)
_DEFAULT_STATS = list(SUBSTATS_POOL.keys())


# ── Verdict styles ────────────────────────────────────────

_VERDICT_STYLE = {
    VERDICT_INCREASE: {"icon": "🔺", "label": "INCREASE",
                       "color": "win",     "order": 0},
    VERDICT_KEEP:     {"icon": "🟢", "label": "KEEP",
                       "color": "accent2", "order": 1},
    VERDICT_DECREASE: {"icon": "🔻", "label": "DECREASE",
                       "color": "lose",    "order": 2},
    VERDICT_NEUTRAL:  {"icon": "—",  "label": "NEUTRAL",
                       "color": "muted",   "order": 3},
}


def _verdict_color(verdict: str) -> str:
    return C[_VERDICT_STYLE.get(verdict, _VERDICT_STYLE[VERDICT_NEUTRAL])["color"]]


def _verdict_label(verdict: str) -> str:
    return _VERDICT_STYLE.get(verdict, _VERDICT_STYLE[VERDICT_NEUTRAL])["label"]


def _verdict_icon(verdict: str) -> str:
    return _VERDICT_STYLE.get(verdict, _VERDICT_STYLE[VERDICT_NEUTRAL])["icon"]


# ════════════════════════════════════════════════════════════
#  VIEW
# ════════════════════════════════════════════════════════════

class OptimizerView(ctk.CTkFrame):

    def __init__(self, parent, controller, app):
        super().__init__(parent, fg_color=C["bg"], corner_radius=0)
        self.controller = controller
        self.app        = app
        self._stop_flag = threading.Event()
        self._running   = False
        self._rows: Dict[str, Dict] = {}  # key -> widgets to refresh

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build()

    # ── Layout ───────────────────────────────────────────────

    def _build(self) -> None:
        # Custom header (with buttons)
        header = ctk.CTkFrame(self, fg_color=C["surface"], corner_radius=0,
                               height=64)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)

        ctk.CTkLabel(header, text="🧬  Stats Optimizer",
                     font=FONT_TITLE, text_color=C["text"]).pack(
            side="left", padx=24, pady=16)

        self._btn_stop = ctk.CTkButton(
            header, text="⏹  Stop",
            font=FONT_BODY, height=36, corner_radius=8,
            fg_color=C["border"], hover_color=C["border_hl"],
            command=self._stop, state="disabled")
        self._btn_stop.pack(side="right", padx=8, pady=14)

        self._btn_start = ctk.CTkButton(
            header, text="▶  Analyze",
            font=FONT_BODY, height=36, corner_radius=8,
            fg_color=C["accent"], hover_color=C["accent_hv"],
            command=self._start)
        self._btn_start.pack(side="right", padx=8, pady=14)

        scroll = ctk.CTkScrollableFrame(self, fg_color=C["bg"],
                                         corner_radius=0)
        scroll.grid(row=1, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        self._build_intro(scroll)
        self._build_config(scroll)
        self._build_progress(scroll)
        self._build_results(scroll)
        self._build_legend(scroll)

    def _build_intro(self, parent: ctk.CTkFrame) -> None:
        card = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=10)
        card.pack(fill="x", padx=20, pady=(16, 8))

        ctk.CTkLabel(card, text="How it works",
                     font=FONT_SUB, text_color=C["accent"]).pack(
            anchor="w", padx=16, pady=(12, 4))
        ctk.CTkLabel(
            card,
            text=("For each stat, the optimizer tests two things on your current profile:\n"
                  "  • « +Δ pts in this stat → better than myself? »\n"
                  "  • « −Δ pts in this stat → worse than myself? »\n"
                  "Based on both results, it tells you whether to increase, keep, "
                  "or reduce that stat. No stat is favored — all are tested with the same Δ budget."),
            font=FONT_SMALL, text_color=C["muted"],
            justify="left", wraplength=750).pack(
            anchor="w", padx=16, pady=(0, 12))

    def _build_config(self, parent: ctk.CTkFrame) -> None:
        card = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=10)
        card.pack(fill="x", padx=20, pady=8)
        card.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(card, text="Parameters",
                     font=FONT_SUB, text_color=C["accent"]).grid(
            row=0, column=0, columnspan=2, padx=16, pady=(12, 8), sticky="w")

        params = [
            ("Δ points tested (+/-)",  "n_points",  8,  1,  20,  1),
            ("Simulations per test",   "n_sims",  200, 50, 800, 50),
        ]
        self._sliders: Dict[str, ctk.CTkSlider] = {}
        self._sld_lbl: Dict[str, ctk.CTkLabel]  = {}

        for col, (label, key, default, lo, hi, step) in enumerate(params):
            fr = ctk.CTkFrame(card, fg_color="transparent")
            fr.grid(row=1, column=col, padx=16, pady=(0, 10), sticky="ew")

            ctk.CTkLabel(fr, text=label, font=FONT_SMALL,
                         text_color=C["muted"]).pack(anchor="w")
            val_lbl = ctk.CTkLabel(fr, text=str(default),
                                   font=("Segoe UI", 18, "bold"),
                                   text_color=C["text"])
            val_lbl.pack(anchor="w")
            self._sld_lbl[key] = val_lbl

            sl = ctk.CTkSlider(
                fr, from_=lo, to=hi,
                number_of_steps=max(1, (hi - lo) // step),
                command=lambda v, k=key: self._on_slider(k, v),
            )
            sl.set(default)
            sl.pack(fill="x")
            self._sliders[key] = sl

        self._lbl_info = ctk.CTkLabel(
            card, text=self._estimate_info(8, 200),
            font=FONT_SMALL, text_color=C["muted"])
        self._lbl_info.grid(row=2, column=0, columnspan=2, padx=16,
                             pady=(0, 12))

    def _estimate_info(self, n_points: int, n_sims: int) -> str:
        # 2 simulations per stat (+ and -), ~13 stats max
        n_stats = len(_DEFAULT_STATS) - 1  # one stat excluded (melee/ranged)
        total   = 2 * n_stats * n_sims
        return (f"≈ {n_stats} stats × 2 tests × {n_sims} sims "
                f"= {total:,} total simulations")

    def _build_progress(self, parent: ctk.CTkFrame) -> None:
        card = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=10)
        card.pack(fill="x", padx=20, pady=8)
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card, text="Progress",
                     font=FONT_SUB, text_color=C["accent"]).grid(
            row=0, column=0, padx=16, pady=(12, 4), sticky="w")

        self._lbl_status = ctk.CTkLabel(card, text="Waiting…",
                                         font=FONT_BODY, text_color=C["muted"])
        self._lbl_status.grid(row=1, column=0, padx=16, sticky="w")

        self._progressbar = ctk.CTkProgressBar(
            card, height=10, corner_radius=4, progress_color=C["accent"])
        self._progressbar.set(0)
        self._progressbar.grid(row=2, column=0, padx=16, pady=(6, 14),
                                sticky="ew")

    def _build_results(self, parent: ctk.CTkFrame) -> None:
        card = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=10)
        card.pack(fill="x", padx=20, pady=8)
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card, text="🎯  Recommendations by stat",
                     font=FONT_SUB, text_color=C["accent"]).grid(
            row=0, column=0, padx=16, pady=(12, 2), sticky="w")
        ctk.CTkLabel(
            card,
            text="Run the analysis to see recommendations. Sorted by descending action priority.",
            font=FONT_SMALL, text_color=C["muted"]).grid(
            row=1, column=0, padx=16, pady=(0, 10), sticky="w")

        self._results_frame = ctk.CTkFrame(card, fg_color="transparent")
        self._results_frame.grid(row=2, column=0, padx=10, pady=(0, 14),
                                  sticky="ew")
        self._results_frame.grid_columnconfigure(0, weight=1)

        self._lbl_empty = ctk.CTkLabel(
            self._results_frame,
            text="(waiting — click « ▶ Analyze » to start)",
            font=FONT_SMALL, text_color=C["muted"])
        self._lbl_empty.pack(pady=20)

    def _build_legend(self, parent: ctk.CTkFrame) -> None:
        card = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=10)
        card.pack(fill="x", padx=20, pady=(8, 20))

        ctk.CTkLabel(card, text="Legend",
                     font=FONT_SUB, text_color=C["accent"]).pack(
            anchor="w", padx=16, pady=(12, 4))

        legends = [
            (VERDICT_INCREASE,
             "Adding +Δ gives a win rate > 50%: the stat still scales, invest more into it."),
            (VERDICT_KEEP,
             "Adding +Δ no longer helps but removing −Δ hurts: the stat is at an optimal threshold, keep it."),
            (VERDICT_DECREASE,
             "Neither adding nor removing changes anything: you can redirect points elsewhere (e.g. stat capped at 100%)."),
            (VERDICT_NEUTRAL,
             "Uncertain effect (between thresholds). Worth monitoring but no clear action needed."),
        ]
        for v, desc in legends:
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=2)
            ctk.CTkLabel(row,
                         text=f"{_verdict_icon(v)}  {_verdict_label(v)}",
                         font=FONT_TINY, text_color=_verdict_color(v),
                         width=130, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=desc, font=FONT_SMALL,
                         text_color=C["muted"], anchor="w",
                         justify="left", wraplength=620).pack(
                side="left", fill="x", expand=True)
        ctk.CTkFrame(card, fg_color="transparent", height=8).pack()

    # ── Controls ──────────────────────────────────────────────

    def _on_slider(self, key: str, value: float) -> None:
        self._sld_lbl[key].configure(text=str(int(round(value))))
        n_points = int(round(self._sliders["n_points"].get()))
        n_sims   = int(round(self._sliders["n_sims"].get()))
        self._lbl_info.configure(text=self._estimate_info(n_points, n_sims))

    def _get_params(self) -> Dict[str, int]:
        return {
            "n_points": int(round(self._sliders["n_points"].get())),
            "n_sims":   int(round(self._sliders["n_sims"].get())),
        }

    def _start(self) -> None:
        if self._running:
            return
        if not self.controller.has_profile():
            self._lbl_status.configure(
                text="⚠ No player profile. Go to Dashboard first.",
                text_color=C["lose"])
            return
        self._running = True
        self._stop_flag.clear()
        self._btn_start.configure(state="disabled")
        self._btn_stop.configure(state="normal")
        self._lbl_status.configure(text="Initializing…", text_color=C["muted"])
        self._progressbar.set(0)
        self._reset_results()
        params = self._get_params()
        threading.Thread(target=self._run, kwargs=params, daemon=True).start()

    def _stop(self) -> None:
        self._stop_flag.set()
        self._lbl_status.configure(text="Stopping…", text_color=C["draw"])

    # ── Thread worker ─────────────────────────────────────────

    def _run(self, n_points: int, n_sims: int) -> None:
        profile = self.controller.get_profile()
        skills = self.controller.get_active_skills()

        def on_progress(idx, total, label):
            pct = idx / total if total else 0.0
            txt = f"{idx}/{total} — {label}"
            self.after(0, lambda p=pct: self._progressbar.set(p))
            self.after(0, lambda l=txt: self._lbl_status.configure(
                text=l, text_color=C["muted"]))

        def on_stat(result):
            self.after(0, lambda r=result: self._upsert_row(r))

        try:
            results = analyze_profile(
                profile=profile,
                skills=skills,
                n_points=n_points,
                n_sims=n_sims,
                progress_cb=on_progress,
                stat_cb=on_stat,
                stop_flag=self._stop_flag,
            )
            self.after(0, lambda r=results: self._render_final(r))
        except Exception as e:
            tb = traceback.format_exc()
            self.after(0, lambda msg=str(e), t=tb: self._lbl_status.configure(
                text=f"Error: {msg}", text_color=C["lose"]))
            print(tb)

        self.after(0, self._on_done)

    def _on_done(self) -> None:
        self._running = False
        self._btn_start.configure(state="normal")
        self._btn_stop.configure(state="disabled")
        if not self._stop_flag.is_set():
            self._lbl_status.configure(text="✅ Analysis complete!",
                                        text_color=C["win"])
            self._progressbar.set(1.0)
        else:
            self._lbl_status.configure(text="⏹ Stopped", text_color=C["draw"])

    # ── Results rendering ─────────────────────────────────────

    def _reset_results(self) -> None:
        for w in self._results_frame.winfo_children():
            w.destroy()
        self._rows = {}

        # Table headers
        head = ctk.CTkFrame(self._results_frame, fg_color="transparent")
        head.pack(fill="x", pady=(0, 4))
        head.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(head, text="VERDICT", font=FONT_TINY,
                     text_color=C["muted"], width=130, anchor="w").grid(
            row=0, column=0, padx=(8, 4), sticky="w")
        ctk.CTkLabel(head, text="STAT", font=FONT_TINY,
                     text_color=C["muted"], width=130, anchor="w").grid(
            row=0, column=1, padx=4, sticky="w")
        ctk.CTkLabel(head, text="CURRENT  →  ±Δ TESTED", font=FONT_TINY,
                     text_color=C["muted"], anchor="w").grid(
            row=0, column=2, padx=4, sticky="w")
        ctk.CTkLabel(head, text="WR if +Δ", font=FONT_TINY,
                     text_color=C["muted"], width=80, anchor="center").grid(
            row=0, column=3, padx=4, sticky="ew")
        ctk.CTkLabel(head, text="WR if −Δ", font=FONT_TINY,
                     text_color=C["muted"], width=80, anchor="center").grid(
            row=0, column=4, padx=(4, 8), sticky="ew")

    def _upsert_row(self, result: Dict) -> None:
        """Adds or updates the row for this stat."""
        if result["key"] in self._rows:
            self._fill_row(self._rows[result["key"]], result)
            return

        row_idx = len(self._rows)
        bg = C["card_alt"] if row_idx % 2 == 0 else C["card"]
        row_f = ctk.CTkFrame(self._results_frame, fg_color=bg, corner_radius=6)
        row_f.pack(fill="x", pady=1, padx=2)
        row_f.grid_columnconfigure(2, weight=1)

        widgets = {
            "frame":    row_f,
            "verdict":  ctk.CTkLabel(row_f, font=FONT_TINY, anchor="w",
                                      width=130),
            "stat":     ctk.CTkLabel(row_f, font=FONT_BODY, anchor="w",
                                      text_color=C["text"], width=130),
            "value":    ctk.CTkLabel(row_f, font=FONT_MONO_S, anchor="w",
                                      text_color=C["muted"]),
            "wr_plus":  ctk.CTkLabel(row_f, font=FONT_MONO, anchor="center",
                                      width=80),
            "wr_minus": ctk.CTkLabel(row_f, font=FONT_MONO, anchor="center",
                                      width=80),
        }
        widgets["verdict"].grid( row=0, column=0, padx=(8, 4), pady=6, sticky="w")
        widgets["stat"].grid(    row=0, column=1, padx=4, pady=6, sticky="w")
        widgets["value"].grid(   row=0, column=2, padx=4, pady=6, sticky="w")
        widgets["wr_plus"].grid( row=0, column=3, padx=4, pady=6, sticky="ew")
        widgets["wr_minus"].grid(row=0, column=4, padx=(4, 8), pady=6, sticky="ew")

        self._rows[result["key"]] = widgets
        self._fill_row(widgets, result)

    def _fill_row(self, widgets: Dict, result: Dict) -> None:
        verdict = result["verdict"]
        col_v   = _verdict_color(verdict)

        widgets["verdict"].configure(
            text=f"{_verdict_icon(verdict)}  {_verdict_label(verdict)}",
            text_color=col_v)

        widgets["stat"].configure(text=result["label"])

        current_value = result["current"]
        delta         = result["delta"]
        widgets["value"].configure(text=f"{current_value:.1f}   ±{delta:.1f}")

        wr_p = result["wr_plus"] * 100
        wr_m = result["wr_minus"] * 100

        color_p = C["win"]  if wr_p > 53 else C["muted"] if wr_p > 47 else C["lose"]
        color_m = C["lose"] if wr_m < 47 else C["muted"] if wr_m < 53 else C["win"]

        widgets["wr_plus"].configure(text=f"{wr_p:.0f}%",  text_color=color_p)
        widgets["wr_minus"].configure(text=f"{wr_m:.0f}%", text_color=color_m)

    def _render_final(self, results: List[Dict]) -> None:
        """Reorders rows according to the final sort by impact."""
        for key in list(self._rows.keys()):
            self._rows[key]["frame"].pack_forget()

        for i, r in enumerate(results):
            w = self._rows.get(r["key"])
            if w is None:
                continue
            # Apply consistent zebra background after sort
            w["frame"].configure(
                fg_color=C["card_alt"] if i % 2 == 0 else C["card"])
            w["frame"].pack(fill="x", pady=1, padx=2)
            self._fill_row(w, r)