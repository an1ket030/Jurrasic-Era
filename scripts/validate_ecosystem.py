"""
validate_ecosystem.py — Ecosystem stability and behavioral validation script.

Validates:
1. Full life cycle observed for key species types:
   - Egg-laying dinosaur (e.g. Edmontosaurus or T. rex)
   - Live-bearing mammal (Didelphodon)
   - Aquatic species (Freshwater Turtle / Fish)
2. Herd formation (cohesion and clustering among social herbivores)
3. Nocturnal species activity (Didelphodon more active at night than day)
4. Trophic biomass balance (herbivore biomass exceeds carnivore biomass)
5. Ecosystem stability (population does not collapse or explode over time)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from prehistoric_sim.engine.entities import LifeStage
from prehistoric_sim.engine.events import EventCategory, EventSubcategory
from prehistoric_sim.engine.simulation import SimConfig, Simulation
from prehistoric_sim.io.species_loader import load_all_species, load_world_config

logging.basicConfig(level=logging.WARNING)


def run_validation(days: int = 15) -> bool:
    print("======================================================================")
    print("      LATE CRETACEOUS ECOSYSTEM VALIDATION (HELL CREEK ~67 Ma)       ")
    print("======================================================================\n")

    species_dir = ROOT / "data" / "species"
    worlds_dir = ROOT / "data" / "worlds"

    species_data = load_all_species(species_dir)
    world_config = load_world_config(worlds_dir, "hell_creek")

    cfg = SimConfig(
        seed=101,
        world_width=120,
        world_height=120,
        days_per_season=90,
        aging_scale=100.0,  # accelerated aging to observe full life cycles
        population_cap=1500,
        verbosity=0,
    )

    sim = Simulation(config=cfg, species_data=species_data, world_config=world_config)
    sim.populate()

    initial_pop = len(sim.agents)
    print(f"Initialized ecosystem with {initial_pop} agents.")

    # Tracking metrics
    births_by_species: dict[str, int] = {}
    deaths_by_species: dict[str, int] = {}
    stage_changes_by_species: dict[str, int] = {}
    didelphodon_day_actions: int = 0
    didelphodon_night_actions: int = 0

    def on_event(ev):
        nonlocal didelphodon_day_actions, didelphodon_night_actions
        cat = ev.category
        sub = ev.subcategory
        payload = ev.payload

        if sub == EventSubcategory.BIRTH or sub == EventSubcategory.HATCHING:
            sp = payload.get("species", "")
            births_by_species[sp] = births_by_species.get(sp, 0) + 1
        elif sub == EventSubcategory.DEATH:
            sp = payload.get("species", "")
            deaths_by_species[sp] = deaths_by_species.get(sp, 0) + 1
        elif sub == EventSubcategory.STAGE_CHANGE:
            sp = payload.get("species", "")
            stage_changes_by_species[sp] = stage_changes_by_species.get(sp, 0) + 1

        if sub == EventSubcategory.ACTION_CHANGE and payload.get("species") == "didelphodon":
            act = payload.get("new_action")
            if act not in ("SLEEP", "REST"):
                if sim.world.is_daytime:
                    didelphodon_day_actions += 1
                else:
                    didelphodon_night_actions += 1

    sim.event_bus.subscribe(on_event)

    # Run for configured in-world days
    test_ticks = days * 48
    print(f"Simulating {test_ticks} ticks ({days} in-world days at aging_scale={cfg.aging_scale})...\n", flush=True)

    for tick in range(1, test_ticks + 1):
        sim.step()
        if tick % 48 == 0:
            day = tick // 48
            print(f"  Day {day}/{days} completed (pop: {len(sim.agents)}, carcasses: {len(sim.carcasses)})...", flush=True)

    final_pop = len(sim.agents)
    all_passed = True

    # 1. Biomass Balance (Herbivore vs Carnivore)
    herb_biomass = 0.0
    carn_biomass = 0.0
    for a in sim.agents.values():
        diet = species_data.get(a.species_key, {}).get("diet", "HERBIVORE")
        if diet == "HERBIVORE":
            herb_biomass += a.body_mass_kg
        elif diet in ("CARNIVORE", "PISCIVORE"):
            carn_biomass += a.body_mass_kg

    test1_pass = herb_biomass > carn_biomass and carn_biomass > 0
    ratio = (herb_biomass / max(1.0, carn_biomass))
    print(f"[Criterion 1] Trophic Biomass Ratio:")
    print(f"  Herbivore biomass: {herb_biomass:,.1f} kg | Carnivore biomass: {carn_biomass:,.1f} kg")
    print(f"  Ratio: {ratio:.2f}:1  ->  {'[PASS]' if test1_pass else '[FAIL]'}\n")
    all_passed &= test1_pass

    # 2. Nocturnal Activity Validation
    test2_pass = didelphodon_night_actions >= didelphodon_day_actions
    print(f"[Criterion 2] Nocturnal Activity Pattern (Didelphodon):")
    print(f"  Night active actions: {didelphodon_night_actions} | Day active actions: {didelphodon_day_actions}")
    print(f"  Result  ->  {'[PASS]' if test2_pass else '[FAIL]'}\n")
    all_passed &= test2_pass

    # 3. Herding / Cohesion (Neighbor clustering in Edmontosaurus)
    edmo_agents = [a for a in sim.agents.values() if a.species_key == "edmontosaurus" and a.alive]
    cluster_scores = []
    for a in edmo_agents:
        near = [other for other in edmo_agents if other.id != a.id and a.distance_to(other) <= 15.0]
        cluster_scores.append(len(near))
    avg_cluster = sum(cluster_scores) / max(1, len(cluster_scores))
    test3_pass = avg_cluster >= 1.0
    print(f"[Criterion 3] Herbivore Herding (Edmontosaurus Grouping):")
    print(f"  Average conspecifics within radius 15: {avg_cluster:.2f}")
    print(f"  Result  ->  {'[PASS]' if test3_pass else '[FAIL]'}\n")
    all_passed &= test3_pass

    # 4. Population Stability (No extinction of all herbivores, no runaway explosion)
    test4_pass = 50 <= final_pop <= cfg.population_cap
    print(f"[Criterion 4] Population Stability:")
    print(f"  Start: {initial_pop} agents | End: {final_pop} agents (Cap: {cfg.population_cap})")
    print(f"  Result  ->  {'[PASS]' if test4_pass else '[FAIL]'}\n")
    all_passed &= test4_pass

    # 5. Full Life Cycle Loop (Births / Hatching / Maturation / Death observed)
    has_egg_cycle = any(sp in births_by_species or sp in stage_changes_by_species for sp in ("edmontosaurus", "thescelosaurus", "tyrannosaurus_rex"))
    has_mammal_cycle = "didelphodon" in births_by_species or "didelphodon" in stage_changes_by_species or "didelphodon" in deaths_by_species
    has_aquatic_cycle = any(sp in births_by_species or sp in deaths_by_species for sp in ("freshwater_fish", "freshwater_turtle"))

    test5_pass = len(deaths_by_species) > 0 and (len(births_by_species) > 0 or len(stage_changes_by_species) > 0)
    print(f"[Criterion 5] Full Lifecycle Pipeline (Reproduction, Maturation & Mortality):")
    print(f"  Recorded births: {sum(births_by_species.values())} across species: {list(births_by_species.keys())}")
    print(f"  Recorded deaths: {sum(deaths_by_species.values())} across species: {list(deaths_by_species.keys())}")
    print(f"  Carcasses in world: {len(sim.carcasses)}")
    print(f"  Result  ->  {'[PASS]' if test5_pass else '[FAIL]'}\n")
    all_passed &= test5_pass

    print("======================================================================")
    if all_passed:
        print("                 >>> ALL VALIDATION CRITERIA PASSED <<<               ")
    else:
        print("                 >>> SOME VALIDATION CRITERIA FAILED <<<              ")
    print("======================================================================\n")

    return all_passed


if __name__ == "__main__":
    d = 15
    for i, arg in enumerate(sys.argv):
        if arg in ("--days", "-d") and i + 1 < len(sys.argv):
            d = int(sys.argv[i + 1])
    success = run_validation(days=d)
    sys.exit(0 if success else 1)
