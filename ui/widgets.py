"""
============================================================
  FORGE MASTER UI — Widgets réutilisables
  Petits composants assemblés à partir de customtkinter pour
  remplacer les blocs dupliqués dans les vues.
============================================================
"""

from typing import Callable, Dict, List, Optional, Tuple

import customtkinter as ctk

from .theme import (
    C,
    FLAT_STAT_KEYS,
    FONT_BODY,
    FONT_BIG,
    FONT_HUGE,
    FONT_MONO,
    FONT_MONO_S,
    FONT_SMALL,
    FONT_SUB,
    FONT_TINY,
    STAT_LABELS,
    fmt_nombre,
    fmt_stat,
    rarity_color,
)


# ════════════════════════════════════════════════════════════
#  EN-TÊTE DE VUE (bande du haut 64px)
# ════════════════════════════════════════════════════════════

def build_header(parent: ctk.CTkBaseClass, title: str,
                 font=None, height: int = 64) -> ctk.CTkFrame:
    """Construit l'en-tête standard d'une vue. Retourne le frame."""
    from .theme import FONT_TITLE
    header = ctk.CTkFrame(parent, fg_color=C["surface"], corner_radius=0, height=height)
    header.grid(row=0, column=0, sticky="ew")
    header.grid_propagate(False)
    header.grid_columnconfigure(1, weight=1)
    ctk.CTkLabel(header, text=title,
                 font=font or FONT_TITLE, text_color=C["text"]).pack(
        side="left", padx=24, pady=16)
    return header


# ════════════════════════════════════════════════════════════
#  LIGNE DE STAT (label à gauche, valeur à droite)
# ════════════════════════════════════════════════════════════

def stat_row(parent: ctk.CTkBaseClass, key: str, value: float,
             row_index: int = 0, label: Optional[str] = None,
             is_flat: Optional[bool] = None) -> ctk.CTkFrame:
    """Une ligne 'Label  ────  Valeur' en zébré alterné."""
    bg = C["card_alt"] if row_index % 2 == 0 else C["card"]
    row = ctk.CTkFrame(parent, fg_color=bg, corner_radius=4)
    row.grid_columnconfigure(1, weight=1)

    ctk.CTkLabel(row, text=label or STAT_LABELS.get(key, key),
                 font=FONT_SMALL, text_color=C["muted"], anchor="w").grid(
        row=0, column=0, padx=10, pady=4, sticky="w")

    if is_flat is None:
        is_flat = key in FLAT_STAT_KEYS
    val_txt = fmt_nombre(value) if is_flat else f"+{value}%"
    ctk.CTkLabel(row, text=val_txt, font=FONT_MONO,
                 text_color=C["text"], anchor="e").grid(
        row=0, column=1, padx=10, pady=4, sticky="e")
    return row


# ════════════════════════════════════════════════════════════
#  BARRES WIN / LOSE / DRAW
# ════════════════════════════════════════════════════════════

def build_wld_bars(parent: ctk.CTkBaseClass, wins: int, loses: int, draws: int,
                   total: Optional[int] = None, bar_height: int = 10,
                   compact: bool = False) -> ctk.CTkFrame:
    """
    Affiche 3 barres horizontales WIN / LOSE / DRAW.
    `total` par défaut = wins + loses + draws.
    """
    total = total or max(1, wins + loses + draws)
    frame = ctk.CTkFrame(parent, fg_color="transparent")

    for label, val, color in (
        ("WIN",  wins,  C["win"]),
        ("LOSE", loses, C["lose"]),
        ("DRAW", draws, C["draw"]),
    ):
        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(fill="x", pady=2 if compact else 3)
        ctk.CTkLabel(row, text=label, font=FONT_SMALL,
                     text_color=color, width=36 if compact else 40).pack(side="left")
        bar = ctk.CTkProgressBar(row, height=bar_height, corner_radius=4,
                                  progress_color=color)
        bar.pack(side="left", fill="x", expand=True, padx=6 if compact else 8)
        bar.set(val / total)
        ctk.CTkLabel(row, text=f"{100 * val / total:.0f}%",
                     font=FONT_SMALL, text_color=C["muted"],
                     width=36 if compact else 40).pack(side="right")
    return frame


# ════════════════════════════════════════════════════════════
#  GROS COMPTEUR "—" (utilisé par simulateur)
# ════════════════════════════════════════════════════════════

def big_counter(parent: ctk.CTkBaseClass, label: str, color: str,
                total_text: str = "/ 1000") -> ctk.CTkLabel:
    """Encadré 'LABEL / chiffre / total'. Retourne le label du chiffre."""
    frame = ctk.CTkFrame(parent, fg_color=C["card_alt"], corner_radius=10)
    ctk.CTkLabel(frame, text=label, font=FONT_SMALL,
                 text_color=C["muted"]).pack(pady=(10, 0))
    value_lbl = ctk.CTkLabel(frame, text="—", font=FONT_HUGE, text_color=color)
    value_lbl.pack()
    ctk.CTkLabel(frame, text=total_text, font=FONT_SMALL,
                 text_color=C["muted"]).pack(pady=(0, 10))
    value_lbl._counter_frame = frame  # pour le caller qui veut .grid() le frame
    return value_lbl


# ════════════════════════════════════════════════════════════
#  CARTE "STAT HÉROS" (HP / ATQ dans le dashboard)
# ════════════════════════════════════════════════════════════

def stat_hero_card(parent: ctk.CTkBaseClass, title: str, value: str,
                   subtitle: str, color: str) -> ctk.CTkFrame:
    card = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=12)
    ctk.CTkLabel(card, text=title, font=FONT_SMALL,
                 text_color=C["muted"]).pack(anchor="w", padx=20, pady=(16, 0))
    ctk.CTkLabel(card, text=value, font=FONT_BIG,
                 text_color=color).pack(anchor="w", padx=20, pady=(2, 0))
    ctk.CTkLabel(card, text=subtitle, font=FONT_SMALL,
                 text_color=C["muted"]).pack(anchor="w", padx=20, pady=(0, 16))
    return card


# ════════════════════════════════════════════════════════════
#  DIALOGUE DE CONFIRMATION (oui / non)
# ════════════════════════════════════════════════════════════

class ConfirmDialog(ctk.CTkToplevel):
    """
    Dialogue modal simple. `result` contient True/False après destroy.
    Utilisation :
        dlg = ConfirmDialog(parent, "Titre", "Message long", "OK", "Annuler")
        parent.wait_window(dlg)
        if dlg.result:
            ...
    """

    def __init__(self, parent, title: str, message: str,
                 ok_label: str = "Confirmer", cancel_label: str = "Annuler",
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


def confirmer(parent, title: str, message: str,
              ok_label: str = "Confirmer",
              cancel_label: str = "Annuler",
              danger: bool = True) -> bool:
    """Ouvre un ConfirmDialog et retourne True/False."""
    dlg = ConfirmDialog(parent, title, message, ok_label, cancel_label, danger)
    parent.wait_window(dlg)
    return dlg.result


# ════════════════════════════════════════════════════════════
#  CARTE "STATS" (pet / mount / equipement résumé)
# ════════════════════════════════════════════════════════════

def stats_card(parent: ctk.CTkBaseClass, title: str, stats: Dict[str, float],
               empty_text: str = "(vide)",
               title_color: Optional[str] = None) -> ctk.CTkFrame:
    """
    Carte avec un titre et des stat_rows pour chaque stat non nulle.
    Affiche `empty_text` si toutes les stats sont nulles.
    """
    card = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=12)
    ctk.CTkLabel(card, text=title, font=FONT_SUB,
                 text_color=title_color or C["text"]).pack(
        padx=16, pady=(14, 6), anchor="w")

    non_nuls = [(k, v) for k, v in stats.items()
                if not k.startswith("__") and v]

    if not non_nuls:
        ctk.CTkLabel(card, text=empty_text, font=FONT_BODY,
                     text_color=C["muted"]).pack(padx=16, pady=20)
    else:
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=10, pady=(0, 10))
        for i, (k, v) in enumerate(non_nuls):
            stat_row(inner, k, v, row_index=i).pack(fill="x", pady=1)

    ctk.CTkFrame(card, fg_color="transparent", height=6).pack()
    return card


# ════════════════════════════════════════════════════════════
#  CARTE "SLOT COMPANION" (pet équipé / mount équipé)
#  En-tête avec icône + nom + badge rareté, puis stats.
# ════════════════════════════════════════════════════════════

def companion_slot_card(parent: ctk.CTkBaseClass, slot_label: str,
                         name: Optional[str], rarity: Optional[str],
                         stats: Dict[str, float],
                         icon_image=None, fallback_emoji: str = "🐾",
                         empty_text: str = "(vide)") -> ctk.CTkFrame:
    """
    Carte d'un slot équipé : libellé du slot, icône + nom + rareté,
    puis liste des stats non nulles. Si `name` est None → état "vide".
    """
    card = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=12)

    # Bandeau du haut : libellé du slot (ex: "🐾 PET1" / "🐴 Mount actuel")
    ctk.CTkLabel(card, text=slot_label, font=FONT_SUB,
                 text_color=C["muted"]).pack(
        padx=16, pady=(12, 4), anchor="w")

    # Bandeau identité : icône + nom + rareté
    head = ctk.CTkFrame(card, fg_color="transparent")
    head.pack(fill="x", padx=12, pady=(0, 6))

    if icon_image is not None:
        ctk.CTkLabel(head, image=icon_image, text="",
                     fg_color="transparent", width=48).pack(side="left",
                                                             padx=(2, 8))
    else:
        ctk.CTkLabel(head, text=fallback_emoji,
                     font=("Segoe UI", 26), width=48).pack(side="left",
                                                            padx=(2, 8))

    info = ctk.CTkFrame(head, fg_color="transparent")
    info.pack(side="left", fill="x", expand=True)

    if name:
        ctk.CTkLabel(info, text=name, font=FONT_SUB,
                     text_color=C["text"], anchor="w").pack(anchor="w")
        if rarity:
            rar = str(rarity).lower()
            ctk.CTkLabel(info, text=rar.upper(), font=FONT_TINY,
                         text_color=rarity_color(rar), anchor="w").pack(
                anchor="w")
    else:
        ctk.CTkLabel(info, text="— libre —", font=FONT_BODY,
                     text_color=C["muted"], anchor="w").pack(anchor="w")

    # Stats (filtre les clés non numériques de l'identité)
    non_nuls = [(k, v) for k, v in stats.items()
                if not k.startswith("__") and v]

    if not non_nuls:
        ctk.CTkLabel(card, text=empty_text, font=FONT_BODY,
                     text_color=C["muted"]).pack(padx=16, pady=(4, 14))
    else:
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=10, pady=(0, 10))
        for i, (k, v) in enumerate(non_nuls):
            stat_row(inner, k, v, row_index=i).pack(fill="x", pady=1)

    ctk.CTkFrame(card, fg_color="transparent", height=6).pack()
    return card


# ════════════════════════════════════════════════════════════
#  ZONE D'IMPORT (textarea + boutons + status)
# ════════════════════════════════════════════════════════════

# ════════════════════════════════════════════════════════════
#  GRILLE D'ICÔNES DE SKILLS (avec toggle)
# ════════════════════════════════════════════════════════════

def skill_icon_grid(parent: ctk.CTkBaseClass,
                    all_skills: Dict,
                    selected: Dict[str, "ctk.BooleanVar"],
                    cols: int = 6,
                    icon_size: int = 44,
                    on_toggle: Optional[Callable[[str], None]] = None
                    ) -> Tuple[ctk.CTkFrame, Dict]:
    """
    Construit une grille cliquable d'icônes pour `all_skills`.
    `selected` est un dict {code: BooleanVar} injecté par l'appelant.
    Retourne (frame, widgets) où widgets = {code: (label, frame)} pour
    que l'appelant puisse rafraîchir visuellement.
    """
    from .theme import load_icon, rarity_color

    grid = ctk.CTkFrame(parent, fg_color=C["bg"],
                        border_color=C["border"], border_width=1,
                        corner_radius=8)

    widgets: Dict[str, Tuple[ctk.CTkLabel, ctk.CTkFrame]] = {}

    def _refresh(code: str) -> None:
        lbl, frame = widgets[code]
        if selected[code].get():
            frame.configure(fg_color=C["selected"], corner_radius=8,
                            border_width=2, border_color=C["win"])
        else:
            frame.configure(fg_color="transparent", border_width=0)

    def _make_toggle(code: str) -> Callable:
        def _click(_evt=None) -> None:
            if on_toggle is not None:
                on_toggle(code)
            _refresh(code)
        return _click

    for i, (code, data) in enumerate(sorted(all_skills.items())):
        color    = rarity_color(str(data.get("rarity", "common")).lower())
        icon_img = load_icon(code, size=icon_size)
        name     = data.get("name", code)

        btn_frame = ctk.CTkFrame(grid, fg_color="transparent",
                                  corner_radius=8)
        btn_frame.grid(row=i // cols, column=i % cols, padx=6, pady=6)

        lbl = ctk.CTkLabel(
            btn_frame,
            image=icon_img if icon_img else None,
            text="" if icon_img else code.upper(),
            font=("Segoe UI", 9, "bold"),
            text_color=color,
            fg_color="transparent",
            corner_radius=8,
            width=icon_size + 8, height=icon_size + 8,
        )
        lbl.pack()
        lbl.bind("<Button-1>", _make_toggle(code))
        widgets[code] = (lbl, btn_frame)

        # Tooltip au survol : remplace l'icône par le nom court
        def _enter(_e, n=name, col=color, w=lbl) -> None:
            w.configure(text=n[:8], text_color=col, image=None)

        def _leave(_e, img=icon_img, w=lbl, c=code) -> None:
            w.configure(text="" if img else c.upper(),
                        image=img if img else None)

        lbl.bind("<Enter>", _enter)
        lbl.bind("<Leave>", _leave)

        _refresh(code)

    for c in range(cols):
        grid.grid_columnconfigure(c, weight=1)

    return grid, widgets


def build_import_zone(parent: ctk.CTkBaseClass, title: str, hint: str,
                      primary_label: str, primary_cmd: Callable,
                      secondary_label: Optional[str] = None,
                      secondary_cmd: Optional[Callable] = None,
                      textbox_height: int = 130
                      ) -> Tuple[ctk.CTkFrame, ctk.CTkTextbox, ctk.CTkLabel]:
    """
    Construit une zone d'import : titre + hint + textarea + 1 ou 2 boutons
    + label de status. Retourne (card, textbox, status_label).
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
                      command=secondary_cmd).pack(side="left")

    status_lbl = ctk.CTkLabel(card, text="", font=FONT_SMALL,
                              text_color=C["muted"])
    status_lbl.grid(row=4, column=0, padx=20, pady=(0, 12))
    return card, textbox, status_lbl
