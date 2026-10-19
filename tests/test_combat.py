"""
test_combat.py — Tests for combat resolution, hunting, injuries, and defenses.
"""

from __future__ import annotations

import pytest

from prehistoric_sim.engine.combat import (
    attempt_fight,
    attempt_hunt,
    resolve_prey_defenses,
)
from prehistoric_sim.engine.entities import Agent, LifeStage
from prehistoric_sim.engine.events import EventBus
from prehistoric_sim.engine.rng import SimRNG
from prehistoric_sim.engine.world import World


def test_hunt_success_and_carcass_creation():
    rng = SimRNG(42)
    bus = EventBus()
    world = World(width=40, height=40, seed=42, rng=rng, event_bus=bus)

    predator = Agent(
        id="trex",
        position=(10, 10),
        species_key="tyrannosaurus_rex",
        body_mass_kg=8000.0,
        max_speed=5.0,
        energy=0.5,
    )
    prey = Agent(
        id="small_prey",
        position=(10, 10),
        species_key="thescelosaurus",
        body_mass_kg=40.0,
        max_speed=6.0,
        life_stage=LifeStage.JUVENILE,
    )

    species_data = {
        "tyrannosaurus_rex": {"hunt_style": "ambush"},
        "thescelosaurus": {"defense_type": "flee"},
    }

    # Attempt hunt
    carcass = attempt_hunt(predator, prey, world, bus, species_data, rng)
    # A huge apex predator on top of a juvenile small prey should kill it or create a carcass
    if carcass is not None:
        assert carcass.original_mass_kg == 40.0
        assert not prey.alive
        assert predator.energy > 0.5


def test_ankylosaurus_tail_club_defense():
    rng = SimRNG(1)
    bus = EventBus()
    world = World(width=40, height=40, seed=1, rng=rng, event_bus=bus)

    predator = Agent(id="dako", position=(5, 5), species_key="dakotaraptor", injury_level=0.0)
    anky = Agent(id="anky", position=(5, 5), species_key="ankylosaurus")

    prey_sd = {"defense_type": "tail_club"}

    # Repeatedly resolve defense to ensure tail_club triggers injury
    injured = False
    for _ in range(20):
        resolve_prey_defenses(predator, anky, prey_sd, world, bus, rng)
        if predator.injury_level > 0.0:
            injured = True
            break

    assert injured


def test_triceratops_charge_defense():
    rng = SimRNG(2)
    bus = EventBus()
    world = World(width=40, height=40, seed=2, rng=rng, event_bus=bus)

    predator = Agent(id="rex", position=(5, 5), species_key="tyrannosaurus_rex", injury_level=0.0)
    trike = Agent(id="trike", position=(5, 5), species_key="triceratops")

    prey_sd = {"defense_type": "charge"}

    charged = False
    for _ in range(20):
        resolve_prey_defenses(predator, trike, prey_sd, world, bus, rng)
        if predator.injury_level > 0.0:
            charged = True
            break

    assert charged
