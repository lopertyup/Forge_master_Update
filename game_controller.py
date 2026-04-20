"""
============================================================
  FORGE MASTER — GameController (bridge UI <-> backend)
  FIX : callbacks thread-safe + logique tester_pet corrigée
============================================================
"""

import threading
from backend.forge_master import (
    charger_profil, sauvegarder_profil,
    charger_skills, charger_pets, sauvegarder_pets,
    parser_texte, finaliser_bases, stats_combat,
    parser_equipement, appliquer_changement,
    parser_pet, appliquer_pet,
    simuler_100,
    PETS_STATS_KEYS,
)


class GameController:
    """Point d'entrée unique pour toute l'UI."""

    def __init__(self):
        self._profil      = None
        self._skills      = []
        self._pets        = {}
        self._tous_skills = {}
        self._tk_root     = None   # référence au widget racine pour after()
        self.reload()

    def set_tk_root(self, root):
        """Enregistre la référence Tkinter root pour les callbacks thread-safe."""
        self._tk_root = root

    # ── Chargement ──────────────────────────────────────────

    def reload(self):
        self._profil, self._skills = charger_profil()
        self._pets                 = charger_pets()
        self._tous_skills          = charger_skills()

    # ── Profil ──────────────────────────────────────────────

    def has_profil(self) -> bool:
        return self._profil is not None

    def get_profil(self) -> dict:
        return dict(self._profil) if self._profil else {}

    def get_skills_actifs(self) -> list:
        return list(self._skills)

    def get_tous_skills(self) -> dict:
        return dict(self._tous_skills)

    def importer_texte_profil(self, texte: str, type_attaque: str) -> dict:
        stats = parser_texte(texte)
        stats["type_attaque"] = type_attaque
        stats = finaliser_bases(stats)
        return stats

    def set_profil(self, profil: dict, skills: list):
        self._profil = profil
        self._skills = skills
        sauvegarder_profil(profil, skills)

    def get_skills_from_codes(self, codes: list) -> list:
        result = []
        for code in codes[:3]:
            code = code.strip().lower()
            if code in self._tous_skills:
                result.append((code, self._tous_skills[code]))
        return result

    # ── Helpers thread-safe ──────────────────────────────────

    def _dispatch(self, callback, *args):
        """
        Appelle callback(*args) dans le thread principal Tkinter.
        Utilise after(0, ...) si on a une référence root, sinon appel direct.
        """
        if self._tk_root is not None:
            self._tk_root.after(0, lambda: callback(*args))
        else:
            callback(*args)

    # ── Simulation ──────────────────────────────────────────

    def simuler(
        self,
        stats_adversaire: dict,
        skills_adversaire: list,
        callback,
        profil_override=None,
        skills_override=None,
    ):
        """Lance 1000 simulations dans un thread secondaire."""
        profil = profil_override if profil_override else self._profil
        skills = skills_override if skills_override else self._skills

        if profil is None:
            self._dispatch(callback, 0, 0, 0)
            return

        sj = stats_combat(profil)
        se = stats_adversaire

        def _run():
            w, l, d = simuler_100(sj, se, skills, skills_adversaire)
            self._dispatch(callback, w, l, d)

        threading.Thread(target=_run, daemon=True).start()

    # ── Équipements ─────────────────────────────────────────

    def comparer_equipement(self, texte_comparaison: str):
        import re
        if not re.search(r'NEW\s*!', texte_comparaison, re.IGNORECASE):
            return None

        parties       = re.split(r'NEW\s*!', texte_comparaison, flags=re.IGNORECASE)
        texte_ancien  = parties[0]
        texte_nouveau = parties[1] if len(parties) > 1 else ""

        eq_ancien  = parser_equipement(texte_ancien)
        eq_nouveau = parser_equipement(texte_nouveau)

        if self._profil is None:
            return None

        profil_nouveau = appliquer_changement(self._profil, eq_ancien, eq_nouveau)
        return eq_ancien, eq_nouveau, profil_nouveau

    def appliquer_equipement(self, profil_nouveau: dict):
        self._profil = profil_nouveau
        sauvegarder_profil(profil_nouveau, self._skills)

    # ── Pets ────────────────────────────────────────────────

    def get_pets(self) -> dict:
        return {k: dict(v) for k, v in self._pets.items()}

    def get_pet(self, nom: str) -> dict:
        return dict(self._pets.get(nom, {}))

    def importer_texte_pet(self, texte: str) -> dict:
        return parser_pet(texte)

    def set_pet(self, nom: str, pet: dict):
        self._pets[nom] = pet
        sauvegarder_pets(self._pets)

    def tester_pet(self, nouveau_pet: dict, callback):
        """
        Simule le remplacement du nouveau pet pour chaque slot.
        Pour chaque slot : NOUVEAU_MOI (avec nouveau pet) vs ANCIEN_MOI (avec ancien pet).
        DUREE_MAX réduit à 60s pour éviter les combats infinis entre deux versions de soi.
        """
        if self._profil is None:
            self._dispatch(callback, {})
            return

        profil_actuel = dict(self._profil)
        pets_actuels  = {k: dict(v) for k, v in self._pets.items()}
        skills        = list(self._skills)

        def _run():
            import backend.forge_master as fm
            duree_originale = fm.DUREE_MAX
            fm.DUREE_MAX    = 60.0
            try:
                resultats = {}
                for nom in ["PET1", "PET2", "PET3"]:
                    pet_ancien     = pets_actuels.get(nom, {k: 0.0 for k in PETS_STATS_KEYS})
                    profil_nouveau = appliquer_pet(profil_actuel, pet_ancien, nouveau_pet)
                    sj = stats_combat(profil_nouveau)   # nouveau moi
                    se = stats_combat(profil_actuel)    # ancien moi
                    wins, loses, draws = 0, 0, 0
                    for _ in range(1000):
                        r = fm.simuler(sj, se, skills, skills)
                        if r == "WIN":    wins  += 1
                        elif r == "LOSE": loses += 1
                        else:             draws += 1
                    resultats[nom] = (wins, loses, draws)
            finally:
                fm.DUREE_MAX = duree_originale
            self._dispatch(callback, resultats)

        threading.Thread(target=_run, daemon=True).start()

    # ── Helpers UI ──────────────────────────────────────────

    @staticmethod
    def fmt_nombre(n: float) -> str:
        if n >= 1_000_000_000:
            return f"{n/1_000_000_000:.2f}B"
        elif n >= 1_000_000:
            return f"{n/1_000_000:.2f}M"
        elif n >= 1_000:
            return f"{n/1_000:.1f}K"
        return f"{n:.0f}"

    @staticmethod
    def rarity_color(rarity: str) -> str:
        return {
            "common":    "#9E9E9E",
            "rare":      "#2196F3",
            "epic":      "#9C27B0",
            "legendary": "#FF9800",
            "ultimate":  "#F44336",
            "mythic":    "#E91E63",
        }.get(str(rarity).lower(), "#9E9E9E")

    @staticmethod
    def stats_display_list() -> list:
        return [
            ("hp_total",        "❤  HP Total",         True),
            ("attaque_total",   "⚔  ATQ Total",         True),
            ("hp_base",         "   HP Base",           True),
            ("attaque_base",    "   ATQ Base",          True),
            ("health_pct",      "❤  Health %",          False),
            ("damage_pct",      "⚔  Damage %",          False),
            ("melee_pct",       "⚔  Melee %",           False),
            ("ranged_pct",      "⚔  Ranged %",          False),
            ("taux_crit",       "🎯 Crit Chance",        False),
            ("degat_crit",      "💥 Crit Damage",        False),
            ("health_regen",    "♻  Health Regen",      False),
            ("lifesteal",       "🩸 Lifesteal",          False),
            ("double_chance",   "✌  Double Chance",     False),
            ("vitesse_attaque", "⚡ Attack Speed",       False),
            ("skill_damage",    "✨ Skill Damage",       False),
            ("skill_cooldown",  "⏱  Skill Cooldown",    False),
            ("chance_blocage",  "🛡  Block Chance",      False),
        ]