"""
test_admin.py — Tests for all admin commands and error resilience.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from prehistoric_sim.admin.commands import execute_command, get_all_commands
from prehistoric_sim.engine.entities import LifeStage
from prehistoric_sim.engine.simulation import SimConfig, Simulation
from prehistoric_sim.io.species_loader import load_all_species


@pytest.fixture
def test_sim():
    species_dir = Path("data/species")
    species_data = load_all_species(species_dir)
    cfg = SimConfig(seed=42, world_width=40, world_height=40)
    sim = Simulation(config=cfg, species_data=species_data)
    return sim


def test_admin_spawn_and_name(test_sim):
    res = test_sim.apply_admin_command("spawn", {"entity_type": "tyrannosaurus_rex", "count": 1, "name": "BigRex"})
    assert "Spawned" in res
    agent = test_sim.find_agent("BigRex")
    assert agent is not None
    assert agent.name == "BigRex"
    assert agent.species_key == "tyrannosaurus_rex"

    # Rename
    res_rename = test_sim.apply_admin_command("name", {"target": "BigRex", "new_name": "KingRex"})
    assert "Renamed" in res_rename
    assert test_sim.find_agent("KingRex") is not None


def test_admin_vitals_commands(test_sim):
    test_sim.apply_admin_command("spawn", {"entity_type": "edmontosaurus", "count": 1, "name": "Ed"})
    agent = test_sim.find_agent("Ed")
    assert agent is not None

    # Injure
    test_sim.apply_admin_command("injure", {"target": "Ed", "amount": 0.4})
    assert agent.injury_level > 0.0

    # Heal
    test_sim.apply_admin_command("heal", {"target": "Ed"})
    assert agent.injury_level == 0.0
    assert agent.health == 1.0

    # Feed & Water
    test_sim.apply_admin_command("set", {"target": "Ed", "field": "energy", "value": 0.3})
    test_sim.apply_admin_command("feed", {"target": "Ed"})
    assert agent.energy == 1.0


def test_admin_possess_and_act(test_sim):
    test_sim.apply_admin_command("spawn", {"entity_type": "thescelosaurus", "count": 1, "name": "Speedy"})
    agent = test_sim.find_agent("Speedy")

    # Possess
    test_sim.apply_admin_command("possess", {"target": "Speedy"})
    assert agent.possessed
    assert agent.id in test_sim._possessed

    # Act override
    test_sim.apply_admin_command("act", {"action": "REST"})
    assert agent.current_action == "REST"

    # Release
    test_sim.apply_admin_command("release", {"target": "Speedy"})
    assert not agent.possessed


def test_admin_save_and_load(test_sim, tmp_path):
    test_sim.apply_admin_command("spawn", {"entity_type": "triceratops", "count": 1, "name": "Trike"})
    test_sim.tick = 42

    save_file = tmp_path / "snapshot_test.json"
    res_save = test_sim.apply_admin_command("save", {"filename": str(save_file)})
    assert "Snapshot saved" in res_save
    assert save_file.exists()

    # Create new empty sim and load snapshot
    cfg = SimConfig(seed=999)
    new_sim = Simulation(config=cfg, species_data=test_sim.species_data)
    res_load = new_sim.apply_admin_command("load", {"filename": str(save_file)})
    assert "successfully loaded" in res_load
    assert new_sim.tick == 42
    assert new_sim.find_agent("Trike") is not None


def test_admin_error_resilience(test_sim):
    # Invalid command
    res1 = test_sim.apply_admin_command("nonexistent_cmd", {})
    assert "Unknown command" in res1

    # Invalid target
    res2 = test_sim.apply_admin_command("kill", {"target": "ghost_creature"})
    assert "not found" in res2.lower()
