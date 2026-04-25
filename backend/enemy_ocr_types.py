"""
============================================================
  FORGE MASTER — Enemy OCR data types

  Three layers, walking from raw OCR towards usable combat
  stats:

    1. EnemyOcrRaw            — Pixels + text, fresh out of OCR.
                                Icons are still images; rarities
                                are still hex colours.

    2. EnemyIdentifiedProfile — Every icon has been mapped to
                                an (age, idx, rarity) tuple via
                                template-matching against the
                                reference assets. Levels and
                                substats are kept as captured.

    3. EnemyComputedStats     — HP/Damage and combat substats
                                rebuilt from zero through the same
                                pipeline as ``statEngine.ts``,
                                ready to drop into the simulator.

  These are plain dataclasses — no behaviour. Helpers/builders
  live in ``enemy_ocr_parser.py`` (raw → identified) and
  ``enemy_stat_calculator.py`` (identified → computed).

  Slot order (matches the in-game UI and the SLOT_TYPE_ID_MAP
  used in the TypeScript companion):

      0=Helmet, 1=Body, 2=Gloves, 3=Necklace,
      4=Ring,   5=Weapon, 6=Shoe,  7=Belt
============================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional


# Canonical slot order used everywhere downstream. Matches both the
# game's SLOT_TYPE_ID_MAP and the JSON Type names used as the second
# component of the ItemBalancingLibrary keys.
SLOT_ORDER: tuple = (
    "Helmet",
    "Body",
    "Gloves",
    "Necklace",
    "Ring",
    "Weapon",
    "Shoe",
    "Belt",
)

# Slot-name → JSON Type-name. Three slots use a different name in the
# JSON than in the UI ("Body" → "Armour", "Shoe" → "Shoes", and
# "Helmet" sometimes appears as "Headgear" in skin libraries — the
# ItemBalancingLibrary uses "Helmet" though).
SLOT_TO_JSON_TYPE = {
    "Helmet":   "Helmet",
    "Body":     "Armour",
    "Gloves":   "Gloves",
    "Necklace": "Necklace",
    "Ring":     "Ring",
    "Weapon":   "Weapon",
    "Shoe":     "Shoes",
    "Belt":     "Belt",
}


# ════════════════════════════════════════════════════════════
#  Layer 1 — raw OCR
# ════════════════════════════════════════════════════════════


@dataclass
class OcrEquipmentSlot:
    """One of the eight equipment slots, as captured by the OCR pass.

    ``icon_crop`` is intentionally typed as ``Any``: it can be a PIL
    Image, a numpy array, a path on disk, or even ``None`` when the
    capture did not include the visual identification step yet.
    """

    level: int = 0
    icon_crop: Any = None
    rarity_color: str = ""   # hex like "#4488ff" — to be mapped to a rarity name
    age_color: str = ""      # hex like "#8B4513" — to be mapped to an Age index


@dataclass
class OcrPet:
    level: int = 0
    icon_crop: Any = None


@dataclass
class OcrMount:
    level: int = 0
    icon_crop: Any = None


@dataclass
class OcrSkill:
    level: int = 0
    icon_crop: Any = None
    rarity_color: str = ""


@dataclass
class OcrSubstat:
    """One ``+X% StatName`` entry parsed out of the OCR text."""

    stat_id: str = ""    # canonical id, e.g. "CriticalChance"
    value: float = 0.0   # in PERCENTAGE POINTS, e.g. 50.1 for "+50.1%"


@dataclass
class EnemyOcrRaw:
    """Bundle of everything the OCR pass produced for one opponent."""

    forge_level: int = 0
    total_damage_displayed: float = 0.0
    total_health_displayed: float = 0.0

    equipment_slots: List[OcrEquipmentSlot] = field(default_factory=list)
    pets: List[OcrPet] = field(default_factory=list)
    mount: Optional[OcrMount] = None
    skills: List[OcrSkill] = field(default_factory=list)
    substats: List[OcrSubstat] = field(default_factory=list)


# ════════════════════════════════════════════════════════════
#  Layer 2 — identified profile (post template-matching)
# ════════════════════════════════════════════════════════════


@dataclass
class IdentifiedItem:
    slot: str = "Helmet"
    age: int = 0
    idx: int = 0
    level: int = 1
    rarity: str = "Common"
    secondary_stats: List[OcrSubstat] = field(default_factory=list)


@dataclass
class IdentifiedPet:
    id: int = 0
    rarity: str = "Common"
    level: int = 1
    secondary_stats: List[OcrSubstat] = field(default_factory=list)


@dataclass
class IdentifiedMount:
    id: int = 0
    rarity: str = "Common"
    level: int = 1
    secondary_stats: List[OcrSubstat] = field(default_factory=list)


@dataclass
class IdentifiedSkill:
    id: str = ""             # skill name, e.g. "Arrows"
    level: int = 1
    rarity: str = "Common"


@dataclass
class EnemyIdentifiedProfile:
    """An opponent's gear + level data, ready for the calculator.

    Substats live at the profile level (we get them as global totals
    from the OCR — see CHANTIER doc) AND optionally per-item, in case
    a future capture pipeline manages to read individual substats off
    the tooltip popups.
    """

    forge_level: int = 0
    total_damage_displayed: float = 0.0
    total_health_displayed: float = 0.0

    items: List[IdentifiedItem] = field(default_factory=list)
    pets: List[IdentifiedPet] = field(default_factory=list)
    mount: Optional[IdentifiedMount] = None
    skills: List[IdentifiedSkill] = field(default_factory=list)

    # Global substats (sum of items + pets + mount, already aggregated by the
    # game when the profile screen is captured). Values are PERCENTAGE
    # POINTS.
    substats: List[OcrSubstat] = field(default_factory=list)

    def substat(self, stat_id: str) -> float:
        """Lookup the global substat by id. Returns 0 when missing."""
        for s in self.substats:
            if s.stat_id == stat_id:
                return s.value
        return 0.0


# ════════════════════════════════════════════════════════════
#  Layer 3 — final stats
# ════════════════════════════════════════════════════════════


@dataclass
class EnemyComputedStats:
    """Result of the recalculation pipeline.

    HP and damage are absolute totals that should match what the game
    displays on the opponent profile screen; the ``*_accuracy`` fields
    quantify the gap between our recomputed value and the OCR-captured
    one.

    Substat fields are stored as decimal multipliers (0.50 = 50%), not
    percentage points, to match the conventions in
    ``backend/stats.py``.
    """

    total_damage:        float = 0.0
    total_health:        float = 0.0

    critical_chance:          float = 0.0
    critical_damage:          float = 1.2   # base 1 + 0.20
    block_chance:             float = 0.0
    double_damage_chance:     float = 0.0
    attack_speed_multiplier:  float = 1.0
    life_steal:               float = 0.0
    health_regen:             float = 0.0
    skill_damage_multiplier:  float = 1.0
    skill_cooldown_reduction: float = 0.0

    is_ranged_weapon:        bool  = False
    weapon_attack_range:     float = 0.3
    weapon_windup_time:      float = 0.5
    weapon_attack_duration:  float = 1.5
    projectile_speed:        float = 0.0

    # Validation — keep both for downstream consumers.
    displayed_damage: float = 0.0
    displayed_health: float = 0.0
    damage_accuracy:  float = 0.0   # |computed - displayed| / displayed × 100
    health_accuracy:  float = 0.0
