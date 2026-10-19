# World Elements Catalogue — Hell Creek Late Cretaceous Ecosystem

> **Period:** Late Cretaceous, ~67 Ma  
> **Location:** Western North America (Hell Creek Formation)  
> **Status:** Phase 1 design document

---

## A. Living Elements

### A1. Animals

#### Apex Predators

| Name | Key Properties | Affects | Affected By | Phase 1 |
|------|---------------|---------|-------------|---------|
| Tyrannosaurus rex | Mass 8000 kg, binocular vision 40 cells, smell 20 cells, max speed 6 m/s (burst), solitary or pair | Prey population, scavenger competition, terrain utilisation | Hunger, injury, season, prey density, mate presence | ✅ |
| Deinosuchus (crocodilian) | Mass 2000 kg, aquatic ambush, low mobility on land, patient wait strategy, ectotherm | Aquatic prey, drinking herbivores at water edges | Water depth, temperature, hunger, prey proximity | ✅ |

#### Mesopredators

| Name | Key Properties | Affects | Affected By | Phase 1 |
|------|---------------|---------|-------------|---------|
| Dakotaraptor (dromaeosaur) | Mass 75 kg, pack/pair hunter, high speed 12 m/s, slashing attack, feathered | Small to medium prey, egg raiding, group coordination | Pack cohesion, hunger, fear of T. rex | ✅ |
| Acheroraptor (small dromaeosaur) | Mass 25 kg, pair hunter, fast, agile, feathered | Small herbivores, eggs, invertebrates | Pack cohesion, hunger, habitat | ✅ |

#### Omnivores / Mesopredators

| Name | Key Properties | Affects | Affected By | Phase 1 |
|------|---------------|---------|-------------|---------|
| Anzu wyliei (oviraptorosaur) | Mass 250 kg, omnivore, egg-raider, crested display, semi-social | Eggs, fruits, invertebrates | Hunger, season (breeding), rival presence | ✅ |

#### Large Herbivores

| Name | Key Properties | Affects | Affected By | Phase 1 |
|------|---------------|---------|-------------|---------|
| Triceratops | Mass 8000 kg, horns, defensive frill display, small groups 2–6, browser | Plant biomass (shrubs/ferns), soil trampling | Hunger, thirst, T. rex presence, herd size | ✅ |
| Edmontosaurus | Mass 4000 kg, large herd 10–50, herd alarm calls, migratory tendency, grazer | Plant biomass (ground layer), water quality | Hunger, thirst, predator alarm, season | ✅ |
| Ankylosaurus | Mass 6000 kg, armored, solitary or pair, tail club, stands ground | Plant biomass (low browse), soil | Hunger, thirst, injury | ✅ |

#### Small-Medium Herbivores

| Name | Key Properties | Affects | Affected By | Phase 1 |
|------|---------------|---------|-------------|---------|
| Pachycephalosaurus | Mass 450 kg, dome-headed, small groups 3–8, head-butting males | Plant biomass, rival males | Hunger, rival presence, predator fear | ✅ |
| Thescelosaurus | Mass 40 kg, small bipedal, fast 9 m/s, skittish, semi-burrows | Ground layer plants | Hunger, thirst, predator fear | ✅ |

#### Scavengers / Flyers

| Name | Key Properties | Affects | Affected By | Phase 1 |
|------|---------------|---------|-------------|---------|
| Quetzalcoatlus (pterosaur) | Mass 250 kg, wingspan 10 m, soars, wide vision radius 60 cells, hunts fish/small prey, scavenges | Carcass decomposition rate, fish/small prey | Wind, weather, thermal columns, hunger | ✅ |

#### Aquatic Life

| Name | Key Properties | Affects | Affected By | Phase 1 |
|------|---------------|---------|-------------|---------|
| Freshwater fish (schooling) | Biomass-based, abundant, simplified schooling, multiple species abstracted | Aquatic nutrient cycle | Water temperature, depth, predation by Deinosuchus/Quetzalcoatlus | ✅ |
| Freshwater turtle | Mass 20 kg, omnivore, slow, buries eggs in mud, ectotherm | Aquatic invertebrates, plant material | Temperature, season (nesting), predation | ✅ |

#### Insectivores / Small Mammals

| Name | Key Properties | Affects | Affected By | Phase 1 |
|------|---------------|---------|-------------|---------|
| Didelphodon (early mammal) | Mass 0.5 kg, nocturnal, live birth, insectivore-omnivore, burrowing | Insect population | Night/day cycle, temperature, predation | ✅ |

#### Insects / Invertebrates

| Name | Key Properties | Affects | Affected By | Phase 1 |
|------|---------------|---------|-------------|---------|
| Insect swarms (dragonflies, beetles, etc.) | Biomass-based, simplified, swarm entities | Pollination (angiosperm growth boost), food for insectivores | Season, temperature, moisture, plant density | ✅ |

---

### A2. Plants (Biomass Layers per Cell)

Each cell tracks biomass as a float [0.0, 1.0] per layer:

| Layer | Representative Species | Terrain Affinity | Regrowth Rate | Nutrient Demand | Phase 1 |
|-------|----------------------|-----------------|--------------|----------------|---------|
| Ground cover (ferns) | *Tempskya*, *Gleichenia* spp. | All non-rocky | Fast | Low | ✅ |
| Low browse (cycads, shrubs) | *Cycadeoidea*, early angiosperms | Woodland, floodplain | Medium | Medium | ✅ |
| Mid canopy (ginkgo, tree ferns) | *Ginkgo adiantoides*, *Metasequoia* | Forest, woodland | Slow | Medium | ✅ |
| High canopy (conifers) | *Brachyphyllum*, *Sequoia*-like | Forest, rocky hills | Very slow | High | ✅ |
| Aquatic / swamp vegetation | Water lilies, horsetails, mosses | Swamp, river edge | Medium | Low | ✅ |
| Algae | Freshwater algae | Lake, river | Fast | Very low | ✅ |

**Regrowth mechanics:**  
`biomass += growth_rate × (1 − biomass) × nutrient_level × seasonal_multiplier`  
Nutrient level is boosted by decomposing carcasses and waste within 3 cells. Herbivore feeding reduces the appropriate layer by the bite amount. Wildfire resets a layer to 0.

---

### A3. Decomposers

| Element | Implementation | Phase 1 |
|---------|---------------|---------|
| Fungi / microbial decomposition | Represented as a decay rate on Carcass entities: `mass_remaining -= decay_rate × temperature_factor × moisture_factor`. No separate agent. Nutrients released proportionally. | ✅ |
| Dung / waste | Each herbivore deposits a micro-nutrient packet per feeding event (simplified: every N ticks a nutrient boost is applied to nearby cells). | ✅ |

---

### A4. Eggs, Nests, and Dependent Offspring

| Entity | Properties | Phase 1 |
|--------|-----------|---------|
| **Egg** | species, parent_ids, clutch_id, incubation_ticks_remaining, temperature_exposure, alive, hatched | ✅ |
| **Nest** | location, owner_id, egg_ids, guarded (bool), construction_ticks | ✅ |
| **Hatchling / Newborn** | Subtype of Agent, life_stage=HATCHLING, follows parent_id, dependency_ticks | ✅ |

---

## B. Non-Living Elements

### B1. Terrain Types

| Terrain | Movement Cost | Visibility Mod | Plant Capacity | Water | Phase 1 |
|---------|--------------|--------------|---------------|-------|---------|
| Floodplain | 1.0 | 1.0 | High (ground, low) | Seasonal | ✅ |
| Forest | 1.4 | 0.4 | High (all layers) | No | ✅ |
| Open woodland | 1.1 | 0.7 | Medium | No | ✅ |
| Swamp | 1.8 | 0.5 | High (aquatic, ferns) | Yes (shallow) | ✅ |
| River | 2.5 (land creatures) / 0.8 (aquatic) | 1.0 | Low (aquatic only) | Yes (flowing) | ✅ |
| Lake | Impassable (land) / 0.6 (aquatic) | 1.0 | Algae | Yes (deep) | ✅ |
| Rocky hills | 1.7 | 1.2 | Low (conifers) | No | ✅ |
| Mud flats | 1.3 | 1.0 | Low | Seasonal | ✅ |

### B2. Water Bodies

| Class | Depth | Occupants | Notes | Phase 1 |
|-------|-------|-----------|-------|---------|
| Shallow puddle | <0.2 | Drinking only | Seasonal, evaporates in drought | ✅ |
| Stream / river | 0.2–1.0 | Fish, turtles, Deinosuchus, drinking | Flows; floods in storm | ✅ |
| Shallow lake | 1.0–3.0 | All aquatic | Seasonal level change | ✅ |
| Deep lake | >3.0 | Aquatic ambush predators | Rare | ✅ |

### B3. Soil and Nutrients

- **Nutrient grid:** float per cell [0.0, 1.0]
- **Sources:** carcass decomposition (radius 2), dung, leaf litter (forest cells get +0.001/tick)
- **Drain:** plant growth consumes nutrients; drought reduces nutrient retention
- **Effect:** plant regrowth_rate multiplied by `(0.5 + 0.5 × nutrient_level)`

### B4. Climate and Time

| Element | Implementation | Phase 1 |
|---------|---------------|---------|
| Tick | Configurable in-world minutes (default 30 min). 48 ticks = 1 day. | ✅ |
| Day / Night | Sun elevation from tick index. Night penalty: vision ×0.3, ectotherm activity ×0.5. | ✅ |
| Moon phase | Optional cosmetic only | ❌ (deferred) |
| Season | Four seasons, configurable length (default 90 days each). | ✅ |
| Temperature | Ambient temp varies by season (25–35 °C summer, 5–10 °C winter) and time of day (±5 °C). Affects ectotherm activity, plant growth, water evaporation. | ✅ |
| Wind | Direction and speed scalar; biases scent propagation, affects wildfire spread | ✅ |

### B5. Weather and Hazards

| Hazard | Trigger | Effects | Duration | Phase 1 |
|--------|---------|---------|----------|---------|
| Rain | Random seasonal probability | Plant growth boost, river level rises, mud movement penalty | 1–5 days | ✅ |
| Storm | Rare, random | Heavy rain + lightning strikes, visibility -80%, flood risk | 0.5–2 days | ✅ |
| Drought | Low rainfall season | Plant growth ×0.1, water evaporation accelerated, animal thirst faster | 5–30 days | ✅ |
| Flood | After heavy storm | Water cells expand, terrain movement penalty, drowning risk for small creatures | 1–3 days | ✅ |
| Wildfire | Lightning strike on dry vegetation | Burns cells sequentially (wind-direction bias), kills creatures caught in it, resets plant biomass | 0.5–5 days | ✅ |
| Volcanic ash | Very rare; optional | Visibility -50%, plant growth -70%, respiratory stress | 1–7 days | ❌ (deferred) |

### B6. Objects

| Object | Properties | Interactions | Phase 1 |
|--------|-----------|-------------|---------|
| Carcass | species, mass_remaining, decay_progress, scavengers_feeding, nutrient_released | Scavenger food source; decays to nutrients | ✅ |
| Bones | Permanent after full decay; purely cosmetic/map indicator | Visual only | ✅ |
| Nest | species, egg_ids, guarded, location | Egg incubation; guarding behavior | ✅ |
| Burrow/Den | species, location, occupants | Shelter (Didelphodon, Thescelosaurus hides near) | ✅ |
| Fallen log | Terrain modifier | Cover bonus for small creatures | ✅ |
| Mud wallow | location, moisture | Ankylosaurus/large herbivore cooling; reduces parasite load | ✅ |
| Rock outcrop | Terrain modifier | Climbing bonus for small creatures, landmark in memory | ✅ |

### Admin-Spawnable Objects
All objects above plus:
- Arbitrary water pools (temporary pond)
- Nutrient deposits
- Hazard events (fire, storm, flood)

---

## Implementation Status Legend

- ✅ Phase 1 — implemented  
- ❌ Deferred to later phase
