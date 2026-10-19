# Technical Design Document: Prehistoric Ecosystem Simulation (Phase 1)

## 1. System Architecture

The Prehistoric Ecosystem Simulation is built as a strictly decoupled, agent-based modeling engine with terminal user interface (TUI) visualization and administrative observability.

```
┌─────────────────────────────────────────────────────────────┐
│                       CLI / Admin Shell                     │
│      (Typer CLI, prompt_toolkit REPL, patch_stdout)         │
└──────────────────────────────┬──────────────────────────────┘
                               │ commands
                               ▼
┌──────────────────┐    ┌─────────────────────────────────────┐
│    UI / Render   │◄───┤           Simulation Engine         │
│  (Rich Console,  │    │  (World, Entities, Mind, Lifecycle, │
│  Theme, Glyphs)  │    │   Metabolism, Combat, Reproduction) │
└──────────────────┘    └──────────────────┬──────────────────┘
         ▲                                 │
         │          Event Bus              │
         └─────────────────────────────────┘
```

### Architectural Boundaries
1. **Decoupled Engine Core (`prehistoric_sim.engine`)**:
   - The engine contains zero imports from `ui`, `admin`, `cli`, or `io`.
   - All state transitions occur via internal tick updates.
   - The engine communicates with external systems purely via typed, immutable `Event` objects published onto an `EventBus`.
2. **Event-Driven UI (`prehistoric_sim.ui`)**:
   - `EventRenderer` subscribes to the `EventBus` with configurable verbosity (0–3) and filtering (species, category, follow ID).
   - Renders formatted, color-coded event feeds using Rich panels, rules, and emojis (with automatic fallback to ASCII on terminals lacking UTF-8 support).
3. **Admin REPL & Command Dispatcher (`prehistoric_sim.admin`)**:
   - Built on `prompt_toolkit` using `patch_stdout` to enable concurrent real-time rendering alongside non-blocking interactive command prompt inputs.
   - All admin actions (spawn, kill, heal, starve, possess, set weather, inspect, snapshot save/load) route through `Simulation.apply_admin_command()`.
4. **Data-Driven Configuration (`prehistoric_sim.io`)**:
   - 15 Late Cretaceous species and 9 Mesozoic plant types configured purely via declarative YAML files in `data/`.

---

## 2. Mathematical Models & Ecological Dynamics

### 2.1 Utility AI Mind & Action Selection
Creatures do not follow hardcoded decision trees. Every creature independently computes utility scores across candidate actions each decision cycle ($u \in [0, 1]$).

#### Drive Equations
Drives represent physiological and psychological pressures bounded in $[0, 1]$:
- **Hunger ($D_{\text{hunger}}$)**:
  $$D_{\text{hunger}} = 1.0 - \text{energy}$$
- **Thirst ($D_{\text{thirst}}$)**:
  $$D_{\text{thirst}} = 1.0 - \text{hydration}$$
- **Fear ($D_{\text{fear}}$)**:
  Decays over time ($\Delta D_{\text{fear}} = -0.05/\text{tick}$) and surges upon predator detection:
  $$D_{\text{fear}} = \min\left(1.0, D_{\text{fear}} + \sum_{p \in \text{predators}} \max\left(0.0, 1.0 - \frac{\text{dist}(p)}{R_{\text{vision}}}\right)\right)$$
- **Reproductive Urge ($D_{\text{repro}}$)**:
  During breeding season, if energy $> 0.45$ and cooldown $= 0$:
  $$D_{\text{repro}}(t+1) = \min(1.0, D_{\text{repro}}(t) + 0.003)$$
- **Social Need ($D_{\text{social}}$)**:
  Builds up when isolated and depletes when conspecifics are within proximity:
  $$D_{\text{social}}(t+1) = \begin{cases} \max(0.0, D_{\text{social}}(t) - 0.02) & \text{if } N_{\text{conspecifics}} > 0 \\ \min(1.0, D_{\text{social}}(t) + 0.01) & \text{otherwise} \end{cases}$$

#### Action Utility Scoring
Each candidate action $A$ receives a score $S(A)$ based on drive pressures, sensory stimulus, and personality traits:
$$S(\text{FLEE}) = D_{\text{fear}} \cdot 1.5 \cdot (1.1 - \text{boldness})$$
$$S(\text{DRINK}) = D_{\text{thirst}} \cdot 1.2 \cdot \left(1.0 - \frac{\text{dist}(\text{water})}{R_{\text{vision}}}\right)$$
$$S(\text{GRAZE}) = D_{\text{hunger}} \cdot 1.0 \cdot \min(1.0, B_{\text{local}})$$
$$S(\text{HUNT}) = D_{\text{hunger}} \cdot (0.6 + 0.4 \cdot \text{aggression}) \cdot \left(1.0 - \frac{\text{dist}(\text{prey})}{R_{\text{vision}}}\right)$$
$$S(\text{MATE}) = D_{\text{repro}} \cdot 0.85 \quad (\text{if adult and partner eligible})$$

#### Commitment Bonus & Hysteresis
To prevent unrealistic behavior oscillating ("jitter") between near-equal priorities, the currently active action receives a commitment bonus:
$$S(A_{\text{current}}) = S(A_{\text{current}}) \cdot 1.15$$

---

### 2.2 Metabolic Scaling & Kleiber's Law
Metabolic rates follow Kleiber's Law, where whole-organism metabolic rate scales as $M^{0.75}$. Consequently, **mass-specific metabolic rate** (energy consumed per kilogram of body mass per unit time) scales as:
$$\text{BMR}_{\text{specific}} \propto M^{-0.25}$$

This fundamental allometric scaling explains why small creatures (e.g. *Didelphodon*, 5 kg) burn energy at a much higher fractional rate than giant sauropods or hadrosaurs (*Edmontosaurus*, 4,000 kg).

#### Basal Energy Burn Formula
$$\Delta E_{\text{basal}} = \left(M^{-0.25} \cdot 0.0008\right) \cdot \mu_{\text{thermo}} \cdot \mu_{\text{action}} \cdot \mu_{\text{efficiency}}$$

Where:
- $\mu_{\text{thermo}}$: $1.0$ for endotherms (*T. rex*, Hadrosaurs, Mammals); for ectotherms (*Deinosuchus*, Turtles), scaled by ambient temperature deviation from $30^\circ\text{C}$:
  $$\mu_{\text{thermo, ecto}} = 0.35 \cdot \left(1.0 + 0.03 \cdot (T_{\text{ambient}} - 25.0)\right)$$
- $\mu_{\text{action}}$: Energy expenditure multiplier based on exertion:
  - `SLEEP`: $0.4\times$
  - `REST`: $0.6\times$
  - `WANDER`: $1.0\times$
  - `GRAZE` / `BROWSE`: $1.1\times$
  - `DRINK`: $0.8\times$
  - `CHASE` / `HUNT`: $2.5\times$
  - `FLEE`: $2.2\times$
  - `FIGHT`: $2.8\times$

#### Hydration Depletion Formula
$$\Delta H = \left(0.0006 + M^{-0.25} \cdot 0.0005\right) \cdot \mu_{\text{temp}} \cdot \mu_{\text{action}}$$
Where $\mu_{\text{temp}} = 1.0 + \max(0.0, (T_{\text{ambient}} - 28.0) \cdot 0.04)$.

---

### 2.3 Spatial Partitioning (Spatial Hash)
Global distance searches among $N$ agents require $O(N^2)$ distance checks per tick. In an ecosystem of 1,500 agents, $N^2 = 2,250,000$ operations per tick, causing severe frame drops.

#### Spatial Hash Grid
The world is partitioned into a uniform 2D grid with bucket cell size $C = 10$:
$$\text{BucketKey}(x, y) = \left(\lfloor x / C \rfloor, \lfloor y / C \rfloor\right)$$

- **Insertion / Movement**: $O(1)$ amortized dictionary lookup and bucket update.
- **Radial Queries**: For radius $R$, only buckets within $\lceil R / C \rceil$ cells are scanned:
  $$\text{Complexity: } O\left(\left(\frac{2R}{C} + 1\right)^2 \cdot \rho\right)$$
  Where $\rho$ is local entity density.
- **Deterministic Traversal**: Bucket contents are sorted by `entity.id` on query resolution to guarantee 100% deterministic decision order across random seed replays.

---

### 2.4 Multi-Layer Plant Regrowth & Carrying Capacity
Vegetation is represented as a 3D NumPy tensor of shape $(6, H, W)$ spanning six vertical strata:
- Layer 0: Ground ferns & mosses ($<0.5$ m)
- Layer 1: Cycads & low shrubs ($0.5–1.5$ m)
- Layer 2: Early flowering angiosperms ($1.5–3.0$ m)
- Layer 3: Tree ferns ($3.0–6.0$ m)
- Layer 4: Ginkgoes ($6.0–12.0$ m)
- Layer 5: Tall conifers ($>12.0$ m)

#### Logistic Growth Equation
For cell $(x, y)$ and layer $L$:
$$\frac{dB_L}{dt} = r_L \cdot B_L \cdot \left(1 - \frac{B_L}{K_L(T)}\right) \cdot \mu_{\text{season}} \cdot \mu_{\text{weather}} \cdot \mu_{\text{nutrient}}$$

Where:
- $K_L(T)$ is the carrying capacity of layer $L$ on terrain type $T$.
- $\mu_{\text{season}}$: Spring ($1.4\times$), Summer ($1.0\times$), Autumn ($0.6\times$), Winter ($0.2\times$).
- $\mu_{\text{weather}}$: Rain ($1.4\times$), Drought ($0.1\times$).
- $\mu_{\text{nutrient}} = 0.5 + 0.5 \cdot \text{Nutrients}(x, y)$.

#### Nutrient Cycling
- Living vegetation extracts nutrients proportionally to growth.
- Carcasses deposited on soil decompose over time, releasing nutrients in a Gaussian radius around the carcass.
- Wildfires consume plant biomass in layers 0–2, releasing instant ash fertilization into the soil.

---

### 2.5 Combat, Hunting, and Defense Resolution

#### Hunt Probability Model
Hunt success combines speed ratio, predator mass advantage, predator stamina, prey vigilance, terrain visibility, and prey life stage:
$$P(\text{kill}) = \left(w_1 \sigma(\Delta v) + w_2 \sigma(\Delta m) + w_3 S_{\text{pred}} + w_4 V_{\text{terrain}} + w_5 (1 - \text{vigilance}) + w_6 \text{stage}\right) \cdot G_{\text{prey}}$$
Where:
- $\sigma(x) = \frac{1}{1 + e^{-k x}}$ is the sigmoid scaling function.
- $G_{\text{prey}}$ is group defense factor ($0.7$ if prey has active herd cohesion).

#### Defensive Counter-Attacks
Prey species with specialized defensive morphologies can injure the predator even during failed or successful attacks:
- **Ankylosaurus (tail club)**: $40\%$ chance to inflict $0.10–0.40$ injury to predator.
- **Triceratops (horn charge)**: $30\%$ chance to inflict $0.05–0.25$ injury to predator.
- Injured predators suffer reduced top speed and increased metabolic cost until healed through resting.

---

## 3. Concurrency, Replay & Determinism

### 3.1 Bit-Exact Seed Reproducibility
The simulation achieves bit-exact reproducibility across runs using:
1. **Isolated SimRNG**: Encapsulates both NumPy BitGenerator (`PCG64`) and Python `random.Random` instances initialized from a single integer seed.
2. **Deterministic Entity IDs**: Sequential hexadecimal IDs generated per simulation run (`reset_id_counter(0)`), avoiding non-deterministic `uuid4` entropy.
3. **Sorted Spatial Iteration**: All spatial queries sort candidates by deterministic entity IDs before returning, preventing hash-seed randomization artifacts.
4. **Command Log Architecture**: All administrative interventions are recorded as timestamped command records. Replaying a session consists of instantiating the simulation with the initial seed and applying logged admin commands at their exact historical ticks.

---

## 4. Performance & Scalability Trade-Offs

| Component | Brute Force Complexity | Simulation Complexity | Optimization Implemented |
| :--- | :--- | :--- | :--- |
| **Neighbor Sensing** | $O(N^2)$ per tick | $O(N \cdot k)$ | Spatial hash with bucket cell size $10$ |
| **Pathfinding** | $O(W \cdot H)$ full Dijkstra | $O(1)$ directional step | Gradient descent / directional ray stepping |
| **Terrain / Plant Updates** | $O(H \cdot W \cdot L)$ in Python loops | Vectorized NumPy | In-place NumPy slicing and arithmetic |
| **TUI Rendering** | Blocking terminal redraw | Decoupled Event Stream | Terminal output throttled by event category filters |
