"""
plant_loader.py — YAML plant schema loading and validation.

Each plant type defines a biomass layer, preferred terrain types,
growth rate, nutrient demand, and carrying capacity.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

REQUIRED_PLANT_FIELDS: dict[str, type] = {
    "plant_key": str,
    "common_name": str,
    "scientific_name": str,
    "layer_index": int,
    "base_growth_rate": (int, float),
    "nutrient_demand": (int, float),
}


class PlantValidationError(ValueError):
    """Raised when a plant YAML file fails validation."""


def validate_plant(data: dict[str, Any], filepath: str = "<unknown>") -> None:
    """Validate a plant schema dict. Raises PlantValidationError on failure."""
    errors: list[str] = []

    for field, expected_type in REQUIRED_PLANT_FIELDS.items():
        if field not in data:
            errors.append(f"Missing required field: '{field}'")
        elif not isinstance(data[field], expected_type):
            errors.append(f"Field '{field}' has wrong type: expected {expected_type}, got {type(data[field])}")

    if "layer_index" in data and not (0 <= data["layer_index"] <= 5):
        errors.append(f"'layer_index' must be between 0 and 5, got {data['layer_index']}")

    if "base_growth_rate" in data and not (0.0 < data["base_growth_rate"] <= 1.0):
        errors.append(f"'base_growth_rate' must be in (0.0, 1.0], got {data['base_growth_rate']}")

    if "nutrient_demand" in data and not (0.0 <= data["nutrient_demand"] <= 2.0):
        errors.append(f"'nutrient_demand' must be in [0.0, 2.0], got {data['nutrient_demand']}")

    if errors:
        raise PlantValidationError(
            f"Plant YAML validation failed for '{filepath}':\n"
            + "\n".join(f"  • {e}" for e in errors)
        )


def load_plant_file(path: Path) -> dict[str, Any]:
    """Load and validate a single plant YAML file."""
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise PlantValidationError(f"Plant file must be a YAML mapping: {path}")

    validate_plant(data, filepath=str(path))
    return data


def load_all_plants(plants_dir: Path) -> dict[str, dict[str, Any]]:
    """Load all *.yaml files from plants_dir. Returns plant_key → data."""
    plants: dict[str, dict[str, Any]] = {}
    if not plants_dir.exists():
        logger.warning("Plants directory not found: %s", plants_dir)
        return plants

    for path in sorted(plants_dir.glob("*.yaml")):
        try:
            data = load_plant_file(path)
            key = data["plant_key"]
            plants[key] = data
        except Exception as e:
            logger.error("Failed to load plant %s: %s", path, e)

    logger.info("Loaded %d plant types", len(plants))
    return plants
