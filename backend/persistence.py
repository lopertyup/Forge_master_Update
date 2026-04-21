"""
============================================================
  FORGE MASTER — Persistance (lecture / écriture fichiers)
  Lecture et écriture de profil.txt, pets.txt, mount.txt, skills.txt.
============================================================
"""

import logging
import os
from typing import Dict, List, Optional, Tuple

from .constants import (
    COMPANION_STATS_KEYS,
    MOUNT_FILE,
    MOUNT_LIBRARY_FILE,
    PETS_FILE,
    PETS_LIBRARY_FILE,
    PROFIL_FILE,
    SKILLS_FILE,
    STATS_KEYS,
)

log = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════
#  PROFIL + SKILLS ACTIFS
# ════════════════════════════════════════════════════════════

def sauvegarder_profil(joueur: Dict, skills: Optional[List[Tuple[str, Dict]]] = None) -> None:
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


def _lire_section(lignes: List[str], debut: int) -> Optional[Dict]:
    """
    Lit une section key=value jusqu'au prochain header [...] ou la fin du fichier.
    `debut` doit pointer sur la première ligne APRÈS le header [SECTION].
    """
    stats: Dict = {}
    for ligne in lignes[debut:]:
        ligne = ligne.strip()
        if ligne.startswith("["):
            break
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        cle, val = ligne.split("=", 1)
        cle, val = cle.strip(), val.strip()
        if cle == "type_attaque":
            stats[cle] = val
        else:
            try:
                stats[cle] = float(val)
            except ValueError:
                log.warning("profil.txt: valeur invalide pour %s = %r", cle, val)
    return stats if stats else None


def charger_profil() -> Tuple[Optional[Dict], List[Tuple[str, Dict]]]:
    if not os.path.isfile(PROFIL_FILE):
        return None, []

    with open(PROFIL_FILE, "r", encoding="utf-8") as f:
        lignes = f.readlines()

    profil: Optional[Dict] = None
    skills_codes = ""
    for i, ligne in enumerate(lignes):
        if ligne.strip() == "[JOUEUR]":
            profil = _lire_section(lignes, i + 1)
        elif "skills" in ligne and "=" in ligne:
            skills_codes = ligne.split("=", 1)[1].strip()

    if profil is None:
        return None, []

    tous_skills = charger_skills()
    skills: List[Tuple[str, Dict]] = []
    if skills_codes:
        for code in skills_codes.split(","):
            code = code.strip()
            if code and code in tous_skills:
                skills.append((code, tous_skills[code]))
    return profil, skills


# ════════════════════════════════════════════════════════════
#  SKILLS (catalogue)
# ════════════════════════════════════════════════════════════

def charger_skills() -> Dict[str, Dict]:
    if not os.path.isfile(SKILLS_FILE):
        return {}

    skills: Dict[str, Dict] = {}
    current_code: Optional[str] = None
    current: Dict = {}

    with open(SKILLS_FILE, "r", encoding="utf-8") as f:
        for ligne in f:
            ligne = ligne.strip()
            if not ligne or ligne.startswith("#"):
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
#  PETS
# ════════════════════════════════════════════════════════════

def companion_vide() -> Dict[str, float]:
    return {k: 0.0 for k in COMPANION_STATS_KEYS}


# Alias rétrocompatible
pet_vide   = companion_vide
mount_vide = companion_vide


def charger_pets() -> Dict[str, Dict[str, float]]:
    pets = {nom: companion_vide() for nom in ("PET1", "PET2", "PET3")}
    if not os.path.isfile(PETS_FILE):
        return pets

    with open(PETS_FILE, "r", encoding="utf-8") as f:
        lignes = f.readlines()

    current: Optional[str] = None
    for ligne in lignes:
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#"):
            continue
        if ligne in ("[PET1]", "[PET2]", "[PET3]"):
            current = ligne[1:-1]
        elif current and "=" in ligne:
            cle, val = ligne.split("=", 1)
            cle, val = cle.strip(), val.strip()
            if cle in ("__name__", "__rarity__"):
                pets[current][cle] = val
            else:
                try:
                    pets[current][cle] = float(val)
                except ValueError:
                    log.warning("pets.txt: valeur invalide pour %s.%s = %r", current, cle, val)
    return pets


def sauvegarder_pets(pets: Dict[str, Dict[str, float]]) -> None:
    with open(PETS_FILE, "w", encoding="utf-8") as f:
        f.write("# ============================================================\n")
        f.write("# FORGE MASTER — Pets actifs (modifiable a la main)\n")
        f.write("# ============================================================\n\n")
        for nom in ("PET1", "PET2", "PET3"):
            pet = pets.get(nom, companion_vide())
            f.write(f"[{nom}]\n")
            # Identité (nom/rareté) en tête de section si renseignée
            if pet.get("__name__"):
                f.write(f"{'__name__':20s} = {pet['__name__']}\n")
            if pet.get("__rarity__"):
                f.write(f"{'__rarity__':20s} = {pet['__rarity__']}\n")
            for k in COMPANION_STATS_KEYS:
                f.write(f"{k:20s} = {pet.get(k, 0.0)}\n")
            f.write("\n")


# ════════════════════════════════════════════════════════════
#  MOUNT
# ════════════════════════════════════════════════════════════

def charger_mount() -> Dict[str, float]:
    mount = companion_vide()
    if not os.path.isfile(MOUNT_FILE):
        return mount

    with open(MOUNT_FILE, "r", encoding="utf-8") as f:
        lignes = f.readlines()

    for ligne in lignes:
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or ligne.startswith("["):
            continue
        if "=" in ligne:
            cle, val = ligne.split("=", 1)
            cle, val = cle.strip(), val.strip()
            if cle in ("__name__", "__rarity__"):
                mount[cle] = val
            else:
                try:
                    mount[cle] = float(val)
                except ValueError:
                    log.warning("mount.txt: valeur invalide pour %s = %r", cle, val)
    return mount


def sauvegarder_mount(mount: Dict[str, float]) -> None:
    with open(MOUNT_FILE, "w", encoding="utf-8") as f:
        f.write("# ============================================================\n")
        f.write("# FORGE MASTER — Mount actif (modifiable a la main)\n")
        f.write("# ============================================================\n\n")
        f.write("[MOUNT]\n")
        if mount.get("__name__"):
            f.write(f"{'__name__':20s} = {mount['__name__']}\n")
        if mount.get("__rarity__"):
            f.write(f"{'__rarity__':20s} = {mount['__rarity__']}\n")
        for k in COMPANION_STATS_KEYS:
            f.write(f"{k:20s} = {mount.get(k, 0.0)}\n")


# ════════════════════════════════════════════════════════════
#  BIBLIOTHÈQUES (pets + mount au level 1)
# ════════════════════════════════════════════════════════════
#
#  Format identique pour les deux fichiers :
#
#      # commentaire
#      [Treant]
#      rarity      = ultimate
#      hp_flat     = 10200000.0
#      damage_flat = 427000.0
#
#      [Phoenix]
#      rarity      = legendary
#      hp_flat     = 8500000.0
#      damage_flat = 380000.0
#
#  La clé d'index (ex. "Treant") est sensible à la casse côté disque
#  mais comparée en lowercase par le controller.
# ════════════════════════════════════════════════════════════

_LIBRARY_KEYS = ("rarity", "hp_flat", "damage_flat")


def _charger_library(path: str) -> Dict[str, Dict]:
    if not os.path.isfile(path):
        return {}

    library: Dict[str, Dict] = {}
    current_name: Optional[str] = None
    current: Dict = {}

    with open(path, "r", encoding="utf-8") as f:
        for ligne in f:
            ligne = ligne.strip()
            if not ligne or ligne.startswith("#"):
                continue
            if ligne.startswith("[") and ligne.endswith("]"):
                if current_name:
                    library[current_name] = current
                current_name = ligne[1:-1].strip()
                current = {"rarity": "common", "hp_flat": 0.0, "damage_flat": 0.0}
            elif current_name and "=" in ligne:
                cle, val = ligne.split("=", 1)
                cle, val = cle.strip(), val.strip()
                if cle == "rarity":
                    current[cle] = val.lower()
                elif cle in ("hp_flat", "damage_flat"):
                    try:
                        current[cle] = float(val)
                    except ValueError:
                        log.warning("%s: valeur invalide pour [%s].%s = %r",
                                    path, current_name, cle, val)
        if current_name:
            library[current_name] = current
    return library


def _sauvegarder_library(path: str, library: Dict[str, Dict], titre: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write("# ============================================================\n")
        f.write(f"# FORGE MASTER — {titre}\n")
        f.write("# Stats de référence au level 1, indexées par nom.\n")
        f.write("# ============================================================\n\n")
        for nom in sorted(library.keys(), key=str.lower):
            entry = library[nom]
            f.write(f"[{nom}]\n")
            f.write(f"{'rarity':12s} = {entry.get('rarity', 'common')}\n")
            f.write(f"{'hp_flat':12s} = {entry.get('hp_flat', 0.0)}\n")
            f.write(f"{'damage_flat':12s} = {entry.get('damage_flat', 0.0)}\n\n")


def charger_pets_library() -> Dict[str, Dict]:
    return _charger_library(PETS_LIBRARY_FILE)


def sauvegarder_pets_library(library: Dict[str, Dict]) -> None:
    _sauvegarder_library(PETS_LIBRARY_FILE, library,
                         "Bibliothèque des pets (level 1)")


def charger_mount_library() -> Dict[str, Dict]:
    return _charger_library(MOUNT_LIBRARY_FILE)


def sauvegarder_mount_library(library: Dict[str, Dict]) -> None:
    _sauvegarder_library(MOUNT_LIBRARY_FILE, library,
                         "Bibliothèque des mounts (level 1)")
