"""
entities.py — All entity types: Agent, Egg, Nest, Carcass, FishSchool, InsectSwarm.

Every entity is a dataclass with an ID and a position.
Mutable numeric fields use plain floats — no hidden global state.
"""

from __future__ import annotations

import dataclasses
import uuid
from enum import Enum, auto
from typing import Any


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class LifeStage(str, Enum):
    """Ordered life stages shared by all agent species."""
    EGG = "EGG"                  # not yet used for agent; Egg entity instead
    HATCHLING = "HATCHLING"      # newly born / hatched; fully dependent
    JUVENILE = "JUVENILE"        # growing; partially dependent
    SUBADULT = "SUBADULT"        # near full size; dispersing
    ADULT = "ADULT"              # fully capable; breeds
    SENESCENT = "SENESCENT"      # aging; slower, weaker

    @classmethod
    def ordered(cls) -> list["LifeStage"]:
        return [cls.HATCHLING, cls.JUVENILE, cls.SUBADULT, cls.ADULT, cls.SENESCENT]


class DietType(str, Enum):
    CARNIVORE = "CARNIVORE"
    HERBIVORE = "HERBIVORE"
    OMNIVORE = "OMNIVORE"
    INSECTIVORE = "INSECTIVORE"
    PISCIVORE = "PISCIVORE"   # fish-eater


class ActivityPattern(str, Enum):
    DIURNAL = "DIURNAL"
    NOCTURNAL = "NOCTURNAL"
    CREPUSCULAR = "CREPUSCULAR"
    CONTINUOUS = "CONTINUOUS"


class ReproductionType(str, Enum):
    EGG_LAYING = "EGG_LAYING"
    LIVE_BIRTH = "LIVE_BIRTH"


class WeatherType(str, Enum):
    CLEAR = "CLEAR"
    RAIN = "RAIN"
    STORM = "STORM"
    DROUGHT = "DROUGHT"
    FLOOD = "FLOOD"
    FIRE = "FIRE"


class TerrainType(str, Enum):
    FLOODPLAIN = "FLOODPLAIN"
    FOREST = "FOREST"
    OPEN_WOODLAND = "OPEN_WOODLAND"
    SWAMP = "SWAMP"
    RIVER = "RIVER"
    LAKE = "LAKE"
    ROCKY_HILLS = "ROCKY_HILLS"
    MUD_FLATS = "MUD_FLATS"


# ---------------------------------------------------------------------------
# Base entity
# ---------------------------------------------------------------------------


_id_counter: int = 0


def reset_id_counter(val: int = 0) -> None:
    global _id_counter
    _id_counter = val


def _new_id(prefix: str) -> str:
    global _id_counter
    _id_counter += 1
    return f"{prefix}-{_id_counter:06x}"


@dataclasses.dataclass(eq=False)
class Entity:
    """Base class for all simulation entities."""

    id: str
    position: tuple[int, int] = (0, 0)  # (x, y) grid cell
    alive: bool = True

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return False
        return self.id == other.id

    def distance_to(self, other: "Entity") -> float:
        dx = self.position[0] - other.position[0]
        dy = self.position[1] - other.position[1]
        return (dx * dx + dy * dy) ** 0.5


# ---------------------------------------------------------------------------
# Personality traits (per individual)
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class Traits:
    """Individual personality, randomised within species bounds at birth.

    All values are in [0, 1] normalised to the species range.
    Inherited from parents with small mutation.
    """

    boldness: float = 0.5        # willingness to face threats
    aggression: float = 0.5      # likelihood of choosing attack over flee
    curiosity: float = 0.5       # drive to explore unknown territory
    sociability: float = 0.5     # strength of cohesion / social need
    size_factor: float = 1.0     # multiplier on base body mass
    speed_factor: float = 1.0    # multiplier on base speed
    metabolic_efficiency: float = 1.0  # multiplier on energy expenditure


# ---------------------------------------------------------------------------
# Drives (need levels, 0–1)
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class Drives:
    """Current motivational state of an agent. Each drive is in [0, 1]."""

    hunger: float = 0.2
    thirst: float = 0.2
    fatigue: float = 0.0
    fear: float = 0.0
    reproductive_urge: float = 0.0
    social_need: float = 0.2
    curiosity: float = 0.3
    parental_drive: float = 0.0


# ---------------------------------------------------------------------------
# Memory record
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class MemoryEntry:
    """A single memorised location or fact with a decay timestamp."""

    kind: str                    # "water", "food", "predator", "nest", "kin"
    position: tuple[int, int]
    tick_stored: int
    detail: str = ""             # e.g. species name for predator sightings
    strength: float = 1.0       # decays toward 0 over time


# ---------------------------------------------------------------------------
# Decision record (for UI explanation)
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class DecisionRecord:
    """Top-3 scored actions from the last decision cycle."""

    tick: int
    action: str
    score: float
    alternatives: list[tuple[str, float]]  # (action, score) pairs
    reason: str                              # plain-English explanation


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


@dataclasses.dataclass(eq=False)
class Agent(Entity):
    """An independent creature agent.

    Attributes cover species identity, current vital stats, personality,
    drives, memory, life history, and current behavioral state.
    """

    # Identity
    species_key: str = ""
    name: str | None = None       # optional player-assigned name
    display_id: str = ""          # e.g. "trex-0042" if no name

    # Life state
    life_stage: LifeStage = LifeStage.ADULT
    age_ticks: int = 0            # age in simulation ticks
    birth_tick: int = 0
    death_tick: int | None = None
    cause_of_death: str | None = None

    # Size and speed (scaled smoothly with age via lifecycle.py)
    body_mass_kg: float = 100.0   # current mass
    current_speed: float = 5.0    # m/s equivalent (movement cells/tick)
    max_speed: float = 5.0        # burst speed

    # Vital stats [0, 1]
    health: float = 1.0
    energy: float = 0.8
    hydration: float = 0.8
    stamina: float = 1.0          # depleted by running; restores when resting

    # Injury
    injury_level: float = 0.0    # [0, 1]; affects speed, energy cost

    # Reproduction state
    pregnant: bool = False
    gestation_ticks_remaining: int = 0
    reproduction_cooldown_ticks: int = 0
    incubating_nest_id: str | None = None  # ID of nest being guarded

    # Social
    group_id: str | None = None   # emergent herd / pack membership
    following_id: str | None = None  # following this agent (parent/leader)

    # Kin
    parent_ids: list[str] = dataclasses.field(default_factory=list)
    offspring_ids: list[str] = dataclasses.field(default_factory=list)
    mate_id: str | None = None

    # Personality
    traits: Traits = dataclasses.field(default_factory=Traits)

    # Drives
    drives: Drives = dataclasses.field(default_factory=Drives)

    # Memory
    memory: list[MemoryEntry] = dataclasses.field(default_factory=list)

    # Current behavior
    current_action: str = "WANDER"
    action_target_id: str | None = None    # ID of target entity
    action_target_pos: tuple[int, int] | None = None
    action_ticks_committed: int = 0        # ticks spent on current action

    # Last decision record (for UI)
    last_decision: DecisionRecord | None = None

    # Admin flags
    possessed: bool = False       # admin is driving this creature
    tracked: bool = False         # verbose event output for this creature
    forced_action: str | None = None
    forced_action_ticks: int = 0

    # Species data reference (loaded at runtime, not serialised)
    _species_data: dict[str, Any] | None = dataclasses.field(
        default=None, repr=False, compare=False
    )

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def display_name(self) -> str:
        """Return name if set, else display_id."""
        return self.name if self.name else self.display_id

    @property
    def is_adult_capable(self) -> bool:
        return self.life_stage in (LifeStage.ADULT, LifeStage.SENESCENT)

    @property
    def effective_speed(self) -> float:
        """Speed reduced by injury and stamina."""
        inj_mod = 1.0 - self.injury_level * 0.6
        stam_mod = max(0.3, self.stamina)
        return self.current_speed * inj_mod * stam_mod

    @property
    def is_mobile(self) -> bool:
        return self.alive and self.health > 0.05


# ---------------------------------------------------------------------------
# Egg
# ---------------------------------------------------------------------------


@dataclasses.dataclass(eq=False)
class Egg(Entity):
    """A single fertilised egg in a nest or exposed on the ground."""

    species_key: str = ""
    parent_ids: list[str] = dataclasses.field(default_factory=list)
    clutch_id: str = ""
    nest_id: str | None = None
    incubation_ticks_total: int = 100
    incubation_ticks_remaining: int = 100
    temperature_stress: float = 0.0    # accumulated; >1.0 → egg dies
    hatched: bool = False

    @property
    def is_viable(self) -> bool:
        return self.alive and not self.hatched and self.temperature_stress < 1.0


# ---------------------------------------------------------------------------
# Nest
# ---------------------------------------------------------------------------


@dataclasses.dataclass(eq=False)
class Nest(Entity):
    """A nest built by an egg-laying species."""

    species_key: str = ""
    owner_id: str = ""
    egg_ids: list[str] = dataclasses.field(default_factory=list)
    guarded: bool = False
    construction_ticks: int = 0   # ticks spent building
    construction_complete: bool = False
    terrain_type: TerrainType = TerrainType.FLOODPLAIN


# ---------------------------------------------------------------------------
# Carcass
# ---------------------------------------------------------------------------


@dataclasses.dataclass(eq=False)
class Carcass(Entity):
    """A dead creature's remains — food source and nutrient packet."""

    species_key: str = ""
    original_mass_kg: float = 100.0
    mass_remaining: float = 100.0
    decay_progress: float = 0.0    # [0, 1]; 1.0 = fully decomposed
    nutrients_released: float = 0.0
    scavengers_feeding: list[str] = dataclasses.field(default_factory=list)
    death_tick: int = 0
    cause_of_death: str = "unknown"

    @property
    def is_depleted(self) -> bool:
        return self.mass_remaining <= 0.5 or self.decay_progress >= 1.0


# ---------------------------------------------------------------------------
# FishSchool (biomass-based aquatic prey)
# ---------------------------------------------------------------------------


@dataclasses.dataclass(eq=False)
class FishSchool(Entity):
    """Abstracted fish population in a water body.

    Not an individual agent — represents a population with biomass.
    """

    water_body_id: str = ""
    biomass: float = 1.0           # [0, 1] fraction of max capacity
    max_biomass_kg: float = 500.0
    regrowth_rate: float = 0.01    # per tick, logistic


# ---------------------------------------------------------------------------
# InsectSwarm (biomass-based)
# ---------------------------------------------------------------------------


@dataclasses.dataclass(eq=False)
class InsectSwarm(Entity):
    """Abstracted insect population in a cell or region."""

    biomass: float = 1.0
    season_peak: str = "SUMMER"    # season of maximum activity
    active: bool = True            # reduced at night / winter
