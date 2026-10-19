"""
test_species_loader.py — Tests for YAML species and plant loading and validation.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from prehistoric_sim.io.plant_loader import PlantValidationError, load_all_plants, validate_plant
from prehistoric_sim.io.species_loader import (
    SpeciesValidationError,
    load_all_species,
    load_species_file,
    validate_species,
)


def test_load_all_valid_species():
    species_dir = Path("data/species")
    species = load_all_species(species_dir)
    assert len(species) >= 13
    assert "tyrannosaurus_rex" in species
    assert "edmontosaurus" in species
    assert "triceratops" in species
    assert "didelphodon" in species


def test_species_validation_missing_field():
    invalid_data = {
        "species_key": "bad_dino",
        "common_name": "Bad Dino",
        # Missing scientific_name, diet, etc.
    }
    with pytest.raises(SpeciesValidationError, match="Missing required field"):
        validate_species(invalid_data)


def test_species_validation_invalid_diet():
    invalid_data = {
        "species_key": "bad_dino",
        "common_name": "Bad Dino",
        "scientific_name": "Badus dinus",
        "diet": "PLASTIC",
        "activity_pattern": "DIURNAL",
        "reproduction_type": "EGG_LAYING",
        "body_mass_kg": 100.0,
        "lifespan_years": 10.0,
        "maturity_age_years": 2.0,
        "max_speed_cells_per_tick": 5.0,
    }
    with pytest.raises(SpeciesValidationError, match="'diet' must be one of"):
        validate_species(invalid_data)


def test_species_validation_out_of_range():
    invalid_data = {
        "species_key": "bad_dino",
        "common_name": "Bad Dino",
        "scientific_name": "Badus dinus",
        "diet": "CARNIVORE",
        "activity_pattern": "DIURNAL",
        "reproduction_type": "EGG_LAYING",
        "body_mass_kg": -50.0,  # Negative mass
        "lifespan_years": 10.0,
        "maturity_age_years": 2.0,
        "max_speed_cells_per_tick": 5.0,
    }
    with pytest.raises(SpeciesValidationError, match="out of range"):
        validate_species(invalid_data)


def test_load_all_valid_plants():
    plants_dir = Path("data/plants")
    plants = load_all_plants(plants_dir)
    assert len(plants) >= 9
    assert "ground_ferns" in plants
    assert "cycads" in plants
    assert "freshwater_algae" in plants


def test_plant_validation_invalid_layer():
    invalid_plant = {
        "plant_key": "bad_plant",
        "common_name": "Bad Plant",
        "scientific_name": "Plantus badus",
        "layer_index": 99,  # Must be 0-5
        "base_growth_rate": 0.01,
        "nutrient_demand": 0.5,
    }
    with pytest.raises(PlantValidationError, match="layer_index"):
        validate_plant(invalid_plant)
