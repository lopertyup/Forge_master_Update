"""
============================================================
  FORGE MASTER — GameController (UI <-> backend bridge)

  Single entry point for the entire UI. All views call methods
  on GameController; the controller orchestrates backend +
  threading + thread-safe dispatch to Tkinter via `after()`.

  Heavy operations (simulate_batch, pet/mount tests) are
  offloaded to daemon threads; callbacks are dispatched back
  to the Tk thread via `_dispatch`.
============================================================
"""

import logging
import re
import threading
from typing import Callable, Dict, List, Optional, Tuple

from backend.constants import (
    COMPANION_MAX_DURATION,
    COMPANION_STATS_KEYS,
    N_SIMULATIONS,
    PETS_STATS_KEYS,
)
from backend.parser import (
    parse_companion_meta,
    parse_equipment,
    parse_mount,
    parse_pet,
    parse_profile_text,
)
from backend.persistence import (
    load_mount,
    load_mount_library,
    load_pets,
    load_pets_library,
    load_profile,
    load_skills,
    save_mount,
    save_mount_library,
    save_pets,
    save_pets_library,
    save_profile,
)
from backend.simulation import simulate_batch
from backend.stats import (
    apply_change,
    apply_mount,
    apply_pet,
    combat_stats,
    finalize_bases,
)

log = logging.getLogger(__name__)


class GameController:
    """Bridge between the CTk views and the backend (stats, persistence, sim)."""

    # ── Init / loading ──────────────────────────────────────

    def __init__(self) -> None:
        self._profile: Optional[Dict]       = None
        self._skills: List                   = []
        self._pets:   Dict[str, Dict]        = {}
        self._mount:  Dict                   = {}
        self._all_skills:    Dict[str, Dict] = {}
        self._pets_library:  Dict[str, Dict] = {}
        self._mount_library: Dict[str, Dict] = {}
        self._tk_root                        = None  # for thread-safe after()
        self.reload()

    def set_tk_root(self, root) -> None:
        """Register the Tk root so callbacks can be dispatched on the UI thread."""
        self._tk_root = root

    def reload(self) -> None:
        """Reload profile + pets + mount + skills + libraries from disk."""
        self._profile, self._skills = load_profile()
        self._pets                  = load_pets()
        self._mount                 = load_mount()
        self._all_skills            = load_skills()
        self._pets_library          = load_pets_library()
        self._mount_library         = load_mount_library()
        log.info("GameController.reload: profile=%s, pets=%d, skills=%d, lib_pets=%d, lib_mount=%d",
                 "OK" if self._profile else "-",
                 len(self._pets), len(self._all_skills),
                 len(self._pets_library), len(self._mount_library))

    # ── Profile ─────────────────────────────────────────────

    def has_profile(self) -> bool:
        return self._profile is not None

    def get_profile(self) -> Dict:
        return dict(self._profile) if self._profile else {}

    def get_active_skills(self) -> List:
        return list(self._skills)

    def get_all_skills(self) -> Dict[str, Dict]:
        return dict(self._all_skills)

    def import_profile_text(self, text: str, attack_type: str) -> Dict:
        stats = parse_profile_text(text)
        stats["attack_type"] = attack_type
        return finalize_bases(stats)

    def set_profile(self, profile: Dict, skills: List) -> None:
        self._profile = profile
        self._skills  = skills
        save_profile(profile, skills)

    def get_skills_from_codes(self, codes: List[str]) -> List[Tuple[str, Dict]]:
        """Convert a list of codes (e.g. ['cgs','uss','beb']) into [(code, data), ...]."""
        result: List[Tuple[str, Dict]] = []
        for code in codes[:3]:
            code = code.strip().lower()
            if code in self._all_skills:
                result.append((code, self._all_skills[code]))
        return result

    # ── Thread-safe helpers ─────────────────────────────────

    def _dispatch(self, callback: Callable, *args) -> None:
        """Call callback(*args) on the main Tk thread (via after)."""
        if self._tk_root is not None:
            self._tk_root.after(0, lambda: callback(*args))
        else:
            callback(*args)

    # ── Main simulation (opponent = pasted build) ───────────

    def simulate(
        self,
        opponent_stats: Dict,
        opponent_skills: List,
        callback: Callable[[int, int, int], None],
        profile_override: Optional[Dict] = None,
        skills_override:  Optional[List] = None,
    ) -> None:
        """Run N_SIMULATIONS fights in a background thread."""
        profile = profile_override if profile_override else self._profile
        skills  = skills_override  if skills_override  else self._skills

        if profile is None:
            self._dispatch(callback, 0, 0, 0)
            return

        sj = combat_stats(profile)
        se = opponent_stats

        def _run() -> None:
            try:
                w, l, d = simulate_batch(sj, se, skills, opponent_skills,
                                         n=N_SIMULATIONS)
            except Exception:
                log.exception("simulate() raised an exception")
                w, l, d = 0, 0, 0
            self._dispatch(callback, w, l, d)

        threading.Thread(target=_run, daemon=True).start()

    # ── Equipment ───────────────────────────────────────────

    def compare_equipment(
        self, comparison_text: str
    ) -> Optional[Tuple[Dict, Dict, Dict]]:
        """Parse 'OLD ... NEW! ... NEW' and return (old, new, new_profile)."""
        if not re.search(r'NEW\s*!', comparison_text, re.IGNORECASE):
            return None

        parts    = re.split(r'NEW\s*!', comparison_text, flags=re.IGNORECASE)
        old_text = parts[0]
        new_text = parts[1] if len(parts) > 1 else ""

        old_eq = parse_equipment(old_text)
        new_eq = parse_equipment(new_text)

        if self._profile is None:
            return None

        new_profile = apply_change(self._profile, old_eq, new_eq)
        return old_eq, new_eq, new_profile

    def apply_equipment(self, new_profile: Dict) -> None:
        self._profile = new_profile
        save_profile(new_profile, self._skills)

    # ── Pets ────────────────────────────────────────────────

    def get_pets(self) -> Dict[str, Dict]:
        return {k: dict(v) for k, v in self._pets.items()}

    def get_pet(self, name: str) -> Dict:
        return dict(self._pets.get(name, {}))

    def import_pet_text(self, text: str) -> Dict:
        return parse_pet(text)

    def resolve_pet(self, text: str) -> Tuple[Optional[Dict], str, Optional[Dict]]:
        """
        Resolve a pet text into (normalized_pet, status, meta).

        status ∈ {"ok", "added", "unknown_not_lvl1", "no_name"}
          - "ok"               : name found in library, flat stats replaced by lvl1
          - "added"            : name unknown but Lv.1 → auto-added, then "ok"
          - "unknown_not_lvl1" : name unknown and not Lv.1 → normalized_pet = None
          - "no_name"          : couldn't extract a name from the text → None
        meta = dict {name, rarity, level, stats} (debug / UI display)
        """
        return self._resolve_companion(
            text, self._pets_library, save_pets_library)

    def get_pets_library(self) -> Dict[str, Dict]:
        return {k: dict(v) for k, v in self._pets_library.items()}

    def remove_pet_library(self, name: str) -> bool:
        return self._remove_library(name, self._pets_library,
                                    save_pets_library)

    def set_pet(self, name: str, pet: Dict) -> None:
        self._pets[name] = pet
        save_pets(self._pets)

    def test_pet(
        self,
        new_pet: Dict,
        callback: Callable[[Dict[str, Tuple[int, int, int]]], None],
    ) -> None:
        """
        For each PET1/PET2/PET3 slot:
          NEW_ME (with new pet) vs OLD_ME (with old pet in that slot).
        Calls callback({slot_name: (w, l, d)}).
        """
        if self._profile is None:
            self._dispatch(callback, {})
            return

        current_profile = dict(self._profile)
        current_pets    = {k: dict(v) for k, v in self._pets.items()}
        skills          = list(self._skills)

        def _run() -> None:
            results: Dict[str, Tuple[int, int, int]] = {}
            try:
                for name in ("PET1", "PET2", "PET3"):
                    old_pet = current_pets.get(
                        name, {k: 0.0 for k in PETS_STATS_KEYS})
                    results[name] = self._compare_profile_vs_profile(
                        new_profile=apply_pet(
                            current_profile, old_pet, new_pet),
                        old_profile=current_profile,
                        skills=skills,
                    )
            except Exception:
                log.exception("test_pet() raised an exception")
            self._dispatch(callback, results)

        threading.Thread(target=_run, daemon=True).start()

    # ── Mount ───────────────────────────────────────────────

    def get_mount(self) -> Dict:
        return dict(self._mount)

    def import_mount_text(self, text: str) -> Dict:
        return parse_mount(text)

    def resolve_mount(self, text: str) -> Tuple[Optional[Dict], str, Optional[Dict]]:
        """Like resolve_pet but for the mount library."""
        return self._resolve_companion(
            text, self._mount_library, save_mount_library)

    def get_mount_library(self) -> Dict[str, Dict]:
        return {k: dict(v) for k, v in self._mount_library.items()}

    def remove_mount_library(self, name: str) -> bool:
        return self._remove_library(name, self._mount_library,
                                    save_mount_library)

    def set_mount(self, mount: Dict) -> None:
        self._mount = mount
        save_mount(mount)

    def test_mount(
        self,
        new_mount: Dict,
        callback: Callable[[int, int, int], None],
    ) -> None:
        """NEW_ME (with new mount) vs OLD_ME (with current mount)."""
        if self._profile is None:
            self._dispatch(callback, 0, 0, 0)
            return

        current_profile = dict(self._profile)
        current_mount   = dict(self._mount) if self._mount else {
            k: 0.0 for k in COMPANION_STATS_KEYS}
        skills          = list(self._skills)

        def _run() -> None:
            try:
                w, l, d = self._compare_profile_vs_profile(
                    new_profile=apply_mount(
                        current_profile, current_mount, new_mount),
                    old_profile=current_profile,
                    skills=skills,
                )
            except Exception:
                log.exception("test_mount() raised an exception")
                w, l, d = 0, 0, 0
            self._dispatch(callback, w, l, d)

        threading.Thread(target=_run, daemon=True).start()

    # ── Library helpers ─────────────────────────────────────

    @staticmethod
    def _find_library_key(library: Dict[str, Dict], name: str) -> Optional[str]:
        """Look up `name` in the library case-insensitively. Returns the exact key or None."""
        name_lc = name.lower()
        for key in library:
            if key.lower() == name_lc:
                return key
        return None

    def _resolve_companion(
        self,
        text: str,
        library: Dict[str, Dict],
        save_fn: Callable[[Dict[str, Dict]], None],
    ) -> Tuple[Optional[Dict], str, Optional[Dict]]:
        """
        Common pet/mount logic:
          1. parse text → meta (name/rarity/level) + stats
          2. if name unknown:
               - if Lv.1 → add it (status "added")
               - else    → reject (status "unknown_not_lvl1")
          3. if name known: replace hp_flat / damage_flat with the level 1
             values stored in the library (status "ok").
        The returned dict is a COMPLETE companion (same keys as parse_pet),
        ready to be passed to apply_pet / apply_mount.
        """
        meta  = parse_companion_meta(text)
        name  = meta.get("name")
        level = meta.get("level")
        stats = dict(meta.get("stats") or {})

        if not name:
            return None, "no_name", meta

        key = self._find_library_key(library, name)

        if key is None:
            # Unknown name — auto-add if Lv.1, otherwise refuse
            if level == 1:
                library[name] = {
                    "rarity":      meta.get("rarity") or "common",
                    "hp_flat":     stats.get("hp_flat", 0.0),
                    "damage_flat": stats.get("damage_flat", 0.0),
                }
                save_fn(library)
                log.info("Library: '%s' auto-added (Lv.1)", name)
                status = "added"
                key    = name
            else:
                return None, "unknown_not_lvl1", meta

        else:
            # Existing entry — if it's an empty placeholder (0/0) and we are
            # importing a Lv.1 with real stats, fill in the library entry.
            existing_ref = library[key]
            placeholder = (
                float(existing_ref.get("hp_flat", 0.0)) == 0.0
                and float(existing_ref.get("damage_flat", 0.0)) == 0.0
            )
            has_real_stats = (
                stats.get("hp_flat", 0.0) or stats.get("damage_flat", 0.0))
            if level == 1 and placeholder and has_real_stats:
                existing_ref["hp_flat"]     = stats.get("hp_flat", 0.0)
                existing_ref["damage_flat"] = stats.get("damage_flat", 0.0)
                if meta.get("rarity"):
                    existing_ref["rarity"] = meta["rarity"]
                save_fn(library)
                log.info("Library: '%s' filled in with Lv.1 stats", key)
                status = "added"
            else:
                status = "ok"

        # Override flat stats with the library values (level 1)
        ref = library[key]
        stats["hp_flat"]     = float(ref.get("hp_flat", 0.0))
        stats["damage_flat"] = float(ref.get("damage_flat", 0.0))

        # Annotate the resolved companion with its identity (used by the UI
        # to show name + icon of the equipped pets/mount)
        stats["__name__"]   = key
        stats["__rarity__"] = str(ref.get("rarity", "common")).lower()
        return stats, status, meta

    @staticmethod
    def _remove_library(
        name: str,
        library: Dict[str, Dict],
        save_fn: Callable[[Dict[str, Dict]], None],
    ) -> bool:
        key = GameController._find_library_key(library, name)
        if key is None:
            return False
        del library[key]
        save_fn(library)
        return True

    # ── Internal helper: NEW_ME vs OLD_ME ────────────────────

    @staticmethod
    def _compare_profile_vs_profile(
        new_profile: Dict,
        old_profile: Dict,
        skills: List,
    ) -> Tuple[int, int, int]:
        """
        Run N_SIMULATIONS fights of new_profile vs old_profile with the
        'companion' max duration (shorter, to avoid draws between two
        nearly identical builds).
        """
        sj = combat_stats(new_profile)
        se = combat_stats(old_profile)
        return simulate_batch(sj, se, skills, skills,
                              n=N_SIMULATIONS,
                              max_duration=COMPANION_MAX_DURATION)

    # ── UI helpers (compat — new views use ui.theme) ─────────

    @staticmethod
    def fmt_number(n: float) -> str:
        from ui.theme import fmt_number
        return fmt_number(n)

    @staticmethod
    def rarity_color(rarity: str) -> str:
        from ui.theme import rarity_color
        return rarity_color(rarity)

    @staticmethod
    def stats_display_list() -> List[Tuple[str, str, bool]]:
        """List (key, label, is_flat) for the detailed display of a profile."""
        return [
            ("hp_total",       "❤  Total HP",          True),
            ("attack_total",   "⚔  Total ATK",          True),
            ("hp_base",        "   Base HP",            True),
            ("attack_base",    "   Base ATK",           True),
            ("health_pct",     "❤  Health %",           False),
            ("damage_pct",     "⚔  Damage %",           False),
            ("melee_pct",      "⚔  Melee %",            False),
            ("ranged_pct",     "⚔  Ranged %",           False),
            ("crit_chance",    "🎯 Crit Chance",         False),
            ("crit_damage",    "💥 Crit Damage",         False),
            ("health_regen",   "♻  Health Regen",       False),
            ("lifesteal",      "🩸 Lifesteal",           False),
            ("double_chance",  "✌  Double Chance",      False),
            ("attack_speed",   "⚡ Attack Speed",        False),
            ("skill_damage",   "✨ Skill Damage",        False),
            ("skill_cooldown", "⏱  Skill Cooldown",     False),
            ("block_chance",   "🛡  Block Chance",       False),
        ]
