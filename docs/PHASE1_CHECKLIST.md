# Phase 1 Implementation Checklist

> **Living document** — tick items as they are completed. Update notes if scope changes.  
> Last updated: Phase 1 build

---

## Sub-Phase 1: Planning, Skeleton, Config, Loaders

- [x] Create `docs/WORLD_ELEMENTS.md`
- [x] Create `docs/SPECIES_CHECKLIST.md`
- [x] Create `docs/PHASE1_CHECKLIST.md` (this file)
- [x] Create project directory layout as specified
- [x] Write `pyproject.toml` with all dependencies and entry points
- [x] Write `requirements.txt` (pinned)
- [x] Write `src/prehistoric_sim/engine/rng.py` — single seeded RNG wrapper
- [x] Write `src/prehistoric_sim/io/species_loader.py` — YAML species schema, load, validate
- [x] Write `src/prehistoric_sim/io/plant_loader.py` — YAML plant schema, load
- [x] Create all species YAML files (`data/species/*.yaml`) for all 13 animal types
- [x] Create all plant YAML files (`data/plants/*.yaml`)
- [x] Create `data/worlds/hell_creek.yaml` — world config
- [x] Create `data/theme.yaml` — colors, glyphs, styles
- [x] Write `tests/test_species_loader.py` — validation pass/fail cases
- [x] Verify: `python -m pytest tests/test_species_loader.py -v`

## Sub-Phase 2: World Generation

- [x] Write `src/prehistoric_sim/engine/world.py`
  - [x] Grid class (2D numpy array, configurable WxH)
  - [x] Procedural terrain generation (seeded noise + rules)
  - [x] At least one river, 2+ lakes, swamp areas, forest patches, open woodland, floodplain, rocky hills
  - [x] Water grid (depth per cell)
  - [x] Plant biomass arrays (per layer, per cell)
  - [x] Climate / time state (tick, day, season, temperature, wind)
  - [x] Nutrient grid
  - [x] Terrain movement cost table
  - [x] Terrain visibility modifier table
  - [x] Plant logistic regrowth per tick (seasonal, nutrient-modulated)
  - [x] Weather state machine (rain, drought, storm, flood, fire)
  - [x] Water level changes with rain/drought
- [x] Write `src/prehistoric_sim/engine/spatial.py` — spatial hash grid, query by radius, query by cone
- [x] Write `tests/test_spatial.py` — correctness, radius, cone, no O(n^2)
- [x] Write `tests/test_world.py` — terrain generates correctly, plants regrow, nutrients cycle
- [x] Verify world generation with quick visual dump

## Sub-Phase 3: Entities, Metabolism, Life Stages, Event Bus

- [x] Write `src/prehistoric_sim/engine/entities.py`
  - [x] `Entity` base dataclass (id, position, alive)
  - [x] `Agent` (species, name, age, life_stage, health, energy, hydration, traits, drives, parents, offspring, action, cause_of_death)
  - [x] `Egg` (species, parent_ids, incubation_remaining, temperature_stress, alive)
  - [x] `Nest` (species, owner_id, egg_ids, guarded, location)
  - [x] `Carcass` (species, mass_remaining, decay_progress, nutrients_released)
  - [x] `PlantPatch` (convenience wrapper if needed)
  - [x] `FishSchool` (water_body_id, biomass)
  - [x] `InsectSwarm` (cell, biomass)
- [x] Write `src/prehistoric_sim/engine/lifecycle.py`
  - [x] Life stage enum: CONCEPTION, EGG, HATCHLING, JUVENILE, SUBADULT, ADULT, SENESCENT
  - [x] Aging per tick with `aging_scale`
  - [x] Stage transitions with event emission
  - [x] Smooth growth scaling (size, speed, strength, energy needs)
  - [x] Death handling: record cause, convert to Carcass
  - [x] Decomposition tick on Carcass, nutrient return
- [x] Write `src/prehistoric_sim/engine/events.py`
  - [x] `EventBus` with subscribe / emit
  - [x] `Event` dataclasses for every category: LIFECYCLE, DECISION, INTERACTION, WORLD, ADMIN, SYSTEM
  - [x] Every event has: tick, category, subcategory, actors (list of ids), position, payload dict
- [x] Write basic herbivore-only ecosystem integration test (spawn herbivores, run 100 ticks, check they eat and live)
- [x] Write `tests/test_lifecycle.py` — every stage transition, death, decomposition
- [x] Write `tests/test_metabolism.py` — energy sanity (Kleiber scaling)

## Sub-Phase 4: Event Renderer and Live CLI Display

- [x] Write `src/prehistoric_sim/ui/theme.py` — load `data/theme.yaml`, provide style lookup
- [x] Write `src/prehistoric_sim/ui/renderer.py`
  - [x] Subscribe to EventBus; format each event category with rich styles
  - [x] Species color per name rendered bold in species color
  - [x] Category glyphs and colors from theme
  - [x] Compact timestamp prefix `D12 06:30 Spring`
  - [x] Major event banners (death of large animal, extinction, disaster)
  - [x] ASCII glyph fallback flag
  - [x] `--no-color` mode support
  - [x] Decision change format: `Rex-3 chose HUNT (0.82) over REST (0.41) ...`
- [x] Write `src/prehistoric_sim/ui/dashboard.py`
  - [x] Population table by species and stage with colored bars
  - [x] World summary panel (day, season, weather, temperature, biomass, carcasses, births, deaths)
  - [x] Configurable interval (default 1 in-world day)
  - [x] `dashboard` command triggers on-demand
- [x] Write `tests/test_renderer.py` — no crash for any event type, both color and no-color modes
- [x] Verify: run 10 ticks with herbivore ecosystem, see styled output

## Sub-Phase 5: Perception, Memory, Utility Mind, Group Behavior

- [x] Write `src/prehistoric_sim/engine/mind.py`
  - [x] Drives: hunger, thirst, fatigue, fear, reproductive_urge, social_need, curiosity, parental_drive
  - [x] Drive update per tick (decay, buildup)
  - [x] Perception: vision cone (range, FOV, night penalty, vegetation occlusion), smell radius (wind bias), hearing radius
  - [x] Bounded memory: known water, foraging patches, predator sightings (with decay), nest location, kin positions
  - [x] Candidate action scoring: utility function using drives × percepts × personality × life_stage × commitment_bonus
  - [x] Decision selection: top scored + small noise
  - [x] Decision record: top 3 options with scores and reasons
  - [x] Commitment bonus (hysteresis to prevent flip-flopping)
  - [x] Activity period enforcement (diurnal/nocturnal/crepuscular)
- [x] Write `src/prehistoric_sim/engine/behaviors.py`
  - [x] REST / SLEEP
  - [x] WANDER
  - [x] GRAZE / BROWSE (consume plant biomass)
  - [x] DRINK (requires water cell adjacency)
  - [x] FLEE (target = threat, max speed)
  - [x] HIDE (seek dense vegetation)
  - [x] FOLLOW / LEAD (cohesion, separation, alignment rules)
  - [x] ALARM_CALL (range-based propagation)
  - [x] SCAVENGE (approach carcass)
  - [x] EAT (consume carcass)
  - [x] MIGRATE (seasonal, directional)
- [x] Group behavior: herds emerge from cohesion/separation/alignment; no central controller
- [x] Write `tests/test_mind.py` — perception limits (range and FOV), memory decay, scoring
- [x] Verify: herbivore herds form; nocturnal creatures (Didelphodon) more active at night

## Sub-Phase 6: Predators, Hunting, Combat, Carcasses, Scavenging

- [x] Write `src/prehistoric_sim/engine/combat.py`
  - [x] Hunt success formula: speed ratio, stamina, terrain, prey group size, prey vigilance, size
  - [x] Chase: costs stamina per tick; predator abandons if expected gain < threshold
  - [x] Injuries: reduce speed, raise energy cost; heal over time
  - [x] Kills: create Carcass; eating takes time, can be interrupted
  - [x] Ankylosaurus tail-club: heavy injury on predator
  - [x] Triceratops charge: injury on attacker
  - [x] Herd defense: group size reduces hunt success probability
- [x] Add HUNT, STALK, CHASE, AMBUSH, FIGHT actions to `behaviors.py`
- [x] Add predator species to world; verify hunting events appear in display
- [x] Scavenging behavior: detect carcass by smell, approach, displace weaker scavengers
- [x] Write `tests/test_combat.py` — hunt resolution, stamina drain, injury, kill→carcass pipeline
- [x] Verify: T. rex hunts Edmontosaurus; Quetzalcoatlus scavenges; nutrient cycle completes

## Sub-Phase 7: Reproduction — Full Life Cycle Loop

- [x] Write `src/prehistoric_sim/engine/reproduction.py`
  - [x] Mating conditions: mature, healthy, energy > threshold, mate in perception range, correct season
  - [x] Courtship display action (scored by reproductive urge)
  - [x] Egg-laying species: nest construction, clutch laid, incubation ticks
  - [x] Incubation: temperature effects, guarding, predator raid events
  - [x] Hatching: Egg → Agent(HATCHLING)
  - [x] Live-bearing: gestation ticks on female Agent; BIRTH event spawns newborn
  - [x] Parental care: parent stays near offspring, feeds/defends; duration from species config
  - [x] Neonatal behavior: follows parent, cannot hunt/breed
  - [x] Dispersal at SUBADULT
  - [x] Full inheritance of traits with mutation
- [x] Verify end-to-end for at least 3 species: T. rex (egg-layer), Didelphodon (live-bearer), turtle (egg-layer aquatic)
- [x] Write `tests/test_reproduction.py` — mating, clutch, incubation, hatch, live birth, parental care

## Sub-Phase 8: Weather and Hazards

- [x] Weather state machine in `world.py` (already stubbed) — flesh out transitions
- [x] Rain: plant growth boost, river rise, mud penalty
- [x] Storm: lightning → wildfire trigger; heavy rain; visibility penalty
- [x] Drought: accelerated evaporation; plant growth penalty
- [x] Flood: water cell expansion; small creature drowning risk
- [x] Wildfire: cell-by-cell burn; wind bias; escape behavior; creature death if caught; plant reset
- [x] Creature behavioral responses: flee fire, seek water in drought, shelter in storm
- [x] Write `tests/test_hazards.py` — fire spreads, drought kills plants, flood expands water

## Sub-Phase 9: Admin Console

- [x] Write `src/prehistoric_sim/admin/commands.py`
  - [x] `spawn` (creature, plant, carcass, nest, egg, water, hazard)
  - [x] `name`, `unname`
  - [x] `inspect`, `story`, `list`, `find`, `census`
  - [x] `track`, `untrack`
  - [x] `kill`, `heal`, `injure`, `feed`, `water_cmd`, `rest_cmd`
  - [x] `set` (energy, hydration, age, stage, health, drive, trait)
  - [x] `teleport`, `move`
  - [x] `possess`, `release`, `act`
  - [x] `force`
  - [x] `breed`, `lay_egg`, `hatch_egg`
  - [x] `age_up`
  - [x] `pause`, `resume`, `step`, `speed`, `fastforward`, `set_time`, `set_season`, `set_weather`
  - [x] `save`, `load`, `record`, `replay`
  - [x] `filter`, `dashboard_cmd`, `map_cmd`
  - [x] `quit`
  - [x] `help` — styled help for every command
  - [x] Unknown command → helpful error, no crash
- [x] Write `src/prehistoric_sim/admin/console.py` — prompt_toolkit integration, patch_stdout, tab completion
- [x] Write `tests/test_admin.py` — every command including bad input

## Sub-Phase 10: Full Species Roster and Balancing

- [x] All 13 animal species YAML files complete and validated
- [x] All plant species YAML files complete
- [x] Population balance: herbivore biomass > carnivore biomass in stable ecosystem
- [x] Write `scripts/validate_ecosystem.py` — validation script: full life cycle, herds form, nocturnal, biomass ratio, stability
- [x] Tune defaults until `--days 365` run is stable (no collapse, no explosion)
- [x] Document tuning decisions in Assumptions section of README

## Sub-Phase 11: Logging, Snapshots, Replay

- [x] Write `src/prehistoric_sim/io/event_log.py`
  - [x] JSONL event writer (unstyled, one event per line)
  - [x] Command log writer (replayable)
  - [x] CSV summary writer (populations, births, deaths, causes at run end)
  - [x] Log file under `outputs/<run_id>/events.jsonl`
- [x] Snapshot: `save <file>` serializes full simulation state to JSON; `load <file>` restores
- [x] Replay: `sim replay <commands.log>` feeds command log into fresh simulation
- [x] Determinism test: same seed + same command log → identical results
- [x] Write `tests/test_determinism.py` — seed replay gives identical event sequence

## Sub-Phase 12: Documentation and Final Polish

- [x] Write `README.md`
  - [x] Overview and install instructions
  - [x] How to run (all CLI entry points)
  - [x] Admin console command reference
  - [x] How the mind works (utility AI)
  - [x] How to add a species
  - [x] Event display legend (color and glyph key)
  - [x] Known limitations
  - [x] Assumptions section
  - [x] Phase 2 roadmap
- [x] Write `DESIGN.md` — architecture overview, utility function details
- [x] Update `docs/PHASE1_CHECKLIST.md` with final true state
- [x] Run full test suite: `python -m pytest tests/ -v`
- [x] Run validation script: `python scripts/validate_ecosystem.py`
- [x] Demo walkthrough documented in README

---

## Notes

- **Aging scale default:** 50 (1 real-time second ≈ 50 in-world ticks of aging)
- **Population cap default:** 1500 agents total
- **World size default:** 120×120 cells
- **Tick = 30 in-world minutes** → 48 ticks/day
