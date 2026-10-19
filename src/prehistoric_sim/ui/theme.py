"""
theme.py — Load and expose the display theme from data/theme.yaml.

Maps event categories, species, and action names to rich styles.
Falls back to safe defaults if theme.yaml is missing or incomplete.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Defaults (used when theme.yaml is absent or missing keys)
# ---------------------------------------------------------------------------

DEFAULT_THEME: dict[str, Any] = {
    "species_colors": {
        "tyrannosaurus_rex":  "bold red",
        "dakotaraptor":       "bold orange1",
        "acheroraptor":       "bold yellow",
        "anzu_wyliei":        "bold magenta",
        "triceratops":        "bold green",
        "edmontosaurus":      "bold cyan",
        "ankylosaurus":       "bold blue",
        "pachycephalosaurus": "bold violet",
        "thescelosaurus":     "bright_green",
        "deinosuchus":        "bold dark_green",
        "freshwater_fish":    "cyan",
        "freshwater_turtle":  "dark_olive_green3",
        "quetzalcoatlus":     "bold sky_blue1",
        "didelphodon":        "grey70",
        "insect_swarm":       "yellow3",
        "default":            "white",
    },
    "species_glyphs": {
        "tyrannosaurus_rex":  "🦖",
        "dakotaraptor":       "🦕",
        "acheroraptor":       "🦴",
        "anzu_wyliei":        "🪶",
        "triceratops":        "🦏",
        "edmontosaurus":      "🐊",
        "ankylosaurus":       "🛡️",
        "pachycephalosaurus":  "🪨",
        "thescelosaurus":     "🦎",
        "deinosuchus":        "🐊",
        "freshwater_fish":    "🐟",
        "freshwater_turtle":  "🐢",
        "quetzalcoatlus":     "🦅",
        "didelphodon":        "🐀",
        "insect_swarm":       "🦟",
        "default":            "?",
    },
    "species_glyphs_ascii": {
        "tyrannosaurus_rex":  "T",
        "dakotaraptor":       "D",
        "acheroraptor":       "A",
        "anzu_wyliei":        "Z",
        "triceratops":        "C",
        "edmontosaurus":      "E",
        "ankylosaurus":       "K",
        "pachycephalosaurus": "P",
        "thescelosaurus":     "H",
        "deinosuchus":        "G",
        "freshwater_fish":    "f",
        "freshwater_turtle":  "u",
        "quetzalcoatlus":     "Q",
        "didelphodon":        "m",
        "insect_swarm":       "i",
        "default":            "?",
    },
    "category_styles": {
        "LIFECYCLE_BIRTH":      "bold bright_green",
        "LIFECYCLE_DEATH":      "bold red",
        "LIFECYCLE_STAGE_CHANGE": "green",
        "LIFECYCLE_EGG_LAID":   "bright_yellow",
        "LIFECYCLE_HATCHING":   "bold bright_yellow",
        "LIFECYCLE_MATING":     "bold pink1",
        "LIFECYCLE_PARENTING":  "green",
        "LIFECYCLE_NEST_BUILT": "yellow",
        "LIFECYCLE_CARCASS_FORMED": "dim red",
        "LIFECYCLE_CARCASS_DECAYED": "dim grey50",
        "DECISION_ACTION_CHANGE": "dim cyan italic",
        "DECISION_ACTION_TICK":   "dim cyan",
        "INTERACTION_HUNT_SUCCESS": "bold orange1",
        "INTERACTION_HUNT_FAIL":   "orange1",
        "INTERACTION_CHASE":       "yellow",
        "INTERACTION_STALK":       "yellow italic",
        "INTERACTION_FIGHT":       "bold red",
        "INTERACTION_FLEE":        "bright_red",
        "INTERACTION_ALARM_CALL":  "bold yellow",
        "INTERACTION_SCAVENGE":    "dim orange1",
        "INTERACTION_EAT":         "orange1",
        "INTERACTION_DRINK":       "bright_blue",
        "INTERACTION_SLEEP":       "dim white",
        "INTERACTION_MATE_DISPLAY":"bold magenta",
        "INTERACTION_INJURY":      "red",
        "WORLD_DAWN":              "bold bright_yellow",
        "WORLD_DUSK":              "dim magenta",
        "WORLD_DAY_START":         "bright_white",
        "WORLD_SEASON_CHANGE":     "bold bright_magenta",
        "WORLD_WEATHER_START":     "bold blue",
        "WORLD_WEATHER_END":       "dim blue",
        "WORLD_FIRE_SPREAD":       "bold red on dark_orange3",
        "WORLD_FLOOD_EXPAND":      "bold blue on dark_blue",
        "WORLD_PLANT_REGROWTH":    "dim green",
        "ADMIN_ADMIN_COMMAND":     "bold yellow reverse",
        "SYSTEM_POP_CAP":          "bold red on white",
        "SYSTEM_SPECIES_EXTINCT":  "bold red underline",
        "SYSTEM_SNAPSHOT_SAVED":   "dim white",
        "default":                 "white",
    },
    "category_glyphs": {
        "LIFECYCLE_BIRTH":      "🌱",
        "LIFECYCLE_DEATH":      "💀",
        "LIFECYCLE_STAGE_CHANGE": "📈",
        "LIFECYCLE_EGG_LAID":   "🥚",
        "LIFECYCLE_HATCHING":   "🐣",
        "LIFECYCLE_MATING":     "💕",
        "LIFECYCLE_PARENTING":  "🪹",
        "LIFECYCLE_NEST_BUILT": "🏕️",
        "LIFECYCLE_CARCASS_FORMED": "☠️",
        "LIFECYCLE_CARCASS_DECAYED": "🦴",
        "DECISION_ACTION_CHANGE": "🧠",
        "INTERACTION_HUNT_SUCCESS": "🩸",
        "INTERACTION_HUNT_FAIL":   "💨",
        "INTERACTION_CHASE":       "💨",
        "INTERACTION_FIGHT":       "⚔️",
        "INTERACTION_FLEE":        "🏃",
        "INTERACTION_ALARM_CALL":  "📢",
        "INTERACTION_EAT":         "🍖",
        "INTERACTION_DRINK":       "💧",
        "WORLD_DAWN":              "🌅",
        "WORLD_DUSK":              "🌆",
        "WORLD_DAY_START":         "📅",
        "WORLD_SEASON_CHANGE":     "🍂",
        "WORLD_WEATHER_START":     "⛈️",
        "WORLD_FIRE_SPREAD":       "🔥",
        "WORLD_FLOOD_EXPAND":      "🌊",
        "ADMIN_ADMIN_COMMAND":     "⚙️",
        "SYSTEM_POP_CAP":          "⚠️",
        "SYSTEM_SPECIES_EXTINCT":  "❌",
        "default":                 "•",
    },
    "category_glyphs_ascii": {
        "LIFECYCLE_BIRTH":      "+",
        "LIFECYCLE_DEATH":      "X",
        "LIFECYCLE_STAGE_CHANGE": "^",
        "LIFECYCLE_EGG_LAID":   "o",
        "LIFECYCLE_HATCHING":   "*",
        "LIFECYCLE_MATING":     "<3",
        "LIFECYCLE_CARCASS_FORMED": "~",
        "LIFECYCLE_CARCASS_DECAYED": "-",
        "DECISION_ACTION_CHANGE": ">",
        "INTERACTION_HUNT_SUCCESS": "!",
        "INTERACTION_HUNT_FAIL":   "x",
        "INTERACTION_CHASE":       ">>",
        "INTERACTION_FLEE":        "<",
        "INTERACTION_ALARM_CALL":  "!",
        "INTERACTION_EAT":         "nom",
        "INTERACTION_DRINK":       "~",
        "WORLD_DAWN":              ":)",
        "WORLD_DUSK":              ":(",
        "WORLD_SEASON_CHANGE":     "~~",
        "WORLD_WEATHER_START":     "***",
        "WORLD_FIRE_SPREAD":       "###",
        "ADMIN_ADMIN_COMMAND":     "[A]",
        "SYSTEM_POP_CAP":          "[!]",
        "default":                 "-",
    },
    "terrain_colors": {
        "FLOODPLAIN":    "green4",
        "FOREST":        "dark_green",
        "OPEN_WOODLAND": "chartreuse3",
        "SWAMP":         "medium_spring_green",
        "RIVER":         "bright_blue",
        "LAKE":          "blue3",
        "ROCKY_HILLS":   "grey58",
        "MUD_FLATS":     "tan",
    },
    "terrain_glyphs": {
        "FLOODPLAIN":    ".",
        "FOREST":        "#",
        "OPEN_WOODLAND": "t",
        "SWAMP":         "~",
        "RIVER":         "=",
        "LAKE":          "O",
        "ROCKY_HILLS":   "^",
        "MUD_FLATS":     ",",
    },
}


class Theme:
    """Holds display theme configuration loaded from theme.yaml."""

    def __init__(self, theme_path: Path | None = None, ascii_glyphs: bool = False, no_color: bool = False) -> None:
        self._data: dict[str, Any] = dict(DEFAULT_THEME)
        self.ascii_glyphs: bool = ascii_glyphs
        self.no_color: bool = no_color

        if theme_path and theme_path.exists():
            try:
                with open(theme_path, encoding="utf-8") as f:
                    user_theme = yaml.safe_load(f) or {}
                # Deep merge (top-level keys only)
                for key, val in user_theme.items():
                    if key in self._data and isinstance(self._data[key], dict):
                        self._data[key].update(val)
                    else:
                        self._data[key] = val
            except Exception as e:
                logger.warning("Failed to load theme.yaml: %s — using defaults", e)

    @classmethod
    def load(cls, path: Path | None = None, ascii_glyphs: bool = False, no_color: bool = False) -> "Theme":
        return cls(theme_path=path, ascii_glyphs=ascii_glyphs, no_color=no_color)

    def species_color(self, species_key: str) -> str:
        if self.no_color:
            return ""
        colors = self._data.get("species_colors", {})
        return colors.get(species_key, colors.get("default", "white"))

    def species_glyph(self, species_key: str) -> str:
        if self.ascii_glyphs:
            glyphs = self._data.get("species_glyphs_ascii", {})
            return glyphs.get(species_key, glyphs.get("default", "?"))
        glyphs = self._data.get("species_glyphs", {})
        glyph = glyphs.get(species_key, glyphs.get("default", "?"))
        try:
            encoding = getattr(sys.stdout, "encoding", "utf-8") or "utf-8"
            glyph.encode(encoding)
            return glyph
        except Exception:
            ascii_map = self._data.get("species_glyphs_ascii", {})
            return ascii_map.get(species_key, "?")

    def category_style(self, category_key: str) -> str:
        """category_key = 'CATEGORY_SUBCATEGORY' e.g. 'LIFECYCLE_BIRTH'."""
        if self.no_color:
            return ""
        styles = self._data.get("category_styles", {})
        return styles.get(category_key, styles.get("default", "white"))

    def category_glyph(self, category_key: str) -> str:
        if self.ascii_glyphs:
            glyphs = self._data.get("category_glyphs_ascii", {})
            return glyphs.get(category_key, glyphs.get("default", "•"))
        glyphs = self._data.get("category_glyphs", {})
        glyph = glyphs.get(category_key, glyphs.get("default", "•"))
        try:
            encoding = getattr(sys.stdout, "encoding", "utf-8") or "utf-8"
            glyph.encode(encoding)
            return glyph
        except Exception:
            ascii_map = self._data.get("category_glyphs_ascii", {})
            return ascii_map.get(category_key, "-")

    def terrain_color(self, terrain_name: str) -> str:
        if self.no_color:
            return ""
        colors = self._data.get("terrain_colors", {})
        return colors.get(terrain_name, "white")

    def terrain_glyph(self, terrain_name: str) -> str:
        glyphs = self._data.get("terrain_glyphs", {})
        return glyphs.get(terrain_name, ".")
