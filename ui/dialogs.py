"""
============================================================
  FORGE MASTER UI — Modal dialogs

  Tiny reusable Toplevel dialogs. Currently only holds the
  yes/no confirmation dialog used for destructive actions.
============================================================
"""

from __future__ import annotations

import customtkinter as ctk

from .theme import C, FONT_BODY, FONT_SUB


class ConfirmDialog(ctk.CTkToplevel):
    """
    Simple modal dialog. `result` holds True/False after destroy.
    Usage:
        dlg = ConfirmDialog(parent, "Title", "Long message", "OK", "Cancel")
        parent.wait_window(dlg)
        if dlg.result:
            ...
    """

    def __init__(self, parent, title: str, message: str,
                 ok_label: str = "Confirm", cancel_label: str = "Cancel",
                 danger: bool = True):
        super().__init__(parent)
        self.result = False
        self.title(title)
        self.geometry("420x200")
        self.resizable(False, False)
        self.configure(fg_color=C["surface"])
        self.grab_set()
        self.transient(parent)

        ctk.CTkLabel(self, text=title, font=FONT_SUB,
                     text_color=C["text"]).pack(padx=24, pady=(22, 8))
        ctk.CTkLabel(self, text=message, font=FONT_BODY,
                     text_color=C["muted"], wraplength=360,
                     justify="center").pack(padx=24, pady=(0, 16))

        btn_f = ctk.CTkFrame(self, fg_color="transparent")
        btn_f.pack(padx=24, pady=(0, 20), fill="x")

        ctk.CTkButton(btn_f, text=cancel_label, fg_color=C["border"],
                      hover_color=C["border_hl"], font=FONT_BODY,
                      width=120, command=self._cancel).pack(side="right", padx=(8, 0))
        ctk.CTkButton(btn_f, text=ok_label,
                      fg_color=C["lose"] if danger else C["accent"],
                      hover_color=C["lose_hv"] if danger else C["accent_hv"],
                      font=FONT_BODY, width=160,
                      command=self._ok).pack(side="right")

    def _ok(self):
        self.result = True
        self.destroy()

    def _cancel(self):
        self.result = False
        self.destroy()


def confirm(parent, title: str, message: str,
            ok_label: str = "Confirm",
            cancel_label: str = "Cancel",
            danger: bool = True) -> bool:
    """Open a ConfirmDialog and return True/False."""
    dlg = ConfirmDialog(parent, title, message, ok_label, cancel_label, danger)
    parent.wait_window(dlg)
    return dlg.result


# Back-compat alias (old French name).
confirmer = confirm
