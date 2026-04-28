"""
============================================================
  FORGE MASTER â Attack Speed calculator (formula-based)

  Reproduces the in-game attack-speed math exactly as it
  appears in the official source:

    * statEngine.ts:1680-1710     â weighted DPS / real cycle
    * BreakpointTables.tsx:21-180 â breakpoint tables shown
                                       in the Profile UI

  The only inputs are taken from data/WeaponLibrary.json:
      WindupTime          (variable per weapon)
      AttackDuration      (1.5 in the JSON â see note below)
      AttackRange         (used elsewhere, not by this module)

  No reliance on any pre-computed table file. Everything is
  derived from the formula on the fly so future weapons (skins,
  patch additions) work as soon as they appear in WeaponLibrary.

  Note on AttackDuration
  ----------------------
  WeaponLibrary.json hardcodes AttackDuration = 1.5 for every
  weapon, but the in-game UI breakpoint tables are computed with
  a smaller per-weapon duration (e.g. â 1.10 s for Siren Song).
  Both the official BreakpointTables.tsx component and this module
  consume "weaponAttackDuration" as a parameter, so callers that
  want UI-accurate breakpoints can pass the wiki value directly.
  The default uses the JSON\'s 1.5 â callers can override.

  Public API
  ----------
      compute_real_cycle(weapon_age, weapon_idx, attack_speed_pct)
          -> RealCycle

      compute_dps_factor(weapon_age, weapon_idx,
                          attack_speed_pct, double_damage_pct)
          -> DpsFactor

      compute_breakpoint_tables(weapon_age, weapon_idx,
                                  attack_speed_pct=0.0)
          -> BreakpointTables       # the 3 wiki tables

  All three functions accept a `weapon_meta` override for callers
  that already have the data in hand (avoids a JSON re-read).
============================================================
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


# ============================================================
#  Game constants (from statEngine.ts and BreakpointTables.tsx)
# ============================================================

# 0.1-second frame discretization. Each phase\'s effective time is
# rounded DOWN to the next 0.1s tick. This is what produces the
# breakpoint behaviour shown in the Profile UI.
FRAME_QUANT_S: float = 0.1

# Hard floor: the cycle never goes below this regardless of speed.
MIN_CYCLE_S: float = 0.4

# Fixed overhead added to every weapon cycle (transition time
# between attacks). Applied AFTER the per-phase floor.
CYCLE_OVERHEAD_S: float = 0.2

# Base sequential delay between the two strikes of a Double Attack.
# Itself discretized by FRAME_QUANT_S after dividing by speed.
DOUBLE_HIT_BASE_DELAY_S: float = 0.25

# Speed multiplier floor (clamp to avoid div-by-zero or runaway).
MIN_SPEED_MULT: float = 0.1

# Fallback values when a weapon has no library entry.
FALLBACK_WINDUP_S:   float = 0.5
FALLBACK_DURATION_S: float = 1.5

# Breakpoint table targets (mirrors BreakpointTables.tsx).
PRIMARY_TARGETS: Tuple[float, ...] = (
    1.7, 1.6, 1.5, 1.4, 1.3, 1.2, 1.1, 1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4,
)
WINDUP_TARGETS:  Tuple[float, ...] = (0.5, 0.4, 0.3, 0.2, 0.1)
DOUBLE_TARGETS:  Tuple[float, ...] = (
    2.0, 1.9, 1.8, 1.7, 1.6, 1.5, 1.4, 1.3, 1.2, 1.1, 1.0, 0.9, 0.8, 0.7, 0.6,
)


# ============================================================
#  Data classes
# ============================================================

@dataclass
class RealCycle:
    """Stepped cycle for a player at a given attack-speed bonus."""
    base_windup_s:        float
    base_attack_duration_s: float
    speed_mult:           float
    stepped_windup_s:     float
    stepped_recovery_s:   float
    stepped_cycle_s:      float
    stepped_double_delay_s: float
    double_hit_cycle_s:   float


@dataclass
class DpsFactor:
    """Real-DPS multiplier given an attack speed AND a double-damage
    chance. Multiply by total_damage * crit_mult to get the final
    real_weapon_dps the in-game UI displays."""
    real_cycle:           RealCycle
    double_damage_chance: float       # in [0, 1]
    average_real_cycle_s: float       # weighted between normal + double
    weighted_aps:         float       # = (1 + d) / averageRealCycle
    theoretical_aps:      float       # speed_mult / base_duration


@dataclass
class BreakpointRow:
    target_s:    float
    req_bonus_pct: float
    is_reached:  bool


@dataclass
class BreakpointTables:
    weapon_age:           int
    weapon_idx:           int
    base_windup_s:        float
    base_attack_duration_s: float
    current_speed_mult:   float
    current_real_cycle_s: float
    current_real_windup_s: float
    current_real_double_cycle_s: float
    primary:  List[BreakpointRow] = field(default_factory=list)
    windup:   List[BreakpointRow] = field(default_factory=list)
    double:   List[BreakpointRow] = field(default_factory=list)


# ============================================================
#  Core math
# ============================================================

def _floor_to_tick(seconds: float) -> float:
    """Floor a duration to the nearest FRAME_QUANT_S boundary."""
    return math.floor(seconds / FRAME_QUANT_S) * FRAME_QUANT_S


def _stepped_phases(base_windup_s: float,
                     base_duration_s: float,
                     speed_mult: float
                     ) -> Tuple[float, float]:
    """Return (stepped_windup, stepped_recovery)."""
    base_recovery = max(0.0, base_duration_s - base_windup_s)
    sw = _floor_to_tick(base_windup_s   / speed_mult)
    sr = _floor_to_tick(base_recovery   / speed_mult)
    return sw, sr


def _stepped_cycle(base_windup_s: float,
                   base_duration_s: float,
                   speed_mult: float
                   ) -> Tuple[float, float, float]:
    """Return (stepped_windup, stepped_recovery, stepped_cycle)."""
    sw, sr = _stepped_phases(base_windup_s, base_duration_s, speed_mult)
    cycle = max(MIN_CYCLE_S, sw + sr + CYCLE_OVERHEAD_S)
    return sw, sr, cycle


def _stepped_double_delay(speed_mult: float) -> float:
    return _floor_to_tick(DOUBLE_HIT_BASE_DELAY_S / speed_mult)


def _binary_search_req_bonus(predicate, low: float = 1.0,
                              high: float = 15.0,
                              iters: int = 25) -> float:
    """Find the smallest speed_mult in [low, high] satisfying
    ``predicate(mid) is True``. Mirrors BreakpointTables.tsx\'s 20-iter
    binary search (we use 25 for slightly tighter precision).

    Returns the resulting bonus percentage = (high - 1) * 100.
    """
    for _ in range(iters):
        mid = (low + high) / 2.0
        if predicate(mid):
            high = mid
        else:
            low = mid
    return (high - 1.0) * 100.0


# ============================================================
#  WeaponLibrary lookup helpers
# ============================================================
#
# WeaponLibrary is read through the central chargeur in
# ``backend.data.libraries`` so the codebase keeps a single JSON
# loader (V2 of the architecture plan: "QU'UN chargeur JSON
# actif").

from ..data.libraries import get_lib as _get_lib, reset_cache as _reset_libs


def _load_wl() -> Dict:
    return _get_lib("weapon_library") or {}


def reset_cache() -> None:
    """Clear the cached WeaponLibrary. Tests use this."""
    _reset_libs()


def _weapon_key(age: int, idx: int) -> str:
    """Build the WeaponLibrary key. Matches the Python repr of the
    JSON dict-like keys used in the patch export."""
    return f"{{'Age': {age}, 'Type': 'Weapon', 'Idx': {idx}}}"


def get_weapon_meta(age: int, idx: int) -> Optional[Dict]:
    """Read the relevant fields from data/WeaponLibrary.json.

    The "AttackDuration" field in the JSON is a placeholder = 1.5 for
    EVERY weapon (broken export). The real per-weapon value lives in
    "RealAttackDuration" which we injected from the wiki-validated
    WindupTimeLibrary. We prefer RealAttackDuration when present and
    fall back to AttackDuration only for weapons missing the override
    (skin weapons Age 999/1000, Age=10000 default).

    Returns:
        {"windup_time": float,
         "attack_duration": float,    # RealAttackDuration if available
         "is_ranged": bool,
         "attack_range": float}
        or None if the weapon is unknown.
    """
    wl = _load_wl()
    entry = wl.get(_weapon_key(age, idx))
    if entry is None:
        return None
    rng = float(entry.get("AttackRange", 0.0))
    # Prefer RealAttackDuration (wiki-validated, ~1.10–1.20 s per weapon)
    real_ad = entry.get("RealAttackDuration")
    if real_ad is None:
        attack_duration = float(entry.get("AttackDuration", FALLBACK_DURATION_S))
    else:
        attack_duration = float(real_ad)
    return {
        "windup_time":     float(entry.get("WindupTime", FALLBACK_WINDUP_S)),
        "attack_duration": attack_duration,
        "is_ranged":       rng > 1.0,        # bypass broken IsRanged flag
        "attack_range":    rng,
    }


def _resolve_meta(weapon_age: Optional[int],
                   weapon_idx: Optional[int],
                   weapon_meta: Optional[Dict]) -> Optional[Dict]:
    """Pick a meta source: explicit override > library lookup."""
    if weapon_meta is not None:
        return weapon_meta
    if weapon_age is None or weapon_idx is None:
        return None
    return get_weapon_meta(weapon_age, weapon_idx)


def _speed_mult(attack_speed_pct: float) -> float:
    return max(MIN_SPEED_MULT, 1.0 + attack_speed_pct / 100.0)


# ============================================================
#  Public API
# ============================================================

def compute_real_cycle(weapon_age: Optional[int] = None,
                        weapon_idx: Optional[int] = None,
                        attack_speed_pct: float = 0.0,
                        *,
                        weapon_meta: Optional[Dict] = None,
                        ) -> Optional[RealCycle]:
    """Stepped cycle for the player. Returns None if the weapon is
    unknown and no override was supplied.

    Mirrors statEngine.ts:1680-1694.
    """
    meta = _resolve_meta(weapon_age, weapon_idx, weapon_meta)
    if meta is None:
        return None
    base_windup   = float(meta.get("windup_time", FALLBACK_WINDUP_S))
    base_duration = float(meta.get("attack_duration", FALLBACK_DURATION_S))
    speed = _speed_mult(attack_speed_pct)

    sw, sr, cycle = _stepped_cycle(base_windup, base_duration, speed)
    sd = _stepped_double_delay(speed)
    return RealCycle(
        base_windup_s=base_windup,
        base_attack_duration_s=base_duration,
        speed_mult=speed,
        stepped_windup_s=sw,
        stepped_recovery_s=sr,
        stepped_cycle_s=cycle,
        stepped_double_delay_s=sd,
        double_hit_cycle_s=cycle + sd,
    )


def compute_dps_factor(weapon_age: Optional[int] = None,
                        weapon_idx: Optional[int] = None,
                        attack_speed_pct: float = 0.0,
                        double_damage_pct: float = 0.0,
                        *,
                        weapon_meta: Optional[Dict] = None,
                        ) -> Optional[DpsFactor]:
    """Real APS + cycle factoring in Double Damage chance.

    Mirrors statEngine.ts:1697-1707. Multiply ``weighted_aps`` by
    ``total_damage * crit_mult`` to get the in-game "Real Weapon DPS".
    """
    rc = compute_real_cycle(weapon_age, weapon_idx, attack_speed_pct,
                              weapon_meta=weapon_meta)
    if rc is None:
        return None
    d = min(max(double_damage_pct / 100.0, 0.0), 1.0)
    avg_cycle = (1.0 - d) * rc.stepped_cycle_s + d * rc.double_hit_cycle_s
    weighted_aps = (1.0 + d) / avg_cycle if avg_cycle > 0 else 0.0
    base_duration = rc.base_attack_duration_s
    theoretical_aps = (rc.speed_mult / base_duration
                        if base_duration > 0 else 0.0)
    return DpsFactor(
        real_cycle=rc,
        double_damage_chance=d,
        average_real_cycle_s=avg_cycle,
        weighted_aps=weighted_aps,
        theoretical_aps=theoretical_aps,
    )


def compute_breakpoint_tables(weapon_age: Optional[int] = None,
                                weapon_idx: Optional[int] = None,
                                attack_speed_pct: float = 0.0,
                                *,
                                weapon_meta: Optional[Dict] = None,
                                ) -> Optional[BreakpointTables]:
    """Generate the 3 wiki-style breakpoint tables.

    Mirrors BreakpointTables.tsx:44-180. Each table lists target
    cycle/windup values with the attack-speed bonus required to
    reach them. Useful for the UI â lets the player see what
    the next gain would buy them.
    """
    meta = _resolve_meta(weapon_age, weapon_idx, weapon_meta)
    if meta is None:
        return None
    base_windup   = float(meta.get("windup_time", FALLBACK_WINDUP_S))
    base_duration = float(meta.get("attack_duration", FALLBACK_DURATION_S))
    base_recovery = max(0.0, base_duration - base_windup)
    current_speed = _speed_mult(attack_speed_pct)
    current_bonus = (current_speed - 1.0) * 100.0

    sw_now, sr_now, cycle_now = _stepped_cycle(base_windup, base_duration,
                                                  current_speed)
    sd_now = _stepped_double_delay(current_speed)
    double_now = cycle_now + sd_now

    out = BreakpointTables(
        weapon_age=weapon_age if weapon_age is not None else -1,
        weapon_idx=weapon_idx if weapon_idx is not None else -1,
        base_windup_s=base_windup,
        base_attack_duration_s=base_duration,
        current_speed_mult=current_speed,
        current_real_cycle_s=cycle_now,
        current_real_windup_s=sw_now,
        current_real_double_cycle_s=double_now,
    )

    # Primary cycle table
    for target in PRIMARY_TARGETS:
        if target > base_duration + 0.201:
            continue
        target_phases = target - CYCLE_OVERHEAD_S
        def _ok(s, w=base_windup, r=base_recovery, t=target_phases):
            return (_floor_to_tick(w / s) + _floor_to_tick(r / s)
                    <= t + 0.001)
        req = _binary_search_req_bonus(_ok)
        out.primary.append(BreakpointRow(
            target_s=round(target, 2),
            req_bonus_pct=round(req, 1),
            is_reached=current_bonus >= req - 0.01,
        ))

    # Windup table
    for target in WINDUP_TARGETS:
        if target > base_windup + 0.001:
            continue
        def _ok(s, w=base_windup, t=target):
            return _floor_to_tick(w / s) <= t + 0.001
        req = _binary_search_req_bonus(_ok)
        out.windup.append(BreakpointRow(
            target_s=round(target, 2),
            req_bonus_pct=round(req, 1),
            is_reached=current_bonus >= req - 0.01,
        ))

    # Double-attack cycle table
    for target in DOUBLE_TARGETS:
        if target > base_duration + 0.5:
            continue
        target_phases = target - CYCLE_OVERHEAD_S
        def _ok(s, w=base_windup, r=base_recovery, t=target_phases):
            return (_floor_to_tick(w / s)
                    + _floor_to_tick(r / s)
                    + _floor_to_tick(DOUBLE_HIT_BASE_DELAY_S / s)
                    <= t + 0.001)
        req = _binary_search_req_bonus(_ok)
        out.double.append(BreakpointRow(
            target_s=round(target, 2),
            req_bonus_pct=round(req, 1),
            is_reached=current_bonus >= req - 0.01,
        ))

    return out


# ============================================================
#  CLI debug helper
# ============================================================

def _cli(argv):
    import argparse
    p = argparse.ArgumentParser(prog="backend.calculator.attack_speed")
    p.add_argument("age", type=int)
    p.add_argument("idx", type=int)
    p.add_argument("attack_speed_pct", type=float)
    p.add_argument("double_damage_pct", type=float, nargs="?", default=0.0)
    p.add_argument("--ad-override", type=float, default=None,
                   help="Override AttackDuration (the JSON has 1.5 for "
                        "every weapon â the wiki uses smaller per-weapon "
                        "values; pass the wiki value to reproduce the "
                        "exact in-game breakpoints).")
    p.add_argument("--tables", action="store_true",
                   help="Also dump the 3 breakpoint tables.")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")

    meta = get_weapon_meta(args.age, args.idx)
    if meta is None:
        print(f"unknown weapon age={args.age} idx={args.idx}")
        return 1
    if args.ad_override is not None:
        meta = dict(meta)
        meta["attack_duration"] = args.ad_override

    factor = compute_dps_factor(
        attack_speed_pct=args.attack_speed_pct,
        double_damage_pct=args.double_damage_pct,
        weapon_meta=meta,
    )
    print("=== DpsFactor ===")
    print(json.dumps(asdict(factor), indent=2))

    if args.tables:
        tables = compute_breakpoint_tables(
            attack_speed_pct=args.attack_speed_pct,
            weapon_meta=meta,
        )
        print("\n=== BreakpointTables ===")
        print(json.dumps(asdict(tables), indent=2))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_cli(sys.argv[1:]))
