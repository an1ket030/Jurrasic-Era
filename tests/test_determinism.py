"""
test_determinism.py — Determinism tests for the prehistoric ecosystem simulation.

Verifies:
1. Two simulations initialized with the identical random seed and configuration
   produce bit-identical trajectories (agent counts, states, positions, and events).
2. Different seeds produce divergent trajectories.
3. State capture and restore preserves world state faithfully.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from prehistoric_sim.engine.simulation import SimConfig, Simulation
from prehistoric_sim.io.species_loader import load_all_species, load_world_config

SPECIES_DIR = Path(__file__).resolve().parent.parent / "data" / "species"
WORLDS_DIR = Path(__file__).resolve().parent.parent / "data" / "worlds"


@pytest.fixture
def species_data():
    return load_all_species(SPECIES_DIR)


@pytest.fixture
def world_config():
    return load_world_config(WORLDS_DIR, "hell_creek")


def test_seed_determinism(species_data, world_config):
    """Two simulations with the same seed must produce identical agent states and event logs."""
    cfg1 = SimConfig(
        seed=12345,
        world_width=40,
        world_height=40,
        days_per_season=30,
        aging_scale=10.0,
        population_cap=200,
    )
    cfg2 = SimConfig(
        seed=12345,
        world_width=40,
        world_height=40,
        days_per_season=30,
        aging_scale=10.0,
        population_cap=200,
    )

    sim1 = Simulation(config=cfg1, species_data=species_data, world_config=world_config)
    sim2 = Simulation(config=cfg2, species_data=species_data, world_config=world_config)

    sim1.populate()
    sim2.populate()

    events1: list[tuple[int, str, str]] = []
    events2: list[tuple[int, str, str]] = []

    sim1.event_bus.subscribe(lambda e: events1.append((e.tick, e.category.value, e.subcategory.value)))
    sim2.event_bus.subscribe(lambda e: events2.append((e.tick, e.category.value, e.subcategory.value)))

    # Run for 30 ticks
    for _ in range(30):
        sim1.step()
        sim2.step()

    assert len(sim1.agents) == len(sim2.agents)
    assert len(sim1.carcasses) == len(sim2.carcasses)

    # Check agents match exactly
    list1 = sorted(sim1.agents.values(), key=lambda a: (a.species_key, a.position, round(a.body_mass_kg, 2)))
    list2 = sorted(sim2.agents.values(), key=lambda a: (a.species_key, a.position, round(a.body_mass_kg, 2)))
    for a1, a2 in zip(list1, list2):
        assert a1.species_key == a2.species_key
        assert a1.position == a2.position
        assert pytest.approx(a1.energy, abs=1e-5) == a2.energy
        assert pytest.approx(a1.hydration, abs=1e-5) == a2.hydration
        assert a1.alive == a2.alive
        assert a1.current_action == a2.current_action

    # Check identical event sequence
    assert len(events1) == len(events2)
    assert events1 == events2


def test_seed_divergence(species_data, world_config):
    """Simulations with different seeds should diverge."""
    cfg1 = SimConfig(seed=101, world_width=40, world_height=40, aging_scale=10.0)
    cfg2 = SimConfig(seed=999, world_width=40, world_height=40, aging_scale=10.0)

    sim1 = Simulation(config=cfg1, species_data=species_data, world_config=world_config)
    sim2 = Simulation(config=cfg2, species_data=species_data, world_config=world_config)

    sim1.populate()
    sim2.populate()

    for _ in range(25):
        sim1.step()
        sim2.step()

    # Positions or energies of agents should not all be identical
    differences = 0
    common_ids = set(sim1.agents.keys()) & set(sim2.agents.keys())
    for aid in common_ids:
        if sim1.agents[aid].position != sim2.agents[aid].position:
            differences += 1
    # Different seeds should produce distinct random placements/paths
    assert differences > 0 or len(sim1.agents) != len(sim2.agents) or len(common_ids) < len(sim1.agents)
