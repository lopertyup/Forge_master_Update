"""
============================================================
  FORGE MASTER — Optimiseur génétique v6
  Sélection par win rate + mutation locale contrainte
  Population : 32 builds
  Adversaire : profil actuel du joueur (fixe)
============================================================
"""

import random
import math

# ════════════════════════════════════════════════════════════
#  CONFIGURATION
# ════════════════════════════════════════════════════════════

N_BUILDS      = 32
N_SUBSTATS    = 24      # points à distribuer par build
SELECTION_PCT = 0.30    # garder top 30%
N_SURVIVORS   = max(2, round(N_BUILDS * SELECTION_PCT))  # ≈ 10

# Plages par point (valeur ajoutée à chaque tirage)
SUBSTATS_POOL = {
    "taux_crit":       (0.0,  12.0),
    "degat_crit":      (0.0, 100.0),
    "vitesse_attaque": (0.0,  40.0),
    "double_chance":   (0.0,  40.0),
    "damage_pct":      (0.0,  15.0),
    "skill_damage":    (0.0,  30.0),
    "ranged_pct":      (0.0,  15.0),
    "melee_pct":       (0.0,  50.0),
    "chance_blocage":  (0.0,   5.0),
    "lifesteal":       (0.0,  20.0),
    "health_regen":    (0.0,   6.0),
    "skill_cooldown":  (-7.0,  0.0),
    "health_pct":      (0.0,  15.0),
}

SUBSTATS_LABELS = {
    "taux_crit":       "Crit Chance",
    "degat_crit":      "Crit Damage",
    "vitesse_attaque": "Attack Speed",
    "double_chance":   "Double Chance",
    "damage_pct":      "Damage %",
    "skill_damage":    "Skill Damage",
    "ranged_pct":      "Ranged Dmg",
    "melee_pct":       "Melee Dmg",
    "chance_blocage":  "Block Chance",
    "lifesteal":       "Lifesteal",
    "health_regen":    "Health Regen",
    "skill_cooldown":  "Skill Cooldown",
    "health_pct":      "Health %",
}

# Valeur moyenne par tirage pour chaque stat
SUBSTATS_MOY_PAR_TIRAGE = {
    k: abs(lo + hi) / 2 if (lo + hi) != 0 else 1.0
    for k, (lo, hi) in SUBSTATS_POOL.items()
}

# Maximum théorique = 24 tirages × valeur moyenne par tirage
# → représente un build qui mettrait TOUS ses points dans cette stat
SUBSTATS_MAX_THEORIQUE = {
    k: N_SUBSTATS * SUBSTATS_MOY_PAR_TIRAGE[k]
    for k in SUBSTATS_POOL
}


# ════════════════════════════════════════════════════════════
#  GÉNÉRATION D'UN BUILD
# ════════════════════════════════════════════════════════════

def _build_depuis_substats(substats, hp_base, atk_base, type_attaque):
    """Calcule hp_total et attaque_total depuis les substats + bases."""
    hp_total  = hp_base * (1 + substats["health_pct"] / 100)
    bonus_atq = substats["damage_pct"] + (
        substats["ranged_pct"] if type_attaque == "distance" else substats["melee_pct"])
    atk_total = atk_base * (1 + bonus_atq / 100)

    return {
        **substats,
        "hp_total":      hp_total,
        "attaque_total": atk_total,
        "hp_base":       hp_base,
        "attaque_base":  atk_base,
        "type_attaque":  type_attaque,
    }


def _substats_vides():
    return {k: 0.0 for k in SUBSTATS_POOL}


def _distribuer_points(pool_actif):
    """
    Distribue N_SUBSTATS points sans biais :
    chaque point va dans une stat aléatoire du pool actif,
    avec une valeur uniforme dans son intervalle.
    """
    substats = _substats_vides()
    keys = list(pool_actif.keys())
    for _ in range(N_SUBSTATS):
        k = random.choice(keys)
        lo, hi = pool_actif[k]
        substats[k] += round(random.uniform(lo, hi), 2)
    return substats


def build_aleatoire(hp_base, atk_base, type_attaque):
    exclus   = "melee_pct" if type_attaque == "distance" else "ranged_pct"
    pool     = {k: v for k, v in SUBSTATS_POOL.items() if k != exclus}
    substats = _distribuer_points(pool)
    return _build_depuis_substats(substats, hp_base, atk_base, type_attaque)


# ════════════════════════════════════════════════════════════
#  MUTATION LOCALE
# ════════════════════════════════════════════════════════════

def muter(build, hp_base, atk_base, type_attaque, force=None):
    """
    Déplace 1 ou 2 points d'une stat vers une autre.
    Contrainte : la somme des points reste N_SUBSTATS.
    force=None → aléatoire entre 1 et 2 (parfois 3 pour échapper aux optima locaux)
    """
    exclus   = "melee_pct" if type_attaque == "distance" else "ranged_pct"
    pool     = {k: v for k, v in SUBSTATS_POOL.items() if k != exclus}
    keys     = list(pool.keys())
    substats = {k: build.get(k, 0.0) for k in SUBSTATS_POOL}

    if force is None:
        force = 3 if random.random() < 0.10 else random.randint(1, 2)

    for _ in range(force):
        sources = [k for k in keys if substats[k] != 0.0]
        if not sources:
            break
        src = random.choice(sources)
        lo_src, hi_src = pool[src]
        retire = round(random.uniform(lo_src, hi_src), 2)
        if lo_src >= 0:
            substats[src] = max(0.0, substats[src] - retire)
        else:
            substats[src] = min(0.0, substats[src] + abs(retire))

        cibles = [k for k in keys if k != src]
        dst    = random.choice(cibles)
        lo_dst, hi_dst = pool[dst]
        ajoute = round(random.uniform(lo_dst, hi_dst), 2)
        substats[dst] += ajoute

    return _build_depuis_substats(substats, hp_base, atk_base, type_attaque)


# ════════════════════════════════════════════════════════════
#  ÉVALUATION
# ════════════════════════════════════════════════════════════

def evaluer(build, adversaire, skills, n_sims):
    from backend.forge_master import simuler_100
    wins, loses, draws = simuler_100(build, adversaire, skills, skills, n=n_sims)
    total = wins + loses + draws
    return wins / total if total > 0 else 0.0


# ════════════════════════════════════════════════════════════
#  ANALYSE : MOYENNE + VARIANCE
# ════════════════════════════════════════════════════════════

def analyser(builds, scores):
    """
    Pour chaque substat, calcule dans le top 30% :
      - pts_moy  : nombre de points investis en moyenne (moyenne / moy_par_tirage)
      - pts_var  : écart-type du nombre de points (variance / moy_par_tirage)
      - moyenne  : valeur brute moyenne (pour affichage)
      - variance : écart-type brut

    Retourne [(pts_moy, pts_var, moyenne, variance, key, label), ...]
    trié par pts_moy desc.
    """
    n       = len(builds)
    n_top   = max(1, round(n * SELECTION_PCT))
    classes = sorted(range(n), key=lambda i: scores[i], reverse=True)
    top     = [builds[i] for i in classes[:n_top]]

    resultats = []
    for k in SUBSTATS_POOL:
        moy_tirage = SUBSTATS_MOY_PAR_TIRAGE[k]
        vals       = [abs(b.get(k, 0.0)) for b in top]
        moyenne    = sum(vals) / len(vals)
        variance   = math.sqrt(
            sum((v - moyenne) ** 2 for v in vals) / len(vals)
        ) if len(vals) > 1 else 0.0

        pts_moy = moyenne  / moy_tirage if moy_tirage else 0.0
        pts_var = variance / moy_tirage if moy_tirage else 0.0

        resultats.append((pts_moy, pts_var, moyenne, variance, k, SUBSTATS_LABELS.get(k, k)))

    return sorted(resultats, key=lambda x: x[0], reverse=True)


# ════════════════════════════════════════════════════════════
#  BOUCLE PRINCIPALE
# ════════════════════════════════════════════════════════════

def optimiser(
    profil,
    skills,
    n_generations=8,
    n_sims=100,
    generation_cb=None,
    progress_cb=None,
    stop_flag=None,
):
    hp_base      = profil["hp_base"]
    atk_base     = profil["attaque_base"]
    type_attaque = profil.get("type_attaque", "corps_a_corps")

    from backend.forge_master import stats_combat
    adversaire = stats_combat(profil)

    builds = [build_aleatoire(hp_base, atk_base, type_attaque)
              for _ in range(N_BUILDS)]

    top_builds = []
    analyse    = []

    for gen in range(1, n_generations + 1):
        if stop_flag and stop_flag.is_set():
            break

        scores = []
        for i, b in enumerate(builds):
            if stop_flag and stop_flag.is_set():
                break
            scores.append(evaluer(b, adversaire, skills, n_sims))
            if progress_cb:
                progress_cb(i + 1, len(builds), gen)

        if not scores:
            break

        analyse    = analyser(builds, scores)
        classes    = sorted(zip(scores, builds), key=lambda x: x[0], reverse=True)
        top_scores = [s for s, _ in classes[:N_SURVIVORS]]
        top_builds = [b for _, b in classes[:N_SURVIVORS]]
        wr_moyen   = sum(top_scores) / len(top_scores)

        if generation_cb:
            # Meilleur build = premier du classement
            meilleur = top_builds[0]
            generation_cb(gen, top_builds, analyse, top_scores, wr_moyen, meilleur)

        nouveaux = list(top_builds)
        while len(nouveaux) < N_BUILDS:
            parent = random.choice(top_builds)
            nouveaux.append(muter(parent, hp_base, atk_base, type_attaque))
        builds = nouveaux

    return top_builds, analyse