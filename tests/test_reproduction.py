"""
test_reproduction.py — Tests for reproduction: mating, eggs, nests, hatching, live birth, parental care.
"""

from __future__ import annotations

import pytest

from prehistoric_sim.engine.entities import Agent, Egg, LifeStage, Nest
from prehistoric_sim.engine.events import EventBus
from prehistoric_sim.engine.reproduction import (
    attempt_mating,
    build_nest,
    can_mate,
    give_birth,
    hatch_egg,
    lay_clutch,
)
from prehistoric_sim.engine.rng import SimRNG
from prehistoric_sim.engine.world import World


def test_can_mate_preconditions():
    rng = SimRNG(42)
    bus = EventBus()
    world = World(width=40, height=40, seed=42, rng=rng, event_bus=bus)
    world.season_index = 0  # SPRING

    sd = {
        "breeding_season": "SPRING",
        "min_energy_to_breed": 0.4,
    }

    # Healthy adult in season
    agent = Agent(id="a1", life_stage=LifeStage.ADULT, energy=0.8, health=1.0)
    assert can_mate(agent, sd, world)

    # Low energy cannot mate
    low_energy_agent = Agent(id="a2", life_stage=LifeStage.ADULT, energy=0.2, health=1.0)
    assert not can_mate(low_energy_agent, sd, world)

    # Juvenile cannot mate
    juv_agent = Agent(id="a3", life_stage=LifeStage.JUVENILE, energy=0.8, health=1.0)
    assert not can_mate(juv_agent, sd, world)


def test_egg_laying_clutch_and_hatching():
    rng = SimRNG(42)
    bus = EventBus()
    world = World(width=40, height=40, seed=42, rng=rng, event_bus=bus)

    parent = Agent(
        id="parent_rex",
        position=(10, 10),
        species_key="tyrannosaurus_rex",
        life_stage=LifeStage.ADULT,
        energy=0.9,
    )

    sd = {
        "species_key": "tyrannosaurus_rex",
        "reproduction_type": "EGG_LAYING",
        "min_clutch_size": 2,
        "max_clutch_size": 4,
        "incubation_days": 10.0,
    }

    nest = build_nest(parent, world, sd, bus, rng)
    assert nest.owner_id == parent.id

    eggs = lay_clutch(parent, nest, world, sd, bus, rng, aging_scale=50.0, all_species_data={"tyrannosaurus_rex": sd})
    assert len(eggs) >= 2
    assert len(nest.egg_ids) == len(eggs)

    egg = eggs[0]
    hatchling = hatch_egg(egg, world, {"tyrannosaurus_rex": sd}, bus, rng, aging_scale=50.0)
    assert hatchling is not None
    assert hatchling.life_stage == LifeStage.HATCHLING
    assert hatchling.species_key == "tyrannosaurus_rex"
    assert "parent_rex" in hatchling.parent_ids


def test_live_birth_didelphodon():
    rng = SimRNG(100)
    bus = EventBus()
    world = World(width=40, height=40, seed=100, rng=rng, event_bus=bus)

    female = Agent(
        id="mom_didelphodon",
        position=(5, 5),
        species_key="didelphodon",
        life_stage=LifeStage.ADULT,
        pregnant=True,
        gestation_ticks_remaining=0,
    )

    sd = {
        "species_key": "didelphodon",
        "reproduction_type": "LIVE_BIRTH",
        "min_clutch_size": 2,
        "max_clutch_size": 5,
    }

    offspring = give_birth(female, world, sd, {"didelphodon": sd}, bus, rng, aging_scale=50.0)
    assert len(offspring) >= 1
    newborn = offspring[0]
    assert newborn.life_stage == LifeStage.HATCHLING
    assert "mom_didelphodon" in newborn.parent_ids
    assert not female.pregnant
