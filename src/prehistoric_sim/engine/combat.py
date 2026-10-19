"""
combat.py — Hunting, fighting, and injury resolution.

Hunt success depends on speed ratio, stamina, terrain, prey group size,
prey vigilance, predator size, and random chance.
Injuries slow creatures and cost extra energy until healed.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from prehistoric_sim.engine.entities import Agent, Carcass, LifeStage
from prehistoric_sim.engine.events import (
    Event,
    EventBus,
    EventCategory,
    EventSubcategory,
)
from prehistoric_sim.engine.lifecycle import create_carcass, kill_agent

if TYPE_CHECKING:
    from prehistoric_sim.engine.world import World

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CHASE_STAMINA_COST: float = 0.04     # stamina drained per tick of chasing
ABANDON_THRESHOLD: float = 0.15      # predator gives up when stamina < this
MIN_KILL_ENERGY_GAIN: float = 0.1    # minimum benefit from a successful hunt

# ---------------------------------------------------------------------------
# Hunt resolution
# ---------------------------------------------------------------------------


def attempt_hunt(
    predator: Agent,
    prey: Agent,
    world: "World",
    event_bus: EventBus,
    species_data: dict[str, dict],
    rng: Any,
) -> Carcass | None:
    """Resolve a single hunt attempt.

    Returns a Carcass if the prey was killed, None otherwise.
    Also handles injury to the predator if prey fights back.
    """
    if not predator.alive or not prey.alive:
        return None

    pred_sd = species_data.get(predator.species_key, {})
    prey_sd = species_data.get(prey.species_key, {})

    # --- Speed advantage ---
    speed_ratio = predator.effective_speed / max(0.1, prey.effective_speed)
    speed_factor = _sigmoid(speed_ratio - 1.0, steepness=2.0)  # ~0.5 if equal

    # --- Size factor (can predator overpower prey?) ---
    mass_ratio = predator.body_mass_kg / max(1.0, prey.body_mass_kg)
    size_factor = _sigmoid(math.log(max(0.01, mass_ratio)), steepness=1.5)

    # --- Predator stamina ---
    stamina_factor = predator.stamina

    # --- Prey group defense ---
    # Approximated by counting nearby conspecifics of prey (passed via prey's group size)
    # Simplified: if prey has group members, reduce success
    # (Full group detection happens in mind.py; here we just apply a penalty if prey has social need low = in a group)
    group_factor = 1.0
    if prey.drives.social_need < 0.3:
        group_factor = 0.7  # in a group; harder to catch

    # --- Prey vigilance (low fear = easier target) ---
    vigilance = max(0.1, 1.0 - prey.drives.fear)
    vigilance_factor = 1.0 - vigilance * 0.4

    # --- Terrain effect (forest favors ambush predators) ---
    terrain_factor = 1.0
    pred_style: str = pred_sd.get("hunt_style", "pursuit")
    from prehistoric_sim.engine.entities import TerrainType  # noqa: PLC0415
    from prehistoric_sim.engine.world import TERRAIN_VISIBILITY  # noqa: PLC0415
    t = world.terrain_at(*predator.position)
    vis = TERRAIN_VISIBILITY.get(t, 1.0)
    if pred_style == "ambush":
        terrain_factor = 1.0 + (1.0 - vis) * 0.5  # ambush in cover
    else:
        terrain_factor = 0.7 + vis * 0.3  # pursuit in open

    # --- Prey life stage penalty (hatchlings/juveniles easier) ---
    stage_factor = 1.0
    if prey.life_stage == LifeStage.HATCHLING:
        stage_factor = 2.0
    elif prey.life_stage == LifeStage.JUVENILE:
        stage_factor = 1.4
    elif prey.life_stage == LifeStage.SENESCENT:
        stage_factor = 1.3

    # --- Composite success probability ---
    base_prob = (
        speed_factor * 0.25
        + size_factor * 0.25
        + stamina_factor * 0.15
        + terrain_factor * 0.15
        + vigilance_factor * 0.1
        + stage_factor * 0.1
    ) * group_factor

    base_prob = max(0.02, min(0.95, base_prob))

    # --- Emit chase / stalk event ---
    dist = predator.distance_to(prey)
    if dist > 5:
        event_bus.emit(Event(
            tick=world.tick,
            category=EventCategory.INTERACTION,
            subcategory=EventSubcategory.CHASE,
            actor_ids=[predator.id, prey.id],
            position=predator.position,
            payload={
                "predator": predator.display_name,
                "prey": prey.display_name,
                "pred_species": predator.species_key,
                "prey_species": prey.species_key,
                "success_prob": round(base_prob, 2),
            },
        ))
    else:
        event_bus.emit(Event(
            tick=world.tick,
            category=EventCategory.INTERACTION,
            subcategory=EventSubcategory.STALK,
            actor_ids=[predator.id, prey.id],
            position=predator.position,
            payload={
                "predator": predator.display_name,
                "prey": prey.display_name,
                "pred_species": predator.species_key,
                "prey_species": prey.species_key,
            },
        ))

    # Drain stamina from chasing
    predator.stamina = max(0.0, predator.stamina - CHASE_STAMINA_COST)

    # Abandon if too tired
    if predator.stamina < ABANDON_THRESHOLD:
        event_bus.emit(Event(
            tick=world.tick,
            category=EventCategory.INTERACTION,
            subcategory=EventSubcategory.HUNT_FAIL,
            actor_ids=[predator.id, prey.id],
            position=predator.position,
            payload={
                "predator": predator.display_name,
                "prey": prey.display_name,
                "reason": "predator exhausted",
            },
        ))
        return None

    # --- Roll ---
    if rng.chance(base_prob):
        # Kill successful
        _apply_prey_defense(predator, prey, pred_sd, prey_sd, world, event_bus, rng)
        kill_agent(prey, f"predation:{predator.species_key}", world, event_bus)
        carcass = create_carcass(prey, world, event_bus)

        # Predator eats immediately (partial)
        feed_amount = min(carcass.mass_remaining, predator.body_mass_kg * 0.15)
        carcass.mass_remaining -= feed_amount
        energy_gain = feed_amount * 0.003
        predator.energy = min(1.0, predator.energy + energy_gain)
        predator.drives.hunger = 1.0 - predator.energy

        event_bus.emit(Event(
            tick=world.tick,
            category=EventCategory.INTERACTION,
            subcategory=EventSubcategory.HUNT_SUCCESS,
            actor_ids=[predator.id, prey.id],
            position=predator.position,
            payload={
                "predator": predator.display_name,
                "prey": prey.display_name,
                "pred_species": predator.species_key,
                "prey_species": prey.species_key,
                "carcass_id": carcass.id,
                "energy_gained": round(energy_gain, 3),
            },
        ))
        return carcass
    else:
        # Hunt failed
        _apply_prey_defense(predator, prey, pred_sd, prey_sd, world, event_bus, rng)
        event_bus.emit(Event(
            tick=world.tick,
            category=EventCategory.INTERACTION,
            subcategory=EventSubcategory.HUNT_FAIL,
            actor_ids=[predator.id, prey.id],
            position=predator.position,
            payload={
                "predator": predator.display_name,
                "prey": prey.display_name,
                "reason": "prey escaped",
            },
        ))
        # Prey flees
        prey.drives.fear = min(1.0, prey.drives.fear + 0.4)
        prey.current_action = "FLEE"
        return None


def resolve_prey_defenses(
    predator: Agent,
    prey: Agent,
    prey_sd: dict,
    world: "World",
    event_bus: EventBus,
    rng: Any,
) -> None:
    """Public function to resolve defensive counter-attacks from prey."""
    _apply_prey_defense(predator, prey, {}, prey_sd, world, event_bus, rng)


def _apply_prey_defense(
    predator: Agent,
    prey: Agent,
    pred_sd: dict,
    prey_sd: dict,
    world: "World",
    event_bus: EventBus,
    rng: Any,
) -> None:
    """Apply defensive counter-attacks from prey (Ankylosaurus tail, Triceratops charge)."""
    prey_defense: str = prey_sd.get("defense_type", "none")

    if prey_defense == "tail_club" and rng.chance(0.4):
        injury = rng.uniform(0.1, 0.4)
        predator.injury_level = min(1.0, predator.injury_level + injury)
        event_bus.emit(Event(
            tick=world.tick,
            category=EventCategory.INTERACTION,
            subcategory=EventSubcategory.INJURY,
            actor_ids=[predator.id, prey.id],
            position=predator.position,
            payload={
                "victim": predator.display_name,
                "attacker": prey.display_name,
                "type": "tail_club",
                "injury": round(injury, 2),
            },
        ))
    elif prey_defense == "charge" and rng.chance(0.3):
        injury = rng.uniform(0.05, 0.25)
        predator.injury_level = min(1.0, predator.injury_level + injury)
        event_bus.emit(Event(
            tick=world.tick,
            category=EventCategory.INTERACTION,
            subcategory=EventSubcategory.INJURY,
            actor_ids=[predator.id, prey.id],
            position=predator.position,
            payload={
                "victim": predator.display_name,
                "attacker": prey.display_name,
                "type": "charge",
                "injury": round(injury, 2),
            },
        ))


# ---------------------------------------------------------------------------
# Intraspecific fighting (territory, dominance)
# ---------------------------------------------------------------------------


def attempt_fight(
    attacker: Agent,
    defender: Agent,
    fight_type: str,
    world: "World",
    event_bus: EventBus,
    rng: Any,
) -> Agent | None:
    """Resolve dominance or territorial contest. Returns winner."""
    # Simplified: compare size * health * traits.aggression
    def strength(a: Agent) -> float:
        return a.body_mass_kg * a.health * a.traits.aggression

    att_str = strength(attacker)
    def_str = strength(defender)
    total = att_str + def_str
    win_prob = att_str / max(1.0, total)

    event_bus.emit(Event(
        tick=world.tick,
        category=EventCategory.INTERACTION,
        subcategory=EventSubcategory.FIGHT,
        actor_ids=[attacker.id, defender.id],
        position=attacker.position,
        payload={
            "attacker": attacker.display_name,
            "defender": defender.display_name,
            "fight_type": fight_type,
            "attacker_win_prob": round(win_prob, 2),
        },
    ))

    # Minor injuries to both
    injury_a = rng.uniform(0.01, 0.08)
    injury_d = rng.uniform(0.02, 0.12)
    attacker.injury_level = min(1.0, attacker.injury_level + injury_a)
    defender.injury_level = min(1.0, defender.injury_level + injury_d)

    if rng.chance(win_prob):
        return attacker
    else:
        return defender


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _sigmoid(x: float, steepness: float = 1.0) -> float:
    """Logistic sigmoid, output in (0, 1)."""
    return 1.0 / (1.0 + math.exp(-steepness * x))
