"""
============================================================
  FORGE MASTER UI — Wiki icon calibration popup

  Launched from Equipment Comparator → "🔍 Calibrate icons".
  Captures the wiki_grid zone (the in-game item-selector
  popup), template-matches each cell against
  data/icons/equipment/, and lets the user validate the
  OCR'd ItemNames before persisting them to AutoItemMapping
  + renaming the source PNG files.

  Workflow:
    1. Pick Age + Slot
    2. Click "Scan grid"
    3. Review the 8-row table (cell index | OCR name | best
       match | score). Tick the rows you want to apply.
    4. Click "Apply selected" — backups
       AutoItemMapping into _archive/ before mutating.
============================================================
"""

from __future__ import annotations

import logging
from typing import List, Optional

import customtkinter as ctk

from backend.scanner.icon_recognition import (
    AGE_INT_TO_FOLDER,
    SLOT_TO_FOLDER,
    DEFAULT_THRESHOLD,
    CellMatch,
)
from ui.theme import C, FONT_BODY, FONT_MONO_S, FONT_SMALL, FONT_SUB, FONT_TITLE

log = logging.getLogger(__name__)


# Display order for the dropdowns. Age dropdown shows the human-readable
# folder name; we map back to the int when calling the controller.
_AGE_NAMES: List[str] = [AGE_INT_TO_FOLDER[i] for i in range(10)]
_SLOT_NAMES: List[str] = list(SLOT_TO_FOLDER.keys())


class WikiCalibrationDialog(ctk.CTkToplevel):
    """Modal-ish popup for the icon calibration workflow."""

    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self._matches: List[CellMatch] = []
        self._row_widgets: List[dict] = []  # one entry per cell row

        self.title("Icon Calibration — Wiki Grid")
        self.geometry("780x620")
        self.configure(fg_color=C["bg"])
        # Keep the popup above the main window (not strictly modal so
        # the user can still glance at the comparator if needed).
        self.transient(parent)
        self.lift()
        self.focus_force()

        self._build()

    # ── Layout ─────────────────────────────────────────────────

    def _build(self) -> None:
        # Header
        header = ctk.CTkFrame(self, fg_color=C["surface"], corner_radius=0,
                               height=56)
        header.pack(fill="x")
        header.pack_propagate(False)
        ctk.CTkLabel(
            header, text="📚  Wiki Icon Calibration",
            font=FONT_TITLE, text_color=C["text"],
        ).pack(side="left", padx=20, pady=14)
        ctk.CTkButton(
            header, text="✕  Close", font=FONT_SMALL, width=80,
            fg_color="transparent", border_color=C["card"], border_width=1,
            command=self.destroy,
        ).pack(side="right", padx=16, pady=12)

        body = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        body.pack(fill="both", expand=True, padx=16, pady=12)

        # ── Controls row: Age | Slot | Threshold | Scan ─────────
        ctrl = ctk.CTkFrame(body, fg_color=C["card"], corner_radius=12)
        ctrl.pack(fill="x", pady=(0, 10))
        for c in range(8):
            ctrl.grid_columnconfigure(c, weight=0)
        ctrl.grid_columnconfigure(7, weight=1)

        ctk.CTkLabel(ctrl, text="Age:",
                     font=FONT_BODY, text_color=C["muted"]).grid(
            row=0, column=0, padx=(16, 6), pady=14, sticky="e")
        self._age_var = ctk.StringVar(value="Primitive")
        ctk.CTkOptionMenu(
            ctrl, variable=self._age_var, values=_AGE_NAMES,
            width=140, font=FONT_SMALL,
        ).grid(row=0, column=1, padx=(0, 14), pady=14)

        ctk.CTkLabel(ctrl, text="Slot:",
                     font=FONT_BODY, text_color=C["muted"]).grid(
            row=0, column=2, padx=(0, 6), pady=14, sticky="e")
        self._slot_var = ctk.StringVar(value="Weapon")
        ctk.CTkOptionMenu(
            ctrl, variable=self._slot_var, values=_SLOT_NAMES,
            width=120, font=FONT_SMALL,
        ).grid(row=0, column=3, padx=(0, 14), pady=14)

        ctk.CTkLabel(ctrl, text="Threshold:",
                     font=FONT_BODY, text_color=C["muted"]).grid(
            row=0, column=4, padx=(0, 6), pady=14, sticky="e")
        self._threshold_var = ctk.StringVar(value=f"{DEFAULT_THRESHOLD:.2f}")
        ctk.CTkEntry(
            ctrl, textvariable=self._threshold_var,
            width=70, font=FONT_MONO_S, justify="center",
        ).grid(row=0, column=5, padx=(0, 14), pady=14)

        self._scan_btn = ctk.CTkButton(
            ctrl, text="📷  Scan grid", font=FONT_BODY, width=130,
            command=self._on_scan_clicked,
        )
        self._scan_btn.grid(row=0, column=6, padx=(0, 16), pady=12)

        # ── Status line ────────────────────────────────────────
        self._status = ctk.CTkLabel(
            body, text="Calibrate the wiki_grid zone first (Zones tab), "
                       "then pick Age + Slot and click Scan grid.",
            font=FONT_SMALL, text_color=C["muted"], wraplength=720,
        )
        self._status.pack(fill="x", pady=(0, 8))

        # ── Results table ──────────────────────────────────────
        self._results_frame = ctk.CTkScrollableFrame(
            body, fg_color=C["card"], corner_radius=12,
        )
        self._results_frame.pack(fill="both", expand=True, pady=(0, 10))
        for c in range(6):
            self._results_frame.grid_columnconfigure(c, weight=0)
        self._results_frame.grid_columnconfigure(2, weight=1)
        self._results_frame.grid_columnconfigure(3, weight=1)

        self._build_table_header()
        self._build_empty_rows()

        # ── Footer: Apply / dry-run / Reset ────────────────────
        footer = ctk.CTkFrame(body, fg_color="transparent")
        footer.pack(fill="x")
        self._select_all_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            footer, text="Select all", variable=self._select_all_var,
            font=FONT_SMALL, command=self._on_select_all,
        ).pack(side="left", padx=(8, 16))

        ctk.CTkButton(
            footer, text="✓  Apply selected", font=FONT_BODY,
            width=170, command=lambda: self._on_apply(dry_run=False),
        ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            footer, text="🧪  Preview (dry-run)", font=FONT_SMALL,
            width=160, fg_color="transparent",
            border_color=C["card"], border_width=1,
            command=lambda: self._on_apply(dry_run=True),
        ).pack(side="right", padx=(8, 0))

    # ── Table construction ─────────────────────────────────────

    def _build_table_header(self) -> None:
        headers = [
            ("✓",      0, 32),
            ("Cell",   1, 60),
            ("OCR'd name",      2, 200),
            ("Best match (PNG stem)", 3, 240),
            ("Score",  4, 80),
            ("Status", 5, 100),
        ]
        for label, col, width in headers:
            lbl = ctk.CTkLabel(
                self._results_frame, text=label,
                font=FONT_SUB, text_color=C["muted"],
                width=width, anchor="w",
            )
            lbl.grid(row=0, column=col, padx=4, pady=(4, 6), sticky="w")

    def _build_empty_rows(self) -> None:
        """Pre-create 8 placeholder rows so the layout is stable."""
        self._row_widgets.clear()
        for i in range(8):
            row_idx = i + 1   # row 0 is the header
            check_var = ctk.BooleanVar(value=False)
            check = ctk.CTkCheckBox(
                self._results_frame, text="", variable=check_var, width=20,
            )
            check.grid(row=row_idx, column=0, padx=4, pady=2, sticky="w")
            check.configure(state="disabled")

            cell_lbl = ctk.CTkLabel(
                self._results_frame, text=f"r{i // 4} c{i % 4}",
                font=FONT_MONO_S, text_color=C["muted"], width=60, anchor="w",
            )
            cell_lbl.grid(row=row_idx, column=1, padx=4, pady=2, sticky="w")

            ocr_lbl = ctk.CTkLabel(
                self._results_frame, text="—",
                font=FONT_MONO_S, text_color=C["text"], anchor="w",
            )
            ocr_lbl.grid(row=row_idx, column=2, padx=4, pady=2, sticky="w")

            match_lbl = ctk.CTkLabel(
                self._results_frame, text="—",
                font=FONT_MONO_S, text_color=C["muted"], anchor="w",
            )
            match_lbl.grid(row=row_idx, column=3, padx=4, pady=2, sticky="w")

            score_lbl = ctk.CTkLabel(
                self._results_frame, text="—",
                font=FONT_MONO_S, text_color=C["muted"], width=80, anchor="w",
            )
            score_lbl.grid(row=row_idx, column=4, padx=4, pady=2, sticky="w")

            status_lbl = ctk.CTkLabel(
                self._results_frame, text="empty",
                font=FONT_SMALL, text_color=C["muted"], width=100, anchor="w",
            )
            status_lbl.grid(row=row_idx, column=5, padx=4, pady=2, sticky="w")

            self._row_widgets.append({
                "check_var":  check_var,
                "check":      check,
                "cell":       cell_lbl,
                "ocr":        ocr_lbl,
                "match":      match_lbl,
                "score":      score_lbl,
                "status":     status_lbl,
            })

    # ── Callbacks ──────────────────────────────────────────────

    def _on_scan_clicked(self) -> None:
        try:
            threshold = float(self._threshold_var.get().replace(",", "."))
        except ValueError:
            self._status.configure(
                text="⚠ Threshold must be a float between 0 and 1.",
                text_color=C["lose"],
            )
            return
        if not (0.0 <= threshold <= 1.0):
            self._status.configure(
                text="⚠ Threshold must be between 0 and 1.",
                text_color=C["lose"],
            )
            return

        age_name = self._age_var.get()
        slot     = self._slot_var.get()
        try:
            age_int = _AGE_NAMES.index(age_name)
        except ValueError:
            self._status.configure(
                text=f"⚠ Unknown age {age_name!r}", text_color=C["lose"])
            return

        self._scan_btn.configure(state="disabled")
        self._status.configure(
            text=f"📷 Scanning {age_name} / {slot} ...",
            text_color=C["accent"],
        )
        self.controller.scan_wiki_grid(
            age=age_int, slot=slot, threshold=threshold,
            callback=self._on_scan_done,
        )

    def _on_scan_done(self, matches: List[CellMatch], status: str) -> None:
        self._scan_btn.configure(state="normal")
        if status == "zone_not_configured":
            self._status.configure(
                text="⚠ wiki_grid zone not configured — go to Zones tab "
                     "and trace the popup region first.",
                text_color=C["lose"],
            )
            return
        if status == "ocr_unavailable":
            self._status.configure(
                text="⚠ OCR backend unavailable — "
                     "install rapidocr_onnxruntime.",
                text_color=C["lose"],
            )
            return
        if status == "capture_failed":
            self._status.configure(
                text="⚠ Screen capture failed.", text_color=C["lose"])
            return
        if status == "scan_error":
            self._status.configure(
                text="⚠ Scan crashed (see log).", text_color=C["lose"])
            return

        self._matches = matches or []
        try:
            threshold = float(self._threshold_var.get().replace(",", "."))
        except ValueError:
            threshold = DEFAULT_THRESHOLD
        self._render_matches(threshold)

        n_filled = sum(1 for m in self._matches if m.is_filled)
        n_good = sum(1 for m in self._matches
                     if m.is_filled and m.score >= threshold)
        n_low = sum(1 for m in self._matches
                    if m.is_filled and m.score < threshold)
        self._status.configure(
            text=(f"✓ Scan complete — {n_filled} filled cells "
                  f"({n_good} above threshold, {n_low} below). "
                  f"Tick the rows to apply, then click Apply."),
            text_color=C["win"] if n_low == 0 else C["accent"],
        )

    def _render_matches(self, threshold: float) -> None:
        for i, w in enumerate(self._row_widgets):
            if i >= len(self._matches):
                break
            m = self._matches[i]
            cell_txt = f"{i}  (r{m.row}c{m.col})"
            w["cell"].configure(text=cell_txt)

            if not m.is_filled:
                w["check"].configure(state="disabled")
                w["check_var"].set(False)
                w["ocr"].configure(text="—", text_color=C["muted"])
                w["match"].configure(text="—", text_color=C["muted"])
                w["score"].configure(text="—", text_color=C["muted"])
                w["status"].configure(text="empty", text_color=C["muted"])
                continue

            ok = m.score >= threshold and m.best_match and m.ocr_name
            color_score = C["win"] if ok else C["lose"]
            w["check"].configure(state="normal")
            w["check_var"].set(bool(ok))
            w["ocr"].configure(
                text=m.ocr_name or "(no OCR)",
                text_color=C["text"] if m.ocr_name else C["lose"],
            )
            w["match"].configure(
                text=m.best_match or "(no match)",
                text_color=C["text"] if m.best_match else C["muted"],
            )
            w["score"].configure(
                text=f"{m.score:.3f}", text_color=color_score,
            )
            if not m.ocr_name:
                w["status"].configure(text="no OCR", text_color=C["lose"])
            elif not m.best_match:
                w["status"].configure(text="no match", text_color=C["lose"])
            elif m.score < threshold:
                w["status"].configure(text="low score", text_color=C["accent"])
            else:
                w["status"].configure(text="OK", text_color=C["win"])

    def _on_select_all(self) -> None:
        v = self._select_all_var.get()
        try:
            threshold = float(self._threshold_var.get().replace(",", "."))
        except ValueError:
            threshold = DEFAULT_THRESHOLD
        for i, w in enumerate(self._row_widgets):
            if i >= len(self._matches):
                continue
            m = self._matches[i]
            if not m.is_filled:
                continue
            # Only auto-tick rows that are above threshold; below-threshold
            # rows must be ticked manually so the user is forced to read
            # the warning.
            if v and m.score >= threshold and m.best_match and m.ocr_name:
                w["check_var"].set(True)
            elif not v:
                w["check_var"].set(False)

    def _on_apply(self, dry_run: bool) -> None:
        if not self._matches:
            self._status.configure(
                text="⚠ Nothing scanned yet.", text_color=C["lose"])
            return

        try:
            threshold = float(self._threshold_var.get().replace(",", "."))
        except ValueError:
            threshold = DEFAULT_THRESHOLD

        selected = [i for i, w in enumerate(self._row_widgets)
                    if i < len(self._matches) and w["check_var"].get()]
        if not selected:
            self._status.configure(
                text="⚠ No rows ticked.", text_color=C["lose"])
            return

        age_name = self._age_var.get()
        slot     = self._slot_var.get()
        try:
            age_int = _AGE_NAMES.index(age_name)
        except ValueError:
            self._status.configure(
                text=f"⚠ Unknown age {age_name!r}", text_color=C["lose"])
            return

        try:
            report = self.controller.apply_wiki_results(
                self._matches, age=age_int, slot=slot,
                selected_indices=selected, threshold=threshold,
                dry_run=dry_run,
            )
        except Exception as e:
            log.exception("apply_wiki_results crashed")
            self._status.configure(
                text=f"⚠ Apply crashed: {e}", text_color=C["lose"])
            return

        n_up = len(report.updated)
        n_sk = len(report.skipped)
        suffix = " (DRY-RUN, nothing written)" if dry_run else ""
        self._status.configure(
            text=(f"✓ Applied {n_up}, skipped {n_sk}{suffix}. "
                  f"{'Backup: ' + str(report.backup_path) if report.backup_path else ''}"),
            text_color=C["win"] if n_up else C["accent"],
        )
        # Mark applied rows visually.
        if not dry_run:
            done = {u["cell_idx"] for u in report.updated}
            for i, w in enumerate(self._row_widgets):
                if i in done:
                    w["status"].configure(
                        text="applied ✓", text_color=C["win"])
                    w["check_var"].set(False)
                    w["check"].configure(state="disabled")
