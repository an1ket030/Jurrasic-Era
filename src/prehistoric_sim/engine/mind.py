"""
mind.py — Needs-driven utility AI: drives, perception, memory, decision loop.

Every agent runs this module independently each tick. No global knowledge.
All perception is strictly local (vision cone, smell radius, hearing radius).
Decision records store top-3 options and plain-English reasoning for the UI.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from prehistoric_sim.engine.entities import (
    Agent,
    ActivityPattern,
    Carcass,
    DecisionRecord,
    Egg,
    LifeStage,
    MemoryEntry,
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
# Constants
# ---------------------------------------------------------------------------

MEMORY_DECAY_TICKS: int = 200          # memory entries lose strength over this window
MEMORY_MAX_ENTRIES: int = 20           # maximum number of memory entries
COMMITMENT_BONUS: float = 0.15         # score bonus for continuing the current action
DECISION_NOISE: float = 0.05           # random noise added to each utility score


# ---------------------------------------------------------------------------
# Perception
# ---------------------------------------------------------------------------


def perceive(
    agent: Agent,
    world: "World",
    agent_hash: "SpatialHash[Agent]",
    carcass_hash: "SpatialHash[Carcass]",
    nest_hash: "SpatialHash[Nest]",
    all_species_data: dict[str, dict],
    rng: Any,
) -> dict[str, Any]:
    """Gather what this agent can currently sense.

    Returns a dict of perceptual findings used by the scoring functions.
    All queries go through the spatial hash — no O(n) global scans.
    """
    sd = agent._species_data or {}
    x, y = agent.position

    # Vision parameters
    base_vision_range: float = sd.get("vision_range_cells", 15.0)
    fov: float = sd.get("fov_degrees", 220.0)
    # Heading approximated from last movement direction (default east)
    heading: float = 0.0

    night_mod = world.night_vision_penalty if world.is_daytime else world.night_vision_penalty
    vis_mod = world.visibility_mod(x, y)
    # Nocturnal creatures have reversed day/night penalty
    activity = sd.get("activity_pattern", "DIURNAL")
    if activity == ActivityPattern.NOCTURNAL.value:
        night_mod = 1.3 - night_mod  # better at night
    vision_range = base_vision_range * night_mod * vis_mod

    smell_range: float = sd.get("smell_range_cells", 8.0)
    # Wind biases smell (simplified: smell_range slightly directional)
    wind_dir = world.weather.wind_direction
    hearing_range: float = sd.get("hearing_range_cells", 10.0)

    # Query neighbours
    nearby_agents: list[Agent] = agent_hash.query_radius(x, y, max(vision_range, smell_range, hearing_range), exclude=agent)
    nearby_carcasses: list[Carcass] = carcass_hash.query_radius(x, y, smell_range * 1.5)
    nearby_nests: list[Nest] = nest_hash.query_radius(x, y, hearing_range)

    # Classify neighbours
    prey_visible: list[Agent] = []
    predators_visible: list[Agent] = []
    conspecifics: list[Agent] = []
    kin: list[Agent] = []

    diet = sd.get("diet", "HERBIVORE")
    prey_list: list[str] = sd.get("prey_species", [])
    fear_list: list[str] = sd.get("fear_species", [])

    for other in nearby_agents:
        if not other.alive:
            continue
        dx = other.position[0] - x
        dy = other.position[1] - y
        dist = (dx * dx + dy * dy) ** 0.5

        # Check vision cone (for visual detection)
        in_vision = _in_cone(dx, dy, dist, vision_range, heading, fov)
        in_smell = dist <= smell_range
        in_hearing = dist <= hearing_range

        if not (in_vision or in_smell or in_hearing):
            continue

        if other.species_key == agent.species_key:
            conspecifics.append(other)
            if other.id in agent.parent_ids or other.id in agent.offspring_ids or agent.id in other.offspring_ids:
                kin.append(other)
        elif other.species_key in prey_list:
            prey_visible.append(other)
        elif other.species_key in fear_list:
            predators_visible.append(other)

    # Water and food locations
    has_water_nearby = world.is_water(x, y) or world.is_water_edge(x, y)
    if not has_water_nearby:
        for ddx in (-3, -2, -1, 0, 1, 2, 3):
            for ddy in (-3, -2, -1, 0, 1, 2, 3):
                if world.in_bounds(x + ddx, y + ddy) and (
                    world.is_water(x + ddx, y + ddy) or world.is_water_edge(x + ddx, y + ddy)
                ):
                    has_water_nearby = True
                    break

    plant_food_at_pos = world.get_plant_biomass_total(x, y)

    # Find nearest carcass within smell range (scavengers)
    edible_carcasses = [c for c in nearby_carcasses if c.alive and c.mass_remaining > 1.0]

    return {
        "prey_visible": prey_visible,
        "predators_visible": predators_visible,
        "conspecifics": conspecifics,
        "kin": kin,
        "nearby_carcasses": edible_carcasses,
        "nearby_nests": nearby_nests,
        "has_water_nearby": has_water_nearby,
        "plant_food_at_pos": plant_food_at_pos,
        "vision_range": vision_range,
        "smell_range": smell_range,
        "in_fire": agent.position in world.weather.fire_cells,
        "in_flood": agent.position in world.weather.flood_cells,
        "is_daytime": world.is_daytime,
    }


def _in_cone(dx: float, dy: float, dist: float, radius: float, dir_deg: float, fov_deg: float) -> bool:
    if dist > radius:
        return False
    if dist == 0:
        return True
    half_fov = math.radians(fov_deg / 2.0)
    dir_rad = math.radians(dir_deg)
    angle = math.atan2(dy, dx)
    diff = abs((angle - dir_rad + math.pi) % (2 * math.pi) - math.pi)
    return diff <= half_fov


# ---------------------------------------------------------------------------
# Memory update
# ---------------------------------------------------------------------------


def update_memory(agent: Agent, percepts: dict[str, Any], world: "World") -> None:
    """Integrate new perceptions into bounded memory, decay old entries."""
    tick = world.tick

    # Decay existing memories
    still_valid: list[MemoryEntry] = []
    for m in agent.memory:
        age = tick - m.tick_stored
        m.strength = max(0.0, 1.0 - age / MEMORY_DECAY_TICKS)
        if m.strength > 0.01:
            still_valid.append(m)
    agent.memory = still_valid

    # Add new memories from percepts
    def _add_or_update(kind: str, pos: tuple[int, int], detail: str = "") -> None:
        for m in agent.memory:
            if m.kind == kind and m.position == pos:
                m.tick_stored = tick
                m.strength = 1.0
                return
        agent.memory.append(MemoryEntry(kind=kind, position=pos, tick_stored=tick, detail=detail))
        # Trim to max
        if len(agent.memory) > MEMORY_MAX_ENTRIES:
            agent.memory.sort(key=lambda m: m.strength)
            agent.memory = agent.memory[1:]

        if percepts.get("has_water_nearby", False):
            nw = world.nearest_water(*agent.position, max_range=5)
            if nw:
                _add_or_update("water", nw)

        if percepts.get("plant_food_at_pos", 0.0) > 0.3:
            _add_or_update("food", agent.position)

        for pred in percepts.get("predators_visible", []):
            _add_or_update("predator", pred.position, detail=pred.species_key)

    if agent.incubating_nest_id:
        _add_or_update("nest", agent.position)


# ---------------------------------------------------------------------------
# Utility scoring
# ---------------------------------------------------------------------------


def score_actions(
    agent: Agent,
    percepts: dict[str, Any],
    world: "World",
    species_data: dict[str, Any],
    rng: Any,
) -> list[tuple[str, float, str]]:
    """Score all candidate actions. Returns list of (action, score, reason) sorted desc."""
    d = agent.drives
    t = agent.traits
    stage = agent.life_stage
    diet = species_data.get("diet", "HERBIVORE")
    activity = species_data.get("activity_pattern", "DIURNAL")
    sd = species_data

    scores: list[tuple[str, float, str]] = []

    def add(action: str, score: float, reason: str) -> None:
        # Commitment bonus
        if action == agent.current_action:
            score += COMMITMENT_BONUS
        # Small noise
        score += rng.uniform(-DECISION_NOISE, DECISION_NOISE)
        scores.append((action, max(0.0, score), reason))

    # Activity period gating
    active_now = _is_active(activity, world)
    if not active_now:
        add("SLEEP", 0.7 + d.fatigue * 0.3, "outside active hours")

    # --- FLEE (highest priority when threatened) ---
    if percepts["predators_visible"] or percepts["in_fire"] or percepts["in_flood"]:
        threat_score = 0.9
        if percepts["in_fire"]:
            threat_score = 1.0
            reason = "ON FIRE — flee!"
        elif percepts["in_flood"]:
            threat_score = 0.95
            reason = "flooding — flee!"
        else:
            closest = min(percepts["predators_visible"], key=lambda a: a.distance_to(agent))
            dist = agent.distance_to(closest)
            threat_score = max(0.5, 1.0 - dist / 20.0) * (1.0 + t.boldness * -0.3)
            reason = f"{closest.species_key} nearby ({dist:.0f} cells)"
        fear_boost = d.fear * 0.2
        add("FLEE", threat_score + fear_boost, reason)

    # --- DRINK ---
    known_water = next((m for m in agent.memory if m.kind == "water"), None)
    if d.thirst > 0.4 and (percepts["has_water_nearby"] or known_water):
        score = d.thirst * 0.9
        reason = "thirsty" + (" — water nearby" if percepts["has_water_nearby"] else " — remember water")
        add("DRINK", score, reason)

    # --- GRAZE / BROWSE (herbivores and omnivores) ---
    if diet in ("HERBIVORE", "OMNIVORE") and stage not in (LifeStage.HATCHLING,):
        food = percepts["plant_food_at_pos"]
        score = d.hunger * 0.85 * max(0.1, food)
        add("GRAZE", score, f"hunger {d.hunger:.2f}, plant biomass {food:.2f}")

    # --- HUNT (carnivores and omnivores with prey visible) ---
    if diet in ("CARNIVORE", "OMNIVORE", "PISCIVORE") and stage not in (LifeStage.HATCHLING,):
        if percepts["prey_visible"]:
            best_prey = _pick_best_prey(agent, percepts["prey_visible"], sd)
            if best_prey:
                dist = agent.distance_to(best_prey)
                size_ratio = best_prey.body_mass_kg / max(1.0, agent.body_mass_kg)
                feasibility = max(0.0, 1.0 - size_ratio * 0.5) * (1.0 - dist / 40.0)
                score = d.hunger * 0.9 * feasibility
                add("HUNT", score, f"hunger {d.hunger:.2f}, {best_prey.display_name} {dist:.0f} cells away")

    # --- SCAVENGE ---
    if diet in ("CARNIVORE", "OMNIVORE") and percepts["nearby_carcasses"]:
        c = percepts["nearby_carcasses"][0]
        dist = ((c.position[0] - agent.position[0]) ** 2 + (c.position[1] - agent.position[1]) ** 2) ** 0.5
        score = d.hunger * 0.7 * (1.0 - dist / 20.0)
        add("SCAVENGE", score, f"carcass {dist:.0f} cells away")

    # --- SOCIAL: FOLLOW / LEAD ---
    if d.social_need > 0.3 and percepts["conspecifics"]:
        sociability_boost = t.sociability
        score = d.social_need * 0.6 * sociability_boost
        add("FOLLOW", score, f"social need {d.social_need:.2f}")

    # --- MATE ---
    if d.reproductive_urge > 0.5 and agent.is_adult_capable and percepts["conspecifics"]:
        eligible = [a for a in percepts["conspecifics"] if a.is_adult_capable and a.id != agent.id]
        if eligible:
            score = d.reproductive_urge * 0.85
            add("MATE", score, f"reproductive urge {d.reproductive_urge:.2f}")

    # --- GUARD NEST ---
    if agent.incubating_nest_id and d.parental_drive > 0.5:
        score = d.parental_drive * 0.9
        add("GUARD_NEST", score, "nest needs guarding")

    # --- GUARD OFFSPRING ---
    if agent.offspring_ids and d.parental_drive > 0.4:
        score = d.parental_drive * 0.7
        add("GUARD_OFFSPRING", score, "offspring nearby")

    # --- REST ---
    if d.fatigue > 0.5 or agent.stamina < 0.2:
        score = d.fatigue * 0.75 + (1.0 - agent.stamina) * 0.25
        add("REST", score, f"fatigue {d.fatigue:.2f}, stamina {agent.stamina:.2f}")

    # --- WANDER (fallback) ---
    curiosity_score = d.curiosity * t.curiosity * 0.4
    add("WANDER", max(0.1, curiosity_score), "exploring")

    scores.sort(key=lambda x: x[1], reverse=True)
    return scores


def _is_active(activity: str, world: "World") -> bool:
    """Return True if it is the creature's active period."""
    if activity == ActivityPattern.CONTINUOUS.value:
        return True
    if activity == ActivityPattern.DIURNAL.value:
        return world.is_daytime
    if activity == ActivityPattern.NOCTURNAL.value:
        return not world.is_daytime
    if activity == ActivityPattern.CREPUSCULAR.value:
        return world.is_dawn_or_dusk
    return True


def _pick_best_prey(
    agent: Agent,
    prey_visible: list["Agent"],
    species_data: dict[str, Any],
) -> "Agent | None":
    """Pick the most attractive prey target."""
    if not prey_visible:
        return None
    # Prefer weakest, closest
    def score(p: Agent) -> float:
        dist = agent.distance_to(p)
        weakness = 1.0 - p.health
        return (1.0 - dist / 50.0) + weakness * 0.3
    return max(prey_visible, key=score)


# ---------------------------------------------------------------------------
# Main decision function
# ---------------------------------------------------------------------------


def decide(
    agent: Agent,
    percepts: dict[str, Any],
    world: "World",
    species_data: dict[str, Any],
    event_bus: EventBus,
    rng: Any,
) -> None:
    """Run the full utility decision loop for one agent for one tick.

    1. Score all candidate actions.
    2. Pick the top action.
    3. If action changed, emit ACTION_CHANGE event.
    4. For tracked agents, emit ACTION_TICK every tick.
    5. Update drives after decision.
    """
    # Forced action overrides
    if agent.forced_action and agent.forced_action_ticks > 0:
        agent.forced_action_ticks -= 1
        if agent.forced_action_ticks <= 0:
            agent.forced_action = None
        else:
            return  # skip normal decision

    if agent.possessed:
        return  # admin is driving; skip AI

    scored = score_actions(agent, percepts, world, species_data, rng)

    if not scored:
        scored = [("WANDER", 0.1, "nothing to do")]

    top_action, top_score, top_reason = scored[0]
    alternatives = [(a, s) for a, s, _ in scored[1:3]]

    old_action = agent.current_action
    action_changed = top_action != old_action

    if action_changed:
        agent.current_action = top_action
        agent.action_ticks_committed = 0

        # Build reason string
        alt_str = " | ".join(f"{a} ({s:.2f})" for a, s in alternatives)
        reason_str = f"{top_reason}"

        dr = DecisionRecord(
            tick=world.tick,
            action=top_action,
            score=top_score,
            alternatives=alternatives,
            reason=reason_str,
        )
        agent.last_decision = dr

        event_bus.emit(Event(
            tick=world.tick,
            category=EventCategory.DECISION,
            subcategory=EventSubcategory.ACTION_CHANGE,
            actor_ids=[agent.id],
            position=agent.position,
            payload={
                "name": agent.display_name,
                "species": agent.species_key,
                "old_action": old_action,
                "new_action": top_action,
                "score": round(top_score, 3),
                "alternatives": [(a, round(s, 3)) for a, s in alternatives],
                "reason": reason_str,
            },
        ))
    else:
        agent.action_ticks_committed += 1

    # Verbose output for tracked creatures (every tick)
    if agent.tracked:
        event_bus.emit(Event(
            tick=world.tick,
            category=EventCategory.DECISION,
            subcategory=EventSubcategory.ACTION_TICK,
            actor_ids=[agent.id],
            position=agent.position,
            payload={
                "name": agent.display_name,
                "species": agent.species_key,
                "action": top_action,
                "score": round(top_score, 3),
                "alternatives": [(a, round(s, 3)) for a, s in alternatives],
                "drives": {
                    "hunger": round(agent.drives.hunger, 2),
                    "thirst": round(agent.drives.thirst, 2),
                    "fatigue": round(agent.drives.fatigue, 2),
                    "fear": round(agent.drives.fear, 2),
                },
            },
        ))

    # Update fear drive based on percepts
    if percepts["predators_visible"]:
        agent.drives.fear = min(1.0, agent.drives.fear + 0.15)
    else:
        agent.drives.fear = max(0.0, agent.drives.fear - 0.05)

    # Update social need
    if percepts["conspecifics"]:
        agent.drives.social_need = max(0.0, agent.drives.social_need - 0.03)
    else:
        agent.drives.social_need = min(1.0, agent.drives.social_need + 0.01)

    # Update parental drive
    if agent.offspring_ids or agent.incubating_nest_id:
        agent.drives.parental_drive = min(1.0, agent.drives.parental_drive + 0.02)
    else:
        agent.drives.parental_drive = max(0.0, agent.drives.parental_drive - 0.01)

    # Update reproductive urge
    if (
        agent.is_adult_capable
        and not agent.pregnant
        and getattr(agent, "reproduction_cooldown_ticks", 0) <= 0
    ):
        from prehistoric_sim.engine.reproduction import is_breeding_season  # noqa: PLC0415
        if is_breeding_season(species_data, world.season) and agent.energy > 0.45:
            agent.drives.reproductive_urge = min(1.0, agent.drives.reproductive_urge + 0.003)
        else:
            agent.drives.reproductive_urge = max(0.0, agent.drives.reproductive_urge - 0.01)
    else:
        agent.drives.reproductive_urge = max(0.0, agent.drives.reproductive_urge - 0.05)
