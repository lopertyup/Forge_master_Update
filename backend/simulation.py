"""
============================================================
  FORGE MASTER — Combat simulation engine
  Deterministic 1v1 tick-based combat with skills, buffs,
  crits, lifesteal, block, double attack, etc.

  IMPORTANT: max_duration is a parameter of simulate() — no
  more monkey-patching a global. This lets multiple threads
  simulate in parallel with different timeouts.
============================================================
"""

import random
from typing import Dict, List, Optional, Tuple

from .constants import (
    BASE_SPEED,
    DEFAULT_MAX_DURATION,
    N_SIMULATIONS,
    RANGED_LEAD,
    TICK,
)


class SkillInstance:
    INITIAL_DELAY = 3.8

    def __init__(self, data: Dict, skill_damage_pct: float, skill_cooldown_pct: float):
        self.data          = data
        self.name          = data["name"]
        self.skill_type    = data["type"]
        self.hits          = int(data.get("hits", 1))
        self.cooldown_base = float(data.get("cooldown", 10.0))
        self.buff_dur      = float(data.get("buff_duration", 0.0))
        self.buff_atk      = float(data.get("buff_atk", data.get("buff_atq", 0.0)))
        self.buff_hp       = float(data.get("buff_hp", 0.0))

        sd = skill_damage_pct / 100.0
        sc = skill_cooldown_pct / 100.0
        dmg_base          = float(data.get("damage", 0.0))
        self.dmg_per_hit  = dmg_base * (1 + sd)
        self.cooldown     = max(0.1, self.cooldown_base * (1 + sc))

        self.timer          = -self.INITIAL_DELAY
        self.hit_interval   = self.cooldown / self.hits if self.hits > 1 else 0.0
        self.hit_timer      = 0.0
        self.hits_remaining = 0
        self.buff_active    = False
        self.buff_timer     = 0.0
        self.atk_bonus      = 0.0
        self.hp_bonus       = 0.0

    def tick(self, dt: float, carrier: "Fighter", target: "Fighter") -> None:
        self.timer += dt
        if self.skill_type == "damage":
            self._tick_damage(dt, target)
        elif self.skill_type == "buff":
            self._tick_buff(dt, carrier)

    def _tick_damage(self, dt: float, target: "Fighter") -> None:
        if self.hits_remaining > 0:
            self.hit_timer += dt
            if self.hit_timer >= self.hit_interval or self.hits == 1:
                if target.alive():
                    target.hp -= self.dmg_per_hit
                self.hits_remaining -= 1
                self.hit_timer = 0.0
        elif self.timer >= self.cooldown:
            self.timer = 0.0
            self.hits_remaining = self.hits - 1
            self.hit_timer = 0.0
            if target.alive():
                target.hp -= self.dmg_per_hit

    def _tick_buff(self, dt: float, carrier: "Fighter") -> None:
        if self.buff_active:
            self.buff_timer += dt
            if self.buff_timer >= self.buff_dur:
                carrier.attack -= self.atk_bonus
                self.atk_bonus  = 0.0
                self.hp_bonus   = 0.0
                self.buff_active = False
                self.buff_timer  = 0.0
        elif self.timer >= self.cooldown:
            self.timer       = 0.0
            self.buff_active = True
            self.buff_timer  = 0.0
            self.atk_bonus   = self.buff_atk
            self.hp_bonus    = self.buff_hp
            carrier.attack += self.atk_bonus
            carrier.hp     += self.hp_bonus


class Fighter:
    def __init__(self, s: Dict, active_skills: Optional[List[Tuple[str, Dict]]] = None):
        self.hp_max        = s.get("hp_total", s.get("hp", 0.0))
        self.hp            = float(self.hp_max)
        self.health_regen  = s.get("health_regen",  0.0) / 100.0
        self.attack        = s.get("attack_total", s.get("attack", 0.0))
        self.attack_speed  = s.get("attack_speed",  0.0) / 100.0
        self.double_chance = s.get("double_chance", 0.0) / 100.0
        self.lifesteal     = s.get("lifesteal",     0.0) / 100.0
        self.crit_chance   = s.get("crit_chance",   0.0) / 100.0
        self.crit_damage   = s.get("crit_damage",   0.0) / 100.0
        self.block_chance  = s.get("block_chance",  0.0) / 100.0
        self.attack_type   = s.get("attack_type", "melee")
        self.freq          = BASE_SPEED * (1.0 + self.attack_speed)
        self.interval      = 1.0 / self.freq
        self.timer         = 0.0

        sd = s.get("skill_damage",   0.0)
        sc = s.get("skill_cooldown", 0.0)
        self.skills = [SkillInstance(data, sd, sc) for _, data in (active_skills or [])]

    def alive(self) -> bool:
        return self.hp > 0

    def regenerate(self, dt: float) -> None:
        if self.hp < self.hp_max:
            self.hp = min(self.hp_max, self.hp + self.hp_max * self.health_regen * dt)

    def strike(self, target: "Fighter") -> None:
        hits = 2 if random.random() < self.double_chance else 1
        for _ in range(hits):
            if random.random() < target.block_chance:
                continue
            dmg = self.attack * (1 + self.crit_damage) if random.random() < self.crit_chance else self.attack
            target.hp -= dmg
            self.hp = min(self.hp_max, self.hp + dmg * self.lifesteal)


def simulate(
    sj: Dict,
    se: Dict,
    skills_p: Optional[List[Tuple[str, Dict]]] = None,
    skills_o: Optional[List[Tuple[str, Dict]]] = None,
    max_duration: float = DEFAULT_MAX_DURATION,
) -> str:
    """Run a single fight. Returns 'WIN', 'LOSE' or 'DRAW'."""
    p = Fighter(sj, skills_p)
    o = Fighter(se, skills_o)

    if p.attack_type == o.attack_type:
        p.timer, o.timer = 0.0, 0.0
    elif p.attack_type == "ranged":
        p.timer, o.timer = 0.0, -RANGED_LEAD
    else:
        p.timer, o.timer = -RANGED_LEAD, 0.0

    t = 0.0
    while t < max_duration:
        if not p.alive() or not o.alive():
            break
        p.regenerate(TICK)
        o.regenerate(TICK)
        for sk in p.skills:
            sk.tick(TICK, p, o)
        for sk in o.skills:
            sk.tick(TICK, o, p)
        p.timer += TICK
        o.timer += TICK
        if p.timer >= p.interval:
            p.timer = 0.0
            if o.alive():
                p.strike(o)
        if o.timer >= o.interval:
            o.timer = 0.0
            if p.alive():
                o.strike(p)
        t += TICK

    if p.alive() and not o.alive():
        return "WIN"
    if o.alive() and not p.alive():
        return "LOSE"
    if not p.alive() and not o.alive():
        return "LOSE"
    return "DRAW"


def simulate_batch(
    sj: Dict,
    se: Dict,
    skills_p: Optional[List[Tuple[str, Dict]]] = None,
    skills_o: Optional[List[Tuple[str, Dict]]] = None,
    n: int = N_SIMULATIONS,
    max_duration: float = DEFAULT_MAX_DURATION,
) -> Tuple[int, int, int]:
    """Run N fights. Returns (wins, loses, draws)."""
    wins = loses = draws = 0
    for _ in range(n):
        r = simulate(sj, se, skills_p, skills_o, max_duration=max_duration)
        if r == "WIN":    wins  += 1
        elif r == "LOSE": loses += 1
        else:             draws += 1
    return wins, loses, draws
