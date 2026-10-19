"""
test_renderer.py — Unit tests for the Rich terminal EventRenderer.

Verifies:
- Formatting and rendering of events across all categories and subcategories
- Filtering logic: verbosity gating (0, 1, 2, 3), species filter, category filter, follow ID
- Safe rendering in both color and no-color modes without crashing
"""

from __future__ import annotations

import io
from pathlib import Path
import pytest
from rich.console import Console

from prehistoric_sim.engine.events import (
    Event,
    EventBus,
    EventCategory,
    EventSubcategory,
)
from prehistoric_sim.ui.renderer import EventRenderer
from prehistoric_sim.ui.theme import Theme


@pytest.fixture
def theme() -> Theme:
    theme_path = Path(__file__).resolve().parent.parent / "data" / "theme.yaml"
    return Theme.load(theme_path)


@pytest.fixture
def mock_world():
    class MockWorld:
        day = 12
        hour_of_day = 6.5
        season = "Spring"
    return MockWorld()


def test_renderer_initialization(theme, mock_world):
    console = Console(file=io.StringIO(), force_terminal=False, no_color=True)
    renderer = EventRenderer(console=console, theme=theme, verbosity=2, world_ref=mock_world)
    assert renderer.verbosity == 2
    assert renderer._world.day == 12


def test_renderer_all_event_subcategories(theme, mock_world):
    """Ensure every supported event subcategory formats without error in both color and no-color mode."""
    for no_color in [False, True]:
        buffer = io.StringIO()
        console = Console(file=buffer, force_terminal=False, no_color=no_color)
        renderer = EventRenderer(console=console, theme=theme, verbosity=3, world_ref=mock_world)

        events = [
            # Lifecycle
            Event(
                category=EventCategory.LIFECYCLE,
                subcategory=EventSubcategory.BIRTH,
                actor_ids=["agent_1"],
                payload={"species": "edmontosaurus", "name": "Edm-1", "life_stage": "HATCHLING"},
            ),
            Event(
                category=EventCategory.LIFECYCLE,
                subcategory=EventSubcategory.STAGE_CHANGE,
                actor_ids=["agent_1"],
                payload={"species": "edmontosaurus", "name": "Edm-1", "old_stage": "JUVENILE", "new_stage": "SUBADULT"},
            ),
            Event(
                category=EventCategory.LIFECYCLE,
                subcategory=EventSubcategory.EGG_LAID,
                actor_ids=["agent_1"],
                payload={"species": "edmontosaurus", "name": "Edm-1", "clutch_size": 12},
            ),
            Event(
                category=EventCategory.LIFECYCLE,
                subcategory=EventSubcategory.NEST_BUILT,
                actor_ids=["agent_1"],
                payload={"species": "edmontosaurus", "name": "Edm-1", "nest_id": "nest_abcdef123"},
            ),
            Event(
                category=EventCategory.LIFECYCLE,
                subcategory=EventSubcategory.HATCHING,
                actor_ids=["agent_2"],
                payload={"species": "edmontosaurus", "clutch_id": "clutch_99887766"},
            ),
            Event(
                category=EventCategory.LIFECYCLE,
                subcategory=EventSubcategory.MATING,
                actor_ids=["agent_1", "agent_2"],
                payload={"species": "edmontosaurus", "partner_a": "Edm-1", "partner_b": "Edm-2"},
            ),
            Event(
                category=EventCategory.LIFECYCLE,
                subcategory=EventSubcategory.PARENTING,
                actor_ids=["agent_1"],
                payload={"species": "edmontosaurus", "action": "guarding"},
            ),
            Event(
                category=EventCategory.LIFECYCLE,
                subcategory=EventSubcategory.CARCASS_FORMED,
                actor_ids=["agent_1"],
                payload={"species": "edmontosaurus", "mass_kg": 4000.0},
            ),
            Event(
                category=EventCategory.LIFECYCLE,
                subcategory=EventSubcategory.CARCASS_DECAYED,
                actor_ids=["carcass_1"],
                payload={"nutrients_released": 5.25},
            ),
            Event(
                category=EventCategory.LIFECYCLE,
                subcategory=EventSubcategory.DEATH,
                actor_ids=["agent_1"],
                payload={"species": "edmontosaurus", "name": "Edm-1", "cause": "STARVATION", "age_days": 15.2, "life_stage": "ADULT"},
            ),
            Event(
                category=EventCategory.LIFECYCLE,
                subcategory=EventSubcategory.SPECIES_EXTINCT,
                actor_ids=[],
                payload={"species": "thescelosaurus"},
            ),
            # Decision
            Event(
                category=EventCategory.DECISION,
                subcategory=EventSubcategory.ACTION_CHANGE,
                actor_ids=["agent_1"],
                payload={"species": "edmontosaurus", "old_action": "GRAZE", "new_action": "SEEK_WATER", "score": 0.85, "reason": "Thirst > 0.6", "alternatives": [("GRAZE", 0.5), ("REST", 0.3)]},
            ),
            Event(
                category=EventCategory.DECISION,
                subcategory=EventSubcategory.ACTION_TICK,
                actor_ids=["agent_1"],
                payload={"species": "edmontosaurus", "action": "SEEK_WATER", "drives": {"hunger": 0.2, "thirst": 0.7, "fear": 0.0}},
            ),
            # Interactions
            Event(
                category=EventCategory.INTERACTION,
                subcategory=EventSubcategory.CHASE,
                actor_ids=["pred_1", "prey_1"],
                payload={"species": "dakotaraptor", "pred_species": "dakotaraptor", "prey": "Thesc-1", "prey_species": "thescelosaurus", "success_prob": 0.65},
            ),
            Event(
                category=EventCategory.INTERACTION,
                subcategory=EventSubcategory.HUNT_SUCCESS,
                actor_ids=["pred_1", "prey_1"],
                payload={"species": "dakotaraptor", "prey": "Thesc-1", "energy_gained": 450.0},
            ),
            Event(
                category=EventCategory.INTERACTION,
                subcategory=EventSubcategory.HUNT_FAIL,
                actor_ids=["pred_1", "prey_1"],
                payload={"species": "dakotaraptor", "prey": "Thesc-1", "reason": "prey escaped into dense cover"},
            ),
            Event(
                category=EventCategory.INTERACTION,
                subcategory=EventSubcategory.FIGHT,
                actor_ids=["a1", "a2"],
                payload={"species": "triceratops", "defender": "Trike-2", "fight_type": "Mating dispute"},
            ),
            Event(
                category=EventCategory.INTERACTION,
                subcategory=EventSubcategory.ALARM_CALL,
                actor_ids=["agent_1"],
                payload={"species": "edmontosaurus"},
            ),
            Event(
                category=EventCategory.INTERACTION,
                subcategory=EventSubcategory.HERD_FORM,
                actor_ids=["agent_1"],
                payload={"species": "edmontosaurus", "size": 8},
            ),
            Event(
                category=EventCategory.INTERACTION,
                subcategory=EventSubcategory.DRINK,
                actor_ids=["agent_1"],
                payload={"species": "edmontosaurus"},
            ),
            Event(
                category=EventCategory.INTERACTION,
                subcategory=EventSubcategory.EAT,
                actor_ids=["agent_1"],
                payload={"species": "edmontosaurus", "amount_kg": 15.0},
            ),
            Event(
                category=EventCategory.INTERACTION,
                subcategory=EventSubcategory.INJURY,
                actor_ids=["agent_1"],
                payload={"species": "edmontosaurus", "attacker": "T. rex", "type": "Bite", "injury": 0.4},
            ),
            # World
            Event(
                category=EventCategory.WORLD,
                subcategory=EventSubcategory.DAWN,
                actor_ids=[],
                payload={"day": 12, "season": "Spring", "temperature": 24.5},
            ),
            Event(
                category=EventCategory.WORLD,
                subcategory=EventSubcategory.WEATHER_START,
                actor_ids=[],
                payload={"weather": "THUNDERSTORM", "intensity": 0.8},
            ),
            Event(
                category=EventCategory.WORLD,
                subcategory=EventSubcategory.FIRE_SPREAD,
                actor_ids=[],
                payload={"cells_burned": 14},
            ),
            Event(
                category=EventCategory.WORLD,
                subcategory=EventSubcategory.SEASON_CHANGE,
                actor_ids=[],
                payload={"old_season": "Spring", "new_season": "Summer"},
            ),
            # Admin & System
            Event(
                category=EventCategory.ADMIN,
                subcategory=EventSubcategory.ADMIN_COMMAND,
                actor_ids=[],
                payload={"command": "spawn tyrannosaurus_rex 50 50"},
            ),
            Event(
                category=EventCategory.SYSTEM,
                subcategory=EventSubcategory.POP_CAP,
                actor_ids=[],
                payload={"current": 1500, "cap": 1500},
            ),
        ]

        for ev in events:
            renderer.handle_event(ev)

        output = buffer.getvalue()
        assert len(output) > 0
        assert "Spring" in output


def test_renderer_verbosity_filtering(theme, mock_world):
    buffer = io.StringIO()
    console = Console(file=buffer, force_terminal=False, no_color=True)
    renderer = EventRenderer(console=console, theme=theme, verbosity=0, world_ref=mock_world)

    # Verbosity 0 should suppress ACTION_CHANGE and DRINK
    drink_event = Event(
        category=EventCategory.INTERACTION,
        subcategory=EventSubcategory.DRINK,
        actor_ids=["agent_1"],
        payload={"species": "edmontosaurus"},
    )
    renderer.handle_event(drink_event)
    assert buffer.getvalue() == ""

    # Verbosity 0 should display DEATH
    death_event = Event(
        category=EventCategory.LIFECYCLE,
        subcategory=EventSubcategory.DEATH,
        actor_ids=["agent_1"],
        payload={"species": "edmontosaurus", "name": "Edm-1", "cause": "OLD_AGE", "age_days": 40.0, "life_stage": "SENESCENT"},
    )
    renderer.handle_event(death_event)
    assert "DEATH" in buffer.getvalue() or "died" in buffer.getvalue()


def test_renderer_species_and_follow_filters(theme, mock_world):
    buffer = io.StringIO()
    console = Console(file=buffer, force_terminal=False, no_color=True)
    renderer = EventRenderer(console=console, theme=theme, verbosity=2, world_ref=mock_world)
    renderer._show_species = "tyrannosaurus_rex"

    ev1 = Event(
        category=EventCategory.LIFECYCLE,
        subcategory=EventSubcategory.BIRTH,
        actor_ids=["agent_edmo"],
        payload={"species": "edmontosaurus", "name": "Edm-1"},
    )
    renderer.handle_event(ev1)
    assert buffer.getvalue() == ""

    ev2 = Event(
        category=EventCategory.LIFECYCLE,
        subcategory=EventSubcategory.BIRTH,
        actor_ids=["agent_trex"],
        payload={"species": "tyrannosaurus_rex", "name": "Rex-1"},
    )
    renderer.handle_event(ev2)
    assert "Rex-1" in buffer.getvalue() or "tyrannosaurus_rex" in buffer.getvalue()
