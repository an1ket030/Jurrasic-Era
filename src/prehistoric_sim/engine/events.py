"""
events.py — Event bus and all engine-side event dataclasses.

The engine emits events; everything outside (UI, IO, admin) consumes them.
The engine never imports from ui, admin, io, or cli.
"""

from __future__ import annotations

import dataclasses
from collections import defaultdict
from enum import Enum, auto
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Event categories
# ---------------------------------------------------------------------------


class EventCategory(str, Enum):
    LIFECYCLE = "LIFECYCLE"
    DECISION = "DECISION"
    INTERACTION = "INTERACTION"
    WORLD = "WORLD"
    ADMIN = "ADMIN"
    SYSTEM = "SYSTEM"


class EventSubcategory(str, Enum):
    # Lifecycle
    CONCEPTION = "CONCEPTION"
    EGG_LAID = "EGG_LAID"
    NEST_BUILT = "NEST_BUILT"
    HATCHING = "HATCHING"
    BIRTH = "BIRTH"
    STAGE_CHANGE = "STAGE_CHANGE"
    MATING = "MATING"
    PARENTING = "PARENTING"
    DEATH = "DEATH"
    CARCASS_FORMED = "CARCASS_FORMED"
    CARCASS_DECAYED = "CARCASS_DECAYED"
    # Decision
    ACTION_CHANGE = "ACTION_CHANGE"
    ACTION_TICK = "ACTION_TICK"  # verbose/tracked only
    # Interaction
    STALK = "STALK"
    CHASE = "CHASE"
    HUNT_SUCCESS = "HUNT_SUCCESS"
    HUNT_FAIL = "HUNT_FAIL"
    FIGHT = "FIGHT"
    FLEE = "FLEE"
    ALARM_CALL = "ALARM_CALL"
    HERD_FORM = "HERD_FORM"
    HERD_SPLIT = "HERD_SPLIT"
    SCAVENGE = "SCAVENGE"
    EAT = "EAT"
    DRINK = "DRINK"
    SLEEP = "SLEEP"
    MATE_DISPLAY = "MATE_DISPLAY"
    EGG_RAID = "EGG_RAID"
    INJURY = "INJURY"
    HEAL = "HEAL"
    POSSESSION_START = "POSSESSION_START"
    POSSESSION_END = "POSSESSION_END"
    # World
    DAWN = "DAWN"
    DUSK = "DUSK"
    DAY_START = "DAY_START"
    SEASON_CHANGE = "SEASON_CHANGE"
    WEATHER_START = "WEATHER_START"
    WEATHER_END = "WEATHER_END"
    FIRE_SPREAD = "FIRE_SPREAD"
    FLOOD_EXPAND = "FLOOD_EXPAND"
    PLANT_REGROWTH = "PLANT_REGROWTH"
    WATER_LEVEL = "WATER_LEVEL"
    NUTRIENT_BOOST = "NUTRIENT_BOOST"
    MIGRATION_WAVE = "MIGRATION_WAVE"
    # Admin
    ADMIN_COMMAND = "ADMIN_COMMAND"
    # System
    POP_CAP = "POP_CAP"
    SPECIES_EXTINCT = "SPECIES_EXTINCT"
    SPECIES_REINTRODUCED = "SPECIES_REINTRODUCED"
    SNAPSHOT_SAVED = "SNAPSHOT_SAVED"
    SNAPSHOT_LOADED = "SNAPSHOT_LOADED"


# ---------------------------------------------------------------------------
# Base Event
# ---------------------------------------------------------------------------


@dataclasses.dataclass(slots=True)
class Event:
    """A single simulation event.

    Attributes:
        tick:        Simulation tick when the event occurred.
        category:    High-level event category.
        subcategory: Specific event type.
        actor_ids:   List of entity IDs involved (first is primary).
        position:    (x, y) grid position of the event, or None.
        payload:     Arbitrary key→value data specific to this event type.
    """

    category: EventCategory
    subcategory: EventSubcategory
    tick: int = 0
    actor_ids: list[str] = dataclasses.field(default_factory=list)
    position: tuple[int, int] | None = None
    payload: dict[str, Any] = dataclasses.field(default_factory=dict)


# ---------------------------------------------------------------------------
# Event Bus
# ---------------------------------------------------------------------------

Handler = Callable[[Event], None]


class EventBus:
    """Publish-subscribe event bus for the simulation engine.

    The engine emits events; subscribers (UI, IO, admin) receive them.
    Subscription is by category (all subtypes) or by exact subcategory.
    """

    def __init__(self) -> None:
        self._category_handlers: dict[EventCategory, list[Handler]] = defaultdict(list)
        self._subcategory_handlers: dict[EventSubcategory, list[Handler]] = defaultdict(list)
        self._wildcard_handlers: list[Handler] = []
        self._history: list[Event] = []
        self._record_history: bool = True
        self._actor_history: dict[str, list[Event]] = defaultdict(list)

    # ------------------------------------------------------------------
    # Subscription
    # ------------------------------------------------------------------

    def subscribe(self, handler: Handler) -> None:
        """Subscribe to ALL events."""
        self._wildcard_handlers.append(handler)

    def subscribe_category(self, category: EventCategory, handler: Handler) -> None:
        """Subscribe to all events of a given category."""
        self._category_handlers[category].append(handler)

    def subscribe_subcategory(self, subcategory: EventSubcategory, handler: Handler) -> None:
        """Subscribe to events of an exact subcategory."""
        self._subcategory_handlers[subcategory].append(handler)

    def unsubscribe(self, handler: Handler) -> None:
        """Remove a handler from wildcard subscriptions."""
        if handler in self._wildcard_handlers:
            self._wildcard_handlers.remove(handler)

    # ------------------------------------------------------------------
    # Emission
    # ------------------------------------------------------------------

    def emit(self, event: Event) -> None:
        """Publish an event to all registered handlers."""
        if self._record_history:
            self._history.append(event)
            for aid in event.actor_ids:
                self._actor_history[aid].append(event)

        # Call handlers (category first, then subcategory, then wildcard)
        for h in self._category_handlers.get(event.category, []):
            h(event)
        for h in self._subcategory_handlers.get(event.subcategory, []):
            h(event)
        for h in self._wildcard_handlers:
            h(event)

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def actor_events(self, actor_id: str) -> list[Event]:
        """Return all events for a specific entity ID (life story)."""
        return list(self._actor_history.get(actor_id, []))

    def all_events(self) -> list[Event]:
        """Return full event history."""
        return list(self._history)

    def clear_history(self) -> None:
        """Clear stored history (for memory management in long runs)."""
        self._history.clear()
        self._actor_history.clear()
