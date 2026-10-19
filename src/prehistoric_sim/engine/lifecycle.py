"""
lifecycle.py — Life stages, aging, growth scaling, death, and decomposition.

Handles transitions between life stages, smooth attribute scaling with age,
death recording, and Carcass creation and decay.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any

from prehistoric_sim.engine.entities import (
    Agent,
    Carcass,
    Egg,
    LifeStage,
    _new_id,
)
from prehistoric_sim.engine.events import (
    Event,
    EventBus,
    EventCategory,
    EventSubcategory,
)

if TYPE_CHECKING:
    from prehistoric_sim.engine.world import World

# ---------------------------------------------------------------------------
# Kleiber's law exponent
# ---------------------------------------------------------------------------

KLEIBER_EXPONENT: float = 0.75


def basal_metabolic_rate(body_mass_kg: float, endothermic: bool = True) -> float:
    """Fractional basal metabolic energy rate per tick following Kleiber's law.

    Specific metabolic rate scales as mass^(-0.25).
    Endotherms burn ~2x more energy than ectotherms.
    """
    mass = max(0.05, body_mass_kg)
    base = (mass ** -0.25) * 0.0008
    return base * (2.0 if endothermic else 1.0)


# ---------------------------------------------------------------------------
# Stage boundary spec — loaded from species YAML at runtime
# ---------------------------------------------------------------------------


def get_stage_thresholds(species_data: dict[str, Any], aging_scale: float) -> dict[LifeStage, int]:
    """Return a mapping of life stage → minimum age in ticks.

    All species age data is in in-world years; we convert to ticks using
    aging_scale and the ticks_per_day constant.

    aging_scale: number of real ticks that represent one in-world year of aging.
    Actual age advance per tick = 1 / aging_scale (so a creature's age in
    "real" ticks equals its biological age in aging units).
    """
    from prehistoric_sim.engine.world import TICKS_PER_DAY  # noqa: PLC0415

    ticks_per_year = TICKS_PER_DAY * 365

    def years_to_ticks(years: float) -> int:
        return max(1, int(years * ticks_per_year / aging_scale))

    repro = species_data.get("reproduction", {})
    ls = species_data.get("life_stages", {})

    hatchling_end = years_to_ticks(ls.get("hatchling_years", 0.1))
    juvenile_end = years_to_ticks(ls.get("juvenile_years", 1.0))
    subadult_end = years_to_ticks(ls.get("subadult_years", 2.0))
    maturity_age = years_to_ticks(species_data.get("maturity_age_years", 3.0))
    lifespan = years_to_ticks(species_data.get("lifespan_years", 20.0))
    senescent_start = years_to_ticks(
        ls.get("senescent_start_years", species_data.get("lifespan_years", 20.0) * 0.75)
    )

    return {
        LifeStage.HATCHLING: 0,
        LifeStage.JUVENILE: hatchling_end,
        LifeStage.SUBADULT: juvenile_end,
        LifeStage.ADULT: subadult_end,
        LifeStage.SENESCENT: senescent_start,
    }


def current_stage_for_age(age_ticks: int, thresholds: dict[LifeStage, int]) -> LifeStage:
    """Determine life stage given current age in ticks."""
    stage = LifeStage.HATCHLING
    for s in (LifeStage.JUVENILE, LifeStage.SUBADULT, LifeStage.ADULT, LifeStage.SENESCENT):
        if age_ticks >= thresholds.get(s, 10**9):
            stage = s
    return stage


def growth_factor(age_ticks: int, thresholds: dict[LifeStage, int]) -> float:
    """Return [0, 1] growth factor for scaling body size/speed.

    Hatchling = ~0.05, Adult = 1.0, Senescent stays at 1.0.
    """
    adult_threshold = thresholds.get(LifeStage.ADULT, 1)
    if adult_threshold <= 0:
        return 1.0
    stage = current_stage_for_age(age_ticks, thresholds)
    if stage in (LifeStage.ADULT, LifeStage.SENESCENT):
        return 1.0
    factor = min(1.0, age_ticks / max(1, adult_threshold))
    # Minimum at hatchling
    return max(0.05, factor)


# ---------------------------------------------------------------------------
# Agent aging and stage transitions
# ---------------------------------------------------------------------------


def age_agent(
    agent: Agent,
    world: "World",
    species_data: dict[str, Any],
    aging_scale: float,
    event_bus: EventBus,
    rng: Any,
) -> None:
    """Advance an agent's age by one tick and handle stage transitions, death."""
    if not agent.alive:
        return

    agent.age_ticks += 1

    thresholds = get_stage_thresholds(species_data, aging_scale)
    old_stage = agent.life_stage
    new_stage = current_stage_for_age(agent.age_ticks, thresholds)

    # Stage transition
    if new_stage != old_stage:
        agent.life_stage = new_stage
        # Rescale physical stats at stage transition
        _rescale_agent_stats(agent, species_data, thresholds)
        event_bus.emit(Event(
            tick=world.tick,
            category=EventCategory.LIFECYCLE,
            subcategory=EventSubcategory.STAGE_CHANGE,
            actor_ids=[agent.id],
            position=agent.position,
            payload={
                "old_stage": old_stage.value,
                "new_stage": new_stage.value,
                "species": agent.species_key,
                "name": agent.display_name,
            },
        ))

    # Smooth stat scaling every tick (gradual growth)
    gf = growth_factor(agent.age_ticks, thresholds)
    base_mass = species_data.get("body_mass_kg", 100.0) * agent.traits.size_factor
    agent.body_mass_kg = base_mass * gf

    base_speed = species_data.get("max_speed_cells_per_tick", 1.0) * agent.traits.speed_factor
    # Hatchling/juvenile slower; senescent slightly slower
    if new_stage == LifeStage.SENESCENT:
        speed_mod = 0.75
    else:
        speed_mod = gf
    agent.max_speed = base_speed * max(0.1, speed_mod)
    agent.current_speed = agent.max_speed

    # Senescence death risk
    if new_stage == LifeStage.SENESCENT:
        lifespan_ticks = thresholds.get(LifeStage.SENESCENT, 1)
        senescent_age = agent.age_ticks - lifespan_ticks
        death_prob = min(0.002, 0.0001 * (1 + senescent_age / max(1, lifespan_ticks)))
        if rng.chance(death_prob):
            kill_agent(agent, "old_age", world, event_bus)
            return

    # Check lifespan cap
    max_age_years = species_data.get("lifespan_years", 30.0) * 1.3  # some live longer
    from prehistoric_sim.engine.world import TICKS_PER_DAY  # noqa: PLC0415
    max_age_ticks = int(max_age_years * TICKS_PER_DAY * 365 / aging_scale)
    if agent.age_ticks >= max_age_ticks:
        kill_agent(agent, "old_age", world, event_bus)


def _rescale_agent_stats(
    agent: Agent,
    species_data: dict[str, Any],
    thresholds: dict[LifeStage, int],
) -> None:
    """Fully recalculate physical stats at a stage transition."""
    gf = growth_factor(agent.age_ticks, thresholds)
    base_mass = species_data.get("body_mass_kg", 100.0) * agent.traits.size_factor
    agent.body_mass_kg = base_mass * gf
    base_speed = species_data.get("max_speed_cells_per_tick", 1.0) * agent.traits.speed_factor
    agent.max_speed = base_speed * max(0.05, gf)
    agent.current_speed = agent.max_speed


# ---------------------------------------------------------------------------
# Metabolism
# ---------------------------------------------------------------------------


def update_metabolism(
    agent: Agent,
    species_data: dict[str, Any],
    rng: Any,
) -> None:
    """Tick-level energy and hydration budgets.

    Applies basal metabolic cost, movement cost (if moving), injury cost,
    growth cost, and dehydration. Updates drives from resulting values.
    """
    endothermic = species_data.get("endothermic", True)
    bmr = basal_metabolic_rate(agent.body_mass_kg, endothermic)
    eff = agent.traits.metabolic_efficiency

    # Base energy drain
    energy_cost = bmr / eff

    # Action modifiers
    action = agent.current_action
    if action in ("CHASE", "FLEE", "SPRINT"):
        energy_cost *= 4.0
        agent.stamina = max(0.0, agent.stamina - 0.04)
    elif action in ("HUNT", "STALK"):
        energy_cost *= 1.8
        agent.stamina = max(0.0, agent.stamina - 0.01)
    elif action in ("REST", "SLEEP"):
        energy_cost *= 0.4
        agent.stamina = min(1.0, agent.stamina + 0.05)
    else:
        agent.stamina = min(1.0, agent.stamina + 0.01)

    # Injury raises energy cost
    if agent.injury_level > 0:
        energy_cost *= 1.0 + agent.injury_level * 0.5

    # Growth cost for young creatures
    if agent.life_stage in (LifeStage.HATCHLING, LifeStage.JUVENILE):
        energy_cost *= 1.3

    agent.energy = max(0.0, agent.energy - energy_cost)

    # Hydration drain scales with mass
    mass = max(0.05, agent.body_mass_kg)
    hydration_cost = 0.0006 + (mass ** -0.25) * 0.0005
    agent.hydration = max(0.0, agent.hydration - hydration_cost)

    # Injury healing (slow)
    if agent.injury_level > 0 and agent.energy > 0.5:
        agent.injury_level = max(0.0, agent.injury_level - 0.0005)

    # Health penalties from starvation and dehydration
    if agent.energy < 0.05:
        agent.health = max(0.0, agent.health - 0.005)
    elif agent.energy > 0.3:
        agent.health = min(1.0, agent.health + 0.001)

    if agent.hydration < 0.05:
        agent.health = max(0.0, agent.health - 0.008)

    # Update drives
    agent.drives.hunger = 1.0 - agent.energy
    agent.drives.thirst = 1.0 - agent.hydration
    agent.drives.fatigue = 1.0 - agent.stamina


# ---------------------------------------------------------------------------
# Death
# ---------------------------------------------------------------------------


def kill_agent(
    agent: Agent,
    cause: str,
    world: "World",
    event_bus: EventBus,
) -> None:
    """Mark an agent as dead and emit the death event."""
    if not agent.alive:
        return
    agent.alive = False
    agent.death_tick = world.tick
    agent.cause_of_death = cause

    event_bus.emit(Event(
        tick=world.tick,
        category=EventCategory.LIFECYCLE,
        subcategory=EventSubcategory.DEATH,
        actor_ids=[agent.id],
        position=agent.position,
        payload={
            "species": agent.species_key,
            "name": agent.display_name,
            "cause": cause,
            "age_ticks": agent.age_ticks,
            "life_stage": agent.life_stage.value,
        },
    ))


def create_carcass(agent: Agent, world: "World", event_bus: EventBus) -> Carcass:
    """Convert a dead agent into a Carcass entity."""
    carcass = Carcass(
        id=_new_id("carcass"),
        position=agent.position,
        alive=True,
        species_key=agent.species_key,
        original_mass_kg=agent.body_mass_kg,
        mass_remaining=agent.body_mass_kg,
        decay_progress=0.0,
        nutrients_released=0.0,
        death_tick=world.tick,
        cause_of_death=agent.cause_of_death or "unknown",
    )
    event_bus.emit(Event(
        tick=world.tick,
        category=EventCategory.LIFECYCLE,
        subcategory=EventSubcategory.CARCASS_FORMED,
        actor_ids=[agent.id],
        position=agent.position,
        payload={
            "carcass_id": carcass.id,
            "species": agent.species_key,
            "mass_kg": agent.body_mass_kg,
        },
    ))
    return carcass


# ---------------------------------------------------------------------------
# Decomposition
# ---------------------------------------------------------------------------


def decay_carcass(
    carcass: Carcass,
    world: "World",
    event_bus: EventBus,
) -> bool:
    """Advance carcass decomposition. Returns True when fully decayed."""
    # Temperature and moisture drive decay
    temp = world.temperature
    temp_factor = max(0.5, temp / 30.0)
    moisture = 1.0 if world.is_water(*carcass.position) else 0.6
    if world.weather.current in (
        from_enum := lambda: None,  # noqa: E731
    ):
        pass  # placeholder pattern

    # Moisture from weather
    if world.weather.current.value in ("RAIN", "STORM", "FLOOD"):
        moisture = 1.0

    decay_rate = 0.0008 * temp_factor * moisture
    carcass.decay_progress = min(1.0, carcass.decay_progress + decay_rate)
    carcass.mass_remaining = max(0.0, carcass.original_mass_kg * (1.0 - carcass.decay_progress))

    # Release nutrients to soil
    if carcass.decay_progress < 1.0:
        nutrient_batch = decay_rate * carcass.original_mass_kg * 0.001
        world.add_nutrients(*carcass.position, nutrient_batch, radius=2)
        carcass.nutrients_released += nutrient_batch

    # Full decay
    if carcass.is_depleted:
        carcass.alive = False
        event_bus.emit(Event(
            tick=world.tick,
            category=EventCategory.LIFECYCLE,
            subcategory=EventSubcategory.CARCASS_DECAYED,
            actor_ids=[carcass.id],
            position=carcass.position,
            payload={
                "species": carcass.species_key,
                "nutrients_released": round(carcass.nutrients_released, 3),
            },
        ))
        return True
    return False


# ---------------------------------------------------------------------------
# Egg incubation
# ---------------------------------------------------------------------------


def incubate_egg(
    egg: Egg,
    world: "World",
    event_bus: EventBus,
    rng: Any,
) -> bool:
    """Advance egg incubation by one tick. Returns True if egg hatches."""
    if not egg.is_viable:
        return False

    # Temperature stress
    temp = world.temperature
    optimal_temp = 30.0  # degrees C; species-specific could be loaded
    deviation = abs(temp - optimal_temp)
    if deviation > 15.0:
        egg.temperature_stress += 0.002 * (deviation - 15.0)

    egg.incubation_ticks_remaining -= 1

    if egg.incubation_ticks_remaining <= 0:
        # Hatch!
        egg.hatched = True
        egg.alive = False
        event_bus.emit(Event(
            tick=world.tick,
            category=EventCategory.LIFECYCLE,
            subcategory=EventSubcategory.HATCHING,
            actor_ids=[egg.id],
            position=egg.position,
            payload={
                "species": egg.species_key,
                "clutch_id": egg.clutch_id,
                "parent_ids": egg.parent_ids,
            },
        ))
        return True

    # Egg death from stress
    if egg.temperature_stress >= 1.0:
        egg.alive = False
        return False

    return False
