"""
test_lifecycle.py — Tests for life stage transitions, aging, growth, death, and carcass decay.
"""

from __future__ import annotations

import pytest

from prehistoric_sim.engine.entities import Agent, LifeStage
from prehistoric_sim.engine.events import EventBus, EventCategory, EventSubcategory
from prehistoric_sim.engine.lifecycle import (
    age_agent,
    create_carcass,
    current_stage_for_age,
    decay_carcass,
    get_stage_thresholds,
    growth_factor,
    kill_agent,
)
from prehistoric_sim.engine.rng import SimRNG
from prehistoric_sim.engine.world import World


def test_stage_thresholds_and_transitions():
    species_data = {
        "species_key": "test_rex",
        "lifespan_years": 30.0,
        "maturity_age_years": 10.0,
        "life_stages": {
            "hatchling_years": 0.5,
            "juvenile_years": 4.0,
            "subadult_years": 8.0,
            "senescent_start_years": 24.0,
        },
    }
    thresholds = get_stage_thresholds(species_data, aging_scale=50.0)

    # Verify order of thresholds
    assert thresholds[LifeStage.HATCHLING] == 0
    assert thresholds[LifeStage.JUVENILE] > thresholds[LifeStage.HATCHLING]
    assert thresholds[LifeStage.SUBADULT] > thresholds[LifeStage.JUVENILE]
    assert thresholds[LifeStage.ADULT] > thresholds[LifeStage.SUBADULT]
    assert thresholds[LifeStage.SENESCENT] > thresholds[LifeStage.ADULT]

    # Verify stage lookup given ticks
    assert current_stage_for_age(0, thresholds) == LifeStage.HATCHLING
    assert current_stage_for_age(thresholds[LifeStage.JUVENILE], thresholds) == LifeStage.JUVENILE
    assert current_stage_for_age(thresholds[LifeStage.ADULT] + 10, thresholds) == LifeStage.ADULT
    assert current_stage_for_age(thresholds[LifeStage.SENESCENT] + 100, thresholds) == LifeStage.SENESCENT


def test_growth_factor_scaling():
    thresholds = {
        LifeStage.HATCHLING: 0,
        LifeStage.JUVENILE: 100,
        LifeStage.SUBADULT: 300,
        LifeStage.ADULT: 600,
        LifeStage.SENESCENT: 1200,
    }
    assert growth_factor(0, thresholds) < 0.2
    assert growth_factor(600, thresholds) >= 1.0


def test_kill_agent_and_carcass_formation():
    rng = SimRNG(42)
    bus = EventBus()
    world = World(width=40, height=40, seed=42, rng=rng, event_bus=bus)

    agent = Agent(
        id="rex-1",
        position=(10, 10),
        species_key="tyrannosaurus_rex",
        body_mass_kg=5000.0,
        alive=True,
    )

    kill_agent(agent, "starvation", world, bus)
    assert not agent.alive
    assert agent.cause_of_death == "starvation"

    carcass = create_carcass(agent, world, bus)
    assert carcass.alive
    assert carcass.original_mass_kg == 5000.0
    assert carcass.mass_remaining == 5000.0
    assert carcass.position == (10, 10)


def test_carcass_decay_and_nutrient_release():
    rng = SimRNG(42)
    bus = EventBus()
    world = World(width=40, height=40, seed=42, rng=rng, event_bus=bus)

    agent = Agent(id="prey-1", position=(15, 15), species_key="thescelosaurus", body_mass_kg=40.0)
    kill_agent(agent, "old_age", world, bus)
    carcass = create_carcass(agent, world, bus)

    initial_nutrients = world.nutrients[15, 15]

    # Step decay multiple times
    for _ in range(50):
        if not carcass.alive:
            break
        decay_carcass(carcass, world, bus)

    assert carcass.decay_progress > 0.0
    assert carcass.nutrients_released > 0.0
    assert world.nutrients[15, 15] >= initial_nutrients
