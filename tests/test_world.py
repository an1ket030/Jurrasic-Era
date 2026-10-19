"""
test_world.py — Tests for world grid, terrain, plants, nutrients, and weather.
"""

from __future__ import annotations

import numpy as np
import pytest

from prehistoric_sim.engine.entities import TerrainType, WeatherType
from prehistoric_sim.engine.events import EventBus
from prehistoric_sim.engine.rng import SimRNG
from prehistoric_sim.engine.world import World


def test_world_generation():
    rng = SimRNG(42)
    bus = EventBus()
    world = World(width=60, height=60, seed=42, rng=rng, event_bus=bus)

    assert world.width == 60
    assert world.height == 60
    assert world.terrain.shape == (60, 60)
    assert world.water_depth.shape == (60, 60)

    # Verify diverse terrain generated
    unique_terrains = set(world.terrain.flatten())
    assert len(unique_terrains) >= 4


def test_plant_regrowth_and_nutrients():
    rng = SimRNG(42)
    bus = EventBus()
    world = World(width=40, height=40, seed=42, rng=rng, event_bus=bus)

    # Consume some plant biomass
    x, y = 20, 20
    consumed = world.consume_plant(x, y, layer=0, amount=0.5)
    assert consumed >= 0.0

    # Add nutrient boost
    world.add_nutrients(x, y, amount=0.4, radius=2)
    assert world.nutrients[y, x] > 0.0

    # Step world to trigger regrowth
    initial_biomass = world.get_plant_biomass_layer(x, y, 0)
    for _ in range(5):
        world.step()
    regrown_biomass = world.get_plant_biomass_layer(x, y, 0)
    assert regrown_biomass >= initial_biomass


def test_weather_state_transitions():
    rng = SimRNG(123)
    bus = EventBus()
    world = World(width=40, height=40, seed=123, rng=rng, event_bus=bus)

    # Force weather start
    world._start_weather(WeatherType.RAIN, duration_ticks=10)
    assert world.weather.current == WeatherType.RAIN
    assert world.weather.ticks_remaining == 10

    # Step through duration
    for _ in range(11):
        world.step()

    # Weather should clear
    assert world.weather.current == WeatherType.CLEAR
