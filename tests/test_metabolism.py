"""
test_metabolism.py — Tests for Kleiber's law, energy consumption, and vital budgets.
"""

from __future__ import annotations

import pytest

from prehistoric_sim.engine.entities import Agent, LifeStage
from prehistoric_sim.engine.lifecycle import basal_metabolic_rate, update_metabolism
from prehistoric_sim.engine.rng import SimRNG


def test_kleiber_scaling():
    # Large animals burn less energy PER UNIT MASS than small animals
    small_mass = 2.0
    large_mass = 4000.0

    bmr_small = basal_metabolic_rate(small_mass, endothermic=True)
    bmr_large = basal_metabolic_rate(large_mass, endothermic=True)

    # Fractional metabolic rate per tick (fraction of body mass) is lower for large animals
    assert bmr_large < bmr_small
    assert bmr_large > 0.0
    assert bmr_small > 0.0


def test_endotherm_vs_ectotherm():
    mass = 100.0
    bmr_endo = basal_metabolic_rate(mass, endothermic=True)
    bmr_ecto = basal_metabolic_rate(mass, endothermic=False)
    assert bmr_endo > bmr_ecto


def test_update_metabolism_action_modifiers():
    rng = SimRNG(42)
    sd = {"endothermic": True}

    resting_agent = Agent(id="a1", body_mass_kg=50.0, current_action="REST", energy=0.8, stamina=0.5)
    sprinting_agent = Agent(id="a2", body_mass_kg=50.0, current_action="CHASE", energy=0.8, stamina=0.5)

    update_metabolism(resting_agent, sd, rng)
    update_metabolism(sprinting_agent, sd, rng)

    # Sprinting burns more energy than resting
    assert sprinting_agent.energy < resting_agent.energy
    # Resting restores stamina; sprinting drains it
    assert resting_agent.stamina > 0.5
    assert sprinting_agent.stamina < 0.5
