"""
simulation.py — Top-level Simulation class.

Owns everything: World, all entities, EventBus, spatial hashes, species data.
Exposes step(), run(), get_state(), apply_admin_command().
The engine never imports from ui, admin, io, or cli.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

from prehistoric_sim.engine.behaviors import (
    do_drink,
    do_eat_carcass,
    do_flee,
    do_follow,
    do_graze,
    do_guard_nest,
    do_hide,
    do_migrate,
    do_rest,
    do_scavenge,
    do_sleep,
    do_wander,
)
from prehistoric_sim.engine.combat import attempt_fight, attempt_hunt
from prehistoric_sim.engine.entities import (
    Agent,
    Carcass,
    Egg,
    FishSchool,
    InsectSwarm,
    LifeStage,
    Nest,
    _new_id,
)
from prehistoric_sim.engine.events import Event, EventBus, EventCategory, EventSubcategory
from prehistoric_sim.engine.lifecycle import (
    age_agent,
    create_carcass,
    decay_carcass,
    incubate_egg,
    kill_agent,
    update_metabolism,
)
from prehistoric_sim.engine.mind import decide, perceive, update_memory
from prehistoric_sim.engine.reproduction import (
    attempt_mating,
    build_nest,
    can_mate,
    give_birth,
    hatch_egg,
    lay_clutch,
)
from prehistoric_sim.engine.rng import SimRNG
from prehistoric_sim.engine.spatial import SpatialHash
from prehistoric_sim.engine.world import TICKS_PER_DAY, World

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration dataclass
# ---------------------------------------------------------------------------


class SimConfig:
    """Runtime configuration for the simulation."""

    def __init__(
        self,
        seed: int = 42,
        world_width: int = 120,
        world_height: int = 120,
        days_per_season: int = 90,
        aging_scale: float = 50.0,
        population_cap: int = 1500,
        verbosity: int = 2,
        auto_name: bool = False,
        ascii_glyphs: bool = False,
        no_color: bool = False,
        world_name: str = "hell_creek",
    ) -> None:
        self.seed = seed
        self.world_width = world_width
        self.world_height = world_height
        self.days_per_season = days_per_season
        self.aging_scale = aging_scale
        self.population_cap = population_cap
        self.verbosity = verbosity
        self.auto_name = auto_name
        self.ascii_glyphs = ascii_glyphs
        self.no_color = no_color
        self.world_name = world_name


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------


class Simulation:
    """The main simulation object.

    All entities (agents, eggs, nests, carcasses, fish schools) live here.
    The event bus is the only communication channel to the outside world.
    Call step() to advance one tick; run() to run for N ticks.
    """

    def __init__(
        self,
        config: SimConfig,
        species_data: dict[str, dict],  # key → species YAML dict
        world_config: dict[str, Any] | None = None,
    ) -> None:
        self.config = config
        self.species_data: dict[str, dict] = species_data
        self.world_config: dict[str, Any] = world_config or {}

        from prehistoric_sim.engine.entities import reset_id_counter  # noqa: PLC0415
        reset_id_counter(0)

        self.rng = SimRNG(config.seed)
        self.event_bus = EventBus()

        self.world = World(
            width=config.world_width,
            height=config.world_height,
            seed=config.seed,
            rng=self.rng,
            days_per_season=config.days_per_season,
            event_bus=self.event_bus,
        )

        # Entity collections
        self.agents: dict[str, Agent] = {}
        self.eggs: dict[str, Egg] = {}
        self.nests: dict[str, Nest] = {}
        self.carcasses: dict[str, Carcass] = {}
        self.fish_schools: dict[str, FishSchool] = {}
        self.insect_swarms: dict[str, InsectSwarm] = {}

        # Spatial hashes (cell_size=10 → good balance)
        self.agent_hash: SpatialHash[Agent] = SpatialHash(cell_size=10)
        self.carcass_hash: SpatialHash[Carcass] = SpatialHash(cell_size=10)
        self.nest_hash: SpatialHash[Nest] = SpatialHash(cell_size=10)

        # Running state
        self.paused: bool = False
        self.speed_multiplier: float = 1.0
        self.tick: int = 0
        self._running: bool = False

        # Admin command log for replay
        self._command_log: list[dict[str, Any]] = []

        # Name counters for auto-naming
        self._name_counters: dict[str, int] = {}

        # Population cap event (fire once when first hit)
        self._cap_warned: bool = False

        # Tracked creatures set
        self._tracked_ids: set[str] = set()

        # Birth/death counters per day
        self._daily_births: int = 0
        self._daily_deaths: int = 0

        # Possessed agents (admin control)
        self._possessed: set[str] = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def step(self) -> None:
        """Advance the simulation by one tick."""
        if self.paused:
            return

        self.tick += 1
        self.world.step()

        # Shuffle agent order each tick (prevents bias)
        agent_list = list(self.agents.values())
        self.rng.shuffle(agent_list)

        # --- Per-agent update ---
        new_agents: list[Agent] = []
        new_eggs: list[Egg] = []
        new_carcasses: list[Carcass] = []
        new_nests: list[Nest] = []

        for agent in agent_list:
            if not agent.alive:
                continue
            if getattr(agent, "reproduction_cooldown_ticks", 0) > 0:
                agent.reproduction_cooldown_ticks -= 1
            sd = self.species_data.get(agent.species_key, {})

            # 1. Metabolism
            update_metabolism(agent, sd, self.rng)

            # 2. Death from stats
            if agent.health <= 0.0:
                cause = "starvation" if agent.energy <= 0.0 else "dehydration" if agent.hydration <= 0.0 else "injury"
                kill_agent(agent, cause, self.world, self.event_bus)
                new_carcasses.append(create_carcass(agent, self.world, self.event_bus))
                self._daily_deaths += 1
                continue

            # 3. Age
            age_agent(agent, self.world, sd, self.config.aging_scale, self.event_bus, self.rng)
            if not agent.alive:
                new_carcasses.append(create_carcass(agent, self.world, self.event_bus))
                self._daily_deaths += 1
                continue

            # 4. Gestation / live birth
            if agent.pregnant:
                agent.gestation_ticks_remaining -= 1
                if agent.gestation_ticks_remaining <= 0:
                    offspring = give_birth(agent, self.world, sd, self.species_data, self.event_bus, self.rng, self.config.aging_scale)
                    new_agents.extend(offspring)
                    self._daily_births += len(offspring)

            # 5. Perception
            percepts = perceive(
                agent, self.world,
                self.agent_hash, self.carcass_hash, self.nest_hash,
                self.species_data, self.rng,
            )

            # 6. Memory update
            update_memory(agent, percepts, self.world)

            # 7. Decision
            decide(agent, percepts, self.world, sd, self.event_bus, self.rng)

            # 8. Execute action
            self._execute_action(
                agent, sd, percepts, new_agents, new_eggs, new_carcasses, new_nests
            )

            # 9. Update spatial hash
            self.agent_hash.insert(agent, *agent.position)

        # --- Egg incubation ---
        hatched_eggs: list[str] = []
        for egg in list(self.eggs.values()):
            if not egg.is_viable:
                hatched_eggs.append(egg.id)
                continue
            if incubate_egg(egg, self.world, self.event_bus, self.rng):
                hatchling = hatch_egg(egg, self.world, self.species_data, self.event_bus, self.rng, self.config.aging_scale)
                if hatchling:
                    new_agents.append(hatchling)
                    self._daily_births += 1
                    # Register as offspring of parent
                    for pid in egg.parent_ids:
                        parent = self.agents.get(pid)
                        if parent and hatchling.id not in parent.offspring_ids:
                            parent.offspring_ids.append(hatchling.id)
                hatched_eggs.append(egg.id)
        for eid in hatched_eggs:
            self.eggs.pop(eid, None)

        # --- Carcass decay ---
        decayed: list[str] = []
        for carcass in list(self.carcasses.values()):
            if not carcass.alive:
                decayed.append(carcass.id)
                continue
            if decay_carcass(carcass, self.world, self.event_bus):
                decayed.append(carcass.id)
        for cid in decayed:
            c = self.carcasses.pop(cid, None)
            if c:
                self.carcass_hash.remove(c)

        # --- Fish school regrowth ---
        for school in self.fish_schools.values():
            school.biomass = min(1.0, school.biomass + school.regrowth_rate * (1.0 - school.biomass))

        # --- Insect swarm update ---
        for swarm in self.insect_swarms.values():
            swarm.active = self.world.is_daytime

        # --- Add new entities ---
        for a in new_agents:
            if len(self.agents) < self.config.population_cap:
                self._register_agent(a)
        for e in new_eggs:
            self.eggs[e.id] = e
        for c in new_carcasses:
            self._register_carcass(c)
        for n in new_nests:
            self._register_nest(n)

        # --- Remove dead agents ---
        dead_ids = [aid for aid, a in self.agents.items() if not a.alive]
        for did in dead_ids:
            a = self.agents.pop(did)
            self.agent_hash.remove(a)

        # --- Population cap check ---
        if len(self.agents) >= self.config.population_cap and not self._cap_warned:
            self._cap_warned = True
            self.event_bus.emit(Event(
                tick=self.tick,
                category=EventCategory.SYSTEM,
                subcategory=EventSubcategory.POP_CAP,
                actor_ids=[],
                position=None,
                payload={"cap": self.config.population_cap, "current": len(self.agents)},
            ))

        # --- Reset cap warning if population drops ---
        if len(self.agents) < self.config.population_cap * 0.9:
            self._cap_warned = False

    def run(self, num_ticks: int, callback: Callable | None = None) -> None:
        """Run the simulation for a given number of ticks.

        Args:
            num_ticks: Number of ticks to advance.
            callback:  Optional per-tick callback (e.g. for rendering).
        """
        self._running = True
        for _ in range(num_ticks):
            if not self._running:
                break
            self.step()
            if callback:
                callback(self)
        self._running = False

    def stop(self) -> None:
        """Stop a running run() loop."""
        self._running = False

    def get_state(self) -> dict[str, Any]:
        """Return a JSON-serialisable snapshot of the full simulation state."""
        return {
            "tick": self.tick,
            "world": self.world.get_state(),
            "rng": self.rng.get_state(),
            "agents": {aid: _agent_to_dict(a) for aid, a in self.agents.items()},
            "eggs": {eid: _egg_to_dict(e) for eid, e in self.eggs.items()},
            "nests": {nid: _nest_to_dict(n) for nid, n in self.nests.items()},
            "carcasses": {cid: _carcass_to_dict(c) for cid, c in self.carcasses.items()},
            "command_log": list(self._command_log),
            "config": {
                "seed": self.config.seed,
                "aging_scale": self.config.aging_scale,
                "population_cap": self.config.population_cap,
            },
        }

    def set_state(self, state: dict[str, Any]) -> None:
        """Restore full simulation state from a snapshot dictionary."""
        self.tick = state.get("tick", 0)
        if "world" in state:
            self.world.set_state(state["world"])
        if "rng" in state:
            self.rng.set_state(state["rng"])

        from prehistoric_sim.engine.entities import (  # noqa: PLC0415
            Agent, Egg, Nest, Carcass, LifeStage, Traits, Drives
        )

        self.agents.clear()
        self.agent_hash = SpatialHash(cell_size=10)
        for aid, ad in state.get("agents", {}).items():
            traits_data = ad.get("traits", {})
            traits = Traits(**traits_data) if traits_data else Traits()
            drives_data = ad.get("drives", {})
            drives = Drives(**drives_data) if drives_data else Drives()
            stage_str = ad.get("life_stage", "ADULT")
            life_stage = LifeStage(stage_str) if stage_str in LifeStage._value2member_map_ else LifeStage.ADULT
            pos = tuple(ad.get("position", [0, 0]))
            agent = Agent(
                id=ad["id"],
                position=pos,
                alive=ad.get("alive", True),
                species_key=ad.get("species_key", ""),
                name=ad.get("name"),
                display_id=ad.get("display_id", ""),
                life_stage=life_stage,
                age_ticks=ad.get("age_ticks", 0),
                birth_tick=ad.get("birth_tick", 0),
                death_tick=ad.get("death_tick"),
                cause_of_death=ad.get("cause_of_death"),
                body_mass_kg=ad.get("body_mass_kg", 100.0),
                max_speed=ad.get("max_speed", 5.0),
                health=ad.get("health", 1.0),
                energy=ad.get("energy", 0.8),
                hydration=ad.get("hydration", 0.8),
                stamina=ad.get("stamina", 1.0),
                injury_level=ad.get("injury_level", 0.0),
                pregnant=ad.get("pregnant", False),
                gestation_ticks_remaining=ad.get("gestation_ticks_remaining", 0),
                reproduction_cooldown_ticks=ad.get("reproduction_cooldown_ticks", 0),
                parent_ids=list(ad.get("parent_ids", [])),
                offspring_ids=list(ad.get("offspring_ids", [])),
                mate_id=ad.get("mate_id"),
                current_action=ad.get("current_action", "WANDER"),
                traits=traits,
                drives=drives,
                incubating_nest_id=ad.get("incubating_nest_id"),
                group_id=ad.get("group_id"),
                tracked=ad.get("tracked", False),
                possessed=ad.get("possessed", False),
            )
            self._register_agent(agent)

        self.eggs.clear()
        for eid, ed in state.get("eggs", {}).items():
            egg = Egg(
                id=ed["id"],
                position=tuple(ed.get("position", [0, 0])),
                alive=ed.get("alive", True),
                species_key=ed.get("species_key", ""),
                parent_ids=list(ed.get("parent_ids", [])),
                clutch_id=ed.get("clutch_id", ""),
                nest_id=ed.get("nest_id", ""),
                incubation_ticks_total=ed.get("incubation_ticks_total", 100),
                incubation_ticks_remaining=ed.get("incubation_ticks_remaining", 100),
                temperature_stress=ed.get("temperature_stress", 0.0),
                hatched=ed.get("hatched", False),
            )
            self.eggs[egg.id] = egg

        self.nests.clear()
        self.nest_hash = SpatialHash(cell_size=10)
        for nid, nd in state.get("nests", {}).items():
            nest = Nest(
                id=nd["id"],
                position=tuple(nd.get("position", [0, 0])),
                alive=nd.get("alive", True),
                species_key=nd.get("species_key", ""),
                owner_id=nd.get("owner_id", ""),
                egg_ids=list(nd.get("egg_ids", [])),
                guarded=nd.get("guarded", False),
                construction_complete=nd.get("construction_complete", True),
            )
            self._register_nest(nest)

        self.carcasses.clear()
        self.carcass_hash = SpatialHash(cell_size=10)
        for cid, cd in state.get("carcasses", {}).items():
            carcass = Carcass(
                id=cd["id"],
                position=tuple(cd.get("position", [0, 0])),
                alive=cd.get("alive", True),
                species_key=cd.get("species_key", ""),
                original_mass_kg=cd.get("original_mass_kg", 100.0),
                mass_remaining=cd.get("mass_remaining", 100.0),
                decay_progress=cd.get("decay_progress", 0.0),
                nutrients_released=cd.get("nutrients_released", 0.0),
                death_tick=cd.get("death_tick", 0),
                cause_of_death=cd.get("cause_of_death", "unknown"),
            )
            self._register_carcass(carcass)

        self._command_log = list(state.get("command_log", []))

    def apply_admin_command(self, command: str, args: dict[str, Any]) -> str:
        """Apply an admin command. Returns a result message."""
        from prehistoric_sim.admin.commands import execute_command  # noqa: PLC0415
        entry = {"tick": self.tick, "command": command, "args": args}
        self._command_log.append(entry)
        result = execute_command(self, command, args)
        # Emit admin event
        self.event_bus.emit(Event(
            tick=self.tick,
            category=EventCategory.ADMIN,
            subcategory=EventSubcategory.ADMIN_COMMAND,
            actor_ids=[],
            position=None,
            payload={"command": command, "args": args, "result": str(result)[:200]},
        ))
        return result

    # ------------------------------------------------------------------
    # Spawning helpers
    # ------------------------------------------------------------------

    def spawn_agent(
        self,
        species_key: str,
        position: tuple[int, int] | None = None,
        life_stage: LifeStage | None = None,
        name: str | None = None,
        age_ticks: int | None = None,
    ) -> Agent | None:
        """Spawn a single agent and register it. Returns the agent."""
        if len(self.agents) >= self.config.population_cap:
            return None

        sd = self.species_data.get(species_key)
        if sd is None:
            logger.warning("Unknown species: %s", species_key)
            return None

        if position is None:
            position = (
                self.rng.randint(5, self.world.width - 5),
                self.rng.randint(5, self.world.height - 5),
            )
        position = (
            max(0, min(self.world.width - 1, position[0])),
            max(0, min(self.world.height - 1, position[1])),
        )

        if life_stage is None:
            life_stage = LifeStage.ADULT

        from prehistoric_sim.engine.reproduction import _spawn_agent  # noqa: PLC0415
        agent = _spawn_agent(
            species_key=species_key,
            position=position,
            species_data=sd,
            life_stage=life_stage,
            parent_ids=[],
            rng=self.rng,
            aging_scale=self.config.aging_scale,
            birth_tick=self.tick,
            name=name,
            age_ticks=age_ticks,
        )
        self._register_agent(agent)

        self.event_bus.emit(Event(
            tick=self.tick,
            category=EventCategory.LIFECYCLE,
            subcategory=EventSubcategory.BIRTH,
            actor_ids=[agent.id],
            position=agent.position,
            payload={
                "species": species_key,
                "name": agent.display_name,
                "life_stage": life_stage.value,
                "admin_spawned": True,
            },
        ))
        return agent

    def populate(self, counts: dict[str, int] | None = None) -> None:
        """Populate the world with creatures based on initial counts or world_config."""
        if counts is None:
            counts = self.world_config.get("initial_populations", {})
        for sp_key, count in counts.items():
            if sp_key not in self.species_data:
                continue
            sd = self.species_data.get(sp_key, {})
            sociality = sd.get("personality_defaults", {}).get("sociality", 0.5)
            if sociality >= 0.6 and count > 3:
                num_groups = max(1, count // 15)
                group_size = count // num_groups
                remainder = count % num_groups
                for g in range(num_groups):
                    cur_size = group_size + (1 if g < remainder else 0)
                    cx = self.rng.randint(20, self.world.width - 20)
                    cy = self.rng.randint(20, self.world.height - 20)
                    for _ in range(cur_size):
                        px = max(0, min(self.world.width - 1, cx + self.rng.randint(-4, 4)))
                        py = max(0, min(self.world.height - 1, cy + self.rng.randint(-4, 4)))
                        self.spawn_agent(sp_key, position=(px, py))
            else:
                for _ in range(count):
                    self.spawn_agent(sp_key)

    def _register_agent(self, agent: Agent) -> None:
        if agent._species_data is None:
            agent._species_data = self.species_data.get(agent.species_key, {})
        self.agents[agent.id] = agent
        self.agent_hash.insert(agent, *agent.position)

    def _register_carcass(self, carcass: Carcass) -> None:
        self.carcasses[carcass.id] = carcass
        self.carcass_hash.insert(carcass, *carcass.position)

    def _register_nest(self, nest: Nest) -> None:
        self.nests[nest.id] = nest
        self.nest_hash.insert(nest, *nest.position)

    # ------------------------------------------------------------------
    # Action dispatch
    # ------------------------------------------------------------------

    def _execute_action(
        self,
        agent: Agent,
        sd: dict,
        percepts: dict,
        new_agents: list,
        new_eggs: list,
        new_carcasses: list,
        new_nests: list,
    ) -> None:
        """Dispatch the agent's chosen action to the appropriate behavior."""
        action = agent.current_action
        if agent.forced_action:
            action = agent.forced_action

        if action == "REST":
            do_rest(agent, self.world, self.event_bus, self.rng)
        elif action == "SLEEP":
            do_sleep(agent, self.world, self.event_bus, self.rng)
        elif action == "WANDER":
            do_wander(agent, self.world, self.event_bus, self.rng)
        elif action in ("GRAZE", "BROWSE", "EAT_PLANT"):
            do_graze(agent, self.world, self.event_bus, sd, self.rng)
        elif action == "DRINK":
            do_drink(agent, self.world, self.event_bus, self.rng)
        elif action == "FLEE":
            do_flee(agent, percepts, self.world, self.event_bus, self.rng)
        elif action == "HIDE":
            do_hide(agent, self.world, self.event_bus, self.rng)
        elif action == "FOLLOW":
            do_follow(agent, percepts, self.world, self.event_bus, self.rng)
        elif action in ("HUNT", "CHASE", "STALK", "AMBUSH"):
            self._do_hunt_action(agent, percepts, sd, new_carcasses)
        elif action == "SCAVENGE":
            do_scavenge(agent, percepts, self.world, self.event_bus, self.rng)
            # Try eating a carcass at position
            for carcass in self.carcasses.values():
                if carcass.alive and carcass.position == agent.position:
                    do_eat_carcass(agent, carcass, self.world, self.event_bus, self.rng)
                    break
        elif action == "MIGRATE":
            do_migrate(agent, self.world, self.event_bus, self.rng)
        elif action == "MATE":
            self._do_mate_action(agent, sd, percepts, new_eggs, new_nests)
        elif action == "GUARD_NEST":
            nest = self.nests.get(agent.incubating_nest_id or "")
            do_guard_nest(agent, nest, self.world, self.event_bus, self.rng)
        elif action == "GUARD_OFFSPRING":
            offspring = [self.agents[oid] for oid in agent.offspring_ids if oid in self.agents]
            from prehistoric_sim.engine.reproduction import do_parental_care  # noqa: PLC0415
            do_parental_care(agent, offspring, self.world, self.event_bus, self.rng)
        else:
            do_wander(agent, self.world, self.event_bus, self.rng)

    def _do_hunt_action(
        self,
        predator: Agent,
        percepts: dict,
        sd: dict,
        new_carcasses: list,
    ) -> None:
        """Move toward prey and attempt a kill when in range."""
        prey_list = percepts.get("prey_visible", [])
        if not prey_list:
            # Move toward last known prey location or wander
            do_wander(predator, self.world, self.event_bus, self.rng)
            return

        from prehistoric_sim.engine.mind import _pick_best_prey  # noqa: PLC0415
        from prehistoric_sim.engine.behaviors import _move_toward  # noqa: PLC0415
        prey = _pick_best_prey(predator, prey_list, sd)
        if prey is None or not prey.alive:
            do_wander(predator, self.world, self.event_bus, self.rng)
            return

        dist = predator.distance_to(prey)
        if dist > 1.5:
            # Move toward prey
            _move_toward(predator, prey.position[0], prey.position[1], self.world,
                         speed_override=predator.max_speed)
        else:
            # Close enough — attempt kill
            carcass = attempt_hunt(predator, prey, self.world, self.event_bus, self.species_data, self.rng)
            if carcass:
                new_carcasses.append(carcass)
                # Remove killed prey from agents (will be cleaned up next tick)
                prey.alive = False

    def _do_mate_action(
        self,
        agent: Agent,
        sd: dict,
        percepts: dict,
        new_eggs: list,
        new_nests: list,
    ) -> None:
        """Handle mating behavior — find partner, court, mate, nest."""
        if len(self.agents) >= self.config.population_cap:
            do_wander(agent, self.world, self.event_bus, self.rng)
            return

        if not can_mate(agent, sd, self.world):
            do_wander(agent, self.world, self.event_bus, self.rng)
            return

        conspecifics = percepts.get("conspecifics", [])
        eligible = [a for a in conspecifics if a.is_adult_capable and can_mate(a, sd, self.world)]
        if not eligible:
            do_wander(agent, self.world, self.event_bus, self.rng)
            return

        from prehistoric_sim.engine.behaviors import _move_toward  # noqa: PLC0415
        partner = eligible[0]
        dist = agent.distance_to(partner)

        if dist > 2.0:
            _move_toward(agent, partner.position[0], partner.position[1], self.world)
            return

        # Attempt mating
        success = attempt_mating(agent, partner, self.world, sd, self.event_bus, self.rng, self.config.aging_scale)
        if not success:
            return

        from prehistoric_sim.engine.world import TICKS_PER_DAY  # noqa: PLC0415
        cooldown = max(48 * 8, int(60 * TICKS_PER_DAY / self.config.aging_scale))
        agent.reproduction_cooldown_ticks = cooldown
        partner.reproduction_cooldown_ticks = cooldown
        agent.drives.reproductive_urge = 0.0
        partner.drives.reproductive_urge = 0.0

        repro_type = sd.get("reproduction_type", "EGG_LAYING")
        if repro_type == "EGG_LAYING":
            # Build a nest and lay eggs
            nest = build_nest(agent, self.world, sd, self.event_bus, self.rng)
            new_nests.append(nest)
            eggs = lay_clutch(agent, nest, self.world, sd, self.event_bus, self.rng, self.config.aging_scale, self.species_data)
            new_eggs.extend(eggs)

    # ------------------------------------------------------------------
    # Population query
    # ------------------------------------------------------------------

    def census(self) -> dict[str, dict[str, int]]:
        """Return population counts by species and life stage."""
        counts: dict[str, dict[str, int]] = {}
        for agent in self.agents.values():
            sp = agent.species_key
            stage = agent.life_stage.value
            if sp not in counts:
                counts[sp] = {}
            counts[sp][stage] = counts[sp].get(stage, 0) + 1
        return counts

    def find_agent(self, name_or_id: str) -> Agent | None:
        """Find an agent by name or ID."""
        for a in self.agents.values():
            if a.id == name_or_id or (a.name and a.name.lower() == name_or_id.lower()):
                return a
        return None

    def population_by_species(self) -> dict[str, int]:
        """Total live agents per species."""
        counts: dict[str, int] = {}
        for a in self.agents.values():
            counts[a.species_key] = counts.get(a.species_key, 0) + 1
        return counts


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _agent_to_dict(a: Agent) -> dict:
    return {
        "id": a.id,
        "species_key": a.species_key,
        "name": a.name,
        "display_id": a.display_id,
        "position": list(a.position),
        "alive": a.alive,
        "life_stage": a.life_stage.value,
        "age_ticks": a.age_ticks,
        "birth_tick": a.birth_tick,
        "death_tick": a.death_tick,
        "cause_of_death": a.cause_of_death,
        "body_mass_kg": a.body_mass_kg,
        "max_speed": a.max_speed,
        "health": a.health,
        "energy": a.energy,
        "hydration": a.hydration,
        "stamina": a.stamina,
        "injury_level": a.injury_level,
        "pregnant": a.pregnant,
        "gestation_ticks_remaining": a.gestation_ticks_remaining,
        "reproduction_cooldown_ticks": getattr(a, "reproduction_cooldown_ticks", 0),
        "parent_ids": a.parent_ids,
        "offspring_ids": a.offspring_ids,
        "mate_id": a.mate_id,
        "current_action": a.current_action,
        "traits": {
            "boldness": a.traits.boldness,
            "aggression": a.traits.aggression,
            "curiosity": a.traits.curiosity,
            "sociability": a.traits.sociability,
            "size_factor": a.traits.size_factor,
            "speed_factor": a.traits.speed_factor,
            "metabolic_efficiency": a.traits.metabolic_efficiency,
        },
        "drives": {
            "hunger": a.drives.hunger,
            "thirst": a.drives.thirst,
            "fatigue": a.drives.fatigue,
            "fear": a.drives.fear,
            "reproductive_urge": a.drives.reproductive_urge,
            "social_need": a.drives.social_need,
            "curiosity": a.drives.curiosity,
            "parental_drive": a.drives.parental_drive,
        },
        "incubating_nest_id": a.incubating_nest_id,
        "group_id": a.group_id,
        "tracked": a.tracked,
        "possessed": a.possessed,
    }


def _egg_to_dict(e: Egg) -> dict:
    return {
        "id": e.id,
        "species_key": e.species_key,
        "parent_ids": e.parent_ids,
        "clutch_id": e.clutch_id,
        "nest_id": e.nest_id,
        "position": list(e.position),
        "alive": e.alive,
        "incubation_ticks_total": e.incubation_ticks_total,
        "incubation_ticks_remaining": e.incubation_ticks_remaining,
        "temperature_stress": e.temperature_stress,
        "hatched": e.hatched,
    }


def _nest_to_dict(n: Nest) -> dict:
    return {
        "id": n.id,
        "species_key": n.species_key,
        "owner_id": n.owner_id,
        "egg_ids": n.egg_ids,
        "guarded": n.guarded,
        "position": list(n.position),
        "alive": n.alive,
        "construction_complete": n.construction_complete,
    }


def _carcass_to_dict(c: Carcass) -> dict:
    return {
        "id": c.id,
        "species_key": c.species_key,
        "position": list(c.position),
        "alive": c.alive,
        "original_mass_kg": c.original_mass_kg,
        "mass_remaining": c.mass_remaining,
        "decay_progress": c.decay_progress,
        "nutrients_released": c.nutrients_released,
        "death_tick": c.death_tick,
        "cause_of_death": c.cause_of_death,
    }
