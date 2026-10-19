"""
behaviors.py — Action implementations for all creature behaviors.

Each behavior function receives the agent, world, percepts, and simulation state.
It modifies agent position/state and emits interaction events.
All movement is through this module — never directly modifying position elsewhere.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from prehistoric_sim.engine.entities import (
    Agent,
    Carcass,
    LifeStage,
    Nest,
)
from prehistoric_sim.engine.events import (
    Event,
    EventBus,
    EventCategory,
    EventSubcategory,
)

if TYPE_CHECKING:
    from prehistoric_sim.engine.spatial import SpatialHash
    from prehistoric_sim.engine.world import World

# ---------------------------------------------------------------------------
# Movement helpers
# ---------------------------------------------------------------------------


def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


def _move_toward(
    agent: Agent,
    tx: int,
    ty: int,
    world: "World",
    speed_override: float | None = None,
) -> None:
    """Move agent one step toward target (tx, ty), respecting terrain cost."""
    x, y = agent.position
    if x == tx and y == ty:
        return

    dx = tx - x
    dy = ty - y
    dist = (dx * dx + dy * dy) ** 0.5
    if dist == 0:
        return

    speed = speed_override if speed_override is not None else agent.effective_speed
    step = min(dist, speed)

    nx = x + dx / dist * step
    ny = y + dy / dist * step
    nx_int = int(round(_clamp(nx, 0, world.width - 1)))
    ny_int = int(round(_clamp(ny, 0, world.height - 1)))

    # Apply terrain movement cost
    cost = world.move_cost(nx_int, ny_int)
    if cost > 5.0:
        # Avoid impassable terrain (lakes) unless aquatic
        return

    agent.position = (nx_int, ny_int)


def _move_random(agent: Agent, world: "World", rng: Any) -> None:
    """Move agent one step in a random direction."""
    x, y = agent.position
    directions = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)]
    rng.shuffle(directions)
    for dx, dy in directions:
        nx, ny = x + dx, y + dy
        if world.in_bounds(nx, ny) and world.move_cost(nx, ny) < 5.0:
            agent.position = (nx, ny)
            return


def _move_away(agent: Agent, tx: int, ty: int, world: "World", rng: Any) -> None:
    """Move agent away from (tx, ty)."""
    x, y = agent.position
    dx = x - tx
    dy = y - ty
    dist = (dx * dx + dy * dy) ** 0.5 or 1.0
    step = agent.effective_speed
    nx = int(round(_clamp(x + dx / dist * step, 0, world.width - 1)))
    ny = int(round(_clamp(y + dy / dist * step, 0, world.height - 1)))
    if world.move_cost(nx, ny) < 5.0:
        agent.position = (nx, ny)
    else:
        _move_random(agent, world, rng)


# ---------------------------------------------------------------------------
# REST / SLEEP
# ---------------------------------------------------------------------------


def do_rest(agent: Agent, world: "World", event_bus: EventBus, rng: Any) -> None:
    """Agent rests in place. Stamina and energy recover."""
    # Stamina recovery handled in metabolism; behavior just keeps agent still
    pass


def do_sleep(agent: Agent, world: "World", event_bus: EventBus, rng: Any) -> None:
    """Agent sleeps (outside active hours). Full rest bonus."""
    if rng.chance(0.05):  # very occasionally emit sleep event
        event_bus.emit(Event(
            tick=world.tick,
            category=EventCategory.INTERACTION,
            subcategory=EventSubcategory.SLEEP,
            actor_ids=[agent.id],
            position=agent.position,
            payload={"species": agent.species_key, "name": agent.display_name},
        ))


# ---------------------------------------------------------------------------
# WANDER
# ---------------------------------------------------------------------------


def do_wander(agent: Agent, world: "World", event_bus: EventBus, rng: Any) -> None:
    """Random walk with a preference for known food patches."""
    # Prefer moving toward remembered food if hungry
    if agent.drives.hunger > 0.5:
        food_mem = next((m for m in agent.memory if m.kind == "food" and m.strength > 0.3), None)
        if food_mem:
            _move_toward(agent, food_mem.position[0], food_mem.position[1], world)
            return
    _move_random(agent, world, rng)


# ---------------------------------------------------------------------------
# GRAZE / BROWSE
# ---------------------------------------------------------------------------


def do_graze(
    agent: Agent,
    world: "World",
    event_bus: EventBus,
    species_data: dict[str, Any],
    rng: Any,
) -> None:
    """Herbivore eats plant biomass at current position."""
    x, y = agent.position
    diet_layers: list[int] = species_data.get("preferred_plant_layers", [0, 1])
    bite_size: float = agent.body_mass_kg * 0.0001  # scales with body mass

    total_eaten = 0.0
    for layer in diet_layers:
        consumed = world.consume_plant(x, y, layer, bite_size)
        total_eaten += consumed

    if total_eaten > 0.0:
        # Restore energy proportional to consumption
        energy_gain = min(1.0 - agent.energy, total_eaten * 0.6 + 0.06)
        agent.energy = min(1.0, agent.energy + energy_gain)
        agent.drives.hunger = 1.0 - agent.energy
    else:
        # No food here — try to move to remembered food or wander
        food_mem = next((m for m in agent.memory if m.kind == "food"), None)
        if food_mem and food_mem.position != agent.position:
            _move_toward(agent, food_mem.position[0], food_mem.position[1], world)
        else:
            _move_random(agent, world, rng)


# ---------------------------------------------------------------------------
# DRINK
# ---------------------------------------------------------------------------


def do_drink(
    agent: Agent,
    world: "World",
    event_bus: EventBus,
    rng: Any,
) -> None:
    """Agent drinks from water source."""
    x, y = agent.position
    has_water = world.is_water(x, y) or world.is_water_edge(x, y)

    if has_water:
        drink_amount = min(1.0 - agent.hydration, 0.4)
        agent.hydration = min(1.0, agent.hydration + drink_amount)
        agent.drives.thirst = 1.0 - agent.hydration
        if rng.chance(0.1):
            event_bus.emit(Event(
                tick=world.tick,
                category=EventCategory.INTERACTION,
                subcategory=EventSubcategory.DRINK,
                actor_ids=[agent.id],
                position=agent.position,
                payload={"species": agent.species_key, "name": agent.display_name},
            ))
    else:
        # Move toward water
        water_mem = next((m for m in agent.memory if m.kind == "water"), None)
        if water_mem:
            _move_toward(agent, water_mem.position[0], water_mem.position[1], world)
        else:
            nw = world.nearest_water(x, y)
            if nw:
                _move_toward(agent, nw[0], nw[1], world)
            else:
                _move_random(agent, world, rng)


# ---------------------------------------------------------------------------
# FLEE
# ---------------------------------------------------------------------------


def do_flee(
    agent: Agent,
    percepts: dict[str, Any],
    world: "World",
    event_bus: EventBus,
    rng: Any,
) -> None:
    """Agent flees from the nearest threat at full speed."""
    fire_cells = world.weather.fire_cells
    flood_cells = world.weather.flood_cells
    x, y = agent.position

    # Priority: fire, flood, then predators
    if agent.position in fire_cells:
        # Move away from nearest fire cell (or any direction)
        _move_away(agent, x, y, world, rng)
        return

    if agent.position in flood_cells:
        # Move to highest ground
        _move_random(agent, world, rng)
        return

    predators = percepts.get("predators_visible", [])
    if predators:
        closest = min(predators, key=lambda a: agent.distance_to(a))
        tx, ty = closest.position
        _move_away(agent, tx, ty, world, rng)
        # Emit alarm call occasionally
        if rng.chance(0.15):
            _alarm_call(agent, world, event_bus)

    agent.drives.fear = min(1.0, agent.drives.fear + 0.05)


def _alarm_call(agent: Agent, world: "World", event_bus: EventBus) -> None:
    event_bus.emit(Event(
        tick=world.tick,
        category=EventCategory.INTERACTION,
        subcategory=EventSubcategory.ALARM_CALL,
        actor_ids=[agent.id],
        position=agent.position,
        payload={"species": agent.species_key, "name": agent.display_name},
    ))


# ---------------------------------------------------------------------------
# HIDE
# ---------------------------------------------------------------------------


def do_hide(agent: Agent, world: "World", event_bus: EventBus, rng: Any) -> None:
    """Agent seeks dense vegetation for cover."""
    x, y = agent.position
    best_pos = (x, y)
    best_cover = world.get_plant_biomass_total(x, y)
    for dx in range(-3, 4):
        for dy in range(-3, 4):
            nx, ny = x + dx, y + dy
            if world.in_bounds(nx, ny):
                cover = world.get_plant_biomass_total(nx, ny)
                if cover > best_cover:
                    best_cover = cover
                    best_pos = (nx, ny)
    if best_pos != (x, y):
        _move_toward(agent, best_pos[0], best_pos[1], world)


# ---------------------------------------------------------------------------
# FOLLOW (group cohesion/separation/alignment)
# ---------------------------------------------------------------------------


def do_follow(
    agent: Agent,
    percepts: dict[str, Any],
    world: "World",
    event_bus: EventBus,
    rng: Any,
) -> None:
    """Emergent herding: cohesion toward conspecifics, separation at close range."""
    conspecifics = percepts.get("conspecifics", [])
    if not conspecifics:
        _move_random(agent, world, rng)
        return

    x, y = agent.position
    # Compute centroid of nearby conspecifics
    cx = sum(a.position[0] for a in conspecifics) / len(conspecifics)
    cy = sum(a.position[1] for a in conspecifics) / len(conspecifics)

    # Separation: if too close to any, move away
    too_close = [a for a in conspecifics if agent.distance_to(a) < 2.0]
    if too_close:
        for other in too_close:
            _move_away(agent, other.position[0], other.position[1], world, rng)
        return

    # Cohesion: move toward centroid
    _move_toward(agent, int(cx), int(cy), world)


# ---------------------------------------------------------------------------
# SCAVENGE / EAT
# ---------------------------------------------------------------------------


def do_scavenge(
    agent: Agent,
    percepts: dict[str, Any],
    world: "World",
    event_bus: EventBus,
    rng: Any,
) -> None:
    """Move toward nearest carcass."""
    carcasses = percepts.get("nearby_carcasses", [])
    if not carcasses:
        _move_random(agent, world, rng)
        return
    target = min(carcasses, key=lambda c: agent.distance_to(c))
    _move_toward(agent, target.position[0], target.position[1], world)
    event_bus.emit(Event(
        tick=world.tick,
        category=EventCategory.INTERACTION,
        subcategory=EventSubcategory.SCAVENGE,
        actor_ids=[agent.id],
        position=agent.position,
        payload={
            "species": agent.species_key,
            "name": agent.display_name,
            "target_id": target.id,
        },
    ))


def do_eat_carcass(
    agent: Agent,
    carcass: Carcass,
    world: "World",
    event_bus: EventBus,
    rng: Any,
) -> None:
    """Eat from a carcass at agent's position."""
    if not carcass.alive or carcass.mass_remaining <= 0:
        return
    bite = min(carcass.mass_remaining, agent.body_mass_kg * 0.05)
    carcass.mass_remaining -= bite
    energy_gain = bite * 0.002 / max(0.1, agent.body_mass_kg * 0.001)
    agent.energy = min(1.0, agent.energy + energy_gain)
    agent.drives.hunger = 1.0 - agent.energy
    if agent.id not in carcass.scavengers_feeding:
        carcass.scavengers_feeding.append(agent.id)
    if rng.chance(0.2):
        event_bus.emit(Event(
            tick=world.tick,
            category=EventCategory.INTERACTION,
            subcategory=EventSubcategory.EAT,
            actor_ids=[agent.id],
            position=agent.position,
            payload={
                "species": agent.species_key,
                "name": agent.display_name,
                "carcass_id": carcass.id,
                "amount_kg": round(bite, 2),
            },
        ))


# ---------------------------------------------------------------------------
# GUARD NEST
# ---------------------------------------------------------------------------


def do_guard_nest(
    agent: Agent,
    nest: Nest | None,
    world: "World",
    event_bus: EventBus,
    rng: Any,
) -> None:
    """Agent moves to and guards its nest."""
    if nest is None:
        return
    _move_toward(agent, nest.position[0], nest.position[1], world)
    nest.guarded = True
    if rng.chance(0.02):
        event_bus.emit(Event(
            tick=world.tick,
            category=EventCategory.LIFECYCLE,
            subcategory=EventSubcategory.PARENTING,
            actor_ids=[agent.id],
            position=agent.position,
            payload={"name": agent.display_name, "action": "guarding nest"},
        ))


# ---------------------------------------------------------------------------
# MIGRATE
# ---------------------------------------------------------------------------


def do_migrate(
    agent: Agent,
    world: "World",
    event_bus: EventBus,
    rng: Any,
    direction: tuple[int, int] | None = None,
) -> None:
    """Agent moves in a preferred migration direction."""
    if direction is None:
        # Default: move toward centre of map (as a simple seasonal migration target)
        tx, ty = world.width // 2, world.height // 2
    else:
        tx, ty = direction
    _move_toward(agent, tx, ty, world)
