# Jurrasic-Era — Prehistoric Ecosystem Simulation (Hell Creek ~67 Ma)

A CLI-first, agent-based simulation of a Late Cretaceous ecosystem (Hell Creek formation, western North America, ~67 million years ago). Every creature is an independent, autonomous agent with its own physiological drives, local perception, spatial memory, and individual personality traits.

Nothing in the ecosystem is globally scripted. Hunting, herding, territorial disputes, mating, nesting, and population cycles emerge purely from bottom-up individual decisions and local interactions.

---

## Features

- **Full Creature Life Cycle**:
  - `EGG` / Conception $\to$ `HATCHLING` $\to$ `JUVENILE` $\to$ `SUBADULT` $\to$ `ADULT` $\to$ `SENESCENT` $\to$ `DEATH` $\to$ `CARCASS` $\to$ `DECOMPOSITION`.
  - Body mass, maximum speed, sensory ranges, and metabolic demands scale continuously across life stages.
  - Carcasses decompose over time, releasing nutrients into the soil to fertilize plant regrowth.
- **Utility AI Minds**:
  - Action selection driven by internal need curves: hunger, thirst, fatigue, fear, reproductive urge, social need, curiosity, and parental drive.
  - Local perception with sensory cone vision, hearing, and wind-biased smell.
  - Bounded spatial memory with temporal decay.
- **Multi-Strata Vegetation**:
  - Six vertical plant layers (ground ferns, cycads, early angiosperms, tree ferns, ginkgoes, conifers) with logistic regrowth modulated by seasons, weather, and soil nutrients.
- **Dynamic Climate & Hazards**:
  - Diurnal light cycles (dawn, day, dusk, night) and seasonal progression (Spring, Summer, Autumn, Winter).
  - Wildfires spreading with wind, droughts desiccating water bodies, and flash floods inundating floodplains.
- **Live Terminal User Interface (TUI)**:
  - Real-time event log rendered via Rich with color-coded categories and species glyphs (automatic ASCII fallback for standard terminals).
  - Non-blocking administrative REPL powered by `prompt_toolkit` and `patch_stdout`.
- **Bit-Exact Determinism & Replay**:
  - Full simulation trajectories reproducible via initial random seeds and timestamped command replay logs.

---

## Quickstart

### Installation

Requires Python 3.10+:

```bash
# Clone the repository
git clone https://github.com/example/jurassic-era.git
cd jurassic-era

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies in editable mode
pip install -e .
```

### CLI Entry Points

The simulation CLI is named `sim`:

```bash
# Run interactive live simulation with admin shell
sim run

# Run headless batch simulation for 15 days with specific seed
sim run --days 15 --seed 101 --batch

# Run with accelerated aging to observe full generational lifecycles
sim run --aging-scale 100.0 --days 30 --batch

# Replay a recorded simulation session from a command log
sim replay artifacts/command_log.json

# List all loaded species and their diets/traits
sim species list

# Validate YAML data definitions (15 species, 9 plants, world configs)
sim species validate

# View comprehensive engine architecture and design documentation
sim docs
```

---

## Admin Command Reference

During an interactive run (`sim run`), the bottom prompt accepts live admin commands without interrupting or dropping background event rendering:

| Command | Arguments | Description | Example |
| :--- | :--- | :--- | :--- |
| `spawn` | `<species> [count] [x] [y] [name]` | Spawn one or more creatures at coordinates or randomly | `spawn tyrannosaurus_rex 1 60 60 KingRex` |
| `kill` | `<target_id_or_name>` | Instantly kill creature and generate carcass | `kill KingRex` |
| `starve` | `<target_id_or_name>` | Deplete creature energy to zero | `starve edmo-000004` |
| `heal` | `<target_id_or_name>` | Restore full health, energy, and clear injuries | `heal KingRex` |
| `injure` | `<target_id_or_name> [amount]` | Inflict physical injury (0.0 to 1.0) | `injure KingRex 0.4` |
| `possess` | `<target_id_or_name>` | Take manual control of creature decision mind | `possess KingRex` |
| `unpossess` | `<target_id_or_name>` | Return creature to autonomous utility AI mind | `unpossess KingRex` |
| `act` | `<action>` | Command currently possessed creature to perform action | `act HUNT` |
| `inspect` | `<target_id_or_name>` | Display detailed vital stats, drives, traits, and memory | `inspect KingRex` |
| `name` | `<target_id_or_name> <new_name>` | Assign custom name to a creature | `name edmo-000001 Betsy` |
| `track` | `<target_id_or_name>` | Flag creature for verbose action tracking | `track Betsy` |
| `untrack` | `<target_id_or_name>` | Remove creature verbose tracking flag | `untrack Betsy` |
| `weather` | `<CLEAR\|RAIN\|STORM\|DROUGHT>` | Force weather condition | `weather DROUGHT` |
| `season` | `<SPRING\|SUMMER\|AUTUMN\|WINTER>` | Force change of in-world season | `season SUMMER` |
| `fire` | `<x> <y>` | Ignite wildfire at specified coordinates | `fire 50 50` |
| `flood` | `<x> <y>` | Trigger floodplain inundation at coordinates | `flood 30 30` |
| `pause` | *none* | Pause simulation time | `pause` |
| `resume` | *none* | Resume simulation time | `resume` |
| `speed` | `<multiplier>` | Adjust simulation tick rate (0.1x to 10.0x) | `speed 2.0` |
| `step` | `[ticks]` | Advance simulation by N ticks while paused | `step 48` |
| `stats` | *none* | Print current census, biomass totals, and carcass counts | `stats` |
| `save` | `<filename>` | Save full world snapshot to JSON file | `save hell_creek_day5.json` |
| `load` | `<filename>` | Load full world snapshot from JSON file | `load hell_creek_day5.json` |
| `clear_carcasses`| *none* | Remove all existing carcasses from the world | `clear_carcasses` |
| `help` | `[command]` | View command syntax and parameter details | `help spawn` |
| `quit` | *none* | Exit simulation | `quit` |

---

## Utility AI: Decision Architecture

Every decision cycle, an agent evaluates all viable actions in its behavioral repertoire. Each candidate action is scored by multiplying its primary drive pressure, environmental stimuli, and personality traits.

```python
# Simplified snippet of utility action scoring in engine/mind.py
def score_actions(agent, percepts, world, species_data):
    scores = []
    drives = agent.drives
    traits = agent.traits

    # 1. Immediate Survival: Flee from apex predators
    if drives.fear > 0.3 and percepts["predators_visible"]:
        score = drives.fear * 1.5 * (1.1 - traits.boldness)
        scores.append(("FLEE", score, "predator detected"))

    # 2. Hydration: Seek water when thirst exceeds threshold
    if drives.thirst > 0.4:
        score = drives.thirst * 1.2
        scores.append(("DRINK", score, "thirsty"))

    # 3. Nutrition: Graze on local plant layers if herbivore
    if drives.hunger > 0.3 and species_data["diet"] == "HERBIVORE":
        food_biomass = world.get_plant_biomass_total(*agent.position)
        score = drives.hunger * 1.0 * min(1.0, food_biomass)
        scores.append(("GRAZE", score, "hungry, plants available"))

    # Apply commitment bonus (+15%) to avoid behavior oscillation
    for action, score, reason in scores:
        if action == agent.current_action:
            score *= 1.15

    # Sort descending by utility score; execute highest
    return sorted(scores, key=lambda x: x[1], reverse=True)
```

---

## Adding a New Species

To introduce a new species, add a YAML file to `data/species/<species_key>.yaml`. No code modifications or new classes are required.

### Example: `data/species/anzu_wyliei.yaml`
```yaml
species_key: "anzu_wyliei"
common_name: "Anzu"
scientific_name: "Anzu wyliei"
diet: "OMNIVORE"
activity_pattern: "CREPUSCULAR"
reproduction_type: "EGG_LAYING"
body_mass_kg: 250.0
lifespan_years: 15.0
maturity_age_years: 3.0
max_speed_cells_per_tick: 5.5
vision_range_cells: 18.0
fov_degrees: 280.0
smell_range_cells: 12.0
hearing_range_cells: 15.0
breeding_season: "SPRING"
defense_type: "flee"
hunt_style: "pursuit"
min_clutch_size: 2
max_clutch_size: 5
incubation_days: 50.0
parental_care_days: 70.0
endothermic: true
prey_species:
  - "thescelosaurus"
  - "didelphodon"
  - "freshwater_turtle"
fear_species:
  - "tyrannosaurus_rex"
  - "dakotaraptor"
preferred_plant_layers:
  - 0
  - 1
  - 2
life_stages:
  hatchling_years: 0.3
  juvenile_years: 1.0
  subadult_years: 2.0
  senescent_start_years: 12.0
personality_defaults:
  aggression: 0.45
  boldness: 0.50
  curiosity: 0.70
  sociality: 0.60
  metabolic_efficiency: 1.0
description: "Large caenagnathid oviraptorosaur ('Chicken from Hell'), omnivorous and active at dawn and dusk."
```

Validate new species definitions immediately using:
```bash
sim species validate
```

---

## Theme Legend

### Species Glyphs & Colors

| Species | Key | Diet | Color | Emoji | ASCII Glyph |
| :--- | :--- | :--- | :--- | :---: | :---: |
| **Tyrannosaurus rex** | `tyrannosaurus_rex` | Carnivore | Bold Red | 🦖 | `T` |
| **Dakotaraptor** | `dakotaraptor` | Carnivore | Bold Orange | 🦕 | `D` |
| **Acheroraptor** | `acheroraptor` | Carnivore | Bold Yellow | 🦴 | `a` |
| **Anzu wyliei** | `anzu_wyliei` | Omnivore | Bold Magenta | 🪶 | `z` |
| **Triceratops** | `triceratops` | Herbivore | Bold Green | 🦏 | `C` |
| **Edmontosaurus** | `edmontosaurus` | Herbivore | Bold Cyan | 🐊 | `E` |
| **Ankylosaurus** | `ankylosaurus` | Herbivore | Bold Blue | 🛡️ | `K` |
| **Pachycephalosaurus** | `pachycephalosaurus` | Herbivore | Bold Violet | 🪨 | `P` |
| **Thescelosaurus** | `thescelosaurus` | Herbivore | Bright Green | 🦎 | `h` |
| **Deinosuchus** | `deinosuchus` | Carnivore | Bold Dark Green| 🐊 | `X` |
| **Freshwater Fish** | `freshwater_fish` | Omnivore | Cyan | 🐟 | `f` |
| **Freshwater Turtle** | `freshwater_turtle` | Omnivore | Dark Olive Green| 🐢 | `u` |
| **Quetzalcoatlus** | `quetzalcoatlus` | Carnivore | Bold Sky Blue | 🦅 | `Q` |
| **Didelphodon** | `didelphodon` | Omnivore | Grey | 🐀 | `m` |
| **Insect Swarm** | `insect_swarm` | Herbivore | Yellow | 🦟 | `i` |

### Category Glyphs

| Event Subcategory | Category | Emoji | ASCII | Description |
| :--- | :--- | :---: | :---: | :--- |
| `BIRTH` | Lifecycle | 🐣 | `+` | Live birth or admin spawn |
| `HATCHING` | Lifecycle | 🐣 | `*` | Egg incubation completes |
| `DEATH` | Lifecycle | 💀 | `X` | Starvation, thirst, predation, age |
| `STAGE_CHANGE` | Lifecycle | 📈 | `^` | Hatchling $\to$ Juvenile $\to$ Adult |
| `MATING` | Lifecycle | 💕 | `<3` | Courtship and copulation |
| `EGG_LAID` | Lifecycle | 🥚 | `o` | Clutch deposited in nest |
| `CARCASS_FORMED`| Lifecycle | ☠️ | `~` | Body mass remains on terrain |
| `HUNT_SUCCESS` | Interaction | 🩸 | `!` | Predator successfully brings down prey |
| `HUNT_FAIL` | Interaction | 💨 | `x` | Prey escapes predator pursuit |
| `FIGHT` | Interaction | ⚔️ | `v` | Intraspecific territorial conflict |
| `INJURY` | Interaction | 🩸 | `!` | Physical injury from attack or defense |
| `DAWN` / `DUSK` | World | 🌅 / 🌆 | `:)` | Diurnal cycle transition |
| `WEATHER_START` | World | ⛈️ | `***` | Storm, rain, or drought begins |
| `FIRE_SPREAD` | World | 🔥 | `###` | Wildfire spreads to adjacent cells |
| `POP_CAP` | System | ⚠️ | `[!]` | Ecosystem population cap warning |

---

## Assumptions & Design Choices

All design assumptions recorded during development:
1. **Simulation Tick Scale**: 1 in-world tick equals 30 minutes. 48 ticks comprise 1 in-world 24-hour day.
2. **Spatial Grid Dimensions**: Default Hell Creek world grid is $120 \times 120$ cells ($\sim 6$ km$^2$).
3. **Aging Acceleration Factor**: Default aging scale is $50.0$ (allows observing full creature lifespans within manageable human run durations; e.g. 15–30 days).
4. **Allometric Metabolic Scaling**: Energy expenditure follows mass-specific Kleiber scaling $M^{-0.25}$. Smaller organisms experience higher fractional turnover rates.
5. **Nocturnal Partitioning**: Didelphodon and small mammals exhibit nocturnal activity patterns (rest during day, active at night), emerging when predatory dinosaurs sleep.
6. **Defensive Morphology**: Heavily armored herbivores (*Ankylosaurus*, *Triceratops*) can inflict severe, debilitating counter-injuries to apex predators (*T. rex*, *Dakotaraptor*) upon hunt attempts.
7. **Carrying Capacity Bounds**: Hard population cap defaults to 1,500 creatures. Reproductive cooldowns and density-dependent gestation bounds naturally prevent runaway population explosions.

---

## Further Planned Work

The GUI and first perspective 3D viewport are implemented. Future work includes richer GPU-rendered meshes, neural or evolutionary minds, speciation, and continuous terrain and fluid simulation.

## Phase 3: Perspective 3D View (first milestone)

The GUI now includes a perspective 3D view over the existing ecological grid. Press **V** to switch between the isometric and 3D views. In 3D, middle/right-drag orbits the camera, the mouse wheel zooms, and WASD changes camera angle. Select a creature and use WASD to steer it while it is possessed. This is the first renderer milestone: simulation state, saves, and ecological rules remain grid based while the viewport gains perspective terrain, elevation, vegetation, and creature forms.

The next 3D work can replace the software-projected low-poly meshes with a dedicated GPU scene renderer and richer creature models without changing the simulation API.

---

## Demo Walkthrough: A Typical 5-Day Simulation

When launching `sim run`, watch for the following emergent ecological sequence:

1. **Day 1 (Spring Morning — The Great Dispersion)**:
   - *Edmontosaurus* and *Triceratops* assemble into clustered herds on the fertile floodplains and begin grazing on ground ferns.
   - *Didelphodon* seeks burrow shelters beneath tree roots as daytime begins.
   - *Acheroraptors* stalk young *Thescelosaurus* near stream edges.
2. **Day 2 (Predation and Carcass Deposition)**:
   - A *Tyrannosaurus rex* ambushes an isolated *Edmontosaurus*, securing a kill.
   - Scavengers (*Didelphodon*, juvenile raptors) detect carcass scent on the wind and approach downwind.
   - Carcass decomposition fertilizes surrounding soil, causing a visible surge in ground fern biomass.
3. **Day 3 (Wildfire Hazard)**:
   - A thunderstorm triggers lightning that ignites dry conifers on the rocky hills.
   - Herds sound alarm calls and flee south toward the river.
   - Ash fertilization replenishes soil nutrients across burned sectors.
4. **Day 4 (Courtship & Nesting)**:
   - High nutrition triggers reproductive urge in adult hadrosaurs.
   - Mating pairs build mound nests and deposit viable clutches of eggs.
   - Parents guard the nests against marauding oviraptorosaurs (*Anzu*).
5. **Day 5 (The New Generation)**:
   - Clutches hatch into vulnerable *Edmontosaurus* hatchlings that follow their parents for protection.
   - Ecosystem stabilizes with a sustainable pyramid of herbivore biomass heavily exceeding carnivore biomass.
