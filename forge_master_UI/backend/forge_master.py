"""
============================================================
  FORGE MASTER — Backend (logique de jeu pure)
  Ce fichier est le backend original, adapté pour fonctionner
  depuis n'importe quel répertoire de travail.
============================================================
"""

import re
import random
import os
import sys

# ── Chemins relatifs au dossier backend/ ──────────────────
_DIR = os.path.dirname(os.path.abspath(__file__))
PROFIL_FILE = os.path.join(_DIR, "profil.txt")
SKILLS_FILE = os.path.join(_DIR, "skills.txt")
PETS_FILE   = os.path.join(_DIR, "pets.txt")

TICK            = 0.01
DUREE_MAX       = 300
VITESSE_BASE    = 0.5
AVANCE_DISTANCE = 3.0

STATS_KEYS = [
    "hp_total", "attaque_total",
    "hp_base", "attaque_base",
    "health_pct", "damage_pct", "melee_pct", "ranged_pct",
    "taux_crit", "degat_crit", "health_regen",
    "lifesteal", "double_chance", "vitesse_attaque",
    "skill_damage", "skill_cooldown", "chance_blocage"
]

PETS_STATS_KEYS = [
    "hp_flat", "damage_flat", "health_pct", "damage_pct",
    "melee_pct", "ranged_pct", "taux_crit", "degat_crit",
    "health_regen", "lifesteal", "double_chance", "vitesse_attaque",
    "skill_damage", "skill_cooldown", "chance_blocage"
]


# ════════════════════════════════════════════════════════════
#  UTILITAIRES
# ════════════════════════════════════════════════════════════

def parse_flat(val_str):
    val_str = str(val_str).strip().lower().replace(",", ".")
    try:
        if val_str.endswith("b"):
            return float(val_str[:-1]) * 1_000_000_000
        elif val_str.endswith("m"):
            return float(val_str[:-1]) * 1_000_000
        elif val_str.endswith("k"):
            return float(val_str[:-1]) * 1_000
        else:
            return float(val_str)
    except ValueError:
        return 0.0


def extraire(texte, motifs):
    for motif in motifs:
        m = re.search(motif, texte, re.IGNORECASE)
        if m:
            try:
                return float(m.group(1).replace(",", ".").replace(" ", "."))
            except ValueError:
                continue
    return 0.0


def extraire_flat(texte, motifs):
    for motif in motifs:
        m = re.search(motif, texte, re.IGNORECASE)
        if m:
            return parse_flat(m.group(1))
    return 0.0


# ════════════════════════════════════════════════════════════
#  PARSING PROFIL
# ════════════════════════════════════════════════════════════

def parser_texte(texte):
    hp_total      = extraire_flat(texte, [r"([\d.]+[km]?)\s*Total Health"])
    attaque_total = extraire_flat(texte, [r"([\d.]+[km]?)\s*Total Damage"])
    health_pct    = extraire(texte, [r"\+([\d. ]+)%\s*Health(?!\s*Regen)"])
    damage_pct    = extraire(texte, [r"\+([\d. ]+)%\s*Damage(?!\s*%)"])
    melee_pct     = extraire(texte, [r"\+([\d. ]+)%\s*Melee Damage"])
    ranged_pct    = extraire(texte, [r"\+([\d. ]+)%\s*Ranged Damage"])

    hp_base      = hp_total / (1 + health_pct / 100) if health_pct else hp_total
    attaque_base = attaque_total

    return {
        "hp_total":       hp_total,
        "attaque_total":  attaque_total,
        "hp_base":        hp_base,
        "attaque_base":   attaque_base,
        "health_pct":     health_pct,
        "damage_pct":     damage_pct,
        "melee_pct":      melee_pct,
        "ranged_pct":     ranged_pct,
        "taux_crit":      extraire(texte, [r"\+([\d. ]+)%\s*Critical Chance"]),
        "degat_crit":     extraire(texte, [r"\+([\d. ]+)%\s*Critical Damage"]),
        "health_regen":   extraire(texte, [r"\+([\d. ]+)%\s*Health Regen"]),
        "lifesteal":      extraire(texte, [r"\+([\d. ]+)%\s*Lifesteal"]),
        "double_chance":  extraire(texte, [r"\+([\d. ]+)%\s*Double Chance"]),
        "vitesse_attaque":extraire(texte, [r"\+([\d. ]+)%\s*Attack Speed"]),
        "skill_damage":   extraire(texte, [r"\+([\d. ]+)%\s*Skill Damage"]),
        "skill_cooldown": extraire(texte, [r"([+-][\d. ]+)%\s*Skill Cooldown"]),
        "chance_blocage": extraire(texte, [r"\+([\d. ]+)%\s*Block Chance"]),
    }


def finaliser_bases(profil):
    type_atq   = profil.get("type_attaque", "corps_a_corps")
    damage_pct = profil.get("damage_pct", 0)
    melee_pct  = profil.get("melee_pct", 0)
    ranged_pct = profil.get("ranged_pct", 0)

    if type_atq == "distance":
        bonus = damage_pct + ranged_pct
    else:
        bonus = damage_pct + melee_pct

    total = profil.get("attaque_total", 0)
    profil["attaque_base"] = total / (1 + bonus / 100) if bonus else total
    return profil


def stats_combat(profil):
    return {
        "hp":              profil["hp_total"],
        "attaque":         profil["attaque_total"],
        "taux_crit":       profil["taux_crit"],
        "degat_crit":      profil["degat_crit"],
        "health_regen":    profil["health_regen"],
        "lifesteal":       profil["lifesteal"],
        "double_chance":   profil["double_chance"],
        "vitesse_attaque": profil["vitesse_attaque"],
        "skill_damage":    profil["skill_damage"],
        "skill_cooldown":  profil["skill_cooldown"],
        "chance_blocage":  profil["chance_blocage"],
        "type_attaque":    profil["type_attaque"],
    }


# ════════════════════════════════════════════════════════════
#  PARSING EQUIPEMENT
# ════════════════════════════════════════════════════════════

def parser_equipement(texte):
    texte_net = re.sub(r'\b[A-Z]\s*$', '', texte, flags=re.MULTILINE)
    texte_net = re.sub(r'\n(?![+\-\[\dNEQV])', ' ', texte_net)

    eq = {k: 0.0 for k in [
        "hp_flat", "damage_flat", "health_pct", "damage_pct",
        "melee_pct", "ranged_pct", "taux_crit", "degat_crit",
        "health_regen", "lifesteal", "double_chance", "vitesse_attaque",
        "skill_damage", "skill_cooldown", "chance_blocage"
    ]}
    eq["type_attaque"] = None

    m = re.search(r'([\d.]+[km]?)\s*Health(?!\s*Regen)(?!\s*%)', texte_net, re.IGNORECASE)
    if m:
        eq["hp_flat"] = parse_flat(m.group(1))

    m = re.search(r'([\d.]+[km]?)\s*Damage(?!\s*%)(\s*\(.*?\))?', texte_net, re.IGNORECASE)
    if m:
        eq["damage_flat"] = parse_flat(m.group(1))

    if re.search(r'\(.*ranged.*\)', texte_net, re.IGNORECASE):
        eq["type_attaque"] = "distance"
    elif eq["damage_flat"] > 0:
        eq["type_attaque"] = "corps_a_corps"

    eq["taux_crit"]       = extraire(texte_net, [r"\+([\d. ]+)%\s*Critical Chance"])
    eq["degat_crit"]      = extraire(texte_net, [r"\+([\d. ]+)%\s*Critical Damage"])
    eq["health_regen"]    = extraire(texte_net, [r"\+([\d. ]+)%\s*Health Regen"])
    eq["lifesteal"]       = extraire(texte_net, [r"\+([\d. ]+)%\s*Lifesteal"])
    eq["double_chance"]   = extraire(texte_net, [r"\+([\d. ]+)%\s*Double Chance"])
    eq["vitesse_attaque"] = extraire(texte_net, [r"\+([\d. ]+)%\s*Attack Speed"])
    eq["skill_damage"]    = extraire(texte_net, [r"\+([\d. ]+)%\s*Skill Damage"])
    eq["skill_cooldown"]  = extraire(texte_net, [r"([+-][\d. ]+)%\s*Skill Cooldown"])
    eq["chance_blocage"]  = extraire(texte_net, [r"\+([\d. ]+)%\s*Block Chance"])
    eq["health_pct"]      = extraire(texte_net, [r"\+([\d. ]+)%\s*Health(?!\s*Regen)"])
    eq["damage_pct"]      = extraire(texte_net, [r"\+([\d. ]+)%\s*Damage(?!\s*%)"])
    eq["melee_pct"]       = extraire(texte_net, [r"\+([\d. ]+)%\s*Melee Damage"])
    eq["ranged_pct"]      = extraire(texte_net, [r"\+([\d. ]+)%\s*Ranged Damage"])

    return eq


def appliquer_changement(profil, eq_ancien, eq_nouveau):
    nouveau = dict(profil)
    type_atq = profil.get("type_attaque", "corps_a_corps")

    for k in ["taux_crit", "degat_crit", "health_regen", "lifesteal",
              "double_chance", "vitesse_attaque", "skill_damage",
              "skill_cooldown", "chance_blocage",
              "health_pct", "damage_pct", "melee_pct", "ranged_pct"]:
        nouveau[k] = round(profil.get(k, 0.0) - eq_ancien.get(k, 0.0) + eq_nouveau.get(k, 0.0), 6)

    if eq_nouveau.get("type_attaque") is not None:
        nouveau["type_attaque"] = eq_nouveau["type_attaque"]
        type_atq = nouveau["type_attaque"]

    nouveau["hp_base"]      = profil["hp_base"] - eq_ancien.get("hp_flat", 0) + eq_nouveau.get("hp_flat", 0)
    nouveau["attaque_base"] = profil["attaque_base"] - eq_ancien.get("damage_flat", 0) + eq_nouveau.get("damage_flat", 0)
    nouveau["hp_total"]     = nouveau["hp_base"] * (1 + nouveau["health_pct"] / 100)

    if type_atq == "distance":
        bonus_atq = nouveau["damage_pct"] + nouveau["ranged_pct"]
    else:
        bonus_atq = nouveau["damage_pct"] + nouveau["melee_pct"]
    nouveau["attaque_total"] = nouveau["attaque_base"] * (1 + bonus_atq / 100)

    return nouveau


# ════════════════════════════════════════════════════════════
#  SAUVEGARDE / CHARGEMENT PROFIL
# ════════════════════════════════════════════════════════════

def sauvegarder_profil(joueur, skills=None):
    with open(PROFIL_FILE, "w", encoding="utf-8") as f:
        f.write("# ============================================================\n")
        f.write("# FORGE MASTER — Profil joueur (modifiable a la main)\n")
        f.write("# ============================================================\n\n")
        f.write("[JOUEUR]\n")
        for k in STATS_KEYS:
            f.write(f"{k:20s} = {joueur.get(k, 0.0)}\n")
        f.write(f"{'type_attaque':20s} = {joueur.get('type_attaque', 'corps_a_corps')}\n")
        codes = ",".join(c for c, _ in (skills or []))
        f.write(f"{'skills':20s} = {codes}\n\n")


def lire_section(lignes, debut):
    stats = {}
    for ligne in lignes[debut:]:
        ligne = ligne.strip()
        if ligne.startswith("[") and ligne != lignes[debut].strip():
            break
        if "=" not in ligne or ligne.startswith("#"):
            continue
        cle, val = ligne.split("=", 1)
        cle, val = cle.strip(), val.strip()
        if cle == "type_attaque":
            stats[cle] = val
        else:
            try:
                stats[cle] = float(val)
            except ValueError:
                pass
    return stats if stats else None


def charger_profil():
    if not os.path.isfile(PROFIL_FILE):
        return None, []
    with open(PROFIL_FILE, "r", encoding="utf-8") as f:
        lignes = f.readlines()
    profil = None
    skills_codes = ""
    for i, ligne in enumerate(lignes):
        if ligne.strip() == "[JOUEUR]":
            profil = lire_section(lignes, i + 1)
        if "skills" in ligne and "=" in ligne:
            skills_codes = ligne.split("=", 1)[1].strip()
    if profil is None:
        return None, []
    tous_skills = charger_skills()
    skills = []
    if skills_codes:
        for code in skills_codes.split(","):
            code = code.strip()
            if code and code in tous_skills:
                skills.append((code, tous_skills[code]))
    return profil, skills


# ════════════════════════════════════════════════════════════
#  SKILLS
# ════════════════════════════════════════════════════════════

def charger_skills():
    if not os.path.isfile(SKILLS_FILE):
        return {}
    skills = {}
    current_code = None
    current = {}
    with open(SKILLS_FILE, "r", encoding="utf-8") as f:
        for ligne in f:
            ligne = ligne.strip()
            if ligne.startswith("#") or ligne == "":
                continue
            if ligne.startswith("[") and ligne.endswith("]"):
                if current_code:
                    skills[current_code] = current
                current_code = ligne[1:-1].lower()
                current = {}
            elif "=" in ligne:
                cle, val = ligne.split("=", 1)
                cle, val = cle.strip(), val.strip()
                try:
                    current[cle] = float(val)
                except ValueError:
                    current[cle] = val
        if current_code:
            skills[current_code] = current
    return skills


# ════════════════════════════════════════════════════════════
#  SIMULATION
# ════════════════════════════════════════════════════════════

class SkillInstance:
    DELAI_INITIAL = 3.8

    def __init__(self, data, skill_damage_pct, skill_cooldown_pct):
        self.data          = data
        self.nom           = data["name"]
        self.type_skill    = data["type"]
        self.hits          = int(data.get("hits", 1))
        self.cooldown_base = float(data.get("cooldown", 10.0))
        self.buff_dur      = float(data.get("buff_duration", 0.0))
        self.buff_atq      = float(data.get("buff_atq", 0.0))
        self.buff_hp       = float(data.get("buff_hp", 0.0))

        sd = skill_damage_pct / 100.0
        sc = skill_cooldown_pct / 100.0
        dmg_base          = float(data.get("damage", 0.0))
        self.dmg_par_hit  = dmg_base * (1 + sd)
        self.cooldown     = self.cooldown_base * (1 + sc)
        if self.cooldown < 0.1:
            self.cooldown = 0.1

        self.timer         = -self.DELAI_INITIAL
        self.hit_interval  = self.cooldown / self.hits if self.hits > 1 else 0
        self.hit_timer     = 0.0
        self.hits_restants = 0
        self.buff_actif    = False
        self.buff_timer    = 0.0
        self.atq_bonus     = 0.0
        self.hp_bonus      = 0.0

    def tick(self, dt, porteur, cible):
        self.timer += dt
        if self.type_skill == "damage":
            self._tick_damage(dt, cible)
        elif self.type_skill == "buff":
            self._tick_buff(dt, porteur)

    def _tick_damage(self, dt, cible):
        if self.hits_restants > 0:
            self.hit_timer += dt
            if self.hit_timer >= self.hit_interval or self.hits == 1:
                if cible.vivant():
                    cible.hp -= self.dmg_par_hit
                self.hits_restants -= 1
                self.hit_timer = 0.0
        elif self.timer >= self.cooldown:
            self.timer = 0.0
            self.hits_restants = self.hits - 1
            self.hit_timer = 0.0
            if cible.vivant():
                cible.hp -= self.dmg_par_hit

    def _tick_buff(self, dt, porteur):
        if self.buff_actif:
            self.buff_timer += dt
            if self.buff_timer >= self.buff_dur:
                porteur.attaque -= self.atq_bonus
                self.atq_bonus   = 0.0
                self.hp_bonus    = 0.0
                self.buff_actif  = False
                self.buff_timer  = 0.0
        else:
            if self.timer >= self.cooldown:
                self.timer      = 0.0
                self.buff_actif = True
                self.buff_timer = 0.0
                self.atq_bonus  = self.buff_atq
                self.hp_bonus   = self.buff_hp
                porteur.attaque += self.atq_bonus
                porteur.hp      += self.hp_bonus


class Combattant:
    def __init__(self, s, skills_actifs=None):
        self.hp_max          = s.get("hp_total", s.get("hp", 0))
        self.hp              = float(self.hp_max)
        self.health_regen    = s["health_regen"] / 100.0
        self.attaque         = s.get("attaque_total", s.get("attaque", 0))
        self.vitesse_attaque = s["vitesse_attaque"] / 100.0
        self.double_chance   = s["double_chance"] / 100.0
        self.lifesteal       = s["lifesteal"] / 100.0
        self.taux_crit       = s["taux_crit"] / 100.0
        self.degat_crit      = s["degat_crit"] / 100.0
        self.chance_blocage  = s["chance_blocage"] / 100.0
        self.type_attaque    = s["type_attaque"]
        self.freq            = VITESSE_BASE * (1.0 + self.vitesse_attaque)
        self.intervalle      = 1.0 / self.freq
        self.timer           = 0.0
        sd = s.get("skill_damage", 0.0)
        sc = s.get("skill_cooldown", 0.0)
        self.skills = [SkillInstance(data, sd, sc) for _, data in (skills_actifs or [])]

    def vivant(self):
        return self.hp > 0

    def regenerer(self, dt):
        if self.hp < self.hp_max:
            self.hp = min(self.hp_max, self.hp + self.hp_max * self.health_regen * dt)

    def frapper(self, cible):
        coups = 2 if random.random() < self.double_chance else 1
        for _ in range(coups):
            if random.random() < cible.chance_blocage:
                continue
            dmg = self.attaque * (1 + self.degat_crit) if random.random() < self.taux_crit else self.attaque
            cible.hp -= dmg
            self.hp = min(self.hp_max, self.hp + dmg * self.lifesteal)


def simuler(sj, se, skills_j=None, skills_e=None):
    j = Combattant(sj, skills_j)
    e = Combattant(se, skills_e)

    if j.type_attaque == e.type_attaque:
        j.timer, e.timer = 0.0, 0.0
    elif j.type_attaque == "distance":
        j.timer, e.timer = 0.0, -AVANCE_DISTANCE
    else:
        j.timer, e.timer = -AVANCE_DISTANCE, 0.0

    temps = 0.0
    while temps < DUREE_MAX:
        if not j.vivant() or not e.vivant():
            break
        j.regenerer(TICK)
        e.regenerer(TICK)
        for sk in j.skills:
            sk.tick(TICK, j, e)
        for sk in e.skills:
            sk.tick(TICK, e, j)
        j.timer += TICK
        e.timer += TICK
        if j.timer >= j.intervalle:
            j.timer = 0.0
            if e.vivant():
                j.frapper(e)
        if e.timer >= e.intervalle:
            e.timer = 0.0
            if j.vivant():
                e.frapper(j)
        temps += TICK

    if j.vivant() and not e.vivant():
        return "WIN"
    elif e.vivant() and not j.vivant():
        return "LOSE"
    elif not j.vivant() and not e.vivant():
        return "LOSE"
    else:
        return "DRAW"


def simuler_100(sj, se, skills_j=None, skills_e=None):
    wins, loses, draws = 0, 0, 0
    for _ in range(1000):
        r = simuler(sj, se, skills_j, skills_e)
        if r == "WIN":      wins += 1
        elif r == "LOSE":   loses += 1
        else:               draws += 1
    return wins, loses, draws


# ════════════════════════════════════════════════════════════
#  PETS
# ════════════════════════════════════════════════════════════

def pet_vide():
    return {k: 0.0 for k in PETS_STATS_KEYS}


def charger_pets():
    pets = {"PET1": pet_vide(), "PET2": pet_vide(), "PET3": pet_vide()}
    if not os.path.isfile(PETS_FILE):
        return pets
    with open(PETS_FILE, "r", encoding="utf-8") as f:
        lignes = f.readlines()
    current = None
    for ligne in lignes:
        ligne = ligne.strip()
        if ligne.startswith("#") or ligne == "":
            continue
        if ligne in ("[PET1]", "[PET2]", "[PET3]"):
            current = ligne[1:-1]
        elif current and "=" in ligne:
            cle, val = ligne.split("=", 1)
            cle, val = cle.strip(), val.strip()
            try:
                pets[current][cle] = float(val)
            except ValueError:
                pass
    return pets


def sauvegarder_pets(pets):
    with open(PETS_FILE, "w", encoding="utf-8") as f:
        f.write("# ============================================================\n")
        f.write("# FORGE MASTER — Pets actifs (modifiable a la main)\n")
        f.write("# ============================================================\n\n")
        for nom in ["PET1", "PET2", "PET3"]:
            pet = pets.get(nom, pet_vide())
            f.write(f"[{nom}]\n")
            for k in PETS_STATS_KEYS:
                f.write(f"{k:20s} = {pet.get(k, 0.0)}\n")
            f.write("\n")


def parser_pet(texte):
    texte_net = re.sub(r'\n(?![+\-\[\d])', ' ', texte)
    pet = pet_vide()

    m = re.search(r'([\d.]+[km]?)\s*Health(?!\s*Regen)(?!\s*%)', texte_net, re.IGNORECASE)
    if m:
        pet["hp_flat"] = parse_flat(m.group(1))

    m = re.search(r'([\d.]+[km]?)\s*Damage(?!\s*%)', texte_net, re.IGNORECASE)
    if m:
        pet["damage_flat"] = parse_flat(m.group(1))

    pet["taux_crit"]       = extraire(texte_net, [r"\+([\d. ]+)%\s*Critical Chance"])
    pet["degat_crit"]      = extraire(texte_net, [r"\+([\d. ]+)%\s*Critical Damage"])
    pet["health_regen"]    = extraire(texte_net, [r"\+([\d. ]+)%\s*Health Regen"])
    pet["lifesteal"]        = extraire(texte_net, [r"\+([\d. ]+)%\s*Lifesteal"])
    pet["double_chance"]   = extraire(texte_net, [r"\+([\d. ]+)%\s*Double Chance"])
    pet["vitesse_attaque"] = extraire(texte_net, [r"\+([\d. ]+)%\s*Attack Speed"])
    pet["skill_damage"]    = extraire(texte_net, [r"\+([\d. ]+)%\s*Skill Damage"])
    pet["skill_cooldown"]  = extraire(texte_net, [r"([+-][\d. ]+)%\s*Skill Cooldown"])
    pet["chance_blocage"]  = extraire(texte_net, [r"\+([\d. ]+)%\s*Block Chance"])
    pet["health_pct"]      = extraire(texte_net, [r"\+([\d. ]+)%\s*Health(?!\s*Regen)"])
    pet["damage_pct"]      = extraire(texte_net, [r"\+([\d. ]+)%\s*Damage(?!\s*%)"])
    pet["melee_pct"]       = extraire(texte_net, [r"\+([\d. ]+)%\s*Melee Damage"])
    pet["ranged_pct"]      = extraire(texte_net, [r"\+([\d. ]+)%\s*Ranged Damage"])

    return pet


def appliquer_pet(profil, pet_ancien, pet_nouveau):
    nouveau = dict(profil)
    type_atq = profil.get("type_attaque", "corps_a_corps")

    for k in ["taux_crit", "degat_crit", "health_regen", "lifesteal",
              "double_chance", "vitesse_attaque", "skill_damage",
              "skill_cooldown", "chance_blocage",
              "health_pct", "damage_pct", "melee_pct", "ranged_pct"]:
        nouveau[k] = round(profil.get(k, 0.0) - pet_ancien.get(k, 0.0) + pet_nouveau.get(k, 0.0), 6)

    nouveau["hp_base"]      = profil["hp_base"] - pet_ancien.get("hp_flat", 0) + pet_nouveau.get("hp_flat", 0)
    nouveau["attaque_base"] = profil["attaque_base"] - pet_ancien.get("damage_flat", 0) + pet_nouveau.get("damage_flat", 0)
    nouveau["hp_total"]     = nouveau["hp_base"] * (1 + nouveau["health_pct"] / 100)

    if type_atq == "distance":
        bonus = nouveau["damage_pct"] + nouveau["ranged_pct"]
    else:
        bonus = nouveau["damage_pct"] + nouveau["melee_pct"]
    nouveau["attaque_total"] = nouveau["attaque_base"] * (1 + bonus / 100)

    return nouveau
