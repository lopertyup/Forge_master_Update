"""
============================================================
  FORGE MASTER UI — Dashboard
  Show all the player's stats + active skills.
============================================================
"""

from typing import Dict

import customtkinter as ctk

from backend.constants import EQUIPMENT_SLOTS, EQUIPMENT_SLOT_NAMES
from ui.theme import (
    C,
    FONT_BIG,
    FONT_BODY,
    FONT_MONO,
    FONT_SMALL,
    FONT_SUB,
    FONT_TITLE,
    FONT_TINY,
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
    companion_slot_card,
    skill_icon_grid,
    stat_hero_card,
)

_PET_SLOTS = ("PET1", "PET2", "PET3")

_SLOT_EMOJI = {
    "EQUIP_HELMET":   "🪖",
    "EQUIP_BODY":     "🦺",
    "EQUIP_GLOVES":   "🧤",
    "EQUIP_NECKLACE": "📿",
    "EQUIP_RING":     "💍",
    "EQUIP_WEAPON":   "⚔",
    "EQUIP_SHOE":     "👢",
    "EQUIP_BELT":     "🎗",
}

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

    def _build(self) -> None:
        # ── Header with import button ───────────────────────
        header = ctk.CTkFrame(self, fg_color=C["surface"], corner_radius=0,
                               height=64)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(header, text="Dashboard",
                     font=FONT_TITLE, text_color=C["text"]).grid(
            row=0, column=0, padx=24, pady=16, sticky="w")

        ctk.CTkButton(
            header, text="⟳ Update profile",
            font=FONT_BODY, height=36, corner_radius=8,
            fg_color=C["accent"], hover_color=C["accent_hv"],
            command=self._open_import,
        ).grid(row=0, column=2, padx=24, pady=14, sticky="e")

        # ── Scrollable body ─────────────────────────────────
        scroll = ctk.CTkScrollableFrame(self, fg_color=C["bg"],
                                         corner_radius=0)
        scroll.grid(row=1, column=0, sticky="nsew")
        scroll.grid_columnconfigure((0, 1), weight=1)

        profile = self.controller.get_profile()
        if not profile:
            self._empty_state(scroll)
            return

        # ── HP & ATK cards ─────────────────────────────────
        hp_card = stat_hero_card(
            scroll, "❤  Total HP",
            fmt_number(profile.get("hp_total", 0)),
            "Base HP: " + fmt_number(profile.get("hp_base", 0)),
            C["lose"])
        hp_card.grid(row=0, column=0, padx=(16, 8), pady=(16, 8), sticky="ew")

        atk_card = stat_hero_card(
            scroll, "⚔  Total ATK",
            fmt_number(profile.get("attack_total", 0)),
            "Base ATK: " + fmt_number(profile.get("attack_base", 0)),
            C["accent2"])
        atk_card.grid(row=0, column=1, padx=(8, 16), pady=(16, 8), sticky="ew")

        # ── Attack type ────────────────────────────────────
        atk_type   = profile.get("attack_type", "?")
        type_label = "🏹 Ranged" if atk_type == "ranged" else "⚔ Melee"
        type_card  = ctk.CTkFrame(scroll, fg_color=C["card"], corner_radius=12)
        type_card.grid(row=1, column=0, columnspan=2, padx=16, pady=(0, 8),
                        sticky="ew")
        ctk.CTkLabel(type_card, text=f"Attack type: {type_label}",
                     font=FONT_SUB, text_color=C["muted"]).pack(
            padx=20, pady=10)

        # ── Equipment (8 slots) ─────────────────────────────
        self._build_equipment_section(scroll)

        # ── Secondary stats ────────────────────────────────
        stats_frame = ctk.CTkFrame(scroll, fg_color=C["card"], corner_radius=12)
        stats_frame.grid(row=3, column=0, columnspan=2, padx=16, pady=(0, 8),
                          sticky="ew")
        stats_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(stats_frame, text="Detailed stats",
                     font=FONT_SUB, text_color=C["text"]).grid(
            row=0, column=0, padx=20, pady=(16, 8), sticky="w")

        # Canonical in-game substat order.
        stat_rows = [
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
        ]

        for i, (key, label) in enumerate(stat_rows):
            val = profile.get(key, 0.0)
            row_f = ctk.CTkFrame(
                stats_frame,
                fg_color=C["card_alt"] if i % 2 == 0 else C["card"],
                corner_radius=6,
            )
            row_f.grid(row=i + 1, column=0, padx=12, pady=1, sticky="ew")
            row_f.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(row_f, text=label, font=FONT_BODY,
                         text_color=C["muted"], anchor="w").grid(
                row=0, column=0, padx=16, pady=6, sticky="w")

            color = C["text"] if val else C["disabled"]
            ctk.CTkLabel(
                row_f,
                text=f"{val:+.2f}%" if val else "—",
                font=FONT_MONO, text_color=color, anchor="e",
            ).grid(row=0, column=2, padx=16, pady=6, sticky="e")

        ctk.CTkFrame(stats_frame, fg_color="transparent", height=8).grid(
            row=len(stat_rows) + 1, column=0)

        # ── Active skills ───────────────────────────────────
        skills   = self.controller.get_active_skills()
        sk_frame = ctk.CTkFrame(scroll, fg_color=C["card"], corner_radius=12)
        sk_frame.grid(row=4, column=0, columnspan=2, padx=16, pady=(0, 16),
                       sticky="ew")
        sk_frame.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkLabel(sk_frame, text="Active skills",
                     font=FONT_SUB, text_color=C["text"]).grid(
            row=0, column=0, columnspan=3, padx=20, pady=(16, 8), sticky="w")

        if not skills:
            ctk.CTkLabel(sk_frame, text="No skill equipped",
                         font=FONT_BODY, text_color=C["disabled"]).grid(
                row=1, column=0, columnspan=3, padx=20, pady=16)
        else:
            # Pad to 3 slots so an empty S2/S3 still shows a placeholder card.
            padded = list(skills) + [None] * max(0, 3 - len(skills))
            for col, entry in enumerate(padded[:3]):
                card = self._skill_card(sk_frame, entry)
                card.grid(row=1, column=col, padx=10, pady=(0, 12),
                           sticky="nsew")

        ctk.CTkFrame(sk_frame, fg_color="transparent", height=8).grid(
            row=2, column=0)

        # ── Pets (3 slots) ──────────────────────────────────
        pets_outer = ctk.CTkFrame(scroll, fg_color=C["card"], corner_radius=12)
        pets_outer.grid(row=5, column=0, columnspan=2, padx=16, pady=(0, 16),
                         sticky="ew")
        pets_outer.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(pets_outer, text="Pets",
                     font=FONT_SUB, text_color=C["text"]).grid(
            row=0, column=0, padx=20, pady=(16, 8), sticky="w")

        pets_row = ctk.CTkFrame(pets_outer, fg_color="transparent")
        pets_row.grid(row=1, column=0, padx=10, pady=(0, 12), sticky="ew")
        pets_row.grid_columnconfigure((0, 1, 2), weight=1)

        pets = self.controller.get_pets() or {}
        for col, slot in enumerate(_PET_SLOTS):
            pet   = pets.get(slot, {}) or {}
            name  = pet.get("__name__")
            rar   = pet.get("__rarity__")
            icon  = load_pet_icon(name, size=44) if name else None
            card  = companion_slot_card(
                pets_row,
                slot_label=f"{PET_ICONS.get(slot, '🐾')}  {slot}",
                name=name,
                rarity=rar,
                stats=pet,
                icon_image=icon,
                fallback_emoji="🐾",
                empty_text="(empty slot)",
            )
            card.grid(row=0, column=col, padx=6, pady=0, sticky="nsew")

        # ── Mount (single slot) ─────────────────────────────
        mount_outer = ctk.CTkFrame(scroll, fg_color=C["card"], corner_radius=12)
        mount_outer.grid(row=6, column=0, columnspan=2, padx=16, pady=(0, 16),
                          sticky="ew")
        mount_outer.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(mount_outer, text="Mount",
                     font=FONT_SUB, text_color=C["text"]).grid(
            row=0, column=0, padx=20, pady=(16, 8), sticky="w")

        mount = self.controller.get_mount() or {}
        m_name = mount.get("__name__")
        m_rar  = mount.get("__rarity__")
        m_icon = load_mount_icon(m_name, size=48) if m_name else None
        mount_card = companion_slot_card(
            mount_outer,
            slot_label=f"{MOUNT_ICON}  Current mount",
            name=m_name,
            rarity=m_rar,
            stats=mount,
            icon_image=m_icon,
            fallback_emoji=MOUNT_ICON,
            empty_text="(no mount registered)",
        )
        mount_card.grid(row=1, column=0, padx=16, pady=(0, 12), sticky="ew")

    # ── Sub-widgets ─────────────────────────────────────────

    def _skill_card(self, parent, entry) -> ctk.CTkFrame:
        """Rich card for an equipped skill — icon, name, rarity/level badges,
        then damage/hits/cd stats (or buff stats) + passive bonuses.

        ``entry`` is the ``(code, data)`` tuple returned by
        ``controller.get_active_skills()``, or ``None`` for an empty slot.
        """
        card = ctk.CTkFrame(parent, fg_color=C["card_alt"], corner_radius=10)

        if entry is None:
            ctk.CTkLabel(card, text="— empty slot —",
                         font=FONT_BODY, text_color=C["muted"]).pack(
                padx=16, pady=28)
            return card

        code, data = entry
        name    = data.get("name") or data.get("__name__") or code.upper()
        rarity  = str(data.get("rarity") or data.get("__rarity__", "common")).lower()
        color   = rarity_color(rarity)
        sk_type = str(data.get("type", "damage"))
        type_ic = "⚔" if sk_type == "damage" else "🛡"

        # Identity band: icon + name + rarity/level badges
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

        # Stats block
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

    # ── Equipment section (ported from BuildView) ────────

    def _build_equipment_section(self, scroll) -> None:
        equip_outer = ctk.CTkFrame(scroll, fg_color=C["card"], corner_radius=12)
        equip_outer.grid(row=2, column=0, columnspan=2, padx=16, pady=(0, 8),
                         sticky="ew")
        equip_outer.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(equip_outer, text="🛡 Equipment",
                     font=FONT_SUB, text_color=C["text"]).grid(
            row=0, column=0, padx=20, pady=(16, 8), sticky="w")

        bar = ctk.CTkFrame(equip_outer, fg_color="transparent")
        bar.grid(row=1, column=0, padx=16, pady=(0, 6), sticky="ew")
        bar.grid_columnconfigure(2, weight=1)

        ctk.CTkButton(
            bar, text="📷  Scan Build",
            font=FONT_SMALL, width=160,
            command=self._on_equipment_scan_clicked,
        ).grid(row=0, column=0, padx=(0, 8))

        ctk.CTkButton(
            bar, text="🔄  Reload",
            font=FONT_SMALL, width=120,
            fg_color="transparent",
            border_color=C["card"], border_width=1,
            command=self._refresh_equipment_slots,
        ).grid(row=0, column=1, padx=(0, 8))

        self._equip_status_lbl = ctk.CTkLabel(
            bar, text="", font=FONT_SMALL,
            text_color=C["muted"], anchor="w",
        )
        self._equip_status_lbl.grid(row=0, column=2, sticky="ew")

        self._equip_grid = ctk.CTkFrame(equip_outer, fg_color="transparent")
        self._equip_grid.grid(row=2, column=0, padx=16, pady=(0, 12),
                              sticky="ew")
        for c in range(4):
            self._equip_grid.grid_columnconfigure(c, weight=1)

        self._refresh_equipment_slots()

    def _refresh_equipment_slots(self) -> None:
        for child in self._equip_grid.winfo_children():
            child.destroy()

        equipment = self.controller.get_equipment()
        for i, slot_key in enumerate(EQUIPMENT_SLOTS):
            slot_name = EQUIPMENT_SLOT_NAMES[i]
            data = equipment.get(slot_key, {}) or {}
            name = data.get("__name__")
            rar  = data.get("__rarity__")

            stats = {}
            if data.get("__level__") is not None:
                stats["__level__"] = data.get("__level__")
            hp_flat = data.get("hp_flat")
            dmg_flat = data.get("damage_flat")
            if hp_flat:
                stats["hp_flat"] = float(hp_flat)
            if dmg_flat:
                stats["damage_flat"] = float(dmg_flat)
            atype = data.get("attack_type")
            if atype:
                stats["attack_type"] = atype

            card = companion_slot_card(
                self._equip_grid,
                slot_label=f"{_SLOT_EMOJI.get(slot_key, '🛡')}  {slot_name}",
                name=name,
                rarity=rar,
                stats=stats,
                fallback_emoji=_SLOT_EMOJI.get(slot_key, "🛡"),
                empty_text="(unscanned)",
            )
            row, col = divmod(i, 4)
            card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")

        n_filled = sum(1 for v in equipment.values()
                       if isinstance(v, dict) and v.get("__name__"))
        self._equip_status_lbl.configure(
            text=f"{n_filled}/8 slots populated",
            text_color=C["muted"],
        )

    def _on_equipment_scan_clicked(self) -> None:
        self._equip_status_lbl.configure(text="📷  Scanning ...",
                                         text_color=C["accent"])

        def _on_done(text: str, status: str) -> None:
            if status == "ocr_unavailable":
                self._equip_status_lbl.configure(
                    text="⚠  OCR unavailable -- install rapidocr_onnxruntime",
                    text_color=C["lose"])
                return
            if status == "zone_not_configured":
                self._equip_status_lbl.configure(
                    text="⚠  Zone player_equipment not configured -- "
                         "set the bbox in the Zones tab first",
                    text_color=C["lose"])
                return
            if status == "ocr_error":
                self._equip_status_lbl.configure(
                    text="⚠  OCR failed", text_color=C["lose"])
                return
            self._refresh_equipment_slots()
            self._equip_status_lbl.configure(
                text="✅  Scan applied",
                text_color=C["win"])

        try:
            self.controller.scan(zone_key="player_equipment", callback=_on_done)
        except Exception as e:
            self._equip_status_lbl.configure(
                text=f"⚠  scan() raised: {e}",
                text_color=C["lose"])

    def _empty_state(self, parent: ctk.CTkBaseClass) -> None:
        ctk.CTkLabel(
            parent,
            text="No profile found\n\nClick « Update profile »\nto import your stats from the game",
            font=FONT_BODY, text_color=C["disabled"], justify="center",
        ).pack(expand=True, pady=80)

    def _open_import(self) -> None:
        ImportDialog(self, self.controller, self.app)


# ════════════════════════════════════════════════════════════
#  Profile import dialog
# ════════════════════════════════════════════════════════════

class ImportDialog(ctk.CTkToplevel):

    def __init__(self, parent, controller, app):
        super().__init__(parent)
        self.controller = controller
        self.app        = app
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
        # Grid layout: row 0 = scrollable content (expands), row 1 = button
        # bar (fixed 64 px). This guarantees the Save/Cancel row stays
        # visible even when the content overflows.
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0, minsize=64)
        self.grid_columnconfigure(0, weight=1)

        # ── Scrollable body (row 0) ───────────────────────────
        content = ctk.CTkScrollableFrame(
            self, fg_color=C["surface"], corner_radius=0,
        )
        content.grid(row=0, column=0, sticky="nsew")

        # ── Button bar (row 1) ────────────────────────────────
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

        # ── Scan row (OCR button + status) ─────────────────
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

        # Attack type
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

        # Skills
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