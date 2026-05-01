"""Text codec for the canonical player profile file."""

from __future__ import annotations

import logging
import re
from copy import deepcopy
from typing import Dict, Iterable, Optional, Tuple

from data.canonical import (
    EQUIPMENT_SLOTS,
    MOUNT_SLOT,
    PET_SLOTS,
    SKILL_SLOTS,
    SUBSTAT_KEYS,
    canonical_substat_key,
)

from .schema import SCHEMA_VERSION, empty_profile

log = logging.getLogger(__name__)

_GROUPS = {"BASE_PROFILE", "EQUIPMENT", "SKILLS", "PETS", "MOUNT", "SUBSTATS_TOTAL"}
_SUBSTAT_RE = re.compile(r"^Substat\s*\((.+)\)$", re.IGNORECASE)


def _float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value: object, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _format_number(value: object) -> str:
    value = _float(value)
    if value.is_integer():
        return str(int(value))
    return repr(value)


def _normalise_substats(raw: Dict[str, object]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for key, value in (raw or {}).items():
        canonical = canonical_substat_key(key) or str(key)
        out[canonical] = _float(value)
    return out


def normalise_equipment_slot(value: Optional[Dict]) -> Dict[str, object]:
    src = dict(value or {})
    out = {
        "__name__": str(src.get("__name__") or src.get("name") or ""),
        "__level__": _int(src.get("__level__", src.get("level", 0))),
        "__age__": _int(src.get("__age__", src.get("age", 0))),
        "__rarity__": str(src.get("__rarity__") or src.get("rarity") or ""),
        "__idx__": _int(src.get("__idx__", src.get("idx", 0))),
        "hp_flat": _float(src.get("hp_flat")),
        "damage_flat": _float(src.get("damage_flat")),
        "substats": _normalise_substats(src.get("substats") or {}),
        "attack_type": str(src.get("attack_type") or ""),
        "weapon_attack_range": _float(src.get("weapon_attack_range")),
        "weapon_windup": _float(src.get("weapon_windup")),
        "weapon_recovery": _float(src.get("weapon_recovery")),
        "projectile_speed": _float(src.get("projectile_speed")),
        "projectile_travel_time": _float(src.get("projectile_travel_time")),
    }
    _pull_legacy_substats(src, out["substats"])
    return out


def normalise_skill_slot(value: Optional[Dict]) -> Dict[str, object]:
    src = dict(value or {})
    damage = src.get("damage_flat", src.get("passive_damage", 0.0))
    hp = src.get("hp_flat", src.get("passive_hp", 0.0))
    out = {
        "__name__": str(src.get("__name__") or src.get("name") or ""),
        "__level__": _int(src.get("__level__", src.get("level", 0))),
        "__rarity__": str(src.get("__rarity__") or src.get("rarity") or ""),
        "hp_flat": _float(hp),
        "damage_flat": _float(damage),
        "type": str(src.get("type") or ""),
        "substats": {},
    }
    for key in ("damage", "hits", "cooldown", "buff_duration", "buff_atk", "buff_hp"):
        if key in src:
            out[key] = _float(src.get(key))
    return out


def normalise_companion_slot(value: Optional[Dict]) -> Dict[str, object]:
    src = dict(value or {})
    out = {
        "__name__": str(src.get("__name__") or src.get("name") or ""),
        "__level__": _int(src.get("__level__", src.get("level", 0))),
        "__rarity__": str(src.get("__rarity__") or src.get("rarity") or ""),
        "hp_flat": _float(src.get("hp_flat")),
        "damage_flat": _float(src.get("damage_flat")),
        "substats": _normalise_substats(src.get("substats") or {}),
    }
    _pull_legacy_substats(src, out["substats"])
    return out


def normalise_profile(profile: Optional[Dict]) -> Dict[str, object]:
    src = deepcopy(profile or {})
    out = empty_profile()
    for slot in EQUIPMENT_SLOTS:
        out["equipment"][slot] = normalise_equipment_slot((src.get("equipment") or {}).get(slot))
    for slot in SKILL_SLOTS:
        out["skills"][slot] = normalise_skill_slot((src.get("skills") or {}).get(slot))
    for slot in PET_SLOTS:
        out["pets"][slot] = normalise_companion_slot((src.get("pets") or {}).get(slot))
    out["mount"][MOUNT_SLOT] = normalise_companion_slot((src.get("mount") or {}).get(MOUNT_SLOT))
    out["base_profile"] = dict(src.get("base_profile") or {})
    out["substats_total"] = {
        key: _float((src.get("substats_total") or {}).get(key))
        for key in SUBSTAT_KEYS
    }
    return out


def _pull_legacy_substats(src: Dict[str, object], dest: Dict[str, float]) -> None:
    for key, value in src.items():
        canonical = canonical_substat_key(key)
        if canonical and key not in {"hp_flat", "damage_flat"}:
            dest[canonical] = _float(value)


def dumps_profile(profile: Dict) -> str:
    profile = normalise_profile(profile)
    lines = [
        "# FORGE MASTER - player profile",
        f"# schema_version = {SCHEMA_VERSION}",
        "",
        "[BASE_PROFILE]",
    ]
    for key, value in sorted((profile.get("base_profile") or {}).items()):
        lines.append(f"{key} = {value}")

    _write_group(lines, "EQUIPMENT", profile["equipment"], EQUIPMENT_SLOTS, _equipment_lines)
    _write_group(lines, "SKILLS", profile["skills"], SKILL_SLOTS, _skill_lines)
    _write_group(lines, "PETS", profile["pets"], PET_SLOTS, _companion_lines)
    _write_group(lines, "MOUNT", profile["mount"], (MOUNT_SLOT,), _companion_lines)

    lines.extend(["", "[SUBSTATS_TOTAL]"])
    for key in SUBSTAT_KEYS:
        lines.append(f"{key} = {_format_number((profile.get('substats_total') or {}).get(key, 0.0))}")
    lines.append("")
    return "\n".join(lines)


def loads_profile(text: str) -> Dict[str, object]:
    profile = empty_profile()
    group: Optional[str] = None
    slot: Optional[str] = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            header = line[1:-1].strip()
            if header in _GROUPS:
                group, slot = header, None
            else:
                slot = header
            continue
        if "=" not in line:
            continue
        key, value = [part.strip() for part in line.split("=", 1)]
        _assign(profile, group, slot, key, value)
    return normalise_profile(profile)


def has_schema_v2(text: str) -> bool:
    return "schema_version = 2" in text or "schema_version=2" in text


def _assign(profile: Dict, group: Optional[str], slot: Optional[str], key: str, value: str) -> None:
    if group == "BASE_PROFILE":
        profile["base_profile"][key] = value if key == "attack_type" else _float(value)
    elif group == "SUBSTATS_TOTAL":
        canonical = canonical_substat_key(key) or key
        profile["substats_total"][canonical] = _float(value)
    elif group in {"EQUIPMENT", "SKILLS", "PETS", "MOUNT"} and slot:
        target = _target(profile, group, slot)
        if target is not None:
            _assign_slot_value(target, key, value)


def _target(profile: Dict, group: str, slot: str) -> Optional[Dict]:
    if group == "EQUIPMENT" and slot in EQUIPMENT_SLOTS:
        return profile["equipment"][slot]
    if group == "SKILLS" and slot in SKILL_SLOTS:
        return profile["skills"][slot]
    if group == "PETS" and slot in PET_SLOTS:
        return profile["pets"][slot]
    if group == "MOUNT" and slot == MOUNT_SLOT:
        return profile["mount"][MOUNT_SLOT]
    log.warning("profile store: ignored unknown %s slot %r", group, slot)
    return None


def _assign_slot_value(target: Dict, key: str, value: str) -> None:
    substat = _SUBSTAT_RE.match(key)
    if substat:
        canonical = canonical_substat_key(substat.group(1)) or substat.group(1)
        target.setdefault("substats", {})[canonical] = _float(value)
        return
    mapping = {
        "Name": "__name__",
        "Level": "__level__",
        "Age": "__age__",
        "Rarity": "__rarity__",
        "Idx": "__idx__",
        "HP": "hp_flat",
        "Damage": "damage_flat",
        "Type": "type",
    }
    dest = mapping.get(key, key)
    if dest in {"__name__", "__rarity__", "attack_type", "type"}:
        target[dest] = value
    elif dest in {"__level__", "__age__", "__idx__"}:
        target[dest] = _int(value)
    else:
        target[dest] = _float(value)


def _write_group(lines: list[str], name: str, values: Dict, slots: Iterable[str], writer) -> None:
    lines.extend(["", f"[{name}]"])
    for slot in slots:
        lines.extend(["", f"[{slot}]"])
        lines.extend(writer(values.get(slot) or {}))


def _identity_lines(entry: Dict) -> list[str]:
    lines = [
        f"Name = {entry.get('__name__', '')}",
        f"Level = {_int(entry.get('__level__'))}",
    ]
    if "__age__" in entry:
        lines.append(f"Age = {_int(entry.get('__age__'))}")
    lines.append(f"Rarity = {entry.get('__rarity__', '')}")
    if "__idx__" in entry:
        lines.append(f"Idx = {_int(entry.get('__idx__'))}")
    lines.extend([
        f"HP = {_format_number(entry.get('hp_flat'))}",
        f"Damage = {_format_number(entry.get('damage_flat'))}",
    ])
    return lines


def _equipment_lines(entry: Dict) -> list[str]:
    lines = _identity_lines(entry)
    if entry.get("attack_type"):
        lines.append(f"attack_type = {entry.get('attack_type')}")
    for key in ("weapon_attack_range", "weapon_windup", "weapon_recovery", "projectile_speed", "projectile_travel_time"):
        if _float(entry.get(key)):
            lines.append(f"{key} = {_format_number(entry.get(key))}")
    lines.extend(_substat_lines(entry))
    return lines


def _skill_lines(entry: Dict) -> list[str]:
    lines = _identity_lines(entry)
    if entry.get("type"):
        lines.append(f"Type = {entry.get('type')}")
    for key in ("damage", "hits", "cooldown", "buff_duration", "buff_atk", "buff_hp"):
        if key in entry:
            lines.append(f"{key} = {_format_number(entry.get(key))}")
    return lines


def _companion_lines(entry: Dict) -> list[str]:
    lines = _identity_lines(entry)
    lines.extend(_substat_lines(entry))
    return lines


def _substat_lines(entry: Dict) -> list[str]:
    return [
        f"Substat ({key}) = {_format_number(value)}"
        for key, value in (entry.get("substats") or {}).items()
    ]

