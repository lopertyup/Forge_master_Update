"""
============================================================
  FORGE MASTER UI — Import zone + OCR scan button

  The shared "paste your OCR text here" card used by every
  import view (profile, pets, mount, equipment, skills). Also
  exposes attach_scan_button() so views with a bespoke layout
  can bolt on a 📷 Scan button without rebuilding the whole
  card.

  The scan button is stateful: multi-capture zones (e.g. the
  profile needs two clicks with a scroll between them) show
  « (n/N) » on the label and concatenate the intermediate
  text before filling the textbox.
============================================================
"""

from __future__ import annotations

from typing import Callable, Optional, Tuple

import customtkinter as ctk

from backend.fix_ocr import fix_ocr

from .theme import (
    C,
    FONT_BODY,
    FONT_MONO_S,
    FONT_SMALL,
    FONT_SUB,
)


_SCAN_LABEL = "📷 Scan"


def build_import_zone(parent: ctk.CTkBaseClass, title: str, hint: str,
                      primary_label: str, primary_cmd: Callable,
                      secondary_label: Optional[str] = None,
                      secondary_cmd: Optional[Callable] = None,
                      textbox_height: int = 130,
                      scan_key:       Optional[str]                     = None,
                      scan_fn:        Optional[Callable]                = None,
                      captures_fn:    Optional[Callable[[str], int]]    = None,
                      on_scan_ready:  Optional[Callable[[], None]]      = None,
                      ) -> Tuple[ctk.CTkFrame, ctk.CTkTextbox, ctk.CTkLabel]:
    """
    Build an import zone: title + hint + textarea + primary button +
    optional secondary + optional OCR scan button + status label.

    OCR-related params (all four opt-in; pass `scan_key` and `scan_fn`
    to enable the 📷 button):
      - scan_key     : key in zones.json (e.g. "pet", "profile", …)
      - scan_fn      : controller.scan, signature
                       `(zone_key, callback, step=None) -> None`
                       with callback `(text, status) -> None`
      - captures_fn  : controller.get_zone_captures, returns an int.
                       Defaults to 1 when missing.
      - on_scan_ready: called once the textbox is fully populated
                       (after the last capture of a multi-capture zone).

    Returns (card, textbox, status_label).
    """
    card = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=12)
    card.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(card, text=title, font=FONT_SUB, text_color=C["text"]).grid(
        row=0, column=0, padx=20, pady=(16, 4), sticky="w")
    ctk.CTkLabel(card, text=hint, font=FONT_SMALL, text_color=C["muted"]).grid(
        row=1, column=0, padx=20, pady=(0, 8), sticky="w")

    textbox = ctk.CTkTextbox(
        card, height=textbox_height, font=FONT_MONO_S,
        fg_color=C["bg"], text_color=C["text"],
        border_color=C["border"], border_width=1)
    textbox.grid(row=2, column=0, padx=16, pady=(0, 8), sticky="ew")

    btn_f = ctk.CTkFrame(card, fg_color="transparent")
    btn_f.grid(row=3, column=0, padx=16, pady=(0, 8), sticky="w")

    ctk.CTkButton(btn_f, text=primary_label,
                  font=FONT_BODY, height=38, corner_radius=8,
                  fg_color=C["accent"], hover_color=C["accent_hv"],
                  command=primary_cmd).pack(side="left", padx=(0, 8))

    if secondary_label and secondary_cmd:
        ctk.CTkButton(btn_f, text=secondary_label,
                      font=FONT_BODY, height=38, corner_radius=8,
                      fg_color=C["border"], hover_color=C["border_hl"],
                      command=secondary_cmd).pack(side="left", padx=(0, 8))

    status_lbl = ctk.CTkLabel(card, text="", font=FONT_SMALL,
                              text_color=C["muted"])
    status_lbl.grid(row=4, column=0, padx=20, pady=(0, 12))

    if scan_key and scan_fn:
        attach_scan_button(
            parent_btn_frame=btn_f,
            textbox=textbox,
            status_lbl=status_lbl,
            scan_key=scan_key,
            scan_fn=scan_fn,
            captures_fn=captures_fn,
            on_scan_ready=on_scan_ready,
        )

    return card, textbox, status_lbl


def attach_scan_button(parent_btn_frame: ctk.CTkBaseClass,
                       textbox: ctk.CTkTextbox,
                       status_lbl: ctk.CTkLabel,
                       scan_key: str,
                       scan_fn: Callable,
                       captures_fn: Optional[Callable[[str], int]] = None,
                       on_scan_ready: Optional[Callable[[], None]] = None,
                       ) -> ctk.CTkButton:
    """Create and pack a 📷 scan button that drives the OCR FSM.

    The button appends onto `parent_btn_frame` with side="left". All
    OCR errors (ocr_unavailable / ocr_error / zone_not_configured /
    empty) are surfaced in `status_lbl`. On success, the textbox is
    populated and `on_scan_ready` is called.
    """
    total = 1
    if captures_fn is not None:
        try:
            total = max(1, int(captures_fn(scan_key)))
        except Exception:
            total = 1

    state = {"step": 0, "buffer": ""}  # mutable closure over the button

    def _label_for_step(step: int) -> str:
        if total <= 1:
            return _SCAN_LABEL
        return f"{_SCAN_LABEL} ({step + 1}/{total})"

    def _reset() -> None:
        state["step"]   = 0
        state["buffer"] = ""
        btn.configure(text=_label_for_step(0), state="normal")

    def _fill_textbox(text: str) -> None:
        textbox.delete("1.0", "end")
        textbox.insert("1.0", text)

    def _on_scan_result(text: str, status: str) -> None:
        # Callback arrives on the Tk thread (dispatched by the controller).
        if status == "ocr_unavailable":
            status_lbl.configure(
                text=("⚠ OCR unavailable — install `rapidocr_onnxruntime` "
                      "(recommended) or `paddleocr paddlepaddle`."),
                text_color=C["lose"])
            btn.configure(state="disabled")
            return
        if status == "ocr_error":
            status_lbl.configure(
                text="⚠ OCR engine crashed — check the logs and retry.",
                text_color=C["lose"])
            _reset()
            return
        if status == "zone_not_configured":
            status_lbl.configure(
                text=(f"⚠ Zone « {scan_key} » not configured — "
                      f"open the Zones tab to set it."),
                text_color=C["lose"])
            _reset()
            return
        if status == "empty" or not text.strip():
            status_lbl.configure(
                text="⚠ OCR found nothing — adjust the capture zone.",
                text_color=C["lose"])
            _reset()
            return

        # status == "ok"
        if state["step"] + 1 < total:
            # Multi-capture, not done yet: buffer and advance.
            state["buffer"] = (state["buffer"] + "\n\n" + text).strip() \
                if state["buffer"] else text
            state["step"] += 1
            btn.configure(text=_label_for_step(state["step"]), state="normal")
            status_lbl.configure(
                text=f"✓ Captured {state['step']}/{total}. Scroll and click again.",
                text_color=C["muted"])
        else:
            # Final step: assemble full text, fill textbox, trigger auto-run.
            full = (state["buffer"] + "\n\n" + text).strip() \
                if state["buffer"] else text
            fixed = fix_ocr(full, context=scan_key)
            _fill_textbox(fixed)
            _reset()
            status_lbl.configure(text="✓ OCR complete.", text_color=C["win"])
            if on_scan_ready is not None:
                try:
                    on_scan_ready()
                except Exception:
                    import logging
                    logging.getLogger(__name__).exception(
                        "on_scan_ready(%r) raised", scan_key)

    def _on_click() -> None:
        # Lock the button during the round-trip to avoid double-clicks.
        btn.configure(state="disabled")
        status_lbl.configure(text="📷 Scanning…", text_color=C["muted"])
        # For multi-capture zones we send a `step=` hint so the controller
        # grabs ONLY the bbox relevant to this click.
        step_arg = state["step"] if total > 1 else None
        try:
            scan_fn(scan_key, _on_scan_result, step=step_arg)
        except Exception as e:
            status_lbl.configure(text=f"⚠ Scan error: {e}", text_color=C["lose"])
            _reset()

    btn = ctk.CTkButton(
        parent_btn_frame, text=_label_for_step(0),
        font=FONT_BODY, height=38, corner_radius=8,
        fg_color=C["border"], hover_color=C["border_hl"],
        command=_on_click,
    )
    btn.pack(side="left", padx=(0, 8))
    return btn
