"""
============================================================
  FORGE MASTER — PvP combat simulation engine (simplified)

  Design rules:
    * HP pool = hp_total x PVP_HP_MULTIPLIER, same on BOTH sides.
      (Companion / skill / equipment contributions are already
       folded into hp_total by stats.apply_*.)
    * One swing takes swing_time(stats) seconds; doubled on a
      double-hit swing. stats.py owns the per-hit time; simulation
      multiplies by 2 when the swing is a double.
    * Double-hit is decided at swing START; both hits (or the
      single hit) are released at swing END.
    * Block cancels a basic attack entirely (no damage, no
      lifesteal). Lifesteal applies only on basic attacks.
    * Crit multiplies the basic-attack damage by crit_multi.
    * Skills cycle cooldown -> cast; they use the chantier (b)
      data (damage per hit / hits / cooldown). Buffs are
      detected via data["type"] == "buff".
    * Regen amount/sec comes from stats.pvp_regen_per_second
      (based on PRE-PvP hp_total), snapshot once per simulated
      second, applied per tick while hp < hp_max.
    * A fighter always targets the OTHER fighter.
    * On timeout, higher HP% wins (|gap| < epsilon -> DRAW).
============================================================
"""

import atexit
import logging
import os
import random
import threading
from typing import Dict, List, Optional, Tuple

from .constants import (
    DEFAULT_MAX_DURATION,
    N_SIMULATIONS,
    PVP_RESOLUTION_EPSILON,
    TICK,
)
from .stats import (
    crit_multi,
    pvp_hp_total,
    pvp_regen_per_second,
    swing_time,
    swing_time_discrete,
    swing_time_double,
)

log = logging.getLogger(__name__)


# ============================================================
#  SKILL INSTANCE
# ============================================================

class SkillInstance:
    """
    One equipped skill, cycling cooldown -> cast -> hits.
    Only the ACTIVE part is used here -- passives (passive_damage /
    passive_hp) are already folded into the profile's attack_base
    and hp_base by stats.apply_skill.
    """

    def __init__(self, data: Dict, skill_damage_pct: float, skill_cooldown_pct: float):
        self.data       = data
        self.name       = str(data.get("__name__") or data.get("name") or "")
        self.skill_type = str(data.get("type", "damage")).lower()
        self.is_buff    = (self.skill_type == "buff")

        hits_raw = data.get("hits", 1)
        self.hits = max(1, int(float(hits_raw or 1)))

        cooldown_pct = skill_cooldown_pct / 100.0
        self.cooldown = max(0.1, float(data.get("cooldown", 10.0)) * (1 + cooldown_pct))

        sd = skill_damage_pct / 100.0
        self.dmg_per_hit = float(data.get("damage", 0.0)) * (1 + sd)

        self.buff_dur = float(data.get("buff_duration", 0.0))
        self.buff_atk = float(data.get("buff_atk", 0.0))
        self.buff_hp  = float(data.get("buff_hp",  0.0))

        # FSM state
        self.cd_timer    = 0.0
        self.casting     = False
        self.cast_timer  = 0.0
        self.hits_fired  = 0
        self.buff_active = False
        self.buff_timer  = 0.0
        self.atk_bonus   = 0.0
        self.hp_bonus    = 0.0

        # Successive hits spread evenly across a fraction of the cooldown
        self.hit_interval = (self.cooldown / self.hits) if self.hits > 1 else 0.0

    # -- lifecycle --

    def tick(self, dt: float, carrier: "Fighter", target: "Fighter") -> None:
        if self.is_buff:
            self._tick_buff(dt, carrier)
            return
        if self.casting:
            self._tick_cast(dt, target)
        else:
            self.cd_timer += dt
            if self.cd_timer >= self.cooldown:
                self.cd_timer   = 0.0
                self.casting    = True
                self.cast_timer = 0.0
                self.hits_fired = 0

    def _tick_cast(self, dt: float, target: "Fighter") -> None:
        self.cast_timer += dt
        while self.hits_fired < self.hits:
            threshold = self.hits_fired * self.hit_interval
            if self.cast_timer < threshold:
                break
            if target.alive() and random.random() >= target.block_chance:
                target.hp -= self.dmg_per_hit
            self.hits_fired += 1
        if self.hits_fired >= self.hits:
            self.casting = False

    def _tick_buff(self, dt: float, carrier: "Fighter") -> None:
        if self.buff_active:
            self.buff_timer += dt
            if self.buff_timer >= self.buff_dur:
                carrier.attack -= self.atk_bonus
                carrier.hp_max  = max(1.0, carrier.hp_max - self.hp_bonus)
                carrier.hp      = min(carrier.hp, carrier.hp_max)
                self.atk_bonus   = 0.0
                self.hp_bonus    = 0.0
                self.buff_active = False
                self.buff_timer  = 0.0
        else:
            self.cd_timer += dt
            if self.cd_timer >= self.cooldown:
                self.cd_timer    = 0.0
                self.buff_active = True
                self.buff_timer  = 0.0
                self.atk_bonus   = self.buff_atk
                self.hp_bonus    = self.buff_hp
                carrier.attack += self.atk_bonus
                carrier.hp_max += self.hp_bonus
                carrier.hp     += self.hp_bonus


# ============================================================
#  FIGHTER
# ============================================================

class Fighter:
    """
    One combatant. Single-phase swing FSM:
      - At swing start, roll double-hit -> sets swing_duration.
      - At swing end, release 1 or 2 hits (block / crit rolled per hit).
    """

    def __init__(
        self,
        stats:         Dict,
        active_skills: Optional[List[Tuple[str, Dict]]] = None,
    ):
        # HP pool -- same x5 scaling for both sides.
        self.hp_max = pvp_hp_total(stats)
        self.hp     = self.hp_max
        self.attack = float(stats.get("attack_total", stats.get("attack", 0.0)))

        self.attack_speed_pct = float(stats.get("attack_speed", 0.0) or 0.0)

        # Discrete attack-speed model -- when the weapon's wind-up and
        # recovery are known, fall back to the per-0.1 s breakpoint
        # cycle (the formula the in-game UI uses). Otherwise keep the
        # legacy linear timing so older code paths are unaffected.
        wu = stats.get("weapon_windup")
        rc = stats.get("weapon_recovery")
        if wu is not None and rc is not None:
            wu = float(wu)
            rc = float(rc)
            self.base_swing_time   = swing_time_discrete(wu, rc, self.attack_speed_pct)
            self.double_swing_time = swing_time_double(wu, rc, self.attack_speed_pct)
            self._weapon_windup    = wu
            self._weapon_recovery  = rc
        else:
            self.base_swing_time   = swing_time(self.attack_speed_pct)
            self.double_swing_time = self.base_swing_time * 2.0
            self._weapon_windup    = None
            self._weapon_recovery  = None

        self.double_chance = min(1.0, float(stats.get("double_chance", 0.0) or 0.0) / 100.0)
        self.lifesteal     = float(stats.get("lifesteal",    0.0) or 0.0) / 100.0
        self.crit_chance   = float(stats.get("crit_chance",  0.0) or 0.0) / 100.0
        self.crit_multi    = crit_multi(float(stats.get("crit_damage", 0.0) or 0.0))
        self.block_chance  = float(stats.get("block_chance", 0.0) or 0.0) / 100.0

        # Projectile travel time -- 0.0 for melee, > 0 for ranged.
        # When > 0 a basic-attack swing pushes a deferred impact onto
        # _pending_impacts instead of applying damage instantly. The
        # SHOOTER's swing cooldown does NOT wait for the projectile;
        # the queue is flushed independently in the simulator loop.
        self.projectile_travel_time = float(
            stats.get("projectile_travel_time", 0.0) or 0.0)
        # List of (impact_time, damage, lifesteal_amount). Ordered by
        # insertion which is also chronological because every push
        # uses the same travel time.
        self._pending_impacts: List[Tuple[float, float, float]] = []

        # Regen: computed on raw hp_total (pre-x5), applied while hp<hp_max.
        self.regen_per_sec    = pvp_regen_per_second(stats)
        self._regen_snapshot  = self.regen_per_sec

        # Swing FSM
        self.swing_timer    = 0.0
        self.swing_duration = self.base_swing_time
        self.is_double      = False
        self._start_swing()

        # Build skill instances
        sd_pct = float(stats.get("skill_damage",   0.0) or 0.0)
        sc_pct = float(stats.get("skill_cooldown", 0.0) or 0.0)
        self.skills: List[SkillInstance] = [
            SkillInstance(data, sd_pct, sc_pct) for _, data in (active_skills or [])
        ]

    # -- queries --

    def alive(self) -> bool:
        return self.hp > 0.0

    def hp_pct(self) -> float:
        return self.hp / self.hp_max if self.hp_max > 0 else 0.0

    # -- regen --

    def refresh_regen_snapshot(self) -> None:
        self._regen_snapshot = self.regen_per_sec

    def apply_regen(self, dt: float) -> None:
        # Inlined min() -- saves a builtin call per tick (~2 M calls / 1k sims).
        hp  = self.hp
        mhp = self.hp_max
        rps = self._regen_snapshot
        if hp <= 0.0 or hp >= mhp or rps <= 0.0:
            return
        new_hp = hp + rps * dt
        self.hp = mhp if new_hp > mhp else new_hp

    # -- attack FSM --

    def _start_swing(self) -> None:
        """Decide now whether this swing is a double-hit, set its duration."""
        self.is_double      = (random.random() < self.double_chance)
        # double_swing_time is set once at __init__: it is either the
        # discrete (windup + recovery + 0.2 s + stepped 0.25 s gap +
        # 0.2 s) cycle when wind-up data is available, or simply twice
        # the legacy single-swing time. Either way one lookup, no math.
        self.swing_duration = (self.double_swing_time
                               if self.is_double
                               else self.base_swing_time)
        self.swing_timer    = 0.0

    def tick_combat(self, dt: float, target: "Fighter", current_time: float = 0.0) -> None:
        self.swing_timer += dt
        if self.swing_timer < self.swing_duration:
            return
        # Release the swing. We DON'T early-out on a dead target here
        # any more: a swing released this tick may schedule a deferred
        # projectile impact, which must still be queued even if the
        # current target.hp is already <= 0 (the user explicitly asked
        # for "if the target is dead, the impact still arrives but HP
        # stays at zero"). The clamp to zero happens at impact time.
        hits = 2 if self.is_double else 1
        for _ in range(hits):
            self._perform_attack(target, current_time)
        self._start_swing()

    def _perform_attack(self, target: "Fighter", current_time: float = 0.0) -> None:
        # Block cancels the hit entirely. Resolved at FIRE time so a
        # deferred projectile that was rolled as "blocked" never
        # reaches the queue at all -- mirrors a missed shot.
        rand = random.random  # local binding
        if rand() < target.block_chance:
            return
        dmg = self.attack
        if rand() < self.crit_chance:
            dmg *= self.crit_multi
        ls_amount = dmg * self.lifesteal if self.lifesteal > 0.0 else 0.0
        travel = self.projectile_travel_time
        if travel <= 0.0:
            # Melee / unknown weapon -> immediate hit & lifesteal.
            self._apply_impact(target, dmg, ls_amount)
        else:
            # Ranged: schedule the impact. The shooter's swing
            # cooldown is unaffected (handled by _start_swing()).
            self._pending_impacts.append((current_time + travel, dmg, ls_amount))

    def _apply_impact(self, target: "Fighter", dmg: float, ls_amount: float) -> None:
        """Land one previously-rolled hit on *target*.

        Damage is clamped at 0 — a target already at 0 HP stays at 0
        (user rule: the impact arrives but HP doesn't dip into the
        negative). Lifesteal is only granted to a still-living
        shooter; a corpse can't heal.
        """
        new_hp = target.hp - dmg
        target.hp = new_hp if new_hp > 0.0 else 0.0
        if ls_amount > 0.0 and self.hp > 0.0:
            hp  = self.hp
            mhp = self.hp_max
            if hp < mhp:
                heal = hp + ls_amount
                self.hp = mhp if heal > mhp else heal

    def tick_pending_impacts(self, current_time: float, target: "Fighter") -> None:
        """Resolve every queued projectile whose flight time elapsed.

        Iterates the list once. Because every entry uses the same
        travel time as the shooter's weapon, the list is naturally
        sorted chronologically — once we find one still in flight we
        can stop. The shooter may itself be dead (corpse): the impact
        still lands on *target*; only the lifesteal heal is skipped
        (handled by _apply_impact).
        """
        pending = self._pending_impacts
        if not pending:
            return
        i = 0
        n = len(pending)
        while i < n:
            t_impact, dmg, ls_amount = pending[i]
            if t_impact > current_time:
                break
            self._apply_impact(target, dmg, ls_amount)
            i += 1
        if i:
            # Drop the resolved entries in one slice op.
            del pending[:i]


# ============================================================
#  SIMULATE
# ============================================================

def _resolve_timeout(p: Fighter, o: Fighter) -> str:
    gap = p.hp_pct() - o.hp_pct()
    if abs(gap) < PVP_RESOLUTION_EPSILON:
        return "DRAW"
    return "WIN" if gap > 0 else "LOSE"


def simulate(
    sj:           Dict,
    se:           Dict,
    skills_p:     Optional[List[Tuple[str, Dict]]] = None,
    skills_o:     Optional[List[Tuple[str, Dict]]] = None,
    max_duration: float                            = DEFAULT_MAX_DURATION,
) -> str:
    """
    Run a single PvP fight. Returns 'WIN', 'LOSE' or 'DRAW'.

    - sj, se               : player / opponent combat stats.
    - skills_p, skills_o   : equipped skills -- [(label, data), ...].
    """
    p = Fighter(sj, skills_p)
    o = Fighter(se, skills_o)

    # Local bindings -- these matter in a 6 000-iteration tight loop.
    rand                 = random.random
    tick                 = TICK
    p_skills             = p.skills
    o_skills             = o.skills
    p_tick_combat        = p.tick_combat
    o_tick_combat        = o.tick_combat
    p_apply_regen        = p.apply_regen
    o_apply_regen        = o.apply_regen
    p_refresh            = p.refresh_regen_snapshot
    o_refresh            = o.refresh_regen_snapshot
    p_tick_impacts       = p.tick_pending_impacts
    o_tick_impacts       = o.tick_pending_impacts
    p_pending            = p._pending_impacts
    o_pending            = o._pending_impacts
    has_any_skill        = bool(p_skills) or bool(o_skills)
    has_any_projectile   = (p.projectile_travel_time > 0.0
                            or o.projectile_travel_time > 0.0)

    t                   = 0.0
    last_regen_refresh  = 0.0
    while t < max_duration:
        # 1. Land arriving projectiles BEFORE deciding alive/dead this
        #    tick so a shot in flight can finish off the target.
        if has_any_projectile:
            if p_pending:
                p_tick_impacts(t, o)
            if o_pending:
                o_tick_impacts(t, p)

        p_alive = p.hp > 0.0
        o_alive = o.hp > 0.0

        # 2. As soon as one side falls, the fight enters a "drain"
        #    phase: no new attacks/skills/regen, but in-flight
        #    projectiles still land. They can tip a WIN into a DRAW.
        if not p_alive or not o_alive:
            if not p_pending and not o_pending:
                break
            t += tick
            continue

        # Regen snapshot once per second, applied every tick.
        if t - last_regen_refresh >= 1.0:
            p_refresh()
            o_refresh()
            last_regen_refresh = t
        p_apply_regen(tick)
        o_apply_regen(tick)

        # Skills -- skip entirely when neither side has any (common fast case).
        if has_any_skill:
            if rand() < 0.5:
                for sk in p_skills: sk.tick(tick, p, o)
                for sk in o_skills: sk.tick(tick, o, p)
            else:
                for sk in o_skills: sk.tick(tick, o, p)
                for sk in p_skills: sk.tick(tick, p, o)

        # Basic-attack FSM (order randomised per tick). Same-tick
        # double-fire is intended: tick = frame, and the user's rule
        # is "if both attack at the same instant, randomise who fires
        # first, the other fires the next frame" — which is exactly
        # the rand()-coin-flip already in place.
        if rand() < 0.5:
            p_tick_combat(tick, o, t)
            o_tick_combat(tick, p, t)
        else:
            o_tick_combat(tick, p, t)
            p_tick_combat(tick, o, t)

        t += tick

    p_alive = p.hp > 0.0
    o_alive = o.hp > 0.0
    if p_alive and not o_alive:
        return "WIN"
    if o_alive and not p_alive:
        return "LOSE"
    if not p_alive and not o_alive:
        return "DRAW"
    return _resolve_timeout(p, o)


# ============================================================
#  PARALLEL SIMULATION POOL
# ============================================================

_PARALLEL_THRESHOLD = 200
_POOL               = None  # type: ignore
_POOL_WORKERS       = max(1, (os.cpu_count() or 2) - 1)
_POOL_LOCK: threading.Lock = threading.Lock()


def _simulate_chunk(
    n:            int,
    sj:           Dict,
    se:           Dict,
    skills_p:     Optional[List[Tuple[str, Dict]]],
    skills_o:     Optional[List[Tuple[str, Dict]]],
    max_duration: float,
) -> Tuple[int, int, int]:
    """Run *n* fights serially. Used by both the serial and parallel paths."""
    wins = loses = draws = 0
    for _ in range(n):
        r = simulate(sj, se, skills_p, skills_o, max_duration=max_duration)
        if   r == "WIN":  wins  += 1
        elif r == "LOSE": loses += 1
        else:             draws += 1
    return wins, loses, draws


def _get_pool():
    global _POOL
    if _POOL is False:
        return None
    if _POOL is not None:
        return _POOL
    with _POOL_LOCK:
        if _POOL is False:
            return None
        if _POOL is not None:
            return _POOL
        try:
            from concurrent.futures import ProcessPoolExecutor
            _POOL = ProcessPoolExecutor(max_workers=_POOL_WORKERS)
            atexit.register(_POOL.shutdown, wait=False)
            log.info("simulate_batch: process pool ready (%d workers)", _POOL_WORKERS)
        except Exception as e:
            log.warning("simulate_batch: process pool unavailable (%s) -- using serial", e)
            _POOL = False
            return None
    return _POOL


def simulate_batch(
    sj:           Dict,
    se:           Dict,
    skills_p:     Optional[List[Tuple[str, Dict]]] = None,
    skills_o:     Optional[List[Tuple[str, Dict]]] = None,
    n:            int                              = N_SIMULATIONS,
    max_duration: float                            = DEFAULT_MAX_DURATION,
) -> Tuple[int, int, int]:
    """Run N fights. Returns (wins, loses, draws)."""
    if n < _PARALLEL_THRESHOLD:
        return _simulate_chunk(n, sj, se, skills_p, skills_o, max_duration)

    pool = _get_pool()
    if pool is None:
        return _simulate_chunk(n, sj, se, skills_p, skills_o, max_duration)

    nw = _POOL_WORKERS
    base, rem = divmod(n, nw)
    chunks = [base + (1 if i < rem else 0) for i in range(nw)]

    try:
        futures = [
            pool.submit(_simulate_chunk, cs, sj, se, skills_p, skills_o, max_duration)
            for cs in chunks if cs > 0
        ]
        total_w = total_l = total_d = 0
        for f in futures:
            w, l, d = f.result()
            total_w += w
            total_l += l
            total_d += d
        return total_w, total_l, total_d
    except Exception as e:
        log.warning("simulate_batch: parallel dispatch failed (%s) -- falling back to serial", e)
        global _POOL
        try:
            pool.shutdown(wait=False)
        except Exception:
            pass
        _POOL = False
        return _simulate_chunk(n, sj, se, skills_p, skills_o, max_duration)
