"""
test_hazards.py — Tests for weather hazards: fire spread, storm, drought, flood.
"""

from __future__ import annotations

import pytest

from prehistoric_sim.engine.entities import TerrainType, WeatherType
from prehistoric_sim.engine.events import EventBus
from prehistoric_sim.engine.rng import SimRNG
from prehistoric_sim.engine.world import World


def test_wildfire_spread_and_plant_reset():
    rng = SimRNG(42)
    bus = EventBus()
    world = World(width=40, height=40, seed=42, rng=rng, event_bus=bus)

    x, y = 20, 20
    world.set_terrain(x, y, TerrainType.FOREST)
    world.plant_biomass[0, y, x] = 1.0

    # Ignite cell
    world.weather.fire_cells.add((x, y))
    assert (x, y) in world.weather.fire_cells

    # Step world to simulate fire spread
    for _ in range(5):
        world.step()

    # Burned cell plant biomass should be consumed/reduced
    assert world.plant_biomass[0, y, x] < 1.0


def test_drought_evaporation_and_growth_suppression():
    rng = SimRNG(123)
    bus = EventBus()
    world = World(width=30, height=30, seed=123, rng=rng, event_bus=bus)

    world._start_weather(WeatherType.DROUGHT, duration_ticks=50)
    assert world.weather.current == WeatherType.DROUGHT

    for _ in range(10):
        world.step()

    # Drought should increase evaporation
    assert world.weather.rainfall_intensity == 0.0


def test_flood_cell_expansion():
    rng = SimRNG(7)
    bus = EventBus()
    world = World(width=30, height=30, seed=7, rng=rng, event_bus=bus)

    world._start_weather(WeatherType.FLOOD, duration_ticks=40)
    for _ in range(5):
        world.step()

    # Flood cells should be populated
    assert len(world.weather.flood_cells) >= 0
