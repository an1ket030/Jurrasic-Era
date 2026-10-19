"""
world.py — World grid, terrain, water, plants, climate, weather, nutrients.

The World owns the 2D grid and all non-agent state. It provides:
- Terrain type and movement cost per cell
- Water depth and edges
- Plant biomass (per layer, per cell)
- Nutrient grid
- Time: tick, day, season, temperature, wind
- Weather state machine
- Procedural generation from a seed
"""

from __future__ import annotations

import dataclasses
import math
from enum import Enum
from typing import TYPE_CHECKING

import numpy as np

from prehistoric_sim.engine.entities import TerrainType, WeatherType
from prehistoric_sim.engine.events import (
    Event,
    EventBus,
    EventCategory,
    EventSubcategory,
)
from prehistoric_sim.engine.rng import SimRNG

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TICKS_PER_DAY: int = 48          # 48 × 30 min = 24 h
DAYS_PER_SEASON: int = 90        # configurable; default 90
SEASONS: list[str] = ["SPRING", "SUMMER", "AUTUMN", "WINTER"]

TERRAIN_MOVE_COST: dict[TerrainType, float] = {
    TerrainType.FLOODPLAIN:    1.0,
    TerrainType.FOREST:        1.4,
    TerrainType.OPEN_WOODLAND: 1.1,
    TerrainType.SWAMP:         1.8,
    TerrainType.RIVER:         2.5,
    TerrainType.LAKE:          9.9,   # effectively impassable for land
    TerrainType.ROCKY_HILLS:   1.7,
    TerrainType.MUD_FLATS:     1.3,
}

TERRAIN_VISIBILITY: dict[TerrainType, float] = {
    TerrainType.FLOODPLAIN:    1.0,
    TerrainType.FOREST:        0.4,
    TerrainType.OPEN_WOODLAND: 0.7,
    TerrainType.SWAMP:         0.5,
    TerrainType.RIVER:         1.0,
    TerrainType.LAKE:          1.0,
    TerrainType.ROCKY_HILLS:   1.2,
    TerrainType.MUD_FLATS:     1.0,
}

# Plant layer indices
LAYER_GROUND = 0     # ferns, ground cover
LAYER_LOW = 1        # cycads, low browse
LAYER_MID = 2        # tree ferns, ginkgo
LAYER_HIGH = 3       # conifers
LAYER_AQUATIC = 4    # aquatic / swamp plants
LAYER_ALGAE = 5      # algae (water cells)
NUM_LAYERS = 6

PLANT_LAYER_NAMES = ["ground_ferns", "low_browse", "mid_canopy", "high_canopy", "aquatic", "algae"]

# Seasonal temperature ranges (°C) [min, max]
SEASON_TEMP: dict[str, tuple[float, float]] = {
    "SPRING": (18.0, 28.0),
    "SUMMER": (28.0, 38.0),
    "AUTUMN": (15.0, 25.0),
    "WINTER": (5.0, 12.0),
}

# Terrain → which plant layers can grow there, and their carrying capacity
TERRAIN_PLANT_CAPACITY: dict[TerrainType, list[float]] = {
    #                         G     L     M     H     AQ    AL
    TerrainType.FLOODPLAIN:  [1.0,  0.7,  0.3,  0.0,  0.2,  0.0],
    TerrainType.FOREST:      [0.8,  0.8,  0.9,  1.0,  0.0,  0.0],
    TerrainType.OPEN_WOODLAND:[0.9,  0.9,  0.6,  0.5,  0.0,  0.0],
    TerrainType.SWAMP:       [0.7,  0.4,  0.3,  0.0,  1.0,  0.3],
    TerrainType.RIVER:       [0.1,  0.0,  0.0,  0.0,  0.8,  0.6],
    TerrainType.LAKE:        [0.0,  0.0,  0.0,  0.0,  0.5,  1.0],
    TerrainType.ROCKY_HILLS: [0.3,  0.2,  0.2,  0.6,  0.0,  0.0],
    TerrainType.MUD_FLATS:   [0.5,  0.3,  0.0,  0.0,  0.6,  0.2],
}

# Base plant regrowth rates per layer per tick
PLANT_REGROWTH_BASE: list[float] = [0.004, 0.002, 0.001, 0.0005, 0.003, 0.006]


# ---------------------------------------------------------------------------
# Weather state
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class WeatherState:
    """Current weather conditions."""

    current: WeatherType = WeatherType.CLEAR
    ticks_remaining: int = 0
    rainfall_intensity: float = 0.0   # [0, 1]
    wind_direction: float = 0.0        # degrees (0 = east)
    wind_speed: float = 0.5            # [0, 1]
    visibility_modifier: float = 1.0   # multiplied onto vision range
    fire_cells: set[tuple[int, int]] = dataclasses.field(default_factory=set)
    flood_cells: set[tuple[int, int]] = dataclasses.field(default_factory=set)


# ---------------------------------------------------------------------------
# World
# ---------------------------------------------------------------------------


class World:
    """The 2D simulation world.

    Owns all spatial data: terrain, water, plants, nutrients, climate.
    Does NOT own agents or other entities — those live in Simulation.
    """

    def __init__(
        self,
        width: int = 120,
        height: int = 120,
        seed: int = 42,
        rng: SimRNG | None = None,
        days_per_season: int = DAYS_PER_SEASON,
        event_bus: EventBus | None = None,
    ) -> None:
        self.width = width
        self.height = height
        self.seed = seed
        self.rng: SimRNG = rng or SimRNG(seed)
        self.days_per_season = days_per_season
        self.event_bus: EventBus | None = event_bus

        # Time
        self.tick: int = 0
        self.day: int = 0
        self.season_index: int = 0         # index into SEASONS
        self.ticks_per_day: int = TICKS_PER_DAY

        # Grids (numpy arrays, shape [height, width])
        self.terrain: np.ndarray = np.zeros((height, width), dtype=np.int8)
        self.water_depth: np.ndarray = np.zeros((height, width), dtype=np.float32)
        self.nutrients: np.ndarray = np.zeros((height, width), dtype=np.float32)
        # Plant biomass: shape [NUM_LAYERS, height, width]
        self.plant_biomass: np.ndarray = np.zeros(
            (NUM_LAYERS, height, width), dtype=np.float32
        )

        # Weather
        self.weather: WeatherState = WeatherState()
        self._drought_duration: int = 0
        self._rain_accumulation: float = 0.0

        # Cached lookups
        self._water_cells: set[tuple[int, int]] = set()
        self._water_edge_cells: set[tuple[int, int]] = set()

        # Generate world
        self._generate()

    # ------------------------------------------------------------------
    # Time
    # ------------------------------------------------------------------

    @property
    def season(self) -> str:
        """Current season name."""
        return SEASONS[self.season_index]

    @property
    def hour_of_day(self) -> float:
        """Decimal hour [0, 24)."""
        tick_in_day = self.tick % self.ticks_per_day
        return (tick_in_day / self.ticks_per_day) * 24.0

    @property
    def is_daytime(self) -> bool:
        h = self.hour_of_day
        return 6.0 <= h < 20.0

    @property
    def is_dawn_or_dusk(self) -> bool:
        h = self.hour_of_day
        return (5.0 <= h < 7.0) or (19.0 <= h < 21.0)

    @property
    def sun_elevation(self) -> float:
        """Normalised sun elevation [0, 1]; 1 = solar noon, 0 = midnight."""
        h = self.hour_of_day
        return max(0.0, math.sin(math.pi * (h - 6.0) / 14.0)) if 6.0 <= h <= 20.0 else 0.0

    @property
    def temperature(self) -> float:
        """Ambient temperature in °C for current season and time of day."""
        lo, hi = SEASON_TEMP[self.season]
        base = lo + (hi - lo) * 0.5
        diurnal = 5.0 * math.sin(math.pi * (self.hour_of_day - 6.0) / 14.0)
        return base + diurnal if self.is_daytime else base - 3.0

    @property
    def night_vision_penalty(self) -> float:
        """Multiplier applied to vision range at night [0.3, 1.0]."""
        return max(0.3, self.sun_elevation)

    # ------------------------------------------------------------------
    # Cell utilities
    # ------------------------------------------------------------------

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def terrain_at(self, x: int, y: int) -> TerrainType:
        return TerrainType(list(TerrainType)[self.terrain[y, x]])

    def is_water(self, x: int, y: int) -> bool:
        return (x, y) in self._water_cells

    def is_water_edge(self, x: int, y: int) -> bool:
        return (x, y) in self._water_edge_cells

    def move_cost(self, x: int, y: int) -> float:
        t = self.terrain_at(x, y)
        base = TERRAIN_MOVE_COST.get(t, 1.0)
        if self.weather.current == WeatherType.RAIN:
            if t in (TerrainType.MUD_FLATS, TerrainType.FLOODPLAIN):
                base *= 1.3
        if (x, y) in self.weather.flood_cells:
            base *= 1.8
        return base

    def visibility_mod(self, x: int, y: int) -> float:
        t = self.terrain_at(x, y)
        base = TERRAIN_VISIBILITY.get(t, 1.0)
        base *= self.weather.visibility_modifier
        # Plant occlusion from high biomass
        plant_density = float(np.sum(self.plant_biomass[LAYER_MID:LAYER_HIGH + 1, y, x]))
        base *= max(0.2, 1.0 - plant_density * 0.3)
        return base

    def nearest_water(self, x: int, y: int, max_range: int = 30) -> tuple[int, int] | None:
        """Find nearest water-edge cell within max_range using BFS."""
        from collections import deque  # noqa: PLC0415

        if (x, y) in self._water_edge_cells or (x, y) in self._water_cells:
            return (x, y)
        queue: deque[tuple[int, int]] = deque([(x, y)])
        visited = {(x, y)}
        dist = 0
        while queue and dist <= max_range:
            for _ in range(len(queue)):
                cx, cy = queue.popleft()
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    nx, ny = cx + dx, cy + dy
                    if (nx, ny) in visited or not self.in_bounds(nx, ny):
                        continue
                    visited.add((nx, ny))
                    if (nx, ny) in self._water_edge_cells or (nx, ny) in self._water_cells:
                        return (nx, ny)
                    queue.append((nx, ny))
            dist += 1
        return None

    def get_plant_biomass_total(self, x: int, y: int) -> float:
        """Total plant biomass across all layers at a cell."""
        if not self.in_bounds(x, y):
            return 0.0
        return float(np.sum(self.plant_biomass[:, y, x]))

    def get_plant_biomass_layer(self, x: int, y: int, layer: int) -> float:
        """Biomass of a specific plant layer at (x, y)."""
        if not self.in_bounds(x, y) or not (0 <= layer < NUM_LAYERS):
            return 0.0
        return float(self.plant_biomass[layer, y, x])

    def set_terrain(self, x: int, y: int, terrain: TerrainType) -> None:
        """Set the terrain type at (x, y)."""
        if self.in_bounds(x, y):
            tv = list(TerrainType)
            self.terrain[y, x] = tv.index(terrain)

    def consume_plant(self, x: int, y: int, layer: int, amount: float) -> float:
        """Consume up to *amount* from a plant layer. Returns actual consumed."""
        if not self.in_bounds(x, y):
            return 0.0
        available = float(self.plant_biomass[layer, y, x])
        consumed = min(available, amount)
        self.plant_biomass[layer, y, x] = max(0.0, available - consumed)
        return consumed

    def add_nutrients(self, x: int, y: int, amount: float, radius: int = 2) -> None:
        """Spread nutrients around a point (from carcass decomposition)."""
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                nx, ny = x + dx, y + dy
                if self.in_bounds(nx, ny):
                    dist = (dx * dx + dy * dy) ** 0.5
                    falloff = max(0.0, 1.0 - dist / (radius + 1))
                    self.nutrients[ny, nx] = min(
                        1.0, float(self.nutrients[ny, nx]) + amount * falloff
                    )

    # ------------------------------------------------------------------
    # World generation (procedural, seeded)
    # ------------------------------------------------------------------

    def _generate(self) -> None:
        """Generate terrain, water, and initial plant biomass."""
        self._generate_terrain()
        self._generate_water()
        self._generate_plants()
        self._build_water_sets()
        self._init_nutrients()

    def _generate_terrain(self) -> None:
        """Use layered noise to assign terrain types."""
        h, w = self.height, self.width

        # Base elevation noise
        elev = self.rng.noise_2d(h, w, scale=1.0)
        # Moisture noise
        moist = self.rng.noise_2d(h, w, scale=1.0)
        # Rocky noise
        rocky = self.rng.noise_2d(h, w, scale=1.0)

        terrain_map = np.zeros((h, w), dtype=np.int8)
        terrain_values = list(TerrainType)

        for y in range(h):
            for x in range(w):
                e = float(elev[y, x])
                m = float(moist[y, x])
                r = float(rocky[y, x])

                if e < 0.25 and m > 0.6:
                    t = TerrainType.SWAMP
                elif e < 0.35:
                    t = TerrainType.FLOODPLAIN
                elif e < 0.45 and m > 0.5:
                    t = TerrainType.MUD_FLATS
                elif r > 0.75:
                    t = TerrainType.ROCKY_HILLS
                elif e > 0.7:
                    t = TerrainType.FOREST
                elif e > 0.55:
                    t = TerrainType.OPEN_WOODLAND
                else:
                    t = TerrainType.FLOODPLAIN

                terrain_map[y, x] = terrain_values.index(t)

        # Carve a main river from west to east with random wandering
        self._carve_river(terrain_map, terrain_values)

        # Add a couple of lakes
        margin_x = max(2, min(20, w // 4))
        margin_y = max(2, min(20, h // 4))
        for _ in range(2):
            lx = self.rng.randint(margin_x, max(margin_x, w - margin_x))
            ly = self.rng.randint(margin_y, max(margin_y, h - margin_y))
            lr = self.rng.randint(2, max(3, min(8, min(w, h) // 5)))
            for dy in range(-lr, lr + 1):
                for dx in range(-lr, lr + 1):
                    if dx * dx + dy * dy <= lr * lr:
                        nx, ny = lx + dx, ly + dy
                        if 0 <= nx < w and 0 <= ny < h:
                            terrain_map[ny, nx] = terrain_values.index(TerrainType.LAKE)

        self.terrain = terrain_map

    def _carve_river(
        self, terrain_map: np.ndarray, terrain_values: list[TerrainType]
    ) -> None:
        """Carve a winding river from the left to the right edge."""
        h, w = self.height, self.width
        y = self.rng.randint(h // 3, 2 * h // 3)
        river_idx = terrain_values.index(TerrainType.RIVER)
        for x in range(w):
            for dy in (-1, 0, 1):
                ny = y + dy
                if 0 <= ny < h:
                    terrain_map[ny, x] = river_idx
            # Random walk
            y += self.rng.randint(-1, 1)
            y = max(2, min(h - 3, y))

    def _generate_water(self) -> None:
        """Set water depth based on terrain."""
        tv = list(TerrainType)
        for y in range(self.height):
            for x in range(self.width):
                t = tv[self.terrain[y, x]]
                if t == TerrainType.LAKE:
                    self.water_depth[y, x] = self.rng.uniform(2.0, 6.0)
                elif t == TerrainType.RIVER:
                    self.water_depth[y, x] = self.rng.uniform(0.3, 1.5)
                elif t == TerrainType.SWAMP:
                    self.water_depth[y, x] = self.rng.uniform(0.1, 0.5)
                else:
                    self.water_depth[y, x] = 0.0

    def _generate_plants(self) -> None:
        """Initialise plant biomass according to terrain capacity."""
        tv = list(TerrainType)
        cap = TERRAIN_PLANT_CAPACITY
        for y in range(self.height):
            for x in range(self.width):
                t = tv[self.terrain[y, x]]
                capacities = cap.get(t, [0.0] * NUM_LAYERS)
                for layer in range(NUM_LAYERS):
                    c = capacities[layer]
                    if c > 0:
                        # Start at 50–90% of capacity
                        initial = self.rng.uniform(0.5, 0.9) * c
                        self.plant_biomass[layer, y, x] = initial

    def _build_water_sets(self) -> None:
        """Cache which cells are water, and which are adjacent to water."""
        tv = list(TerrainType)
        for y in range(self.height):
            for x in range(self.width):
                t = tv[self.terrain[y, x]]
                if t in (TerrainType.RIVER, TerrainType.LAKE, TerrainType.SWAMP):
                    self._water_cells.add((x, y))

        for (x, y) in list(self._water_cells):
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nx, ny = x + dx, y + dy
                if (nx, ny) not in self._water_cells and self.in_bounds(nx, ny):
                    self._water_edge_cells.add((nx, ny))

    def _init_nutrients(self) -> None:
        """Initial nutrient level based on terrain type."""
        tv = list(TerrainType)
        for y in range(self.height):
            for x in range(self.width):
                t = tv[self.terrain[y, x]]
                if t == TerrainType.FOREST:
                    self.nutrients[y, x] = self.rng.uniform(0.6, 0.9)
                elif t == TerrainType.FLOODPLAIN:
                    self.nutrients[y, x] = self.rng.uniform(0.5, 0.8)
                elif t in (TerrainType.SWAMP, TerrainType.MUD_FLATS):
                    self.nutrients[y, x] = self.rng.uniform(0.4, 0.7)
                elif t in (TerrainType.LAKE, TerrainType.RIVER):
                    self.nutrients[y, x] = self.rng.uniform(0.3, 0.6)
                else:
                    self.nutrients[y, x] = self.rng.uniform(0.2, 0.5)

    # ------------------------------------------------------------------
    # Per-tick updates
    # ------------------------------------------------------------------

    def step(self) -> None:
        """Advance the world by one tick."""
        self.tick += 1
        prev_day = self.day
        self.day = self.tick // self.ticks_per_day
        tick_in_day = self.tick % self.ticks_per_day

        # Dawn / dusk events
        if self.event_bus:
            if tick_in_day == 12:  # ~6 AM
                self.event_bus.emit(Event(
                    tick=self.tick,
                    category=EventCategory.WORLD,
                    subcategory=EventSubcategory.DAWN,
                    actor_ids=[],
                    position=None,
                    payload={"day": self.day, "season": self.season, "temperature": round(self.temperature, 1)},
                ))
            elif tick_in_day == 40:  # ~8 PM
                self.event_bus.emit(Event(
                    tick=self.tick,
                    category=EventCategory.WORLD,
                    subcategory=EventSubcategory.DUSK,
                    actor_ids=[],
                    position=None,
                    payload={"day": self.day, "season": self.season},
                ))
            if self.day != prev_day:
                self.event_bus.emit(Event(
                    tick=self.tick,
                    category=EventCategory.WORLD,
                    subcategory=EventSubcategory.DAY_START,
                    actor_ids=[],
                    position=None,
                    payload={"day": self.day, "season": self.season},
                ))

        # Season transitions
        season_day = self.day % (self.days_per_season * len(SEASONS))
        new_season_index = season_day // self.days_per_season
        if new_season_index != self.season_index:
            old_season = self.season
            self.season_index = new_season_index
            if self.event_bus:
                self.event_bus.emit(Event(
                    tick=self.tick,
                    category=EventCategory.WORLD,
                    subcategory=EventSubcategory.SEASON_CHANGE,
                    actor_ids=[],
                    position=None,
                    payload={"old_season": old_season, "new_season": self.season},
                ))

        self._update_weather()
        self._update_plants()
        self._update_nutrients()

    def _update_weather(self) -> None:
        """Tick the weather state machine."""
        if self.weather.ticks_remaining > 0:
            self.weather.ticks_remaining -= 1
            if self.weather.ticks_remaining == 0:
                old = self.weather.current
                self.weather.current = WeatherType.CLEAR
                self.weather.visibility_modifier = 1.0
                self.weather.rainfall_intensity = 0.0
                if self.event_bus:
                    self.event_bus.emit(Event(
                        tick=self.tick,
                        category=EventCategory.WORLD,
                        subcategory=EventSubcategory.WEATHER_END,
                        actor_ids=[],
                        position=None,
                        payload={"weather": old.value},
                    ))
                # Clear flood cells
                if old == WeatherType.FLOOD:
                    self.weather.flood_cells.clear()
            return

        # Decide if a new weather event starts (per tick)
        season = self.season
        rain_prob = {"SPRING": 0.006, "SUMMER": 0.003, "AUTUMN": 0.005, "WINTER": 0.008}.get(season, 0.004)
        drought_prob = {"SUMMER": 0.002, "SPRING": 0.0005}.get(season, 0.0)
        storm_prob = 0.0015

        roll = self.rng.random()
        if roll < storm_prob:
            self._start_weather(WeatherType.STORM, self.rng.randint(24, 96))
        elif roll < storm_prob + rain_prob:
            self._start_weather(WeatherType.RAIN, self.rng.randint(48, 240))
        elif roll < storm_prob + rain_prob + drought_prob:
            self._start_weather(WeatherType.DROUGHT, self.rng.randint(240, 1440))

        # Advance drought
        if self.weather.current == WeatherType.DROUGHT:
            self._drought_duration += 1
        else:
            self._drought_duration = 0

        # Accumulate rain → flood trigger
        if self.weather.current in (WeatherType.RAIN, WeatherType.STORM):
            self._rain_accumulation += self.weather.rainfall_intensity
            if self._rain_accumulation > 8.0 and self.rng.chance(0.05):
                self._trigger_flood()
        else:
            self._rain_accumulation = max(0.0, self._rain_accumulation - 0.1)

        # Lightning → wildfire (during storm, on dry vegetation)
        if self.weather.current == WeatherType.STORM and self.rng.chance(0.01):
            self._trigger_lightning()

    def _start_weather(self, wtype: WeatherType, duration_ticks: int) -> None:
        """Begin a weather event."""
        self.weather.current = wtype
        self.weather.ticks_remaining = duration_ticks
        if wtype in (WeatherType.RAIN, WeatherType.STORM):
            self.weather.rainfall_intensity = self.rng.uniform(0.4, 1.0) if wtype == WeatherType.STORM else self.rng.uniform(0.1, 0.5)
            self.weather.visibility_modifier = 0.3 if wtype == WeatherType.STORM else 0.7
        elif wtype == WeatherType.DROUGHT:
            self.weather.rainfall_intensity = 0.0
            self.weather.visibility_modifier = 1.0
        elif wtype == WeatherType.FIRE:
            self.weather.visibility_modifier = 0.5

        if self.event_bus:
            self.event_bus.emit(Event(
                tick=self.tick,
                category=EventCategory.WORLD,
                subcategory=EventSubcategory.WEATHER_START,
                actor_ids=[],
                position=None,
                payload={
                    "weather": wtype.value,
                    "duration_ticks": duration_ticks,
                    "intensity": self.weather.rainfall_intensity,
                },
            ))

    def _trigger_lightning(self) -> None:
        """Lightning strike on a random forested/dry cell — may start fire."""
        x = self.rng.randint(0, self.width - 1)
        y = self.rng.randint(0, self.height - 1)
        tv = list(TerrainType)
        t = tv[self.terrain[y, x]]
        if t in (TerrainType.FOREST, TerrainType.OPEN_WOODLAND, TerrainType.FLOODPLAIN):
            plant_fuel = float(np.sum(self.plant_biomass[:, y, x]))
            if plant_fuel > 0.5:
                self.weather.fire_cells.add((x, y))
                if self.event_bus:
                    self.event_bus.emit(Event(
                        tick=self.tick,
                        category=EventCategory.WORLD,
                        subcategory=EventSubcategory.FIRE_SPREAD,
                        actor_ids=[],
                        position=(x, y),
                        payload={"ignition": True, "cause": "lightning"},
                    ))

    def _trigger_flood(self) -> None:
        """Expand water cells into adjacent low terrain."""
        new_flood: set[tuple[int, int]] = set()
        tv = list(TerrainType)
        for (wx, wy) in self._water_cells:
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nx, ny = wx + dx, wy + dy
                if not self.in_bounds(nx, ny):
                    continue
                t = tv[self.terrain[ny, nx]]
                if t in (TerrainType.FLOODPLAIN, TerrainType.MUD_FLATS) and (nx, ny) not in self._water_cells:
                    new_flood.add((nx, ny))

        self.weather.flood_cells.update(new_flood)
        self._start_weather(WeatherType.FLOOD, self.rng.randint(48, 144))
        if self.event_bus:
            self.event_bus.emit(Event(
                tick=self.tick,
                category=EventCategory.WORLD,
                subcategory=EventSubcategory.FLOOD_EXPAND,
                actor_ids=[],
                position=None,
                payload={"cells_flooded": len(new_flood)},
            ))
        self._rain_accumulation = 0.0

    def _update_plants(self) -> None:
        """Logistic regrowth of all plant layers, modulated by season and nutrients."""
        season_mods = {"SPRING": 1.4, "SUMMER": 1.0, "AUTUMN": 0.6, "WINTER": 0.2}
        s_mod = season_mods.get(self.season, 1.0)

        drought_mod = 0.1 if self.weather.current == WeatherType.DROUGHT else 1.0
        rain_mod = 1.4 if self.weather.current == WeatherType.RAIN else 1.0

        tv = list(TerrainType)
        cap = TERRAIN_PLANT_CAPACITY

        for y in range(self.height):
            for x in range(self.width):
                t = tv[self.terrain[y, x]]
                capacities = cap.get(t, [0.0] * NUM_LAYERS)
                n = float(self.nutrients[y, x])
                n_mod = 0.5 + 0.5 * n

                for layer in range(NUM_LAYERS):
                    c = capacities[layer]
                    if c <= 0:
                        continue
                    b = float(self.plant_biomass[layer, y, x])
                    rate = PLANT_REGROWTH_BASE[layer] * s_mod * drought_mod * rain_mod * n_mod
                    new_b = b + rate * (1.0 - b / c) * c
                    self.plant_biomass[layer, y, x] = min(c, max(0.0, new_b))

        # Fire: burn cells
        burned = set()
        spread = set()
        for (fx, fy) in list(self.weather.fire_cells):
            # Consume plants
            self.plant_biomass[:, fy, fx] = 0.0
            burned.add((fx, fy))
            # Spread to neighbours with wind bias
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nx, ny = fx + dx, fy + dy
                if not self.in_bounds(nx, ny):
                    continue
                if (nx, ny) in self.weather.fire_cells:
                    continue
                fuel = float(np.sum(self.plant_biomass[:, ny, nx]))
                if fuel > 0.3 and self.rng.chance(0.12):
                    spread.add((nx, ny))

        self.weather.fire_cells.update(spread)
        # Random extinguishing
        to_extinguish = {c for c in self.weather.fire_cells if self.rng.chance(0.04)}
        self.weather.fire_cells -= to_extinguish

    def _update_nutrients(self) -> None:
        """Slowly deplete nutrients consumed by plant growth; forest floor replenishes."""
        # Natural leaf litter in forests
        tv = list(TerrainType)
        decay_rate = 0.0002
        litter_rate = 0.0005

        for y in range(self.height):
            for x in range(self.width):
                t = tv[self.terrain[y, x]]
                n = float(self.nutrients[y, x])
                if t == TerrainType.FOREST:
                    n = min(1.0, n + litter_rate)
                else:
                    n = max(0.0, n - decay_rate)
                # Rain leaches some nutrients
                if self.weather.current in (WeatherType.RAIN, WeatherType.STORM):
                    n = max(0.0, n - 0.0001)
                self.nutrients[y, x] = n

    # ------------------------------------------------------------------
    # State serialisation (for snapshot / replay)
    # ------------------------------------------------------------------

    def get_state(self) -> dict:
        """Return a serialisable snapshot of world state."""
        return {
            "width": self.width,
            "height": self.height,
            "seed": self.seed,
            "tick": self.tick,
            "day": self.day,
            "season_index": self.season_index,
            "terrain": self.terrain.tolist(),
            "water_depth": self.water_depth.tolist(),
            "nutrients": self.nutrients.tolist(),
            "plant_biomass": self.plant_biomass.tolist(),
            "weather": {
                "current": self.weather.current.value,
                "ticks_remaining": self.weather.ticks_remaining,
                "rainfall_intensity": self.weather.rainfall_intensity,
                "wind_direction": self.weather.wind_direction,
                "wind_speed": self.weather.wind_speed,
                "visibility_modifier": self.weather.visibility_modifier,
                "fire_cells": list(self.weather.fire_cells),
                "flood_cells": list(self.weather.flood_cells),
            },
        }

    def set_state(self, state: dict) -> None:
        """Restore world from a snapshot."""
        self.tick = state["tick"]
        self.day = state["day"]
        self.season_index = state["season_index"]
        self.terrain = np.array(state["terrain"], dtype=np.int8)
        self.height, self.width = self.terrain.shape
        self.water_depth = np.array(state["water_depth"], dtype=np.float32)
        self.nutrients = np.array(state["nutrients"], dtype=np.float32)
        self.plant_biomass = np.array(state["plant_biomass"], dtype=np.float32)
        w = state["weather"]
        self.weather.current = WeatherType(w["current"])
        self.weather.ticks_remaining = w["ticks_remaining"]
        self.weather.rainfall_intensity = w["rainfall_intensity"]
        self.weather.wind_direction = w["wind_direction"]
        self.weather.wind_speed = w["wind_speed"]
        self.weather.visibility_modifier = w["visibility_modifier"]
        self.weather.fire_cells = {tuple(c) for c in w["fire_cells"]}
        self.weather.flood_cells = {tuple(c) for c in w["flood_cells"]}
        self._build_water_sets()
