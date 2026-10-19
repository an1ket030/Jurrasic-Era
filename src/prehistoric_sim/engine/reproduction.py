"""
reproduction.py — Mating, eggs, nests, hatching, live birth, parental care.

All reproductive events flow through this module. Species-specific parameters
(clutch size, incubation time, gestation, care level) come from YAML data —
no per-species code branches needed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from prehistoric_sim.engine.entities import (
    Agent,
    Egg,
    LifeStage,
    Nest,
    ReproductionType,
    Traits,
    _new_id,
)
from prehistoric_sim.engine.events import (
    Event,
    EventBus,
    EventCategory,
    EventSubcategory,
)
from prehistoric_sim.engine.lifecycle import get_stage_thresholds

if TYPE_CHECKING:
    from prehistoric_sim.engine.rng import SimRNG
    from prehistoric_sim.engine.world import World

# ---------------------------------------------------------------------------
# Seasonal breeding check
# ---------------------------------------------------------------------------

BREEDING_SEASONS: dict[str, list[str]] = {
    "SPRING": ["SPRING"],
    "SUMMER": ["SUMMER"],
    "SPRING_SUMMER": ["SPRING", "SUMMER"],
    "ANY": ["SPRING", "SUMMER", "AUTUMN", "WINTER"],
}


def is_breeding_season(species_data: dict[str, Any], current_season: str) -> bool:
    """Return True if the current season allows breeding for this species."""
    breed_season: str = species_data.get("breeding_season", "SPRING")
    allowed = BREEDING_SEASONS.get(breed_season, [breed_season])
    return current_season in allowed


def can_mate(
    agent: Agent,
    species_data: dict[str, Any],
    world: "World",
) -> bool:
    """Check all mating preconditions."""
    if not agent.is_adult_capable:
        return False
    if agent.energy < species_data.get("min_energy_to_breed", 0.5):
        return False
    if agent.health < 0.3:
        return False
    if agent.pregnant:
        return False
    if getattr(agent, "reproduction_cooldown_ticks", 0) > 0:
        return False
    if not is_breeding_season(species_data, world.season):
        return False
    return True


# ---------------------------------------------------------------------------
# Courtship
# ---------------------------------------------------------------------------


def do_mate_display(
    agent: Agent,
    partner: Agent,
    world: "World",
    event_bus: EventBus,
    rng: Any,
) -> None:
    """Courtship display — costs energy, increases reproductive success."""
    cost = 0.01
    agent.energy = max(0.0, agent.energy - cost)
    event_bus.emit(Event(
        tick=world.tick,
        category=EventCategory.INTERACTION,
        subcategory=EventSubcategory.MATE_DISPLAY,
        actor_ids=[agent.id, partner.id],
        position=agent.position,
        payload={
            "displayer": agent.display_name,
            "partner": partner.display_name,
            "species": agent.species_key,
        },
    ))


# ---------------------------------------------------------------------------
# Mating
# ---------------------------------------------------------------------------


def attempt_mating(
    agent_a: Agent,
    agent_b: Agent,
    world: "World",
    species_data: dict[str, Any],
    event_bus: EventBus,
    rng: Any,
    aging_scale: float,
) -> bool:
    """Attempt mating between two adults. Returns True if successful."""
    # Energy cost
    cost = species_data.get("mating_energy_cost", 0.08)
    agent_a.energy = max(0.0, agent_a.energy - cost)
    agent_b.energy = max(0.0, agent_b.energy - cost)

    event_bus.emit(Event(
        tick=world.tick,
        category=EventCategory.LIFECYCLE,
        subcategory=EventSubcategory.MATING,
        actor_ids=[agent_a.id, agent_b.id],
        position=agent_a.position,
        payload={
            "species": agent_a.species_key,
            "partner_a": agent_a.display_name,
            "partner_b": agent_b.display_name,
        },
    ))

    repro_type = species_data.get("reproduction_type", "EGG_LAYING")

    # Record mate
    agent_a.mate_id = agent_b.id
    agent_b.mate_id = agent_a.id

    if repro_type == ReproductionType.LIVE_BIRTH.value:
        # Determine which is "female" (lower id for determinism)
        female = agent_a if agent_a.id < agent_b.id else agent_b
        from prehistoric_sim.engine.world import TICKS_PER_DAY  # noqa: PLC0415
        gestation_days = species_data.get("gestation_days", 30)
        gestation_ticks = max(1, int(gestation_days * TICKS_PER_DAY / aging_scale))
        female.pregnant = True
        female.gestation_ticks_remaining = gestation_ticks
        female.action_target_id = agent_b.id if female is agent_a else agent_a.id
    return True


# ---------------------------------------------------------------------------
# Egg laying
# ---------------------------------------------------------------------------


def lay_clutch(
    parent: Agent,
    nest: Nest,
    world: "World",
    species_data: dict[str, Any],
    event_bus: EventBus,
    rng: Any,
    aging_scale: float,
    all_species_data: dict[str, Any],
) -> list[Egg]:
    """Create a clutch of eggs in a nest."""
    clutch_size: int = rng.randint(
        species_data.get("min_clutch_size", 1),
        species_data.get("max_clutch_size", 4),
    )
    from prehistoric_sim.engine.world import TICKS_PER_DAY  # noqa: PLC0415
    incubation_days: float = species_data.get("incubation_days", 60)
    incubation_ticks = max(1, int(incubation_days * TICKS_PER_DAY / aging_scale))

    clutch_id = _new_id("clutch")
    eggs: list[Egg] = []
    for _ in range(clutch_size):
        egg = Egg(
            id=_new_id("egg"),
            position=nest.position,
            alive=True,
            species_key=parent.species_key,
            parent_ids=[parent.id],
            clutch_id=clutch_id,
            nest_id=nest.id,
            incubation_ticks_total=incubation_ticks,
            incubation_ticks_remaining=incubation_ticks,
        )
        eggs.append(egg)
        nest.egg_ids.append(egg.id)

    parent.incubating_nest_id = nest.id

    event_bus.emit(Event(
        tick=world.tick,
        category=EventCategory.LIFECYCLE,
        subcategory=EventSubcategory.EGG_LAID,
        actor_ids=[parent.id],
        position=nest.position,
        payload={
            "species": parent.species_key,
            "name": parent.display_name,
            "clutch_size": clutch_size,
            "incubation_ticks": incubation_ticks,
            "nest_id": nest.id,
        },
    ))
    return eggs


def build_nest(
    parent: Agent,
    world: "World",
    species_data: dict[str, Any],
    event_bus: EventBus,
    rng: Any,
) -> Nest:
    """Create a nest at the parent's position."""
    nest = Nest(
        id=_new_id("nest"),
        position=parent.position,
        alive=True,
        species_key=parent.species_key,
        owner_id=parent.id,
        egg_ids=[],
        guarded=False,
        construction_complete=True,
    )
    event_bus.emit(Event(
        tick=world.tick,
        category=EventCategory.LIFECYCLE,
        subcategory=EventSubcategory.NEST_BUILT,
        actor_ids=[parent.id],
        position=parent.position,
        payload={
            "species": parent.species_key,
            "name": parent.display_name,
            "nest_id": nest.id,
        },
    ))
    return nest


# ---------------------------------------------------------------------------
# Hatching
# ---------------------------------------------------------------------------


def hatch_egg(
    egg: Egg,
    world: "World",
    all_species_data: dict[str, Any],
    event_bus: EventBus,
    rng: Any,
    aging_scale: float,
) -> "Agent | None":
    """Create a hatchling agent from a hatched egg."""
    sd = all_species_data.get(egg.species_key)
    if sd is None:
        return None

    hatchling = _spawn_agent(
        species_key=egg.species_key,
        position=egg.position,
        species_data=sd,
        life_stage=LifeStage.HATCHLING,
        parent_ids=egg.parent_ids,
        rng=rng,
        aging_scale=aging_scale,
        birth_tick=world.tick,
    )
    event_bus.emit(Event(
        tick=world.tick,
        category=EventCategory.LIFECYCLE,
        subcategory=EventSubcategory.HATCHING,
        actor_ids=[hatchling.id],
        position=hatchling.position,
        payload={
            "species": hatchling.species_key,
            "name": hatchling.display_name,
            "parent_ids": egg.parent_ids,
        },
    ))
    return hatchling


# ---------------------------------------------------------------------------
# Live birth
# ---------------------------------------------------------------------------


def give_birth(
    mother: Agent,
    world: "World",
    species_data: dict[str, Any],
    all_species_data: dict[str, Any],
    event_bus: EventBus,
    rng: Any,
    aging_scale: float,
) -> list["Agent"]:
    """Spawn newborn live-bearing offspring."""
    litter_size: int = rng.randint(
        species_data.get("min_litter_size", 1),
        species_data.get("max_litter_size", 3),
    )
    mother.pregnant = False
    mother.gestation_ticks_remaining = 0
    from prehistoric_sim.engine.world import TICKS_PER_DAY  # noqa: PLC0415
    mother.reproduction_cooldown_ticks = max(48 * 8, int(60 * TICKS_PER_DAY / aging_scale))
    mother.drives.reproductive_urge = 0.0

    offspring: list[Agent] = []
    for _ in range(litter_size):
        newborn = _spawn_agent(
            species_key=mother.species_key,
            position=mother.position,
            species_data=species_data,
            life_stage=LifeStage.HATCHLING,
            parent_ids=[mother.id],
            rng=rng,
            aging_scale=aging_scale,
            birth_tick=world.tick,
        )
        offspring.append(newborn)
        mother.offspring_ids.append(newborn.id)

    event_bus.emit(Event(
        tick=world.tick,
        category=EventCategory.LIFECYCLE,
        subcategory=EventSubcategory.BIRTH,
        actor_ids=[mother.id] + [o.id for o in offspring],
        position=mother.position,
        payload={
            "mother": mother.display_name,
            "species": mother.species_key,
            "litter_size": litter_size,
        },
    ))
    return offspring


# ---------------------------------------------------------------------------
# Parental care
# ---------------------------------------------------------------------------


def do_parental_care(
    parent: Agent,
    offspring: list["Agent"],
    world: "World",
    event_bus: EventBus,
    rng: Any,
) -> None:
    """Parent tends to nearby offspring."""
    if not offspring:
        return
    # Move toward nearest dependent offspring
    alive_young = [o for o in offspring if o.alive and o.life_stage == LifeStage.HATCHLING]
    if alive_young:
        target = min(alive_young, key=lambda o: parent.distance_to(o))
        from prehistoric_sim.engine.behaviors import _move_toward  # noqa: PLC0415
        _move_toward(parent, target.position[0], target.position[1], world)
        if rng.chance(0.05):
            event_bus.emit(Event(
                tick=world.tick,
                category=EventCategory.LIFECYCLE,
                subcategory=EventSubcategory.PARENTING,
                actor_ids=[parent.id, target.id],
                position=parent.position,
                payload={
                    "parent": parent.display_name,
                    "offspring": target.display_name,
                    "action": "tending",
                },
            ))


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------


def _spawn_agent(
    species_key: str,
    position: tuple[int, int],
    species_data: dict[str, Any],
    life_stage: LifeStage,
    parent_ids: list[str],
    rng: Any,
    aging_scale: float,
    birth_tick: int = 0,
    name: str | None = None,
    age_ticks: int | None = None,
) -> Agent:
    """Create an agent with species-appropriate stats and randomised personality."""
    from prehistoric_sim.engine.lifecycle import (  # noqa: PLC0415
        get_stage_thresholds,
        growth_factor,
    )

    # Traits — inherit from parents with mutation if available
    base_traits = {
        "boldness": species_data.get("base_boldness", 0.5),
        "aggression": species_data.get("base_aggression", 0.5),
        "curiosity": species_data.get("base_curiosity", 0.5),
        "sociability": species_data.get("base_sociability", 0.5),
    }
    traits = Traits(
        boldness=rng.clamp_normal(base_traits["boldness"], 0.1, 0.1, 0.9),
        aggression=rng.clamp_normal(base_traits["aggression"], 0.1, 0.0, 1.0),
        curiosity=rng.clamp_normal(base_traits["curiosity"], 0.1, 0.1, 0.9),
        sociability=rng.clamp_normal(base_traits["sociability"], 0.1, 0.0, 1.0),
        size_factor=rng.clamp_normal(1.0, 0.08, 0.7, 1.3),
        speed_factor=rng.clamp_normal(1.0, 0.05, 0.8, 1.2),
        metabolic_efficiency=rng.clamp_normal(1.0, 0.05, 0.8, 1.2),
    )

    # Compute starter age ticks
    from prehistoric_sim.engine.world import TICKS_PER_DAY  # noqa: PLC0415
    if age_ticks is None:
        thresholds = get_stage_thresholds(species_data, aging_scale)
        age_ticks = thresholds.get(life_stage, 0)

    # Body mass and speed scaled to life stage
    thresholds = get_stage_thresholds(species_data, aging_scale)
    gf = growth_factor(age_ticks, thresholds)
    base_mass = species_data.get("body_mass_kg", 10.0) * traits.size_factor
    body_mass = base_mass * max(0.05, gf)
    base_speed = species_data.get("max_speed_cells_per_tick", 1.0) * traits.speed_factor
    current_speed = base_speed * max(0.1, gf)

    # Display ID counter (simplified: use partial ID)
    eid = _new_id(species_key[:4].replace("_", ""))
    display_id = eid

    agent = Agent(
        id=eid,
        position=position,
        alive=True,
        species_key=species_key,
        name=name,
        display_id=display_id,
        life_stage=life_stage,
        age_ticks=age_ticks,
        birth_tick=birth_tick,
        body_mass_kg=body_mass,
        current_speed=current_speed,
        max_speed=current_speed,
        health=1.0,
        energy=rng.uniform(0.6, 0.9),
        hydration=rng.uniform(0.6, 0.9),
        stamina=1.0,
        parent_ids=list(parent_ids),
        traits=traits,
        _species_data=species_data,
    )
    return agent
