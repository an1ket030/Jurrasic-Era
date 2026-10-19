# Species Checklist — Hell Creek Late Cretaceous Ecosystem

> **Status:** Phase 1 design document  
> All Phase 1 species are implemented as individual YAML files under `data/species/`.  
> Adding a new species requires only a new YAML file — zero code changes.

---

## Animals

### Apex Predators

- [x] **Tyrannosaurus rex** (*Tyrannosaurus rex*)
  - **Role:** Apex pursuit-ambush predator
  - **Diet:** Carnivore (large herbivores; will scavenge)
  - **Activity:** Diurnal/crepuscular
  - **Social structure:** Solitary or bonded pair; tolerates mate and own juveniles only
  - **Signature behavior:** Ambushes from cover then charges; guards nest aggressively; known individuals may develop "hunting ground" territories encoded in memory

- [x] **Deinosuchus** (*Deinosuchus riograndensis*)
  - **Role:** Aquatic ambush apex predator
  - **Diet:** Carnivore (fish, turtles, drinking herbivores)
  - **Activity:** Crepuscular / patient wait (ectotherm, activity tied to temperature)
  - **Social structure:** Solitary, territory around water-hole
  - **Signature behavior:** Motionless wait at water edge; lunges at drinking animals within 2 cells; retreats to water when threatened

### Mesopredators / Pack Hunters

- [x] **Dakotaraptor** (*Dakotaraptor steini*)
  - **Role:** Pack / pair hunter, mesopredator
  - **Diet:** Carnivore (medium herbivores, eggs, small prey)
  - **Activity:** Diurnal
  - **Social structure:** Pack 2–6, strong cohesion, coordinated flanking
  - **Signature behavior:** Flanking coordination — pack members disperse to cut off prey escape routes; emits alarm call on T. rex sighting

- [x] **Acheroraptor** (*Acheroraptor temertyorum*)
  - **Role:** Small pack / pair hunter
  - **Diet:** Carnivore (small herbivores, insects, eggs)
  - **Activity:** Diurnal
  - **Social structure:** Pair or small group 2–4
  - **Signature behavior:** High-speed pursuit in relay; one member flushes prey toward others

### Omnivores / Egg Raiders

- [x] **Anzu wyliei** (*Anzu wyliei*)
  - **Role:** Omnivore, egg raider
  - **Diet:** Omnivore (fruits, eggs, invertebrates, small vertebrates)
  - **Activity:** Diurnal
  - **Social structure:** Semi-social; loose bands of 2–5 outside breeding season; solitary nesters
  - **Signature behavior:** Crest display in dominance contests; raids unguarded nests; steals kills from smaller predators

### Large Herbivores

- [x] **Triceratops** (*Triceratops horridus*)
  - **Role:** Large defensive herbivore
  - **Diet:** Herbivore (low browse, cycads, ferns)
  - **Activity:** Diurnal
  - **Social structure:** Small groups 2–6; defensive circle with horns outward when threatened
  - **Signature behavior:** Charges T. rex when cornered; dominant male contests via horn-locking; calves kept in center of group

- [x] **Edmontosaurus** (*Edmontosaurus annectens*)
  - **Role:** Large herd herbivore
  - **Diet:** Herbivore (ground cover, ferns, low browse)
  - **Activity:** Diurnal
  - **Social structure:** Herd 10–50; juveniles in center; alarm calls trigger mass flight
  - **Signature behavior:** Migration between feeding grounds seasonally; sentinel behavior (individuals take turns scanning horizon); alarm crest inflation (simplified as call range bonus)

- [x] **Ankylosaurus** (*Ankylosaurus magniventris*)
  - **Role:** Armored tank herbivore
  - **Diet:** Herbivore (ground ferns, low browse)
  - **Activity:** Diurnal / crepuscular
  - **Social structure:** Solitary or loose pair
  - **Signature behavior:** Stands ground rather than fleeing; tail-club swing at approaching predators deals heavy injury; uses mud wallows

### Small-Medium Herbivores

- [x] **Pachycephalosaurus** (*Pachycephalosaurus wyomingensis*)
  - **Role:** Small group herbivore
  - **Diet:** Herbivore (ferns, seeds, fruit)
  - **Activity:** Diurnal
  - **Social structure:** Small group 3–8; clear dominance hierarchy
  - **Signature behavior:** Males engage in head-butting contests for dominance rank, which determines breeding priority; subordinates defer but do not leave

- [x] **Thescelosaurus** (*Thescelosaurus neglectus*)
  - **Role:** Fast, skittish small bipedal herbivore
  - **Diet:** Herbivore (ferns, ground cover, roots)
  - **Activity:** Diurnal, retreats to burrow edges at night
  - **Social structure:** Loose group 4–12; no strong cohesion
  - **Signature behavior:** Fastest ground speed of herbivores; hides in dense vegetation; uses burrow entrances as escape refuges (no true burrowing modeled)

### Scavengers / Flyers

- [x] **Quetzalcoatlus** (*Quetzalcoatlus northropi*)
  - **Role:** Aerial scavenger and opportunistic hunter
  - **Diet:** Carnivore / scavenger (fish, small prey, carcasses)
  - **Activity:** Diurnal (thermalling depends on daytime heat)
  - **Social structure:** Mostly solitary; multiple individuals may gather at large carcass
  - **Signature behavior:** Wide-radius aerial scan; descends to carcasses; competes with Anzu for scraps; departs before T. rex arrives at a carcass

### Aquatic Life

- [x] **Freshwater fish** (*Myledaphus bipartitus* and mixed fauna, abstracted)
  - **Role:** Abundant aquatic prey
  - **Diet:** Omnivore (algae, invertebrates)
  - **Activity:** Continuous
  - **Social structure:** Schools (biomass-based, not individual agents — simplified pool per water body)
  - **Signature behavior:** School biomass depleted by predation, restored by logistic regrowth; fish "flee" by reducing catchability when predator detection simulated

- [x] **Freshwater turtle** (*Axestemys* spp., abstracted)
  - **Role:** Slow omnivore, terrestrial egg-layer
  - **Diet:** Omnivore (aquatic plants, invertebrates, carrion)
  - **Activity:** Diurnal (ectotherm, basks)
  - **Social structure:** Solitary
  - **Signature behavior:** Buries clutch in mud flat or riverbank; slow movement; retreats into shell (damage reduction) when threatened; basks on logs

### Early Mammals

- [x] **Didelphodon** (*Didelphodon vorax*)
  - **Role:** Nocturnal insectivore-omnivore
  - **Diet:** Omnivore (insects, eggs, plant matter, small vertebrates)
  - **Activity:** Nocturnal (vision penalty reversed at night)
  - **Social structure:** Solitary except during breeding; live birth (pouch young, simplified as dependent newborns)
  - **Signature behavior:** Active during predator sleep window; scavenges scraps near large carcasses after dark; uses burrows as dens

### Insects / Invertebrates

- [x] **Insect swarm** (dragonflies, beetles, orthopterans — abstracted)
  - **Role:** Base of insectivore food chain; pollinators
  - **Diet:** Herbivore (plant matter)
  - **Activity:** Diurnal and crepuscular
  - **Social structure:** Swarm (biomass-based entity)
  - **Signature behavior:** Swarm size responds to season and plant biomass; consumed by Didelphodon, Anzu; provides angiosperm growth boost (pollination effect)

---

## Plants (Each as a Biomass Layer)

- [x] **Ground ferns** (*Gleichenia*, *Tempskya* spp.) — Ground cover layer; high regrowth; primary food of hadrosaurs, ankylosaurs
- [x] **Cycads and low browse** (*Cycadeoidea* spp.) — Low browse layer; medium regrowth; Triceratops primary food
- [x] **Early angiosperms / flowering shrubs** (proto-Magnolia, laurels) — Low-mid layer; fast regrowth with insect pollinators; seeds and fruit consumed by omnivores
- [x] **Tree ferns** (*Tempskya* arborescents) — Mid canopy layer; slow regrowth; canopy ferns provide shade modifier
- [x] **Ginkgo** (*Ginkgo adiantoides*) — Mid canopy; very slow regrowth; high nutrient demand
- [x] **Conifers** (*Brachyphyllum*, *Sequoia*-like) — High canopy; very slow regrowth; high nutrient demand; fire-sensitive
- [x] **Swamp horsetails** (*Equisetum* spp.) — Aquatic/swamp layer; fast regrowth; stabilizes mud banks
- [x] **Water lilies and aquatic floating plants** — Aquatic layer; moderate regrowth; algae nutrient competition
- [x] **Freshwater algae** — Aquatic floor layer; fastest regrowth; base of aquatic food chain

---

## Notes on Adding New Species (Phase 2+)

To add any new species:
1. Create `data/species/<species_key>.yaml` following the schema in `src/prehistoric_sim/io/species_loader.py`.
2. Run `sim species validate` to confirm the file is valid.
3. No code changes are required. The engine dynamically loads all YAML files in `data/species/`.
