"""
============================================================
  FORGE MASTER UI — Mount Management

  Phase-3 refactor (UI_REFACTOR_PLAN §11):
  3-tab layout (CTkTabview) — same flow as Pets / Skills /
  Equipment > Comparer:

      [Équipée]   [Comparer]   [Librairie]

    * Équipée   : the persisted mount + Scan / Paste actions
                  (and a Remove button if a mount is registered).
    * Comparer  : SwapPanel (current vs candidate) + Compare
                  button + ResultDelta (apply / discard).
    * Librairie : LibraryList of every collected mount, with
                  rarity filter chips + per-row Compare / Delete.

  All shared widgets come from ui/cards.py (Phase-2 module).
============================================================
"""

from typing import Dict, Optional

import customtkinter as ctk

from ui.theme import (
    C, FONT_BODY, FONT_SMALL, FONT_SUB,
    MOUNT_ICON, load_mount_icon,
)
from ui.widgets import (
    build_header,
    build_import_zone,
    confirm,
)
from ui.cards import (
    ItemCard,
    LibraryList,
    ResultDelta,
    SwapPanel,
)
from backend.constants import N_SIMULATIONS


class MountView(ctk.CTkFrame):

    def __init__(self, parent, controller, app):
        super().__init__(parent, fg_color=C["bg"], corner_radius=0)
        self.controller = controller
        self.app        = app

        # Currently parsed candidate (set by _resolve_candidate, consumed by
        # _on_compare / _apply_after_compare). Lives on the instance because
        # the result callback is async.
        self._candidate: Optional[Dict] = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build()

    # ── Build ─────────────────────────────────────────────────

    def _build(self) -> None:
        build_header(self, f"{MOUNT_ICON}  Mount Management")

        self._tabs = ctk.CTkTabview(
            self,
            fg_color=C["bg"],
            segmented_button_fg_color=C["card"],
            segmented_button_selected_color=C["accent"],
            segmented_button_selected_hover_color=C["accent"],
        )
        self._tabs.grid(row=1, column=0, sticky="nsew", padx=8, pady=(8, 8))

        self._build_equipped_tab(self._tabs.add("Équipée"))
        self._build_compare_tab(self._tabs.add("Comparer"))
        self._build_library_tab(self._tabs.add("Librairie"))

    # ── Tab 1 — Équipée ──────────────────────────────────────

    def _build_equipped_tab(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(parent, fg_color=C["bg"],
                                         corner_radius=0)
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        mount = self.controller.get_mount() or {}
        name  = mount.get("__name__")
        rar   = mount.get("__rarity__")
        icon  = load_mount_icon(name, size=48) if name else None

        card = ItemCard(
            scroll,
            slot_label=f"{MOUNT_ICON}  Current mount",
            name=name,
            rarity=rar,
            stats=mount,
            icon_image=icon,
            fallback_emoji=MOUNT_ICON,
            empty_text="(no mount registered)",
        )
        card.grid(row=0, column=0, padx=16, pady=16, sticky="ew")

        # Quick-actions row — Scan / Paste / Remove.
        bar = ctk.CTkFrame(scroll, fg_color="transparent")
        bar.grid(row=1, column=0, padx=16, pady=(0, 16), sticky="ew")
        bar.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkButton(
            bar, text="↪  Go to « Comparer »",
            font=FONT_SMALL, height=34, corner_radius=8,
            fg_color=C["accent"], hover_color=C["accent_hv"],
            command=lambda: self._tabs.set("Comparer"),
        ).grid(row=0, column=0, padx=(0, 4), sticky="ew")

        ctk.CTkButton(
            bar, text="📚  Open library",
            font=FONT_SMALL, height=34, corner_radius=8,
            fg_color="transparent", border_color=C["card"], border_width=1,
            hover_color=C["border"], text_color=C["text"],
            command=lambda: self._tabs.set("Librairie"),
        ).grid(row=0, column=1, padx=4, sticky="ew")

        # Remove button only useful when a mount is currently equipped.
        rm_state = "normal" if name else "disabled"
        ctk.CTkButton(
            bar, text="🗑  Unequip",
            font=FONT_SMALL, height=34, corner_radius=8,
            fg_color="transparent", border_color=C["card"], border_width=1,
            hover_color=C["lose"], text_color=C["muted"],
            state=rm_state,
            command=self._unequip,
        ).grid(row=0, column=2, padx=(4, 0), sticky="ew")

    def _unequip(self) -> None:
        if not confirm(
            self.app, "Unequip mount",
            "Remove the current mount from the active build?",
            ok_label="Unequip", danger=True,
        ):
            return
        # `set_mount({})` mirrors what other slot views do for "no slot"
        # — the controller just persists the empty dict, which downstream
        # treats as "no mount equipped".
        self.controller.set_mount({})
        self.app.refresh_current()

    # ── Tab 2 — Comparer ─────────────────────────────────────

    def _build_compare_tab(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        # Top: shared paste / scan import zone (same UX as before).
        import_card, self._textbox, self._lbl_status = build_import_zone(
            parent,
            title="Candidate mount",
            hint="Paste the mount stats from the game, or scan with the camera button.",
            primary_label="🔬  Compare (1000 fights)",
            primary_cmd=self._on_compare,
            secondary_label="💾  Save without testing",
            secondary_cmd=self._save_direct,
            scan_key="mount",
            scan_fn=self.controller.scan,
            captures_fn=self.controller.get_zone_captures,
            on_scan_ready=self._on_compare,
        )
        import_card.grid(row=0, column=0, padx=16, pady=(12, 8), sticky="ew")

        # Middle: SwapPanel (current vs candidate + result slot).
        self._swap = SwapPanel(
            parent,
            left_title="Equipped mount",
            right_title="Candidate mount (paste above first)",
            on_compare=None,                # the import card already has it
        )
        self._swap.outer.grid(row=1, column=0, padx=16, pady=(0, 16),
                               sticky="nsew")

        self._refresh_swap_left()
        self._refresh_swap_right(None)

    def _refresh_swap_left(self) -> None:
        self._swap.clear_left()
        mount = self.controller.get_mount() or {}
        name  = mount.get("__name__")
        rar   = mount.get("__rarity__")
        icon  = load_mount_icon(name, size=48) if name else None
        ItemCard(
            self._swap.left_slot,
            slot_label=f"{MOUNT_ICON}  Current",
            name=name, rarity=rar, stats=mount,
            icon_image=icon, fallback_emoji=MOUNT_ICON,
            empty_text="(no mount equipped)",
        ).pack(fill="both", expand=True)

    def _refresh_swap_right(self, candidate: Optional[Dict]) -> None:
        self._swap.clear_right()
        if not candidate:
            ItemCard(
                self._swap.right_slot,
                slot_label=f"{MOUNT_ICON}  Candidate",
                name=None, rarity=None, stats={},
                fallback_emoji=MOUNT_ICON,
                empty_text="(no candidate yet — paste or scan)",
            ).pack(fill="both", expand=True)
            return
        name = candidate.get("__name__")
        rar  = candidate.get("__rarity__")
        icon = load_mount_icon(name, size=48) if name else None
        ItemCard(
            self._swap.right_slot,
            slot_label=f"{MOUNT_ICON}  Candidate",
            name=name, rarity=rar, stats=candidate,
            icon_image=icon, fallback_emoji=MOUNT_ICON,
        ).pack(fill="both", expand=True)

    # ── Compare flow ─────────────────────────────────────────

    def _resolve_candidate(self, text: str) -> Optional[Dict]:
        """Parse the textbox into a normalised mount dict, or post an
        error in the status label and return None."""
        candidate, status, meta = self.controller.resolve_mount(text)

        if status == "no_name":
            self._lbl_status.configure(
                text="⚠ Could not read the mount name (expected: « [Rarity] Name »).",
                text_color=C["lose"])
            return None
        if status == "unknown":
            name = meta.get("name") if meta else "?"
            self._lbl_status.configure(
                text=f"⚠ « {name} » is not in the library — check the spelling or "
                     "add it manually to mount_library.txt.",
                text_color=C["lose"])
            return None
        return candidate

    def _on_compare(self) -> None:
        # Tab may not have been built yet if the user clicks Scan from the
        # Equipped tab — switch over first to make the result visible.
        try:
            self._tabs.set("Comparer")
        except Exception:
            pass

        if not self.controller.has_profile():
            self._lbl_status.configure(
                text="⚠ No player profile. Go to Dashboard first.",
                text_color=C["lose"])
            return

        text = self._textbox.get("1.0", "end").strip()
        if not text:
            self._lbl_status.configure(text="⚠ Paste the mount stats.",
                                        text_color=C["lose"])
            return

        candidate = self._resolve_candidate(text)
        if candidate is None:
            return

        self._candidate = candidate
        self._refresh_swap_right(candidate)
        self._swap.clear_result()

        self._lbl_status.configure(text="⏳ Simulation running…",
                                    text_color=C["muted"])
        self.update_idletasks()

        def on_result(w: int, l: int, d: int) -> None:
            self._lbl_status.configure(text="", text_color=C["muted"])
            self._render_result(w, l, d, candidate)

        self.controller.test_mount(candidate, on_result)

    def _render_result(self, wins: int, loses: int, draws: int,
                        candidate: Dict) -> None:
        self._swap.clear_result()
        ResultDelta(
            self._swap.result_slot,
            wins, loses, draws,
            total=N_SIMULATIONS,
            title="Result — New mount vs Old mount",
            subtitle="Both mounts are flattened to Lv.1 stats for fairness.",
            on_apply=lambda c=candidate: self._apply(c),
            on_discard=self._clear_compare,
            apply_label="💾  Apply this mount",
            discard_label="✖  Keep current",
        ).pack(fill="x")

    def _apply(self, candidate: Dict) -> None:
        if not confirm(
            self.app, "Confirm replacement",
            f"Replace the current mount with « {candidate.get('__name__', '?')} »?",
            ok_label="Replace", danger=False,
        ):
            return
        self.controller.set_mount(candidate)
        self._lbl_status.configure(text="✅ Mount updated!",
                                    text_color=C["win"])
        self.app.refresh_current()

    def _clear_compare(self) -> None:
        self._candidate = None
        self._refresh_swap_right(None)
        self._swap.clear_result()
        self._textbox.delete("1.0", "end")
        self._lbl_status.configure(text="", text_color=C["muted"])

    def _save_direct(self) -> None:
        text = self._textbox.get("1.0", "end").strip()
        if not text:
            self._lbl_status.configure(
                text="⚠ Paste the mount stats first.",
                text_color=C["lose"])
            return

        candidate = self._resolve_candidate(text)
        if candidate is None:
            return

        if not confirm(
            self.app, "Save without simulating",
            "Save this mount without testing if it's better than the current one?",
            ok_label="Save", danger=False,
        ):
            return
        self.controller.set_mount(candidate)
        self._lbl_status.configure(text="✅ Mount saved!",
                                    text_color=C["win"])
        self.app.refresh_current()

    # ── Tab 3 — Librairie ────────────────────────────────────

    def _build_library_tab(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        # Hint card on top — explains why the library exists at Lv.1.
        hint = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=12)
        hint.grid(row=0, column=0, padx=16, pady=(12, 6), sticky="ew")
        ctk.CTkLabel(
            hint,
            text="📚  Mount Library",
            font=FONT_SUB, text_color=C["text"],
        ).pack(padx=16, pady=(12, 2), anchor="w")
        ctk.CTkLabel(
            hint,
            text=("Every mount you've pasted is kept here at its Lv.1 reference. "
                  "Use the 🔬 Compare button on a row to dispatch it as a candidate."),
            font=FONT_SMALL, text_color=C["muted"],
            wraplength=700, justify="left",
        ).pack(padx=16, pady=(0, 12), anchor="w")

        library = self.controller.get_mount_library() or {}
        items   = self._library_items(library)

        list_frame, _ctrl = LibraryList(
            parent,
            items,
            title="Collected mounts",
            hint=None,
            filters={"rarity": self._available_rarities(items)} if items else None,
            on_action=self._library_use_as_candidate,
            on_delete=self._library_delete,
            icon_loader=lambda name: load_mount_icon(name, size=40),
            fallback_emoji=MOUNT_ICON,
            max_height=420,
        )
        list_frame.grid(row=1, column=0, padx=16, pady=(0, 16), sticky="nsew")

    @staticmethod
    def _library_items(library: Dict[str, Dict]) -> list:
        rows = []
        for name, entry in library.items():
            rows.append({
                "key":         name,
                "name":        name,
                "rarity":      str(entry.get("rarity", "common")).lower(),
                "hp_flat":     entry.get("hp_flat", 0),
                "damage_flat": entry.get("damage_flat", 0),
            })
        return rows

    @staticmethod
    def _available_rarities(items: list) -> list:
        seen = []
        for it in items:
            r = it.get("rarity")
            if r and r not in seen:
                seen.append(r)
        return seen

    def _library_use_as_candidate(self, item: Dict) -> None:
        """Drop a library row into the Comparer tab as a candidate.
        We rebuild a paste-like text so resolve_mount() can normalise it
        the same way as a manual paste."""
        name   = item.get("name", "?")
        rarity = str(item.get("rarity", "common")).title()
        hp     = item.get("hp_flat") or 0
        dmg    = item.get("damage_flat") or 0
        text = (f"[{rarity}] {name}\n"
                f"Lv.1\n"
                f"+{int(dmg)} Damage\n"
                f"+{int(hp)} Health\n")
        try:
            self._tabs.set("Comparer")
        except Exception:
            pass
        self._textbox.delete("1.0", "end")
        self._textbox.insert("1.0", text)
        self._on_compare()

    def _library_delete(self, item: Dict) -> None:
        name = item.get("name") or item.get("key")
        if not name:
            return
        if not confirm(
            self.app, "Remove from library",
            f"Remove « {name} » from the mount library?",
            ok_label="Remove", danger=True,
        ):
            return
        if self.controller.remove_mount_library(name):
            self.app.refresh_current()
