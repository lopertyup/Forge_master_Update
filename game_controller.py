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
from backend.constants import SKILL_PASSIVE_LV1
from backend.parser import (
    parse_companion_meta,
    parse_equipment,
    parse_mount,
    parse_pet,
    parse_profile_text,
    parse_skill_meta,
)
from backend.persistence import (
    SKILL_SLOTS,
    empty_skill,
    load_mount,
    load_mount_library,
    load_pets,
    load_pets_library,
    load_profile,
    load_skill_slots,
    load_skills,
    load_skills_library,
    load_zones,
    save_mount,
    save_mount_library,
    save_pets,
    save_pets_library,
    save_profile,
    save_skills,
    save_skills_library,
)
from backend import zone_store
from backend.simulation import simulate_batch
from backend.stats import (
    apply_change,
    apply_mount,
    apply_pet,
    apply_skill,
    combat_stats,
    finalize_bases,
)

log = logging.getLogger(__name__)


class GameController:
    """Bridge between the CTk views and the backend (stats, persistence, sim)."""

    # ── Init / loading ──────────────────────────────────────

    def __init__(self) -> None:
        self._profile: Optional[Dict]        = None
        self._skills:  List[Tuple[str, Dict]] = []   # equipped skills (S1/S2/S3 → data)
        self._skill_slots:    Dict[str, Dict] = {}   # raw {slot_label: data}
        self._pets:           Dict[str, Dict] = {}
        self._mount:          Dict            = {}
        self._pets_library:   Dict[str, Dict] = {}
        self._mount_library:  Dict[str, Dict] = {}
        self._skills_library: Dict[str, Dict] = {}
        self._zones:          Dict[str, Dict] = {}   # OCR capture zones
        self._tk_root                         = None  # for thread-safe after()
        self.reload()

    def set_tk_root(self, root) -> None:
        """Register the Tk root so callbacks can be dispatched on the UI thread."""
        self._tk_root = root

    def reload(self) -> None:
        """Reload profile + pets + mount + skills + libraries + zones from disk."""
        self._profile, self._skills = load_profile()
        self._skill_slots           = load_skill_slots()
        self._pets                  = load_pets()
        self._mount                 = load_mount()
        self._pets_library          = load_pets_library()
        self._mount_library         = load_mount_library()
        self._skills_library        = load_skills_library()
        self._zones                 = load_zones()
        log.info("GameController.reload: profile=%s, pets=%d, skills=%d/3, "
                 "lib_pets=%d, lib_mount=%d, lib_skills=%d, zones=%d",
                 "OK" if self._profile else "-",
                 len(self._pets), len(self._skills),
                 len(self._pets_library), len(self._mount_library),
                 len(self._skills_library), len(self._zones))

    # ── Profile ─────────────────────────────────────────────

    def has_profile(self) -> bool:
        return self._profile is not None

    def get_profile(self) -> Dict:
        return dict(self._profile) if self._profile else {}

    def get_active_skills(self) -> List[Tuple[str, Dict]]:
        """Equipped skills as [(slot_label, data), ...]."""
        return list(self._skills)

    # ── Back-compat shims for the old code-based skill API ──
    #
    # The old views (simulator, dashboard) iterate a catalog keyed by
    # a "code" and pick 3 entries by code. With the library-based
    # system, the catalog is `skills_library` keyed by NAME. The
    # name IS the code — case is preserved so skill_icon_grid's
    # `load_icon(code)` maps to `skill_icons/<Name>.png`.

    def get_all_skills(self) -> Dict[str, Dict]:
        """Expose the skills library keyed by the skill's Name (as-is)."""
        out: Dict[str, Dict] = {}
        for name, entry in self._skills_library.items():
            merged = dict(entry)
            merged.setdefault("name", name)
            out[name] = merged
        return out

    def get_skills_from_codes(self, codes: List[str]) -> List[Tuple[str, Dict]]:
        """
        Resolve a list of skill names → [(name, data), ...].
        Case-insensitive lookup against the library so legacy
        lowercased codes still resolve.
        """
        catalog = self.get_all_skills()
        lc_index = {k.lower(): k for k in catalog}
        result: List[Tuple[str, Dict]] = []
        for raw in (codes or [])[:3]:
            key = lc_index.get(str(raw).strip().lower())
            if key is not None:
                result.append((key, catalog[key]))
        return result

    def import_profile_text(self, text: str, attack_type: str) -> Dict:
        stats = parse_profile_text(text)
        stats["attack_type"] = attack_type
        return finalize_bases(stats)

    def set_profile(self, profile: Dict, skills: Optional[List] = None) -> None:
        """
        `skills` is accepted for back-compat but ignored: equipped skills
        are persisted separately via set_skill().
        """
        self._profile = profile
        save_profile(profile)

    # ── Thread-safe helpers ─────────────────────────────────

    def _dispatch(self, callback: Callable, *args) -> None:
        """Call callback(*args) on the main Tk thread (via after)."""
        if self._tk_root is not None:
            self._tk_root.after(0, lambda: callback(*args))
        else:
            callback(*args)

    # ── OCR scan (screen capture + PaddleOCR) ───────────────
    #
    #  Zones live in zones.json (one entry per semantic target:
    #  profile, opponent, equipment, pet, mount, skill). A zone
    #  holds N bboxes — `captures` controls how many successive
    #  grabs the user performs (e.g. 2 if they must scroll).
    #
    #  The view passes a callback; we run the OCR on a daemon
    #  thread so the UI doesn't freeze, then dispatch back.
    #
    #  Returned status:
    #    "ok"                 — non-empty text captured
    #    "empty"              — OCR ran but returned no text
    #    "zone_not_configured" — all bboxes are zero, or unknown key
    #    "ocr_unavailable"     — Pillow or a PaddleOCR backend missing
    #    "ocr_error"           — engine crashed mid-run (logged)

    def get_zone_captures(self, zone_key: str) -> int:
        """Number of successive clicks the user has to perform for this zone."""
        z = self._zones.get(zone_key) or {}
        return max(1, int(z.get("captures", 1)))

    def get_zones(self) -> Dict[str, Dict]:
        """Full zones dict (a shallow copy) — used by the Zones view."""
        return {k: {"captures": v.get("captures", 1),
                    "bboxes":   [list(b) for b in (v.get("bboxes") or [])]}
                for k, v in self._zones.items()}

    def get_zone(self, zone_key: str) -> Dict:
        """Single zone entry (or defaults if unknown)."""
        return zone_store.get_zone(zone_key, zones=self._zones)

    def set_zone_bboxes(self, zone_key: str,
                        bboxes) -> None:
        """Update the bboxes for `zone_key`, save, and refresh the cache."""
        self._zones = zone_store.set_zone_bboxes(
            zone_key, bboxes, zones=self._zones)

    def reset_zone(self, zone_key: str) -> None:
        """Zero out the bboxes for `zone_key`."""
        self._zones = zone_store.reset_zone(zone_key, zones=self._zones)

    def is_zone_configured(self, zone_key: str) -> bool:
        """True iff every bbox in this zone has non-zero area."""
        return zone_store.is_zone_configured(zone_key, zones=self._zones)

    def scan(
        self,
        zone_key: str,
        callback: Callable[[str, str], None],
        step:     Optional[int] = None,
    ) -> None:
        """Run OCR on zone_key (all bboxes, or just step=n) and dispatch
        (text, status) back on the Tk thread."""
        z = self._zones.get(zone_key)
        if z is None:
            self._dispatch(callback, "", "zone_not_configured")
            return

        bboxes = [tuple(b) for b in (z.get("bboxes") or [])]
        if step is not None:
            if step < 0 or step >= len(bboxes):
                self._dispatch(callback, "", "zone_not_configured")
                return
            bboxes = [bboxes[step]]

        # "All zero" → zone not yet calibrated.
        if not bboxes or all(all(c == 0 for c in b) for b in bboxes):
            self._dispatch(callback, "", "zone_not_configured")
            return

        def _run() -> None:
            from backend import ocr  # lazy import — Pillow only loaded on first scan
            from backend.fix_ocr import fix_ocr  # normalize OCR artifacts
            if not ocr.is_available():
                self._dispatch(callback, "", "ocr_unavailable")
                return
            # --- Engine run: a crash here means PaddleOCR itself failed
            #     (bad image, model file missing, etc.). Distinct from the
            #     "engine not installed" branch above.
            try:
                raw_text = ocr.run_ocr(bboxes)
            except Exception:
                log.exception("scan(%r, step=%r): OCR engine crashed", zone_key, step)
                self._dispatch(callback, "", "ocr_error")
                return
            # --- Normalize the raw OCR output BEFORE handing it to the UI:
            # fixes brackets, Lv. prefixes, spacing, stat names, and drops
            # UI artifacts (player-name blobs, timers, [-FR-] tags, etc.).
            # `zone_key` is forwarded as context so profile/opponent get
            # extra cleanup (dedup of the two captures, drop of standalone
            # "Lv. XX" badges, drop of corrupt stats, canonical ordering).
            # The transform is idempotent so pasting clean text later stays safe.
            #
            # A bug in the normalizer would otherwise silently kill this
            # daemon thread; instead we log it and fall back to the raw
            # text so the user still sees something they can hand-edit.
            try:
                text = fix_ocr(raw_text, context=zone_key)
            except Exception:
                log.exception("scan(%r, step=%r): fix_ocr crashed — using raw text",
                              zone_key, step)
                text = raw_text
            status = "ok" if text.strip() else "empty"
            self._dispatch(callback, text, status)

        threading.Thread(target=_run, daemon=True).start()

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
        """Parse two items separated by a '[Rarity] Name' boundary and
        return (old_eq, new_eq, new_profile)."""
        result = parse_equipment(comparison_text)

        # parse_equipment returns {"equipped": ..., "candidate": ...} when
        # two items are detected, or a flat dict for a single item.
        if "equipped" not in result:
            return None

        old_eq = result["equipped"]
        new_eq = result["candidate"]

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
        # New pet & old pets are downgraded to Lv.1 stats so the swap
        # comparison is fair (a Lv.10 wouldn't auto-beat a Lv.5).
        new_pet_lv1     = self._lv1_version_of(new_pet, self._pets_library)

        def _run() -> None:
            results: Dict[str, Tuple[int, int, int]] = {}
            try:
                for name in ("PET1", "PET2", "PET3"):
                    old_pet = current_pets.get(
                        name, {k: 0.0 for k in PETS_STATS_KEYS})
                    old_pet_lv1 = self._lv1_version_of(
                        old_pet, self._pets_library)
                    results[name] = self._compare_profile_vs_profile(
                        new_profile=apply_pet(
                            current_profile, old_pet_lv1, new_pet_lv1),
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
        # Same fair-comparison rule as test_pet: both old and new mount
        # are downgraded to Lv.1 stats from the library before applying.
        new_mount_lv1   = self._lv1_version_of(new_mount, self._mount_library)
        old_mount_lv1   = self._lv1_version_of(current_mount, self._mount_library)

        def _run() -> None:
            try:
                w, l, d = self._compare_profile_vs_profile(
                    new_profile=apply_mount(
                        current_profile, old_mount_lv1, new_mount_lv1),
                    old_profile=current_profile,
                    skills=skills,
                )
            except Exception:
                log.exception("test_mount() raised an exception")
                w, l, d = 0, 0, 0
            self._dispatch(callback, w, l, d)

        threading.Thread(target=_run, daemon=True).start()

    # ── Skills ──────────────────────────────────────────────

    def get_skill_slots(self) -> Dict[str, Dict]:
        """Raw {S1: data, S2: data, S3: data} including empty slots."""
        return {k: dict(v) for k, v in self._skill_slots.items()}

    def get_skill_slot(self, slot: str) -> Dict:
        return dict(self._skill_slots.get(slot, empty_skill()))

    def get_skills_library(self) -> Dict[str, Dict]:
        return {k: dict(v) for k, v in self._skills_library.items()}

    def remove_skill_library(self, name: str) -> bool:
        return self._remove_library(name, self._skills_library,
                                    save_skills_library)

    def resolve_skill(self, text: str) -> Tuple[Optional[Dict], str, Optional[Dict]]:
        """
        Resolve a pasted skill text into (normalized_skill, status, meta).

        status ∈ {"ok", "added", "unknown_not_lvl1", "no_name"}
          - "ok"               : name found in library, current-level stats kept
          - "added"            : name unknown but Lv.1 → auto-added, then "ok"
          - "unknown_not_lvl1" : name unknown and not Lv.1 → normalized = None
          - "no_name"          : couldn't extract a skill name → None
        """
        meta  = parse_skill_meta(text)
        name  = meta.get("name")
        level = meta.get("level")
        rarity_in = meta.get("rarity")

        if not name:
            return None, "no_name", meta

        key = self._find_library_key(self._skills_library, name)

        if key is None:
            # Unknown — auto-add iff Lv.1 with full stats
            if level == 1 and (
                meta.get("total_damage") or meta.get("passive_damage")
                or meta.get("passive_hp")
            ):
                # We don't know `hits`/`cooldown`/`type` from a paste alone.
                # Default: damage skill, 1 hit, cooldown 0 (UX flag for the
                # user to fill it in afterwards). The library is editable
                # by hand for refinement.
                rarity = rarity_in or "common"
                pass_lv1 = SKILL_PASSIVE_LV1.get(rarity, {})
                self._skills_library[name] = {
                    "rarity":         rarity,
                    "type":           "damage",
                    "damage":         float(meta.get("total_damage") or 0.0),
                    "hits":           1.0,
                    "cooldown":       0.0,
                    "buff_duration":  0.0,
                    "buff_atk":       0.0,
                    "buff_hp":        0.0,
                    "passive_damage": float(meta.get("passive_damage")
                                             or pass_lv1.get("passive_damage", 0.0)),
                    "passive_hp":     float(meta.get("passive_hp")
                                             or pass_lv1.get("passive_hp", 0.0)),
                }
                save_skills_library(self._skills_library)
                log.info("Skills library: '%s' auto-added (Lv.1)", name)
                key = name
                status = "added"
            else:
                return None, "unknown_not_lvl1", meta
        else:
            status = "ok"

        # Build a fully-stated skill dict at the player's CURRENT level
        # using the library entry as a structural reference.
        ref       = self._skills_library[key]
        hits      = max(1, int(ref.get("hits", 1) or 1))
        per_hit   = (float(meta.get("total_damage") or 0.0) / hits) if meta.get("total_damage") else float(ref.get("damage", 0.0))
        rarity    = str(ref.get("rarity", rarity_in or "common")).lower()
        pass_dmg  = float(meta.get("passive_damage") or 0.0) or float(ref.get("passive_damage", 0.0))
        pass_hp   = float(meta.get("passive_hp")     or 0.0) or float(ref.get("passive_hp",     0.0))

        out: Dict = {
            "__name__":       key,
            "__rarity__":     rarity,
            "__level__":      int(level) if level is not None else 1,
            "name":           key,
            "type":           str(ref.get("type", "damage")),
            "damage":         per_hit,
            "hits":           float(hits),
            "cooldown":       float(ref.get("cooldown", 0.0)),
            "buff_duration":  float(ref.get("buff_duration", 0.0)),
            "buff_atk":       float(ref.get("buff_atk", 0.0)),
            "buff_hp":        float(ref.get("buff_hp", 0.0)),
            "passive_damage": pass_dmg,
            "passive_hp":     pass_hp,
        }
        return out, status, meta

    def set_skill(self, slot: str, skill: Dict) -> None:
        """Persist a skill into a slot AND apply its passive swap on the profile."""
        if slot not in SKILL_SLOTS:
            log.warning("set_skill: invalid slot %r", slot)
            return

        old_slot = dict(self._skill_slots.get(slot) or empty_skill())
        new_slot = dict(skill)

        # Update the on-disk skill slot
        self._skill_slots[slot] = new_slot
        save_skills(self._skill_slots)

        # Refresh in-memory equipped list (mirror name → "name" for sim)
        self._skills = [(s, self._skill_slots[s])
                        for s in SKILL_SLOTS
                        if self._skill_slots[s].get("__name__")]

        # Re-apply the passive delta on the profile
        if self._profile is not None:
            new_profile = apply_skill(self._profile, old_slot, new_slot)
            self._profile = new_profile
            save_profile(new_profile)

    def test_skill(
        self,
        new_skill: Dict,
        callback: Callable[[Dict[str, Tuple[int, int, int]]], None],
    ) -> None:
        """
        For each S1/S2/S3 slot:
          NEW_ME (with new skill installed in that slot, profile passive
          adjusted) vs OLD_ME (current profile, current skills).
        Both versions of the skill are flattened to Lv.1 for fairness.
        """
        if self._profile is None:
            self._dispatch(callback, {})
            return

        current_profile = dict(self._profile)
        current_slots   = {k: dict(v) for k, v in self._skill_slots.items()}
        new_skill_lv1   = self._skill_lv1_version(new_skill)
        active_slots_old = [(s, current_slots[s])
                            for s in SKILL_SLOTS
                            if current_slots[s].get("__name__")]

        def _run() -> None:
            results: Dict[str, Tuple[int, int, int]] = {}
            try:
                for slot in SKILL_SLOTS:
                    old_skill = current_slots.get(slot) or empty_skill()
                    old_skill_lv1 = self._skill_lv1_version(old_skill)
                    candidate_profile = apply_skill(
                        current_profile, old_skill_lv1, new_skill_lv1)
                    # Build the candidate's active skill list: same as current,
                    # but with `slot` replaced by the new (Lv.1) skill.
                    candidate_slots = dict(current_slots)
                    candidate_slots[slot] = new_skill_lv1
                    active_slots_new = [(s, candidate_slots[s])
                                        for s in SKILL_SLOTS
                                        if candidate_slots[s].get("__name__")]
                    results[slot] = self._compare_profile_vs_profile(
                        new_profile=candidate_profile,
                        old_profile=current_profile,
                        skills_new=active_slots_new,
                        skills_old=active_slots_old,
                    )
            except Exception:
                log.exception("test_skill() raised an exception")
            self._dispatch(callback, results)

        threading.Thread(target=_run, daemon=True).start()

    def _skill_lv1_version(self, skill: Dict) -> Dict:
        """
        Build a Lv.1-equivalent of an equipped skill, used for swap
        comparisons. The skill's NAME is looked up in the library and
        all the leveled stats (damage, passive_damage, passive_hp) are
        rebased to the library's Lv.1 values. Cooldown/hits/buff_*
        already don't scale with level — we keep them as-is.
        """
        if not skill or not skill.get("__name__"):
            return dict(skill or {})
        key = self._find_library_key(self._skills_library, skill["__name__"])
        if key is None:
            return dict(skill)
        ref = self._skills_library[key]
        out = dict(skill)
        out["damage"]         = float(ref.get("damage", 0.0))
        out["hits"]           = float(ref.get("hits", out.get("hits", 1.0)))
        out["cooldown"]       = float(ref.get("cooldown", out.get("cooldown", 0.0)))
        out["buff_duration"]  = float(ref.get("buff_duration",
                                              out.get("buff_duration", 0.0)))
        out["buff_atk"]       = float(ref.get("buff_atk", out.get("buff_atk", 0.0)))
        out["buff_hp"]        = float(ref.get("buff_hp", out.get("buff_hp", 0.0)))
        out["passive_damage"] = float(ref.get("passive_damage", 0.0))
        out["passive_hp"]     = float(ref.get("passive_hp", 0.0))
        return out

    # ── Library helpers ─────────────────────────────────────

    @staticmethod
    def _find_library_key(library: Dict[str, Dict], name: str) -> Optional[str]:
        """Look up `name` in the library case-insensitively. Returns the exact key or None."""
        name_lc = name.lower()
        for key in library:
            if key.lower() == name_lc:
                return key
        return None

    @staticmethod
    def _lv1_version_of(
        companion: Dict, library: Dict[str, Dict],
    ) -> Dict:
        """
        Build a Lv.1-equivalent of an equipped pet/mount, used for swap
        comparisons. We keep the % stats (lifesteal, attack_speed, etc.)
        as-is — only the FLAT stats (hp_flat / damage_flat) are pulled
        from the library so the comparison stays at "equal level".

        If the companion isn't in the library (no __name__), the input
        is returned unchanged (best effort).
        """
        if not companion:
            return companion
        name = companion.get("__name__")
        if not name:
            return dict(companion)
        key = GameController._find_library_key(library, name)
        if key is None:
            return dict(companion)
        ref = library[key]
        out = dict(companion)
        out["hp_flat"]     = float(ref.get("hp_flat", 0.0))
        out["damage_flat"] = float(ref.get("damage_flat", 0.0))
        return out

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

        # Keep the ACTUAL scanned hp_flat / damage_flat (current level).
        # The Lv.1 reference values stay in the library and are looked up
        # only when running swap simulations (see _lv1_version_of below).
        ref = library[key]

        # Annotate the resolved companion with its identity + level (used
        # by the UI to show name + icon + level of the equipped slot).
        stats["__name__"]   = key
        stats["__rarity__"] = str(ref.get("rarity", "common")).lower()
        if level is not None:
            stats["__level__"] = int(level)
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
        skills:      Optional[List] = None,
        skills_new:  Optional[List] = None,
        skills_old:  Optional[List] = None,
    ) -> Tuple[int, int, int]:
        """
        Run N_SIMULATIONS fights of new_profile vs old_profile with the
        'companion' max duration (shorter, to avoid draws between two
        nearly identical builds).

        `skills` provides the same skill list to both sides (pet/mount
        swap tests). For a skill swap test, pass distinct `skills_new`
        and `skills_old` instead.
        """
        if skills_new is None: skills_new = skills
        if skills_old is None: skills_old = skills
        sj = combat_stats(new_profile)
        se = combat_stats(old_profile)
        return simulate_batch(sj, se, skills_new, skills_old,
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
        """List (key, label, is_flat) for the detailed display of a profile.

        Order: flat stats first (totals then bases), then substats in the
        canonical in-game order (crit / block / regen / ... / health).
        """
        return [
            ("hp_total",       "❤  Total HP",          True),
            ("attack_total",   "⚔  Total ATK",          True),
            ("hp_base",        "   Base HP",            True),
            ("attack_base",    "   Base ATK",           True),
            ("crit_chance",    "🎯 Crit Chance",         False),
            ("crit_damage",    "💥 Crit Damage",         False),
            ("block_chance",   "🛡  Block Chance",       False),
            ("health_regen",   "♻  Health Regen",       False),
            ("lifesteal",      "🩸 Lifesteal",           False),
            ("double_chance",  "✌  Double Chance",      False),
            ("damage_pct",     "⚔  Damage %",           False),
            ("melee_pct",      "⚔  Melee %",            False),
            ("ranged_pct",     "⚔  Ranged %",           False),
            ("attack_speed",   "⚡ Attack Speed",        False),
            ("skill_damage",   "✨ Skill Damage",        False),
            ("skill_cooldown", "⏱  Skill Cooldown",     False),
            ("health_pct",     "❤  Health %",           False),
        ]
