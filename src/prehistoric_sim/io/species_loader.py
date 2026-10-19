"""
species_loader.py — YAML species schema loading and validation.

Each species is defined by a YAML file in data/species/. This module
loads, validates, and returns them as plain dicts. Invalid files are
rejected with descriptive error messages. No engine code depends on
any specific species — the schema is fully data-driven.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Required fields (field_name: (type, description))
# ---------------------------------------------------------------------------

REQUIRED_FIELDS: dict[str, type] = {
    "species_key": str,
    "common_name": str,
    "scientific_name": str,
    "diet": str,
    "activity_pattern": str,
    "reproduction_type": str,
    "body_mass_kg": (int, float),
    "lifespan_years": (int, float),
    "maturity_age_years": (int, float),
    "max_speed_cells_per_tick": (int, float),
}

VALID_DIETS = {"CARNIVORE", "HERBIVORE", "OMNIVORE", "INSECTIVORE", "PISCIVORE"}
VALID_ACTIVITY = {"DIURNAL", "NOCTURNAL", "CREPUSCULAR", "CONTINUOUS"}
VALID_REPRO = {"EGG_LAYING", "LIVE_BIRTH"}
VALID_SEASONS = {"SPRING", "SUMMER", "AUTUMN", "WINTER", "SPRING_SUMMER", "ANY"}
VALID_DEFENSES = {"none", "tail_club", "charge", "shell", "armor", "flee"}
VALID_HUNT_STYLES = {"pursuit", "ambush", "pack", "aquatic_ambush", "aerial"}


class SpeciesValidationError(ValueError):
    """Raised when a species YAML file fails validation."""


def validate_species(data: dict[str, Any], filepath: str = "<unknown>") -> None:
    """Validate a species data dict. Raises SpeciesValidationError on failure."""
    errors: list[str] = []

    # Required fields
    for field, expected_type in REQUIRED_FIELDS.items():
        if field not in data:
            errors.append(f"Missing required field: '{field}'")
        elif not isinstance(data[field], expected_type):
            errors.append(
                f"Field '{field}' has wrong type: expected {expected_type.__name__ if isinstance(expected_type, type) else expected_type}, got {type(data[field]).__name__}"
            )

    # Enum checks
    if "diet" in data and data["diet"] not in VALID_DIETS:
        errors.append(f"'diet' must be one of {VALID_DIETS}, got '{data['diet']}'")

    if "activity_pattern" in data and data["activity_pattern"] not in VALID_ACTIVITY:
        errors.append(f"'activity_pattern' must be one of {VALID_ACTIVITY}")

    if "reproduction_type" in data and data["reproduction_type"] not in VALID_REPRO:
        errors.append(f"'reproduction_type' must be one of {VALID_REPRO}")

    if "breeding_season" in data and data["breeding_season"] not in VALID_SEASONS:
        errors.append(f"'breeding_season' must be one of {VALID_SEASONS}")

    if "defense_type" in data and data["defense_type"] not in VALID_DEFENSES:
        errors.append(f"'defense_type' must be one of {VALID_DEFENSES}")

    if "hunt_style" in data and data["hunt_style"] not in VALID_HUNT_STYLES:
        errors.append(f"'hunt_style' must be one of {VALID_HUNT_STYLES}")

    # Value range checks
    for field, (lo, hi) in [
        ("body_mass_kg", (0.001, 100_000)),
        ("lifespan_years", (0.1, 200)),
        ("maturity_age_years", (0.01, 100)),
        ("max_speed_cells_per_tick", (0.01, 20)),
        ("vision_range_cells", (1, 80)),
        ("fov_degrees", (10, 360)),
        ("smell_range_cells", (0, 40)),
    ]:
        if field in data:
            val = data[field]
            if not (lo <= val <= hi):
                errors.append(f"'{field}' value {val} out of range [{lo}, {hi}]")

    if errors:
        raise SpeciesValidationError(
            f"Species YAML validation failed for '{filepath}':\n"
            + "\n".join(f"  • {e}" for e in errors)
        )


def load_species_file(path: Path) -> dict[str, Any]:
    """Load and validate a single species YAML file."""
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise SpeciesValidationError(f"Species file must be a YAML mapping: {path}")

    validate_species(data, filepath=str(path))
    logger.debug("Loaded species: %s from %s", data.get("species_key"), path)
    return data


def load_all_species(species_dir: Path) -> dict[str, dict[str, Any]]:
    """Load all *.yaml files from species_dir. Returns species_key → data."""
    species: dict[str, dict[str, Any]] = {}
    if not species_dir.exists():
        logger.warning("Species directory not found: %s", species_dir)
        return species

    for path in sorted(species_dir.glob("*.yaml")):
        try:
            data = load_species_file(path)
            key = data["species_key"]
            if key in species:
                logger.warning("Duplicate species_key '%s' in %s — skipping", key, path)
                continue
            species[key] = data
        except SpeciesValidationError as e:
            logger.error("%s", e)
        except Exception as e:
            logger.error("Failed to load %s: %s", path, e)

    logger.info("Loaded %d species", len(species))
    return species


def load_all_plants(plants_dir: Path) -> dict[str, dict[str, Any]]:
    """Load all plant YAML files."""
    plants: dict[str, dict[str, Any]] = {}
    if not plants_dir.exists():
        return plants
    for path in sorted(plants_dir.glob("*.yaml")):
        try:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if isinstance(data, dict) and "plant_key" in data:
                plants[data["plant_key"]] = data
        except Exception as e:
            logger.error("Failed to load plant %s: %s", path, e)
    return plants


def load_world_config(worlds_dir: Path, world_name: str) -> dict[str, Any]:
    """Load a world configuration YAML."""
    path = worlds_dir / f"{world_name}.yaml"
    if not path.exists():
        logger.warning("World config not found: %s", path)
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
