"""
============================================================
  FORGE MASTER UI — Stats Optimizer

  Phase-4 refactor (UI_REFACTOR_PLAN §8 / §11.4.C).

  Two-column layout:
      Left  — results table (stat → +Δ WR / −Δ WR / verdict).
      Right — configuration (Δ slider, sims slider, Run / Stop,
              Export CSV / Copy-to-clipboard).

  Verdict colors stay as defined in §8 of the plan.
  Backend access goes through controller.run_optimizer
  (Plan §4.C.4) so this view has no backend.* import.
============================================================
"""

import threading
import traceback
from typing import Dict, List

import customtkinter as ctk

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


# Verdict constants — duplicated locally to satisfy "no backend import"
# (Plan D1). Strings must match backend.calculator.optimizer's exports.
_VERDICT_INCREASE = "INCREASE"
_VERDICT_KEEP     = "KEEP"
_VERDICT_DECREASE = "DECREASE"
_VERDICT_NEUTRAL  = "NEUTRAL"

_VERDICT_STYLE = {
    _VERDICT_INCREASE: {"icon": "🔺", "label": "INCREASE",
                        "color": "win",     "order": 0},
    _VERDICT_KEEP:     {"icon": "🟢", "label": "KEEP",
                        "color": "accent2", "order": 1},
    _VERDICT_DECREASE: {"icon": "🔻", "label": "DECREASE",
                        "color": "lose",    "order": 2},
    _VERDICT_NEUTRAL:  {"icon": "—",  "label": "NEUTRAL",
                        "color": "muted",   "order": 3},
}


def _verdict_color(verdict: str) -> str:
    return C[_VERDICT_STYLE.get(verdict, _VERDICT_STYLE[_VERDICT_NEUTRAL])["color"]]


def _verdict_label(verdict: str) -> str:
    return _VERDICT_STYLE.get(verdict, _VERDICT_STYLE[_VERDICT_NEUTRAL])["label"]


def _verdict_icon(verdict: str) -> str:
    return _VERDICT_STYLE.get(verdict, _VERDICT_STYLE[_VERDICT_NEUTRAL])["icon"]


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
        self._rows: Dict[str, Dict] = {}     # key -> widget bundle
        self._results: List[Dict]   = []     # last finalized results

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build()

    # ── Layout ───────────────────────────────────────────────

    def _build(self) -> None:
        # Header bar.
        header = ctk.CTkFrame(self, fg_color=C["surface"], corner_radius=0,
                               height=64)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        ctk.CTkLabel(header, text="🧬  Stats Optimizer",
                     font=FONT_TITLE, text_color=C["text"]).pack(
            side="left", padx=24, pady=16)
        self._lbl_status = ctk.CTkLabel(
            header, text="", font=FONT_SMALL, text_color=C["muted"])
        self._lbl_status.pack(side="right", padx=24)

        # Two-column body. Left = results, right = config.
        body = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        body.grid(row=1, column=0, sticky="nsew", padx=12, pady=(8, 12))
        body.grid_columnconfigure(0, weight=2)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self._build_results_column(body)
        self._build_config_column(body)

    # ── Left column — Results table ───────────────────────────

    def _build_results_column(self, parent: ctk.CTkFrame) -> None:
        outer = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=12)
        outer.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        outer.grid_columnconfigure(0, weight=1)
        outer.grid_rowconfigure(2, weight=1)

        # Title row + export buttons.
        head = ctk.CTkFrame(outer, fg_color="transparent")
        head.grid(row=0, column=0, padx=16, pady=(14, 4), sticky="ew")
        head.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(head, text="🎯  Recommendations by stat",
                     font=FONT_SUB, text_color=C["accent"]).grid(
            row=0, column=0, sticky="w")

        ctk.CTkButton(
            head, text="⤓  CSV",
            font=FONT_TINY, height=24, width=70, corner_radius=6,
            fg_color="transparent",
            border_color=C["card_alt"], border_width=1,
            hover_color=C["border"], text_color=C["muted"],
            command=self._export_csv,
        ).grid(row=0, column=1, padx=(4, 4))
        ctk.CTkButton(
            head, text="📋  Copy",
            font=FONT_TINY, height=24, width=70, corner_radius=6,
            fg_color="transparent",
            border_color=C["card_alt"], border_width=1,
            hover_color=C["border"], text_color=C["muted"],
            command=self._copy_clipboard,
        ).grid(row=0, column=2, padx=(4, 0))

        ctk.CTkLabel(
            outer,
            text="Sorted by descending action priority — INCREASE on top.",
            font=FONT_SMALL, text_color=C["muted"],
        ).grid(row=1, column=0, padx=16, pady=(0, 8), sticky="w")

        # Scrollable results frame.
        self._results_frame = ctk.CTkScrollableFrame(
            outer, fg_color=C["bg"], corner_radius=8,
        )
        self._results_frame.grid(row=2, column=0, padx=10, pady=(0, 10),
                                  sticky="nsew")
        self._results_frame.grid_columnconfigure(0, weight=1)

        self._lbl_empty = ctk.CTkLabel(
            self._results_frame,
            text="(waiting — click « ▶ Analyze » to start)",
            font=FONT_SMALL, text_color=C["muted"])
        self._lbl_empty.pack(pady=20)

        # Legend strip at the bottom.
        legend = ctk.CTkFrame(outer, fg_color="transparent")
        legend.grid(row=3, column=0, padx=16, pady=(0, 12), sticky="ew")
        for i, v in enumerate(
                (_VERDICT_INCREASE, _VERDICT_KEEP,
                 _VERDICT_DECREASE, _VERDICT_NEUTRAL)):
            ctk.CTkLabel(
                legend,
                text=f"{_verdict_icon(v)} {_verdict_label(v)}",
                font=FONT_TINY, text_color=_verdict_color(v),
            ).pack(side="left", padx=(0 if i == 0 else 12, 0))

    # ── Right column — Configuration ──────────────────────────

    def _build_config_column(self, parent: ctk.CTkFrame) -> None:
        outer = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=12)
        outer.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        outer.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(outer, text="Configuration",
                     font=FONT_SUB, text_color=C["accent"]).grid(
            row=0, column=0, padx=16, pady=(14, 8), sticky="w")

        # Compact "how it works" subline.
        ctk.CTkLabel(
            outer,
            text=("For each stat, +Δ and −Δ are tested against your\n"
                  "current profile. The verdict tells you whether to\n"
                  "INCREASE, KEEP, DECREASE or leave NEUTRAL."),
            font=FONT_SMALL, text_color=C["muted"], justify="left",
        ).grid(row=1, column=0, padx=16, pady=(0, 12), sticky="w")

        # ── Slider: Δ points tested ───────────────────────────
        self._sliders: Dict[str, ctk.CTkSlider] = {}
        self._sld_lbl: Dict[str, ctk.CTkLabel]  = {}

        params = (
            ("Δ points tested (+/-)",  "n_points",  8,  1,  20,  1),
            ("Simulations per test",   "n_sims",  200, 50, 800, 50),
        )
        for i, (label, key, default, lo, hi, step) in enumerate(params):
            fr = ctk.CTkFrame(outer, fg_color="transparent")
            fr.grid(row=2 + i, column=0, padx=16, pady=(0, 10), sticky="ew")

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

        # ── Estimate line ─────────────────────────────────────
        self._lbl_info = ctk.CTkLabel(
            outer, text=self._estimate_info(8, 200),
            font=FONT_SMALL, text_color=C["muted"], wraplength=260,
            justify="left",
        )
        self._lbl_info.grid(row=4, column=0, padx=16, pady=(0, 12), sticky="w")

        # ── Progress bar + label ──────────────────────────────
        ctk.CTkLabel(outer, text="Progress",
                     font=FONT_SMALL, text_color=C["muted"]).grid(
            row=5, column=0, padx=16, pady=(0, 2), sticky="w")
        self._progressbar = ctk.CTkProgressBar(
            outer, height=10, corner_radius=4, progress_color=C["accent"])
        self._progressbar.set(0)
        self._progressbar.grid(row=6, column=0, padx=16, pady=(0, 6),
                                sticky="ew")
        self._lbl_progress = ctk.CTkLabel(
            outer, text="Waiting…", font=FONT_SMALL, text_color=C["muted"],
            wraplength=260, justify="left",
        )
        self._lbl_progress.grid(row=7, column=0, padx=16, pady=(0, 12),
                                 sticky="w")

        # ── Run / Stop buttons ────────────────────────────────
        btns = ctk.CTkFrame(outer, fg_color="transparent")
        btns.grid(row=8, column=0, padx=16, pady=(0, 14), sticky="ew")
        btns.grid_columnconfigure((0, 1), weight=1)
        self._btn_start = ctk.CTkButton(
            btns, text="▶  Analyze",
            font=FONT_BODY, height=40, corner_radius=8,
            fg_color=C["accent"], hover_color=C["accent_hv"],
            command=self._start)
        self._btn_start.grid(row=0, column=0, padx=(0, 4), sticky="ew")
        self._btn_stop = ctk.CTkButton(
            btns, text="⏹  Stop",
            font=FONT_BODY, height=40, corner_radius=8,
            fg_color=C["border"], hover_color=C["border_hl"],
            command=self._stop, state="disabled")
        self._btn_stop.grid(row=0, column=1, padx=(4, 0), sticky="ew")

    def _estimate_info(self, n_points: int, n_sims: int) -> str:
        # Roughly 13 stats × 2 tests (+/−) per analysis.
        n_stats = 13
        total   = 2 * n_stats * n_sims
        return (f"≈ {n_stats} stats × 2 tests × {n_sims} sims "
                f"= {total:,} total simulations")

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
                text="⚠ No player profile — go to Dashboard first.",
                text_color=C["lose"])
            return
        self._running = True
        self._stop_flag.clear()
        self._btn_start.configure(state="disabled")
        self._btn_stop.configure(state="normal")
        self._lbl_status.configure(text="", text_color=C["muted"])
        self._lbl_progress.configure(text="Initializing…",
                                       text_color=C["muted"])
        self._progressbar.set(0)
        self._reset_results()
        params = self._get_params()
        threading.Thread(target=self._run, kwargs=params, daemon=True).start()

    def _stop(self) -> None:
        self._stop_flag.set()
        self._lbl_progress.configure(text="Stopping…", text_color=C["draw"])

    # ── Thread worker ─────────────────────────────────────────

    def _run(self, n_points: int, n_sims: int) -> None:
        def on_progress(idx, total, label):
            pct = idx / total if total else 0.0
            txt = f"{idx}/{total} — {label}"
            self.after(0, lambda p=pct: self._progressbar.set(p))
            self.after(0, lambda l=txt: self._lbl_progress.configure(
                text=l, text_color=C["muted"]))

        def on_stat(result):
            self.after(0, lambda r=result: self._upsert_row(r))

        try:
            results = self.controller.run_optimizer(
                n_points=n_points,
                n_sims=n_sims,
                progress_cb=on_progress,
                stat_cb=on_stat,
                stop_flag=self._stop_flag,
            )
            self.after(0, lambda r=results: self._render_final(r))
        except Exception as e:
            tb = traceback.format_exc()
            self.after(0, lambda msg=str(e): self._lbl_progress.configure(
                text=f"Error: {msg}", text_color=C["lose"]))
            print(tb)

        self.after(0, self._on_done)

    def _on_done(self) -> None:
        self._running = False
        self._btn_start.configure(state="normal")
        self._btn_stop.configure(state="disabled")
        if not self._stop_flag.is_set():
            self._lbl_progress.configure(text="✅ Analysis complete",
                                           text_color=C["win"])
            self._progressbar.set(1.0)
        else:
            self._lbl_progress.configure(text="⏹ Stopped",
                                           text_color=C["draw"])

    # ── Results rendering ─────────────────────────────────────

    def _reset_results(self) -> None:
        for w in self._results_frame.winfo_children():
            w.destroy()
        self._rows = {}
        self._results = []

        head = ctk.CTkFrame(self._results_frame, fg_color="transparent")
        head.pack(fill="x", pady=(0, 4))
        head.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(head, text="VERDICT", font=FONT_TINY,
                     text_color=C["muted"], width=110, anchor="w").grid(
            row=0, column=0, padx=(8, 4), sticky="w")
        ctk.CTkLabel(head, text="STAT", font=FONT_TINY,
                     text_color=C["muted"], width=110, anchor="w").grid(
            row=0, column=1, padx=4, sticky="w")
        ctk.CTkLabel(head, text="CURRENT  →  ±Δ", font=FONT_TINY,
                     text_color=C["muted"], anchor="w").grid(
            row=0, column=2, padx=4, sticky="w")
        ctk.CTkLabel(head, text="WR +", font=FONT_TINY,
                     text_color=C["muted"], width=60, anchor="center").grid(
            row=0, column=3, padx=4, sticky="ew")
        ctk.CTkLabel(head, text="WR −", font=FONT_TINY,
                     text_color=C["muted"], width=60, anchor="center").grid(
            row=0, column=4, padx=(4, 8), sticky="ew")

    def _upsert_row(self, result: Dict) -> None:
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
                                      width=110),
            "stat":     ctk.CTkLabel(row_f, font=FONT_BODY, anchor="w",
                                      text_color=C["text"], width=110),
            "value":    ctk.CTkLabel(row_f, font=FONT_MONO_S, anchor="w",
                                      text_color=C["muted"]),
            "wr_plus":  ctk.CTkLabel(row_f, font=FONT_MONO, anchor="center",
                                      width=60),
            "wr_minus": ctk.CTkLabel(row_f, font=FONT_MONO, anchor="center",
                                      width=60),
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
        self._results = list(results)
        for key in list(self._rows.keys()):
            self._rows[key]["frame"].pack_forget()

        for i, r in enumerate(results):
            w = self._rows.get(r["key"])
            if w is None:
                continue
            w["frame"].configure(
                fg_color=C["card_alt"] if i % 2 == 0 else C["card"])
            w["frame"].pack(fill="x", pady=1, padx=2)
            self._fill_row(w, r)

    # ── Export helpers ────────────────────────────────────────

    def _result_rows_as_tsv(self) -> str:
        lines = ["verdict\tstat\tcurrent\tdelta\twr_plus\twr_minus"]
        for r in self._results:
            lines.append(
                f"{r.get('verdict', '')}\t"
                f"{r.get('label', '')}\t"
                f"{r.get('current', 0):.2f}\t"
                f"{r.get('delta', 0):.2f}\t"
                f"{r.get('wr_plus', 0):.4f}\t"
                f"{r.get('wr_minus', 0):.4f}"
            )
        return "\n".join(lines)

    def _result_rows_as_csv(self) -> str:
        lines = ["verdict,stat,current,delta,wr_plus,wr_minus"]
        for r in self._results:
            lines.append(
                f"{r.get('verdict', '')},"
                f"\"{r.get('label', '')}\","
                f"{r.get('current', 0):.2f},"
                f"{r.get('delta', 0):.2f},"
                f"{r.get('wr_plus', 0):.4f},"
                f"{r.get('wr_minus', 0):.4f}"
            )
        return "\n".join(lines)

    def _export_csv(self) -> None:
        if not self._results:
            self._lbl_status.configure(
                text="⚠ Run the analysis first.", text_color=C["lose"])
            return
        try:
            from tkinter import filedialog
            path = filedialog.asksaveasfilename(
                title="Export optimizer results",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            )
            if not path:
                return
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self._result_rows_as_csv())
            self._lbl_status.configure(
                text=f"✅ CSV exported → {path}", text_color=C["win"])
        except Exception as e:  # noqa: BLE001
            self._lbl_status.configure(
                text=f"⚠ Export failed: {e}", text_color=C["lose"])

    def _copy_clipboard(self) -> None:
        if not self._results:
            self._lbl_status.configure(
                text="⚠ Run the analysis first.", text_color=C["lose"])
            return
        try:
            self.clipboard_clear()
            self.clipboard_append(self._result_rows_as_tsv())
            self._lbl_status.configure(
                text="✅ Copied (TSV) to clipboard.", text_color=C["win"])
        except Exception as e:  # noqa: BLE001
            self._lbl_status.configure(
                text=f"⚠ Copy failed: {e}", text_color=C["lose"])
