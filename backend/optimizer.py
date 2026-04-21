"""
============================================================
  FORGE MASTER — Stat optimizer (marginal analysis)

  For EACH stat in SUBSTATS_POOL, the optimizer runs two
  tests:
    1. profile_plus  = profile + Δ points in this stat
    2. profile_minus = profile − Δ points in this stat
  then simulates each one against the current profile and
  measures the win rate.

  Verdict drawn from the two results:
    +Δ helps AND −Δ hurts        → KEEP      (stat at the right level)
    +Δ helps AND −Δ doesn't hurt → INCREASE  (under-invested)
    +Δ doesn't help AND −Δ hurts → KEEP      (capped but useful)
    +Δ doesn't help AND −Δ doesn't hurt → DECREASE (wasted points)

  Directly answers the question:
  "Which stats should I increase, which can I decrease?"
============================================================
"""

import logging
from typing import Callable, Dict, List, Optional, Tuple

from .constants import COMPANION_MAX_DURATION
from .simulation import simulate_batch
from .stats import combat_stats

log = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════
#  TESTED STATS DEFINITION
# ════════════════════════════════════════════════════════════
#
# For each stat: (lo, hi) = range of one "draw point".
# Lo<0 ⇒ "negative-is-better" stat (e.g. skill_cooldown).
# Value of one point = mean |lo+hi|/2.

SUBSTATS_POOL: Dict[str, Tuple[float, float]] = {
    "crit_chance":     (0.0,  12.0),
    "crit_damage":     (0.0, 100.0),
    "attack_speed":    (0.0,  40.0),
    "double_chance":   (0.0,  40.0),
    "damage_pct":      (0.0,  15.0),
    "skill_damage":    (0.0,  30.0),
    "ranged_pct":      (0.0,  15.0),
    "melee_pct":       (0.0,  50.0),
    "block_chance":    (0.0,   5.0),
    "lifesteal":       (0.0,  20.0),
    "health_regen":    (0.0,   6.0),
    "skill_cooldown":  (-7.0,  0.0),
    "health_pct":      (0.0,  15.0),
}

SUBSTATS_LABELS = {
    "crit_chance":     "Crit Chance",
    "crit_damage":     "Crit Damage",
    "attack_speed":    "Attack Speed",
    "double_chance":   "Double Chance",
    "damage_pct":      "Damage %",
    "skill_damage":    "Skill Damage",
    "ranged_pct":      "Ranged Dmg",
    "melee_pct":       "Melee Dmg",
    "block_chance":    "Block Chance",
    "lifesteal":       "Lifesteal",
    "health_regen":    "Health Regen",
    "skill_cooldown":  "Skill Cooldown",
    "health_pct":      "Health %",
}

SUBSTATS_VALUE_PER_POINT: Dict[str, float] = {
    k: abs(lo + hi) / 2 if (lo + hi) != 0 else 1.0
    for k, (lo, hi) in SUBSTATS_POOL.items()
}


# ════════════════════════════════════════════════════════════
#  VERDICTS
# ════════════════════════════════════════════════════════════

VERDICT_INCREASE = "INCREASE"
VERDICT_KEEP     = "KEEP"
VERDICT_DECREASE = "DECREASE"
VERDICT_NEUTRAL  = "NEUTRAL"

# Thresholds (in win-rate points above/below 0.50)
SIGNIFICANT_THRESHOLD = 0.03   # 3 pp = real effect
NEUTRAL_THRESHOLD     = 0.015  # 1.5 pp = noise


# ════════════════════════════════════════════════════════════
#  PROFILE HELPERS
# ════════════════════════════════════════════════════════════

def _recompute_totals(profile: Dict) -> None:
    """Recompute hp_total and attack_total after a % stat change."""
    profile["hp_total"] = profile["hp_base"] * (
        1 + profile.get("health_pct", 0.0) / 100)

    atk_type = profile.get("attack_type", "melee")
    bonus = profile.get("damage_pct", 0.0) + (
        profile.get("ranged_pct", 0.0) if atk_type == "ranged"
        else profile.get("melee_pct", 0.0))
    profile["attack_total"] = profile["attack_base"] * (1 + bonus / 100)


def profile_with_delta(profile: Dict, stat: str,
                       player_signed_delta: float) -> Dict:
    """
    Returns a new profile with a Δ applied to `stat`,
    where `player_signed_delta > 0` means "in the player's favor".

    For negative-is-better stats (skill_cooldown), Δ>0 makes the
    value more negative (= better for the player).
    """
    lo, _ = SUBSTATS_POOL[stat]
    new = dict(profile)
    current = float(new.get(stat, 0.0))

    if lo >= 0:
        new[stat] = max(0.0, current + player_signed_delta)
    else:
        # 'negative-is-better' stat: player favor = more negative
        new[stat] = min(0.0, current - player_signed_delta)

    _recompute_totals(new)
    return new


# ════════════════════════════════════════════════════════════
#  CLASSIFICATION
# ════════════════════════════════════════════════════════════

def _classify(wr_plus: float, wr_minus: float) -> str:
    """
    wr_plus  = win rate of boosted profile vs current profile
               (>0.5 if adding helps)
    wr_minus = win rate of weakened profile vs current profile
               (<0.5 if removing hurts)
    """
    help_significant = (wr_plus  - 0.5) >  SIGNIFICANT_THRESHOLD
    loss_significant = (0.5 - wr_minus) >  SIGNIFICANT_THRESHOLD
    help_neutral     = abs(wr_plus  - 0.5) < NEUTRAL_THRESHOLD
    loss_neutral     = abs(wr_minus - 0.5) < NEUTRAL_THRESHOLD

    if help_significant and not loss_significant:
        return VERDICT_INCREASE
    if loss_significant and not help_significant:
        return VERDICT_KEEP
    if help_significant and loss_significant:
        # +Δ helps AND −Δ hurts: useful stat, push it further
        return VERDICT_INCREASE
    if help_neutral and loss_neutral:
        return VERDICT_DECREASE
    return VERDICT_NEUTRAL


def _impact_score(wr_plus: float, wr_minus: float, verdict: str) -> float:
    """Numerical score used to sort results by 'action priority'."""
    if verdict == VERDICT_INCREASE:
        return 1000 + (wr_plus - 0.5)   # bigger gain ranks higher
    if verdict == VERDICT_DECREASE:
        return 500  + (0.5 - wr_minus)  # safer to remove ranks higher
    if verdict == VERDICT_KEEP:
        return 100  + (0.5 - wr_minus)
    return 0  # neutral at the bottom


# ════════════════════════════════════════════════════════════
#  MAIN ANALYSIS
# ════════════════════════════════════════════════════════════

def analyze_profile(
    profile: Dict,
    skills: List,
    n_points: int = 8,
    n_sims: int = 200,
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
    stat_cb:     Optional[Callable[[Dict], None]]          = None,
    stop_flag=None,
) -> List[Dict]:
    """
    Marginal stat-by-stat analysis. Returns a list sorted by
    decreasing impact:

      [{
        "key"       : "crit_chance",
        "label"     : "Crit Chance",
        "current"   : 35.0,
        "delta"     : 36.0,          # size of the tested Δ (in stat value)
        "wr_plus"   : 0.62,
        "wr_minus"  : 0.41,
        "verdict"   : "INCREASE",
      }, ...]

    `progress_cb(i, total, label)` : called when each stat finishes
    `stat_cb(result_dict)`         : called with the result as soon as
                                     it is computed (UI streaming)
    `stop_flag`                    : threading.Event, clean stop
    """
    base_stats  = combat_stats(profile)
    attack_type = profile.get("attack_type", "melee")
    excluded    = "melee_pct" if attack_type == "ranged" else "ranged_pct"

    keys = [k for k in SUBSTATS_POOL if k != excluded]
    total = len(keys)

    results: List[Dict] = []

    for idx, stat in enumerate(keys, start=1):
        if stop_flag is not None and stop_flag.is_set():
            break

        value_per_pt = SUBSTATS_VALUE_PER_POINT[stat]
        delta_value  = n_points * value_per_pt
        current      = float(profile.get(stat, 0.0))

        profile_plus  = profile_with_delta(profile, stat, +delta_value)
        profile_minus = profile_with_delta(profile, stat, -delta_value)

        # If the minus profile couldn't move down (already at 0), skip the
        # negative test and mark −Δ as "unchanged" (wr_minus = 0.5).
        if abs(profile_minus.get(stat, 0.0) - current) < 1e-9:
            wr_minus = 0.5
        else:
            sj_minus = combat_stats(profile_minus)
            w_m, l_m, d_m = simulate_batch(
                sj_minus, base_stats, skills, skills,
                n=n_sims, max_duration=COMPANION_MAX_DURATION)
            tot_m = max(1, w_m + l_m + d_m)
            wr_minus = w_m / tot_m

        sj_plus = combat_stats(profile_plus)
        w_p, l_p, d_p = simulate_batch(
            sj_plus, base_stats, skills, skills,
            n=n_sims, max_duration=COMPANION_MAX_DURATION)
        tot_p = max(1, w_p + l_p + d_p)
        wr_plus = w_p / tot_p

        verdict = _classify(wr_plus, wr_minus)

        result = {
            "key":       stat,
            "label":     SUBSTATS_LABELS.get(stat, stat),
            "current":   current,
            "delta":     delta_value,
            "wr_plus":   wr_plus,
            "wr_minus":  wr_minus,
            "verdict":   verdict,
            "impact":    _impact_score(wr_plus, wr_minus, verdict),
        }
        results.append(result)

        if stat_cb is not None:
            stat_cb(dict(result))
        if progress_cb is not None:
            progress_cb(idx, total, result["label"])

    results.sort(key=lambda r: r["impact"], reverse=True)
    return results


# Back-compat alias
analyser_profil = analyze_profile
