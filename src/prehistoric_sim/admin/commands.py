"""
commands.py — Admin command parsing and execution against the Simulation.

Every command is a function that takes the sim object plus parsed args.
Returns a string result message.
All admin actions emit an ADMIN event through the sim's event bus.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from prehistoric_sim.engine.simulation import Simulation

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Command registry
# ---------------------------------------------------------------------------

_COMMANDS: dict[str, Any] = {}


def _cmd(name: str):
    """Decorator to register a command function."""
    def decorator(fn):
        _COMMANDS[name] = fn
        return fn
    return decorator


def execute_command(sim: "Simulation", command: str, args: dict[str, Any]) -> str:
    """Execute a parsed admin command. Returns result string."""
    fn = _COMMANDS.get(command)
    if fn is None:
        return f"Unknown command: '{command}'. Type 'help' for a list of commands."
    try:
        return fn(sim, args)
    except Exception as e:
        logger.exception("Command error: %s %s", command, args)
        return f"Error executing '{command}': {e}"


def get_all_commands() -> list[str]:
    """Return sorted list of all registered command names."""
    return sorted(_COMMANDS.keys())


# ---------------------------------------------------------------------------
# Command implementations
# ---------------------------------------------------------------------------


@_cmd("help")
def cmd_help(sim: "Simulation", args: dict) -> str:
    """Print help for all commands or a specific command."""
    target = args.get("command")
    if target:
        fn = _COMMANDS.get(target)
        if fn:
            return f"{target}: {fn.__doc__ or 'No documentation.'}"
        return f"Unknown command: {target}"
    lines = ["Available commands:"]
    for name in sorted(_COMMANDS.keys()):
        doc = _COMMANDS[name].__doc__ or ""
        first_line = doc.strip().split("\n")[0]
        lines.append(f"  {name:20s} {first_line}")
    return "\n".join(lines)


# --- SPAWN ---

@_cmd("spawn")
def cmd_spawn(sim: "Simulation", args: dict) -> str:
    """Spawn creatures, plants, carcasses, nests, eggs, water, or hazards.

    Usage: spawn <species> <count> [x y] [--age <stage>] [--name <name>]
    """
    from prehistoric_sim.engine.entities import LifeStage  # noqa: PLC0415

    entity_type = args.get("entity_type", args.get("species", ""))
    count = max(1, int(args.get("count", 1)))
    x = args.get("x")
    y = args.get("y")
    name_base = args.get("name")
    stage_str = args.get("age", "ADULT")
    radius = int(args.get("radius", 0))

    # Map stage string
    stage_map = {s.value: s for s in LifeStage}
    life_stage = stage_map.get(stage_str.upper(), LifeStage.ADULT)

    if entity_type == "water":
        # Spawn a temporary water pool
        px = int(x) if x is not None else sim.world.width // 2
        py = int(y) if y is not None else sim.world.height // 2
        rad = int(args.get("radius", 4))
        for dy in range(-rad, rad + 1):
            for dx in range(-rad, rad + 1):
                nx, ny = px + dx, py + dy
                if sim.world.in_bounds(nx, ny) and dx * dx + dy * dy <= rad * rad:
                    sim.world.water_depth[ny, nx] = 1.0
                    sim.world._water_cells.add((nx, ny))
        sim.world._build_water_sets()
        return f"Created water pool at ({px},{py}) radius {rad}"

    if entity_type == "hazard":
        hazard = args.get("hazard_type", "fire")
        hx = int(x) if x is not None else sim.rng.randint(10, sim.world.width - 10)
        hy = int(y) if y is not None else sim.rng.randint(10, sim.world.height - 10)
        if hazard == "fire":
            sim.world.weather.fire_cells.add((hx, hy))
            return f"Started fire at ({hx},{hy})"
        elif hazard in ("storm", "rain", "drought", "flood"):
            from prehistoric_sim.engine.entities import WeatherType  # noqa: PLC0415
            try:
                wt = WeatherType(hazard.upper())
                sim.world._start_weather(wt, 240)
                return f"Started {hazard} weather"
            except ValueError:
                return f"Unknown hazard: {hazard}"
        return f"Unknown hazard type: {hazard}"

    if entity_type == "carcass":
        species = args.get("species_key", entity_type)
        sd = sim.species_data.get(species)
        if not sd:
            return f"Unknown species: {species}"
        from prehistoric_sim.engine.entities import Carcass, _new_id  # noqa: PLC0415
        pos = (int(x) if x else sim.rng.randint(5, sim.world.width - 5),
               int(y) if y else sim.rng.randint(5, sim.world.height - 5))
        c = Carcass(
            id=_new_id("carcass"), position=pos, alive=True,
            species_key=species, original_mass_kg=sd.get("body_mass_kg", 100),
            mass_remaining=sd.get("body_mass_kg", 100),
        )
        sim._register_carcass(c)
        return f"Spawned carcass of {species} at {pos}"

    # Default: spawn agent(s)
    species_key = entity_type
    if species_key not in sim.species_data:
        return f"Unknown species: '{species_key}'. Available: {', '.join(sorted(sim.species_data.keys()))}"

    spawned: list[str] = []
    for i in range(count):
        pos = None
        if x is not None and y is not None:
            px, py = int(x), int(y)
            if radius > 0:
                px += sim.rng.randint(-radius, radius)
                py += sim.rng.randint(-radius, radius)
            pos = (max(0, min(sim.world.width - 1, px)), max(0, min(sim.world.height - 1, py)))

        agent_name = None
        if name_base:
            agent_name = f"{name_base}-{i + 1}" if count > 1 else name_base

        agent = sim.spawn_agent(species_key, position=pos, life_stage=life_stage, name=agent_name)
        if agent:
            spawned.append(agent.display_name)

    if not spawned:
        return f"Failed to spawn (population cap reached or unknown species)"
    return f"Spawned {len(spawned)} {species_key}: {', '.join(spawned[:5])}" + ("…" if len(spawned) > 5 else "")


# --- INSPECT ---

@_cmd("inspect")
def cmd_inspect(sim: "Simulation", args: dict) -> str:
    """Full panel inspection of a creature.

    Usage: inspect <name_or_id>
    """
    target = args.get("target", "")
    agent = sim.find_agent(target)
    if agent is None:
        return f"Agent not found: '{target}'"

    d = agent.drives
    t = agent.traits
    lines = [
        f"╔══════════════════════════════════════════",
        f"║ {agent.display_name} [{agent.species_key}]",
        f"║ ID: {agent.id}  Position: {agent.position}",
        f"║ Stage: {agent.life_stage.value}  Age: {agent.age_ticks} ticks",
        f"║ Health: {agent.health:.2f}  Energy: {agent.energy:.2f}  Hydration: {agent.hydration:.2f}",
        f"║ Stamina: {agent.stamina:.2f}  Injury: {agent.injury_level:.2f}",
        f"║ Mass: {agent.body_mass_kg:.1f} kg  Speed: {agent.max_speed:.2f}",
        f"║ Action: {agent.current_action} (committed {agent.action_ticks_committed} ticks)",
        f"║ Pregnant: {agent.pregnant}  Nest: {agent.incubating_nest_id}",
        f"╠── DRIVES",
        f"║  Hunger:{d.hunger:.2f} Thirst:{d.thirst:.2f} Fatigue:{d.fatigue:.2f}",
        f"║  Fear:{d.fear:.2f} Repro:{d.reproductive_urge:.2f} Social:{d.social_need:.2f}",
        f"║  Curiosity:{d.curiosity:.2f} Parental:{d.parental_drive:.2f}",
        f"╠── TRAITS",
        f"║  Boldness:{t.boldness:.2f} Aggression:{t.aggression:.2f} Curiosity:{t.curiosity:.2f}",
        f"║  Sociability:{t.sociability:.2f} Size:{t.size_factor:.2f} Speed:{t.speed_factor:.2f}",
        f"║  MetabEff:{t.metabolic_efficiency:.2f}",
        f"╠── KIN",
        f"║  Parents: {agent.parent_ids}",
        f"║  Offspring: {agent.offspring_ids}",
        f"║  Mate: {agent.mate_id}",
        f"╠── MEMORY ({len(agent.memory)} entries)",
    ]
    for m in agent.memory[:5]:
        lines.append(f"║  [{m.kind}] {m.position} str={m.strength:.2f} '{m.detail}'")
    if agent.last_decision:
        dr = agent.last_decision
        lines.append(f"╠── LAST DECISION (tick {dr.tick})")
        lines.append(f"║  {dr.action} ({dr.score:.2f}): {dr.reason}")
    if agent.cause_of_death:
        lines.append(f"╠── DEAD: {agent.cause_of_death} at tick {agent.death_tick}")
    lines.append("╚══════════════════════════════════════════")
    return "\n".join(lines)


@_cmd("story")
def cmd_story(sim: "Simulation", args: dict) -> str:
    """Print a creature's life history from the event log.

    Usage: story <name_or_id>
    """
    target = args.get("target", "")
    agent = sim.find_agent(target)
    if agent is None:
        # Try by ID directly in event bus history
        return f"Agent not found: '{target}'"
    events = sim.event_bus.actor_events(agent.id)
    if not events:
        return f"No recorded events for {agent.display_name}"
    lines = [f"Life story of {agent.display_name} ({agent.species_key}):"]
    for ev in events:
        lines.append(f"  T{ev.tick:06d} [{ev.subcategory.value}] {ev.payload}")
    return "\n".join(lines)


@_cmd("census")
def cmd_census(sim: "Simulation", args: dict) -> str:
    """Population count by species and life stage.

    Usage: census
    """
    census = sim.census()
    lines = ["Population census:"]
    for sp, stages in sorted(census.items()):
        total = sum(stages.values())
        detail = " ".join(f"{k}:{v}" for k, v in stages.items())
        lines.append(f"  {sp:28s} total={total:4d}  {detail}")
    lines.append(f"  {'TOTAL':28s} total={len(sim.agents):4d}")
    return "\n".join(lines)


@_cmd("list")
def cmd_list(sim: "Simulation", args: dict) -> str:
    """List creatures, optionally filtered by species or stage.

    Usage: list [species] [--stage ADULT]
    """
    species_filter = args.get("species")
    stage_filter = args.get("stage")
    results = []
    for a in sim.agents.values():
        if species_filter and a.species_key != species_filter:
            continue
        if stage_filter and a.life_stage.value != stage_filter.upper():
            continue
        results.append(f"  {a.display_name:20s} [{a.species_key}] {a.life_stage.value} pos={a.position}")
    if not results:
        return "No matching agents."
    return "\n".join(results[:50]) + (f"\n  ... and {len(results) - 50} more" if len(results) > 50 else "")


@_cmd("find")
def cmd_find(sim: "Simulation", args: dict) -> str:
    """Find a creature by name.

    Usage: find <name>
    """
    name = args.get("name", "")
    agent = sim.find_agent(name)
    if agent is None:
        return f"Not found: '{name}'"
    return cmd_inspect(sim, {"target": name})


# --- TRACK ---

@_cmd("track")
def cmd_track(sim: "Simulation", args: dict) -> str:
    """Enable verbose per-tick output for a creature.

    Usage: track <name_or_id>
    """
    target = args.get("target", "")
    agent = sim.find_agent(target)
    if agent is None:
        return f"Agent not found: '{target}'"
    agent.tracked = True
    sim._tracked_ids.add(agent.id)
    return f"Now tracking {agent.display_name} (verbose output enabled)"


@_cmd("untrack")
def cmd_untrack(sim: "Simulation", args: dict) -> str:
    """Disable verbose tracking for a creature.

    Usage: untrack <name_or_id>
    """
    target = args.get("target", "")
    agent = sim.find_agent(target)
    if agent is None:
        return f"Agent not found: '{target}'"
    agent.tracked = False
    sim._tracked_ids.discard(agent.id)
    return f"Stopped tracking {agent.display_name}"


# --- NAME ---

@_cmd("name")
def cmd_name(sim: "Simulation", args: dict) -> str:
    """Give a creature a custom name.

    Usage: name <id> <new_name>
    """
    target = args.get("target", "")
    new_name = args.get("new_name", "")
    agent = sim.find_agent(target)
    if agent is None:
        return f"Agent not found: '{target}'"
    if not new_name:
        return "Please provide a new name."
    agent.name = new_name
    return f"Renamed to '{new_name}'"


@_cmd("unname")
def cmd_unname(sim: "Simulation", args: dict) -> str:
    """Remove a creature's custom name.

    Usage: unname <name_or_id>
    """
    target = args.get("target", "")
    agent = sim.find_agent(target)
    if agent is None:
        return f"Agent not found: '{target}'"
    old = agent.name
    agent.name = None
    return f"Removed name '{old}' from {agent.display_id}"


# --- MODIFY ---

@_cmd("kill")
def cmd_kill(sim: "Simulation", args: dict) -> str:
    """Kill a creature instantly.

    Usage: kill <name_or_id> [--cause <reason>]
    """
    from prehistoric_sim.engine.lifecycle import create_carcass, kill_agent  # noqa: PLC0415
    target = args.get("target", "")
    cause = args.get("cause", "admin_kill")
    agent = sim.find_agent(target)
    if agent is None:
        return f"Agent not found: '{target}'"
    kill_agent(agent, cause, sim.world, sim.event_bus)
    c = create_carcass(agent, sim.world, sim.event_bus)
    sim._register_carcass(c)
    return f"Killed {agent.display_name} (cause: {cause})"


@_cmd("heal")
def cmd_heal(sim: "Simulation", args: dict) -> str:
    """Fully heal a creature (health, energy, hydration).

    Usage: heal <name_or_id>
    """
    target = args.get("target", "")
    agent = sim.find_agent(target)
    if agent is None:
        return f"Agent not found: '{target}'"
    agent.health = 1.0
    agent.energy = 1.0
    agent.hydration = 1.0
    agent.injury_level = 0.0
    agent.stamina = 1.0
    return f"Healed {agent.display_name}"


@_cmd("injure")
def cmd_injure(sim: "Simulation", args: dict) -> str:
    """Apply injury to a creature.

    Usage: injure <name_or_id> [--amount 0.5]
    """
    target = args.get("target", "")
    amount = float(args.get("amount", 0.3))
    agent = sim.find_agent(target)
    if agent is None:
        return f"Agent not found: '{target}'"
    agent.injury_level = min(1.0, agent.injury_level + amount)
    return f"Injured {agent.display_name} by {amount:.2f} (now {agent.injury_level:.2f})"


@_cmd("feed")
def cmd_feed(sim: "Simulation", args: dict) -> str:
    """Give a creature a full meal.

    Usage: feed <name_or_id>
    """
    target = args.get("target", "")
    agent = sim.find_agent(target)
    if agent is None:
        return f"Agent not found: '{target}'"
    agent.energy = 1.0
    agent.drives.hunger = 0.0
    return f"Fed {agent.display_name} (energy=1.0)"


@_cmd("water")
def cmd_water(sim: "Simulation", args: dict) -> str:
    """Give a creature a drink.

    Usage: water <name_or_id>
    """
    target = args.get("target", "")
    agent = sim.find_agent(target)
    if agent is None:
        return f"Agent not found: '{target}'"
    agent.hydration = 1.0
    agent.drives.thirst = 0.0
    return f"Hydrated {agent.display_name} (hydration=1.0)"


@_cmd("set")
def cmd_set(sim: "Simulation", args: dict) -> str:
    """Set a creature's stat or drive/trait.

    Usage: set <name_or_id> <field> <value>
    Fields: energy, hydration, age, stage, health, drive:<name>, trait:<name>
    """
    target = args.get("target", "")
    field = args.get("field", "")
    value = args.get("value")
    agent = sim.find_agent(target)
    if agent is None:
        return f"Agent not found: '{target}'"
    if value is None:
        return "Please provide a value."

    try:
        if field == "energy":
            agent.energy = float(value)
        elif field == "hydration":
            agent.hydration = float(value)
        elif field == "health":
            agent.health = float(value)
        elif field == "age":
            agent.age_ticks = int(value)
        elif field == "stage":
            from prehistoric_sim.engine.entities import LifeStage  # noqa: PLC0415
            agent.life_stage = LifeStage(str(value).upper())
        elif field.startswith("drive:"):
            drive_name = field.split(":", 1)[1]
            if hasattr(agent.drives, drive_name):
                setattr(agent.drives, drive_name, float(value))
            else:
                return f"Unknown drive: {drive_name}"
        elif field.startswith("trait:"):
            trait_name = field.split(":", 1)[1]
            if hasattr(agent.traits, trait_name):
                setattr(agent.traits, trait_name, float(value))
            else:
                return f"Unknown trait: {trait_name}"
        else:
            return f"Unknown field: {field}"
        return f"Set {agent.display_name}.{field} = {value}"
    except (ValueError, TypeError) as e:
        return f"Invalid value: {e}"


@_cmd("teleport")
def cmd_teleport(sim: "Simulation", args: dict) -> str:
    """Teleport a creature to coordinates.

    Usage: teleport <name_or_id> <x> <y>
    """
    target = args.get("target", "")
    x = args.get("x")
    y = args.get("y")
    if x is None or y is None:
        return "Please provide x and y coordinates."
    agent = sim.find_agent(target)
    if agent is None:
        return f"Agent not found: '{target}'"
    new_pos = (
        max(0, min(sim.world.width - 1, int(x))),
        max(0, min(sim.world.height - 1, int(y))),
    )
    old_pos = agent.position
    agent.position = new_pos
    sim.agent_hash.insert(agent, *new_pos)
    return f"Teleported {agent.display_name} from {old_pos} to {new_pos}"


@_cmd("possess")
def cmd_possess(sim: "Simulation", args: dict) -> str:
    """Take direct control of a creature's actions.

    Usage: possess <name_or_id>
    Then use: act <action> [target]
    Release with: release <name_or_id>
    """
    target = args.get("target", "")
    agent = sim.find_agent(target)
    if agent is None:
        return f"Agent not found: '{target}'"
    agent.possessed = True
    agent.current_action = "REST"
    agent.action_target_id = None
    agent.action_target_pos = None
    agent.forced_action = None
    agent.forced_action_ticks = 0
    sim._possessed.add(agent.id)
    return f"Now possessing {agent.display_name}. Use 'act <action>' to control it. 'release {target}' to stop."


@_cmd("release")
def cmd_release(sim: "Simulation", args: dict) -> str:
    """Release admin possession of a creature.

    Usage: release <name_or_id>
    """
    target = args.get("target", "")
    agent = sim.find_agent(target)
    if agent is None:
        return f"Agent not found: '{target}'"
    agent.possessed = False
    sim._possessed.discard(agent.id)
    return f"Released {agent.display_name} back to autonomous control."


@_cmd("unpossess")
def cmd_unpossess(sim: "Simulation", args: dict) -> str:
    """Alias for release, matching the GUI and documented command name."""
    return cmd_release(sim, args)


@_cmd("act")
def cmd_act(sim: "Simulation", args: dict) -> str:
    """Override a possessed creature's action.

    Usage: act <action> [--target <name_or_id>] [--possessing <name_or_id>]
    """
    possessing_id = args.get("possessing")
    action = args.get("action", "WANDER").upper()
    action_target = args.get("target")
    action_position = args.get("position")

    if possessing_id:
        agent = sim.find_agent(possessing_id)
    elif sim._possessed:
        agent_id = next(iter(sim._possessed))
        agent = sim.agents.get(agent_id)
    else:
        return "No creature is possessed. Use 'possess <name>' first."

    if agent is None:
        return "Possessed creature not found."
    if not agent.possessed:
        return f"{agent.display_name} is not possessed."

    agent.current_action = action
    if action_position is not None:
        agent.action_target_pos = tuple(action_position)
    if action_target:
        target_agent = sim.find_agent(action_target)
        if target_agent:
            agent.action_target_id = target_agent.id
            agent.action_target_pos = target_agent.position

    return f"{agent.display_name} — action set to {action}"


@_cmd("steer")
def cmd_steer(sim: "Simulation", args: dict) -> str:
    """Move a possessed creature immediately in a requested grid direction."""
    agent = sim.find_agent(args.get("target", ""))
    if agent is None:
        return f"Agent not found: '{args.get('target', '')}'"
    if not agent.possessed:
        return f"{agent.display_name} is not possessed."
    dx = max(-1, min(1, int(args.get("dx", 0))))
    dy = max(-1, min(1, int(args.get("dy", 0))))
    if dx == 0 and dy == 0:
        return "Choose a movement direction."
    old_position = agent.position
    distance = max(1, min(3, int(round(agent.effective_speed))))
    tx = max(0, min(sim.world.width - 1, int(old_position[0]) + dx * distance))
    ty = max(0, min(sim.world.height - 1, int(old_position[1]) + dy * distance))
    from prehistoric_sim.engine.behaviors import _move_toward  # noqa: PLC0415
    _move_toward(agent, tx, ty, sim.world, speed_override=float(distance))
    agent.current_action = "REST"
    agent.action_target_pos = None
    sim.agent_hash.insert(agent, *agent.position)
    return f"Steered {agent.display_name} from {old_position} to {agent.position}."


@_cmd("force")
def cmd_force(sim: "Simulation", args: dict) -> str:
    """Force a creature to perform an action for N ticks.

    Usage: force <name_or_id> <action> [--duration <ticks>]
    """
    target = args.get("target", "")
    action = args.get("action", "WANDER").upper()
    duration = int(args.get("duration", 10))
    agent = sim.find_agent(target)
    if agent is None:
        return f"Agent not found: '{target}'"
    agent.forced_action = action
    agent.forced_action_ticks = duration
    return f"Forcing {agent.display_name} to {action} for {duration} ticks"


@_cmd("age_up")
def cmd_age_up(sim: "Simulation", args: dict) -> str:
    """Fast-forward a creature's age by a number of stages or ticks.

    Usage: age_up <name_or_id> <stages|ticks> [--unit stages|ticks]
    """
    target = args.get("target", "")
    amount = args.get("amount", 1)
    unit = args.get("unit", "stages")
    agent = sim.find_agent(target)
    if agent is None:
        return f"Agent not found: '{target}'"

    from prehistoric_sim.engine.lifecycle import get_stage_thresholds, LifeStage  # noqa: PLC0415
    sd = sim.species_data.get(agent.species_key, {})
    thresholds = get_stage_thresholds(sd, sim.config.aging_scale)

    if unit == "stages":
        ordered = [LifeStage.HATCHLING, LifeStage.JUVENILE, LifeStage.SUBADULT, LifeStage.ADULT, LifeStage.SENESCENT]
        cur_idx = ordered.index(agent.life_stage) if agent.life_stage in ordered else 0
        new_idx = min(len(ordered) - 1, cur_idx + int(amount))
        new_stage = ordered[new_idx]
        agent.age_ticks = thresholds.get(new_stage, agent.age_ticks)
        agent.life_stage = new_stage
        return f"Aged {agent.display_name} to {new_stage.value}"
    else:
        agent.age_ticks += int(amount)
        return f"Advanced {agent.display_name} by {amount} ticks (age={agent.age_ticks})"


@_cmd("breed")
def cmd_breed(sim: "Simulation", args: dict) -> str:
    """Force a mating attempt between two creatures.

    Usage: breed <nameA> <nameB>
    """
    a_name = args.get("target_a", "")
    b_name = args.get("target_b", "")
    a = sim.find_agent(a_name)
    b = sim.find_agent(b_name)
    if a is None:
        return f"Agent not found: '{a_name}'"
    if b is None:
        return f"Agent not found: '{b_name}'"
    if a.species_key != b.species_key:
        return "Agents must be the same species to breed."

    from prehistoric_sim.engine.reproduction import attempt_mating  # noqa: PLC0415
    sd = sim.species_data.get(a.species_key, {})
    new_eggs: list = []
    new_nests: list = []
    attempt_mating(a, b, sim.world, sd, sim.event_bus, sim.rng, sim.config.aging_scale)
    return f"Forced mating between {a.display_name} and {b.display_name}"


# --- WORLD CONTROL ---

@_cmd("pause")
def cmd_pause(sim: "Simulation", args: dict) -> str:
    """Pause the simulation.

    Usage: pause
    """
    sim.paused = True
    return "Simulation paused."


@_cmd("resume")
def cmd_resume(sim: "Simulation", args: dict) -> str:
    """Resume the simulation.

    Usage: resume
    """
    sim.paused = False
    return "Simulation resumed."


@_cmd("speed")
def cmd_speed(sim: "Simulation", args: dict) -> str:
    """Set simulation speed multiplier.

    Usage: speed <multiplier>
    """
    mult = float(args.get("multiplier", 1.0))
    sim.speed_multiplier = max(0.1, mult)
    return f"Speed set to {sim.speed_multiplier}x"


@_cmd("step")
def cmd_step(sim: "Simulation", args: dict) -> str:
    """Advance N ticks while paused.

    Usage: step [n]
    """
    n = int(args.get("n", 1))
    was_paused = sim.paused
    sim.paused = False
    for _ in range(n):
        sim.step()
    sim.paused = was_paused
    return f"Advanced {n} tick(s). Now at tick {sim.tick}."


@_cmd("fastforward")
def cmd_fastforward(sim: "Simulation", args: dict) -> str:
    """Fast-forward N in-world days (suppresses output).

    Usage: fastforward <days>
    """
    days = int(args.get("days", 1))
    from prehistoric_sim.engine.world import TICKS_PER_DAY  # noqa: PLC0415
    ticks = days * TICKS_PER_DAY
    was_paused = sim.paused
    sim.paused = False
    for _ in range(ticks):
        sim.step()
    sim.paused = was_paused
    return f"Fast-forwarded {days} days ({ticks} ticks). Now at tick {sim.tick}."


@_cmd("set_time")
def cmd_set_time(sim: "Simulation", args: dict) -> str:
    """Set the in-world time.

    Usage: set_time <day> <hour>
    """
    day = int(args.get("day", sim.world.day))
    hour = float(args.get("hour", 12.0))
    from prehistoric_sim.engine.world import TICKS_PER_DAY  # noqa: PLC0415
    sim.world.tick = day * TICKS_PER_DAY + int(hour / 24.0 * TICKS_PER_DAY)
    return f"Time set to Day {day}, Hour {hour:.1f}"


@_cmd("set_season")
def cmd_set_season(sim: "Simulation", args: dict) -> str:
    """Set the current season.

    Usage: set_season <SPRING|SUMMER|AUTUMN|WINTER>
    """
    from prehistoric_sim.engine.world import SEASONS  # noqa: PLC0415
    season = args.get("season", "SPRING").upper()
    if season not in SEASONS:
        return f"Unknown season: {season}. Choose from {SEASONS}"
    sim.world.season_index = SEASONS.index(season)
    return f"Season set to {season}"


@_cmd("set_weather")
def cmd_set_weather(sim: "Simulation", args: dict) -> str:
    """Override the current weather.

    Usage: set_weather <CLEAR|RAIN|STORM|DROUGHT|FLOOD|FIRE>
    """
    from prehistoric_sim.engine.entities import WeatherType  # noqa: PLC0415
    weather_str = args.get("weather", "CLEAR").upper()
    try:
        wt = WeatherType(weather_str)
    except ValueError:
        return f"Unknown weather: {weather_str}"
    if wt == WeatherType.CLEAR:
        sim.world.weather.current = WeatherType.CLEAR
        sim.world.weather.ticks_remaining = 0
        return "Weather cleared."
    sim.world._start_weather(wt, 240)
    return f"Weather set to {weather_str} for 240 ticks"


@_cmd("weather")
def cmd_weather_alias(sim: "Simulation", args: dict) -> str:
    return cmd_set_weather(sim, {"weather": args.get("weather", args.get("value", "CLEAR"))})


@_cmd("season")
def cmd_season_alias(sim: "Simulation", args: dict) -> str:
    return cmd_set_season(sim, {"season": args.get("season", args.get("value", "SPRING"))})


@_cmd("fire")
def cmd_fire(sim: "Simulation", args: dict) -> str:
    x = max(0, min(sim.world.width - 1, int(args.get("x", sim.world.width // 2))))
    y = max(0, min(sim.world.height - 1, int(args.get("y", sim.world.height // 2))))
    sim.world.weather.fire_cells.add((x, y))
    return f"Ignited wildfire at ({x}, {y})."


@_cmd("flood")
def cmd_flood(sim: "Simulation", args: dict) -> str:
    x = max(0, min(sim.world.width - 1, int(args.get("x", sim.world.width // 2))))
    y = max(0, min(sim.world.height - 1, int(args.get("y", sim.world.height // 2))))
    radius = max(1, min(8, int(args.get("radius", 3))))
    cells = {(cx, cy) for cy in range(max(0, y - radius), min(sim.world.height, y + radius + 1))
             for cx in range(max(0, x - radius), min(sim.world.width, x + radius + 1))
             if (cx - x) ** 2 + (cy - y) ** 2 <= radius ** 2}
    sim.world.weather.flood_cells.update(cells)
    from prehistoric_sim.engine.entities import WeatherType  # noqa: PLC0415
    sim.world._start_weather(WeatherType.FLOOD, 144)
    return f"Flooded {len(cells)} cells around ({x}, {y})."


@_cmd("extinguish")
def cmd_extinguish(sim: "Simulation", args: dict) -> str:
    count = len(sim.world.weather.fire_cells)
    sim.world.weather.fire_cells.clear()
    return f"Extinguished {count} active fire cell(s)."


@_cmd("stats")
def cmd_stats(sim: "Simulation", args: dict) -> str:
    populations = sim.population_by_species()
    total = sum(populations.values())
    carcasses = len(sim.carcasses)
    return f"Population: {total}; species: {len(populations)}; carcasses: {carcasses}; tick: {sim.tick}."


@_cmd("bloom")
def cmd_bloom(sim: "Simulation", args: dict) -> str:
    """Rapidly regrow plants using the world's terrain and layer capacities."""
    fire_cells = sim.world.weather.fire_cells
    sim.world.weather.fire_cells = set()
    try:
        for _ in range(24):
            sim.world._update_plants()
    finally:
        sim.world.weather.fire_cells = fire_cells
    return "Vegetation regrown across the ecosystem."


@_cmd("clear_carcasses")
def cmd_clear_carcasses(sim: "Simulation", args: dict) -> str:
    count = len(sim.carcasses)
    for carcass in list(sim.carcasses.values()):
        sim.carcass_hash.remove(carcass)
    sim.carcasses.clear()
    return f"Removed {count} carcass(es)."


@_cmd("mate")
def cmd_mate_nearest(sim: "Simulation", args: dict) -> str:
    """Attempt forced mating with the nearest eligible conspecific."""
    target = sim.find_agent(args.get("target", ""))
    if target is None:
        return f"Agent not found: '{args.get('target', '')}'"
    candidates = [a for a in sim.agents.values() if a.id != target.id
                  and a.alive and a.species_key == target.species_key
                  and a.is_adult_capable]
    if not candidates:
        return f"No adult {target.species_key} partner is available."
    partner = min(candidates, key=lambda a: (target.distance_to(a), a.id))
    from prehistoric_sim.engine.reproduction import attempt_mating  # noqa: PLC0415
    sd = sim.species_data.get(target.species_key, {})
    attempt_mating(target, partner, sim.world, sd, sim.event_bus, sim.rng, sim.config.aging_scale)
    return f"Forced mating attempt: {target.display_name} and {partner.display_name}."


# --- SAVE/LOAD ---

@_cmd("save")
def cmd_save(sim: "Simulation", args: dict) -> str:
    """Save simulation snapshot to a file.

    Usage: save <filename>
    """
    import json  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    filename = args.get("filename", "snapshot.json")
    path = Path(filename)
    state = sim.get_state()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, default=str)
        from prehistoric_sim.engine.events import Event, EventCategory, EventSubcategory  # noqa: PLC0415
        sim.event_bus.emit(Event(
            tick=sim.tick, category=EventCategory.SYSTEM,
            subcategory=EventSubcategory.SNAPSHOT_SAVED,
            actor_ids=[], position=None, payload={"path": str(path)},
        ))
        return f"Snapshot saved to {path}"
    except Exception as e:
        return f"Save failed: {e}"


@_cmd("load")
def cmd_load(sim: "Simulation", args: dict) -> str:
    """Load simulation snapshot from a file.

    Usage: load <filename>
    """
    import json  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    filename = args.get("filename", "snapshot.json")
    path = Path(filename)
    if not path.exists():
        return f"Snapshot file not found: {path}"
    try:
        with open(path, encoding="utf-8") as f:
            state = json.load(f)
        sim.set_state(state)
        return f"Snapshot successfully loaded from {path}. Simulation now at tick {sim.tick}."
    except Exception as e:
        return f"Load failed: {e}"


@_cmd("dashboard")
def cmd_dashboard(sim: "Simulation", args: dict) -> str:
    """Show the world summary dashboard.

    Usage: dashboard
    """
    return "__DASHBOARD__"  # Handled specially in console.py


@_cmd("map")
def cmd_map(sim: "Simulation", args: dict) -> str:
    """Show an ASCII map of the world.

    Usage: map
    """
    return "__MAP__"  # Handled specially in console.py


@_cmd("filter")
def cmd_filter(sim: "Simulation", args: dict) -> str:
    """Control event display filtering.

    Usage: filter verbosity <0-3>  |  filter species <key>  |  filter reset
    """
    return args.get("spec", "Pass filter settings to renderer via console.")


@_cmd("quit")
def cmd_quit(sim: "Simulation", args: dict) -> str:
    """Quit the simulation.

    Usage: quit
    """
    sim.stop()
    return "__QUIT__"
