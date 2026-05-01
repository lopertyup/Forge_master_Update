"""Compatibility shim for the schema-v2 profile store."""

from __future__ import annotations

import warnings
from typing import Dict, List, Optional, Tuple

from .profile_store import store
from .skills import load_skills


def save_profile(player: Dict, skills: Optional[List[Tuple[str, Dict]]] = None) -> None:
    warnings.warn(
        "backend.persistence.profile.save_profile is deprecated; use "
        "backend.persistence.profile_store.store.save_profile",
        DeprecationWarning,
        stacklevel=2,
    )
    profile = store.load_profile()
    profile["base_profile"] = dict(player or {})
    store.save_profile(profile)


def load_profile() -> Tuple[Optional[Dict], List[Tuple[str, Dict]]]:
    warnings.warn(
        "backend.persistence.profile.load_profile is deprecated; use "
        "backend.persistence.profile_store.store.load_profile",
        DeprecationWarning,
        stacklevel=2,
    )
    profile = store.load_profile()
    base = dict(profile.get("base_profile") or {})
    return (base or None), load_skills()


def _read_section(lines: List[str], start: int) -> Optional[Dict]:
    stats: Dict = {}
    for line in lines[start:]:
        line = line.strip()
        if line.startswith("["):
            break
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = [part.strip() for part in line.split("=", 1)]
        if key == "attack_type":
            stats[key] = val
        else:
            try:
                stats[key] = float(val)
            except ValueError:
                stats[key] = val
    return stats if stats else None

