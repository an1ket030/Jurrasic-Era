"""
test_mind.py — Tests for perception limits, memory decay, and utility decision scoring.
"""

from __future__ import annotations

import pytest

from prehistoric_sim.engine.entities import Agent, LifeStage, MemoryEntry
from prehistoric_sim.engine.events import EventBus
from prehistoric_sim.engine.mind import (
    decide,
    perceive,
    score_actions,
    update_memory,
)
from prehistoric_sim.engine.rng import SimRNG
from prehistoric_sim.engine.spatial import SpatialHash
from prehistoric_sim.engine.world import World


def test_perception_limits_and_occlusion():
    rng = SimRNG(42)
    bus = EventBus()
    world = World(width=50, height=50, seed=42, rng=rng, event_bus=bus)

    agent_hash = SpatialHash[Agent](cell_size=10)
    carcass_hash = SpatialHash(cell_size=10)
    nest_hash = SpatialHash(cell_size=10)

    predator = Agent(
        id="pred",
        position=(20, 20),
        species_key="tyrannosaurus_rex",
        _species_data={
            "vision_range_cells": 15.0,
            "fov_degrees": 180.0,
            "diet": "CARNIVORE",
            "prey_species": ["thescelosaurus"],
        },
    )

    # Prey inside vision range
    prey_near = Agent(id="p1", position=(25, 20), species_key="thescelosaurus")
    # Prey far beyond vision range
    prey_far = Agent(id="p2", position=(45, 45), species_key="thescelosaurus")

    agent_hash.insert(predator, 20, 20)
    agent_hash.insert(prey_near, 25, 20)
    agent_hash.insert(prey_far, 45, 45)

    percepts = perceive(
        predator, world, agent_hash, carcass_hash, nest_hash,
        all_species_data={}, rng=rng
    )

    visible_ids = [p.id for p in percepts["prey_visible"]]
    assert "p1" in visible_ids
    assert "p2" not in visible_ids


def test_memory_storage_and_decay():
    rng = SimRNG(42)
    bus = EventBus()
    world = World(width=50, height=50, seed=42, rng=rng, event_bus=bus)
    world.tick = 100

    agent = Agent(id="a1", position=(10, 10))
    agent.memory.append(MemoryEntry(kind="water", position=(12, 12), tick_stored=100, strength=1.0))
    agent.memory.append(MemoryEntry(kind="predator", position=(15, 15), tick_stored=10, strength=0.5))

    percepts = {"has_water_nearby": False, "edible_carcasses": [], "predators_visible": []}

    # Step world to tick 300 to trigger decay
    world.tick = 300
    update_memory(agent, percepts, world)

    # Old predator sighting should have decayed and been purged
    predator_mem = [m for m in agent.memory if m.kind == "predator"]
    assert len(predator_mem) == 0


def test_utility_scoring_priorities():
    rng = SimRNG(42)
    bus = EventBus()
    world = World(width=50, height=50, seed=42, rng=rng, event_bus=bus)

    agent = Agent(id="a1", position=(10, 10), species_key="edmontosaurus")
    agent.drives.hunger = 0.95
    agent.drives.thirst = 0.1

    percepts = {
        "predators_visible": [],
        "in_fire": False,
        "in_flood": False,
        "has_water_nearby": False,
        "plant_food_at_pos": 1.5,
        "edible_carcasses": [],
        "conspecifics": [],
    }

    sd = {
        "diet": "HERBIVORE",
        "activity_pattern": "DIURNAL",
        "preferred_plant_layers": [0, 1],
    }

    scored = score_actions(agent, percepts, world, sd, rng)
    top_action, top_score, _ = scored[0]

    # When starving and plant food is at position, GRAZE should score highest
    assert top_action == "GRAZE"
    assert top_score > 0.5
