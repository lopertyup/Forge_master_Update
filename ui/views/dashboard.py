"""
============================================================
  FORGE MASTER UI — Dashboard

  Phase-4 refactor (UI_REFACTOR_PLAN §3 / §11).

  Single-column scrollable view, six cards (Plan §3):

      Header  : title + [Scan profile] [Update] [Reset]
      Card 1  : Stats principales  (HP/DMG totals + bases)
      Card 2  : Substats combat
      Card 3  : Skills équipés     (3 mini-cards)
      Card 4  : Pet & Mount actifs (3 pets + 1 mount)
      Card 5  : Équipement         (4×2 grid, click → Equipment view)

  All shared widgets come from ui/cards.py (Phase-2 module).
  No imports from backend/* here — Plan §11 D1 / Plan P4.
============================================================
"""

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
    confirm,
    skill_icon_grid,
)
from ui.cards import ItemCard, StatBlock


# ── Slot layout (kept local: no backend import — Plan D1) ────

_PET_SLOTS = ("PET1", "PET2", "PET3")

# 8 equipment slots displayed in canonical in-game order
# (Helmet → Belt). Mirrors backend.constants.EQUIPMENT_SLOTS but
# duplicated locally so the dashboard satisfies the "no backend
# import" criterion (Plan §11 D1).
_EQUIPMENT_SLOTS = (
    ("EQUIP_HELMET",   "Helmet",   "🪖"),
    ("EQUIP_BODY",     "Body",     "🦺"),
    ("EQUIP_GLOVES",   "Gloves",   "🧤"),
    ("EQUIP_NECKLACE", "Necklace", "📿"),
    ("EQUIP_RING",     "Ring",     "💍"),
    ("EQUIP_WEAPON",   "Weapon",   "⚔"),
    ("EQUIP_SHOE",     "Shoe",     "👢"),
    ("EQUIP_BELT",     "Belt",     "🎗"),
)

# Substats shown in the "Substats combat" card. Order is the
# canonical in-game order (mirrors equipment.py:_STAT_ROWS for
# the percentage-only stats).
_SUBSTAT_ROWS = (
    ("crit_chance",    "Crit Chance"),
    ("crit_damage",    "Crit Damage"),
    ("block_chance",   "Block Chance"),
    ("health_regen",   "Health Regen"),
    ("lifesteal",      "Lifesteal"),
    ("double_chance",  "Double Chance"),
    ("damage_pct",     "Damage %"),
    ("melee_pct",      "Melee %"),
    ("ranged_pct",     "Ranged %"),
    ("attack_speed",   "Attack Speed"),
    ("skill_damage",   "Skill Damage"),
    ("skill_cooldown", "Skill Cooldown"),
    ("health_pct",     "Health %"),
)

# Profile-import dialog geometry — fixed (no session persistence).
# Tuned to sit flush against the left edge of the main window.
_PROFILE_DIALOG_GEOMETRY = "670x641+-12+0"


class DashboardView(ctk.CTkFrame):

    def __init__(self, parent, controller, app):
        super().__init__(parent, fg_color=C["bg"], corner_radius=0)
        self.controller = controller
        self.app        = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build()

    # ── Build ─────────────────────────────────────────────────

    def _build(self) -> None:
        self._build_header()

        # Single-column scrollable body (Plan §3).
        scroll = ctk.CTkScrollableFrame(
            self, fg_color=C["bg"], corner_radius=0,
        )
        scroll.grid(row=1, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)
        self._scroll = scroll

        if not self.controller.has_profile():
            self._empty_state(scroll)
            return

        self._build_main_stats_card(scroll, row=0)
        self._build_substats_card(scroll, row=1)
        self._build_skills_card(scroll, row=2)
        self._build_companions_card(scroll, row=3)
        self._build_equipment_card(scroll, row=4)

    # ── Header (title + actions) ─────────────────────────────

    def _build_header(self) -> None:
        header = ctk.CTkFrame(
            self, fg_color=C["surface"], corner_radius=0, height=64,
        )
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            header, text="Dashboard",
            font=FONT_TITLE, text_color=C["text"],
        ).grid(row=0, column=0, padx=24, pady=16, sticky="w")

        # Right-side action cluster (Plan §3): Scan / Update / Reset.
        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.grid(row=0, column=2, padx=12, pady=12, sticky="e")

        ctk.CTkButton(
            actions, text="📷  Scan profile",
            font=FONT_SMALL, height=36, width=140, corner_radius=8,
            fg_color="transparent",
            border_color=C["card"], border_width=1,
            hover_color=C["border"], text_color=C["text"],
            command=self._on_scan_profile,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            actions, text="⟳  Update profile",
            font=FONT_SMALL, height=36, width=140, corner_radius=8,
            fg_color=C["accent"], hover_color=C["accent_hv"],
            command=self._open_import,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            actions, text="🗑  Reset",
            font=FONT_SMALL, height=36, width=80, corner_radius=8,
            fg_color="transparent",
            border_color=C["card"], border_width=1,
            hover_color=C["lose"], text_color=C["muted"],
            command=self._on_reset,
        ).pack(side="left", padx=4)

        # Header status line (under buttons): used to surface scan progress.
        self._lbl_header_status = ctk.CTkLabel(
            header, text="", font=FONT_SMALL, text_color=C["muted"],
            anchor="e",
        )
        self._lbl_header_status.grid(
            row=1, column=0, columnspan=3,
            padx=24, pady=(0, 4), sticky="e",
        )

    # ── Card 1 — Stats principales ───────────────────────────

    def _build_main_stats_card(self, parent: ctk.CTkFrame, row: int) -> None:
        profile = self.controller.get_profile()

        # Wrapper row so HP / DMG can sit side-by-side and the attack-type
        # subline takes the full width — the rest of the dashboard stays
        # single-column at the scroll level.
        row_f = ctk.CTkFrame(parent, fg_color="transparent")
        row_f.grid(row=row, column=0, padx=16, pady=(16, 8), sticky="ew")
        row_f.grid_columnconfigure((0, 1), weight=1)

        self._hero_card(
            row_f, "❤  Total HP",
            fmt_number(profile.get("hp_total", 0)),
            "Base HP: " + fmt_number(profile.get("hp_base", 0)),
            C["lose"],
        ).grid(row=0, column=0, padx=(0, 8), sticky="ew")

        self._hero_card(
            row_f, "⚔  Total ATK",
            fmt_number(profile.get("attack_total", 0)),
            "Base ATK: " + fmt_number(profile.get("attack_base", 0)),
            C["accent2"],
        ).grid(row=0, column=1, padx=(8, 0), sticky="ew")

        # Attack-type subline below the two heroes (full-width).
        atk_type   = profile.get("attack_type", "?")
        type_label = "🏹 Ranged" if atk_type == "ranged" else "⚔ Melee"
        type_card  = ctk.CTkFrame(row_f, fg_color=C["card"], corner_radius=12)
        type_card.grid(row=1, column=0, columnspan=2,
                        padx=0, pady=(8, 0), sticky="ew")
        ctk.CTkLabel(
            type_card, text=f"Attack type: {type_label}",
            font=FONT_SUB, text_color=C["muted"],
        ).pack(padx=20, pady=10)

    @staticmethod
    def _hero_card(parent: ctk.CTkBaseClass, title: str, value: str,
                   subtitle: str, color: str) -> ctk.CTkFrame:
        """Compact hero card — title (muted) / big value / muted subtitle."""
        card = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=12)
        ctk.CTkLabel(card, text=title, font=FONT_SMALL,
                     text_color=C["muted"]).pack(anchor="w",
                                                   padx=20, pady=(16, 0))
        ctk.CTkLabel(card, text=value, font=FONT_BIG,
                     text_color=color).pack(anchor="w",
                                              padx=20, pady=(2, 0))
        ctk.CTkLabel(card, text=subtitle, font=FONT_SMALL,
                     text_color=C["muted"]).pack(anchor="w",
                                                   padx=20, pady=(0, 16))
        return card

    # ── Card 2 — Substats combat ──────────────────────────────

    def _build_substats_card(self, parent: ctk.CTkFrame, row: int) -> None:
        profile = self.controller.get_profile()

        outer = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=12)
        outer.grid(row=row, column=0, padx=16, pady=(0, 8), sticky="ew")
        outer.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            outer, text="Substats combat",
            font=FONT_SUB, text_color=C["text"],
        ).grid(row=0, column=0, padx=20, pady=(16, 8), sticky="w")

        rows_idx = 0
        any_value = False
        for key, label in _SUBSTAT_ROWS:
            val = float(profile.get(key, 0.0) or 0.0)
            if not val:
                # Plan §3: filter zero stats so the card doesn't become a
                # wall of "—" rows. The user can always check an empty
                # substat by re-importing the profile.
                continue
            any_value = True
            row_f = ctk.CTkFrame(
                outer,
                fg_color=C["card_alt"] if rows_idx % 2 == 0 else C["card"],
                corner_radius=6,
            )
            row_f.grid(row=rows_idx + 1, column=0, padx=12, pady=1, sticky="ew")
            row_f.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(
                row_f, text=label, font=FONT_BODY,
                text_color=C["muted"], anchor="w",
            ).grid(row=0, column=0, padx=16, pady=6, sticky="w")
            ctk.CTkLabel(
                row_f, text=f"{val:+.2f}%", font=FONT_MONO,
                text_color=C["text"], anchor="e",
            ).grid(row=0, column=2, padx=16, pady=6, sticky="e")
            rows_idx += 1

        if not any_value:
            ctk.CTkLabel(
                outer, text="(no substat detected — re-scan or paste your profile)",
                font=FONT_BODY, text_color=C["muted"],
            ).grid(row=1, column=0, padx=20, pady=(0, 16), sticky="w")
        else:
            ctk.CTkFrame(outer, fg_color="transparent", height=10).grid(
                row=rows_idx + 1, column=0)

    # ── Card 3 — Skills équipés ───────────────────────────────

    def _build_skills_card(self, parent: ctk.CTkFrame, row: int) -> None:
        skills = self.controller.get_active_skills()

        outer = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=12)
        outer.grid(row=row, column=0, padx=16, pady=(0, 16), sticky="ew")
        outer.grid_columnconfigure(0, weight=1)

        # Header row with title + "Edit in Skills" link (Plan §3 step 4).
        head = ctk.CTkFrame(outer, fg_color="transparent")
        head.grid(row=0, column=0, padx=16, pady=(14, 6), sticky="ew")
        head.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            head, text="Active skills", font=FONT_SUB, text_color=C["text"],
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            head, text="Edit in Skills →",
            font=FONT_TINY, height=24, corner_radius=6,
            fg_color="transparent",
            border_color=C["card_alt"], border_width=1,
            hover_color=C["border"], text_color=C["muted"],
            command=lambda: self.app.show_view("skills"),
        ).grid(row=0, column=1, padx=(8, 4), sticky="e")

        grid = ctk.CTkFrame(outer, fg_color="transparent")
        grid.grid(row=1, column=0, padx=10, pady=(0, 12), sticky="ew")
        grid.grid_columnconfigure((0, 1, 2), weight=1)

        if not skills:
            ctk.CTkLabel(
                grid, text="No skill equipped",
                font=FONT_BODY, text_color=C["disabled"],
            ).grid(row=0, column=0, columnspan=3, padx=20, pady=16)
            return

        # Pad to 3 slots — empty S2/S3 still shows a placeholder card.
        padded = list(skills) + [None] * max(0, 3 - len(skills))
        for col, entry in enumerate(padded[:3]):
            card = self._skill_card(grid, entry)
            card.grid(row=0, column=col, padx=10, pady=(0, 4),
                       sticky="nsew")

    # ── Card 4 — Pet & Mount actifs ──────────────────────────

    def _build_companions_card(self, parent: ctk.CTkFrame, row: int) -> None:
        outer = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=12)
        outer.grid(row=row, column=0, padx=16, pady=(0, 16), sticky="ew")
        outer.grid_columnconfigure(0, weight=1)

        # ── Header with section nav links ─────────────────────
        head = ctk.CTkFrame(outer, fg_color="transparent")
        head.grid(row=0, column=0, padx=16, pady=(14, 6), sticky="ew")
        head.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            head, text="Companions", font=FONT_SUB, text_color=C["text"],
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            head, text="Pets →", font=FONT_TINY, height=24, corner_radius=6,
            fg_color="transparent",
            border_color=C["card_alt"], border_width=1,
            hover_color=C["border"], text_color=C["muted"],
            command=lambda: self.app.show_view("pets"),
        ).grid(row=0, column=1, padx=(8, 4), sticky="e")
        ctk.CTkButton(
            head, text="Mount →", font=FONT_TINY, height=24, corner_radius=6,
            fg_color="transparent",
            border_color=C["card_alt"], border_width=1,
            hover_color=C["border"], text_color=C["muted"],
            command=lambda: self.app.show_view("mount"),
        ).grid(row=0, column=2, padx=(4, 4), sticky="e")

        # ── 3 pets + 1 mount in a 4-column row ────────────────
        grid = ctk.CTkFrame(outer, fg_color="transparent")
        grid.grid(row=1, column=0, padx=10, pady=(0, 12), sticky="ew")
        grid.grid_columnconfigure((0, 1, 2, 3), weight=1)

        pets = self.controller.get_pets() or {}
        for col, slot in enumerate(_PET_SLOTS):
            pet  = pets.get(slot, {}) or {}
            name = pet.get("__name__")
            rar  = pet.get("__rarity__")
            icon = load_pet_icon(name, size=44) if name else None
            card = ItemCard(
                grid,
                slot_label=f"{PET_ICONS.get(slot, '🐾')}  {slot}",
                name=name, rarity=rar, stats=pet,
                icon_image=icon, fallback_emoji="🐾",
                empty_text="(empty slot)",
            )
            card.grid(row=0, column=col, padx=4, pady=0, sticky="nsew")

        mount = self.controller.get_mount() or {}
        m_name = mount.get("__name__")
        m_rar  = mount.get("__rarity__")
        m_icon = load_mount_icon(m_name, size=44) if m_name else None
        mcard  = ItemCard(
            grid,
            slot_label=f"{MOUNT_ICON}  Mount",
            name=m_name, rarity=m_rar, stats=mount,
            icon_image=m_icon, fallback_emoji=MOUNT_ICON,
            empty_text="(no mount)",
        )
        mcard.grid(row=0, column=3, padx=4, pady=0, sticky="nsew")

    # ── Card 5 — Équipement ───────────────────────────────────

    def _build_equipment_card(self, parent: ctk.CTkFrame, row: int) -> None:
        outer = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=12)
        outer.grid(row=row, column=0, padx=16, pady=(0, 16), sticky="ew")
        outer.grid_columnconfigure(0, weight=1)

        head = ctk.CTkFrame(outer, fg_color="transparent")
        head.grid(row=0, column=0, padx=16, pady=(14, 6), sticky="ew")
        head.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            head, text="Equipment", font=FONT_SUB, text_color=C["text"],
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            head, text="Open Equipment →",
            font=FONT_TINY, height=24, corner_radius=6,
            fg_color="transparent",
            border_color=C["card_alt"], border_width=1,
            hover_color=C["border"], text_color=C["muted"],
            command=lambda: self.app.show_view("equipment"),
        ).grid(row=0, column=1, padx=(8, 4), sticky="e")

        grid = ctk.CTkFrame(outer, fg_color="transparent")
        grid.grid(row=1, column=0, padx=10, pady=(0, 12), sticky="ew")
        for c in range(4):
            grid.grid_columnconfigure(c, weight=1)

        equipment = self.controller.get_equipment() or {}
        for i, (slot_key, slot_name, emoji) in enumerate(_EQUIPMENT_SLOTS):
            data = equipment.get(slot_key, {}) or {}
            r, c = divmod(i, 4)
            mini = self._eq_mini_slot(grid, slot_key, slot_name, emoji, data)
            mini.grid(row=r, column=c, padx=4, pady=4, sticky="nsew")

    # ── Sub-widgets ───────────────────────────────────────────

    def _skill_card(self, parent, entry) -> ctk.CTkFrame:
        """Rich card for an equipped skill — icon, name, rarity/level
        badges, then damage/hits/cd stats (or buff stats) + passive
        bonuses.

        ``entry`` is the ``(code, data)`` tuple returned by
        ``controller.get_active_skills()``, or ``None`` for an empty slot.
        """
        card = ctk.CTkFrame(parent, fg_color=C["card_alt"], corner_radius=10)

        if entry is None:
            ctk.CTkLabel(
                card, text="— empty slot —",
                font=FONT_BODY, text_color=C["muted"],
            ).pack(padx=16, pady=28)
            return card

        code, data = entry
        name    = data.get("name") or data.get("__name__") or code.upper()
        rarity  = str(data.get("rarity") or data.get("__rarity__", "common")).lower()
        color   = rarity_color(rarity)
        sk_type = str(data.get("type", "damage"))
        type_ic = "⚔" if sk_type == "damage" else "🛡"

        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=12, pady=(12, 6))

        icon_img = load_skill_icon_by_name(name, size=44)
        ctk.CTkLabel(
            head,
            image=icon_img if icon_img else None,
            text="" if icon_img else type_ic,
            font=("Segoe UI", 24),
            text_color=color,
            width=48, height=48,
        ).pack(side="left", padx=(2, 8))

        info = ctk.CTkFrame(head, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(info, text=name, font=FONT_SUB,
                     text_color=C["text"], anchor="w").pack(anchor="w")

        meta_row = ctk.CTkFrame(info, fg_color="transparent")
        meta_row.pack(anchor="w", fill="x")
        ctk.CTkLabel(meta_row, text=rarity.upper(), font=FONT_TINY,
                     text_color=color, anchor="w").pack(side="left")
        ctk.CTkLabel(meta_row, text=f"[{code.upper()}]", font=FONT_TINY,
                     text_color=C["muted"], anchor="w").pack(
            side="left", padx=(8, 0))
        lvl = data.get("__level__")
        if lvl:
            ctk.CTkLabel(meta_row, text=f"Lv.{int(lvl)}", font=FONT_TINY,
                         text_color=C["accent"], anchor="w").pack(
                side="left", padx=(8, 0))

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=10, pady=(0, 12))

        rows = list(self._skill_stat_rows(data))
        pd   = float(data.get("passive_damage", 0) or 0)
        ph   = float(data.get("passive_hp",     0) or 0)
        if pd: rows.append(("⚔  Passive Dmg", fmt_number(pd)))
        if ph: rows.append(("❤  Passive HP",  fmt_number(ph)))

        for i, (lbl, val) in enumerate(rows):
            bg  = C["card"] if i % 2 == 0 else C["card_alt"]
            row = ctk.CTkFrame(inner, fg_color=bg, corner_radius=4)
            row.pack(fill="x", pady=1)
            row.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(row, text=lbl, font=FONT_SMALL,
                         text_color=C["muted"], anchor="w").grid(
                row=0, column=0, padx=10, pady=4, sticky="w")
            ctk.CTkLabel(row, text=val, font=FONT_MONO,
                         text_color=C["text"], anchor="e").grid(
                row=0, column=1, padx=10, pady=4, sticky="e")
        return card

    def _eq_mini_slot(self, parent, slot_key: str, slot_name: str,
                      emoji: str, data: Dict) -> ctk.CTkFrame:
        """Compact clickable card for one equipment slot.

        Layout (top → bottom):  emoji + slot name (muted) /
        item name (rarity-colored) /  Lv.X chip.
        Clicking anywhere on the card switches to the Equipment view
        with the matching slot pre-selected on the Comparer tab.
        """
        card = ctk.CTkFrame(parent, fg_color=C["card_alt"], corner_radius=10)

        name = data.get("__name__")
        rar  = data.get("__rarity__")
        lvl  = data.get("__level__")

        ctk.CTkLabel(
            card, text=f"{emoji}  {slot_name}",
            font=FONT_TINY, text_color=C["muted"], anchor="w",
        ).pack(padx=10, pady=(8, 2), anchor="w", fill="x")

        if name:
            ctk.CTkLabel(
                card, text=name, font=FONT_SMALL,
                text_color=rarity_color(rar) if rar else C["text"],
                anchor="w", wraplength=140, justify="left",
            ).pack(padx=10, pady=(0, 2), anchor="w", fill="x")
            if lvl:
                ctk.CTkLabel(
                    card, text=f"Lv.{int(lvl)}",
                    font=FONT_TINY, text_color=C["accent"], anchor="w",
                ).pack(padx=10, pady=(0, 8), anchor="w")
            else:
                ctk.CTkFrame(card, fg_color="transparent", height=8).pack()
        else:
            ctk.CTkLabel(
                card, text="(unscanned)", font=FONT_SMALL,
                text_color=C["disabled"], anchor="w",
            ).pack(padx=10, pady=(0, 8), anchor="w")

        # Bind click on every label — Tk does not bubble <Button-1> from a
        # Label up to its parent Frame, so we wire each child explicitly.
        def _bind_click(widget):
            try:
                widget.bind(
                    "<Button-1>",
                    lambda e, sk=slot_key: self._open_equipment_at_slot(sk),
                )
                widget.configure(cursor="hand2")
            except Exception:
                pass
            for child in widget.winfo_children():
                _bind_click(child)
        _bind_click(card)
        return card

    def _open_equipment_at_slot(self, slot_key: str) -> None:
        """Switch the main app to the Equipment view and ask it to focus
        on `slot_key` (Plan §3)."""
        try:
            self.app.show_view("equipment")
        except Exception:
            return
        view = self.app._view_cache.get("equipment")
        if view is not None and hasattr(view, "focus_slot"):
            view.focus_slot(slot_key)

    @staticmethod
    def _skill_stat_rows(data: Dict):
        """Yield (label, value) pairs for the active part of a skill."""
        sk_type = str(data.get("type", "damage"))
        if sk_type == "damage":
            dmg  = float(data.get("damage", 0) or 0)
            hits = int(data.get("hits", 1) or 1)
            cd   = float(data.get("cooldown", 0) or 0)
            if dmg:  yield ("⚔  Damage / hit", fmt_number(dmg))
            if hits: yield ("🔢 Hits",          str(hits))
            if cd:   yield ("⏱  Cooldown",      f"{cd:g}s")
        else:
            dur = float(data.get("buff_duration", 0) or 0)
            atk = float(data.get("buff_atk",      0) or 0)
            hp  = float(data.get("buff_hp",       0) or 0)
            cd  = float(data.get("cooldown",      0) or 0)
            if dur: yield ("⏳ Buff duration", f"{dur:g}s")
            if atk: yield ("⚔  Buff ATK",     fmt_number(atk))
            if hp:  yield ("❤  Buff HP",      fmt_number(hp))
            if cd:  yield ("⏱  Cooldown",     f"{cd:g}s")

    # ── Empty state ───────────────────────────────────────────

    def _empty_state(self, parent: ctk.CTkBaseClass) -> None:
        """Big CTA for the "no profile yet" path (Plan §3 step 7)."""
        wrapper = ctk.CTkFrame(parent, fg_color="transparent")
        wrapper.pack(expand=True, pady=80)

        ctk.CTkLabel(
            wrapper,
            text="No profile loaded yet",
            font=FONT_BIG, text_color=C["text"],
        ).pack(pady=(0, 8))
        ctk.CTkLabel(
            wrapper,
            text="Scan or paste your in-game profile to start using Forge Master.",
            font=FONT_BODY, text_color=C["muted"], justify="center",
        ).pack(pady=(0, 20))

        bar = ctk.CTkFrame(wrapper, fg_color="transparent")
        bar.pack()
        ctk.CTkButton(
            bar, text="📷  Scan profile",
            font=FONT_BODY, height=44, width=180, corner_radius=10,
            fg_color=C["accent"], hover_color=C["accent_hv"],
            command=self._on_scan_profile,
        ).pack(side="left", padx=6)
        ctk.CTkButton(
            bar, text="📋  Paste text",
            font=FONT_BODY, height=44, width=180, corner_radius=10,
            fg_color="transparent",
            border_color=C["card"], border_width=1,
            hover_color=C["border"], text_color=C["text"],
            command=self._open_import,
        ).pack(side="left", padx=6)

    # ── Header actions ────────────────────────────────────────

    def _open_import(self) -> None:
        ImportDialog(self, self.controller, self.app)

    def _on_scan_profile(self) -> None:
        """Trigger controller.scan('profile') and pipe the OCR text into
        ImportDialog so the user can confirm before saving (Plan §3
        path A). Pure controller call — no backend import (P1)."""
        self._lbl_header_status.configure(
            text="📷  Scanning profile…", text_color=C["accent"],
        )

        def _on_done(text: str, status: str) -> None:
            if status == "ocr_unavailable":
                self._lbl_header_status.configure(
                    text="⚠ OCR unavailable — install rapidocr_onnxruntime",
                    text_color=C["lose"])
                return
            if status == "zone_not_configured":
                self._lbl_header_status.configure(
                    text="⚠ Zone « profile » not configured — set the bbox in the Zones view first.",
                    text_color=C["lose"])
                return
            if status == "ocr_error":
                self._lbl_header_status.configure(
                    text="⚠ OCR failed.", text_color=C["lose"])
                return
            if status == "empty" or not text.strip():
                self._lbl_header_status.configure(
                    text="⚠ OCR returned no text — re-frame the bbox.",
                    text_color=C["lose"])
                return
            # Success: open the import dialog pre-filled so the user can
            # tweak the attack-type / skills before persisting.
            self._lbl_header_status.configure(
                text="✓ Scan ready — confirm to save.", text_color=C["win"])
            ImportDialog(self, self.controller, self.app, prefill_text=text)

        try:
            self.controller.scan(zone_key="profile", callback=_on_done)
        except Exception as e:  # noqa: BLE001
            self._lbl_header_status.configure(
                text=f"⚠ scan() raised: {e}", text_color=C["lose"])

    def _on_reset(self) -> None:
        if not confirm(
            self.app, "Reset profile",
            "Erase the current profile? Pets, mount, equipment and "
            "skills are kept — only the player stats are cleared.",
            ok_label="Reset", danger=True,
        ):
            return
        # set_profile({}) mirrors what other slot views do for "no slot".
        self.controller.set_profile({})
        self.app.refresh_current()


# ════════════════════════════════════════════════════════════
#  Profile import dialog
# ════════════════════════════════════════════════════════════

class ImportDialog(ctk.CTkToplevel):

    def __init__(self, parent, controller, app,
                  prefill_text: Optional[str] = None):
        super().__init__(parent)
        self.controller = controller
        self.app        = app
        self._prefill   = prefill_text
        self.title("Update profile")
        self.configure(fg_color=C["surface"])
        self.resizable(False, False)

        # Apply geometry FIRST + lock propagation so the window can't
        # auto-resize itself to fit its (potentially tall) contents.
        self.geometry(_PROFILE_DIALOG_GEOMETRY)
        self.grid_propagate(False)
        self.pack_propagate(False)

        self.transient(parent)

        self._build()

        # Re-assert the geometry after children are placed, in case
        # CustomTkinter scheduled an autosize on the idle queue.
        self.after(0, lambda: self.geometry(_PROFILE_DIALOG_GEOMETRY))

        self.grab_set()

    def _build(self) -> None:
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0, minsize=64)
        self.grid_columnconfigure(0, weight=1)

        content = ctk.CTkScrollableFrame(
            self, fg_color=C["surface"], corner_radius=0,
        )
        content.grid(row=0, column=0, sticky="nsew")

        btn_bar = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=0,
                                height=64)
        btn_bar.grid(row=1, column=0, sticky="ew")
        btn_bar.grid_propagate(False)

        self._lbl_btn_status = ctk.CTkLabel(
            btn_bar, text="", font=FONT_SMALL, text_color=C["lose"])
        self._lbl_btn_status.pack(side="left", padx=24)

        ctk.CTkButton(btn_bar, text="Cancel", fg_color=C["border"],
                      hover_color=C["border_hl"], font=FONT_BODY, width=120,
                      command=self.destroy).pack(side="right", padx=(8, 24),
                                                  pady=14)
        ctk.CTkButton(btn_bar, text="✓  Save",
                      fg_color=C["accent"], hover_color=C["accent_hv"],
                      font=FONT_BODY, width=160,
                      command=self._save).pack(side="right", pady=14)

        ctk.CTkLabel(content, text="Paste the profile text",
                     font=("Segoe UI", 16, "bold"),
                     text_color=C["text"]).pack(padx=24, pady=(20, 4),
                                                 anchor="w")

        ctk.CTkLabel(content,
                     text="Copy the stat summary from the game and paste it below",
                     font=FONT_BODY, text_color=C["muted"]).pack(
            padx=24, pady=(0, 8), anchor="w")

        self.text_box = ctk.CTkTextbox(
            content, height=180, font=FONT_MONO,
            fg_color=C["bg"], text_color=C["text"],
            border_color=C["border"], border_width=1,
        )
        self.text_box.pack(padx=24, pady=(0, 4), fill="x")

        # Pre-fill with OCR text if the dialog was opened from a successful
        # « Scan profile » header click (Plan §3 path A).
        if self._prefill:
            self.text_box.insert("1.0", self._prefill)

        scan_row = ctk.CTkFrame(content, fg_color="transparent")
        scan_row.pack(padx=24, pady=(0, 10), fill="x")
        self._lbl_scan_status = ctk.CTkLabel(
            scan_row, text="", font=FONT_SMALL, text_color=C["muted"])
        self._lbl_scan_status.pack(side="right", padx=(8, 0))
        attach_scan_button(
            parent_btn_frame=scan_row,
            textbox=self.text_box,
            status_lbl=self._lbl_scan_status,
            scan_key="profile",
            scan_fn=self.controller.scan,
            captures_fn=self.controller.get_zone_captures,
        )

        type_frame = ctk.CTkFrame(content, fg_color=C["card"], corner_radius=8)
        type_frame.pack(padx=24, pady=(0, 12), fill="x")
        ctk.CTkLabel(type_frame, text="Attack type:",
                     font=FONT_BODY, text_color=C["text"]).pack(
            side="left", padx=16, pady=10)
        self.type_var = ctk.StringVar(value="ranged")
        ctk.CTkRadioButton(type_frame, text="🏹 Ranged",
                           variable=self.type_var, value="ranged",
                           text_color=C["text"]).pack(side="left", padx=16,
                                                       pady=10)
        ctk.CTkRadioButton(type_frame, text="⚔ Melee",
                           variable=self.type_var, value="melee",
                           text_color=C["text"]).pack(side="left", padx=8,
                                                       pady=10)

        ctk.CTkLabel(content, text="Active skills — select up to 3",
                     font=FONT_BODY, text_color=C["text"]).pack(
            padx=24, pady=(0, 6), anchor="w")

        all_skills    = self.controller.get_all_skills()
        current_codes = {c for c, _ in self.controller.get_active_skills()}
        self._skill_vars = {
            code: ctk.BooleanVar(value=(code in current_codes))
            for code in all_skills
        }

        sk_frame, _btns = skill_icon_grid(
            content, all_skills, self._skill_vars, on_toggle=self._toggle_skill,
        )
        sk_frame.pack(padx=24, pady=(0, 4), fill="x")

        self._skill_limit_label = ctk.CTkLabel(
            content, text="", font=FONT_SMALL, text_color=C["lose"])
        self._skill_limit_label.pack(padx=24, pady=(0, 16))

    def _toggle_skill(self, code: str) -> None:
        var      = self._skill_vars[code]
        selected = [c for c, v in self._skill_vars.items() if v.get()]
        if not var.get():
            if len(selected) >= 3:
                self._skill_limit_label.configure(text="⚠ Maximum of 3 active skills")
                return
            var.set(True)
        else:
            var.set(False)
        self._skill_limit_label.configure(text="")

    def _save(self) -> None:
        text = self.text_box.get("1.0", "end").strip()
        if not text:
            self._lbl_btn_status.configure(text="⚠ Paste the profile text first")
            return

        selected = [c for c, v in self._skill_vars.items() if v.get()]
        if len(selected) > 3:
            self._lbl_btn_status.configure(text="⚠ Maximum of 3 active skills")
            return

        attack_type = self.type_var.get()
        profile     = self.controller.import_profile_text(text, attack_type)
        skills      = self.controller.get_skills_from_codes(selected)
        self.controller.set_profile(profile, skills)

        self.destroy()
        self.app.refresh_current()
