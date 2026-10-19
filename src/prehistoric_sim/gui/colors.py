"""
colors.py — Pygame RGB colour palette for the JurassicEra GUI.

Maps terrain types, species, actions, event categories, and UI chrome
to concrete (R, G, B) tuples so nothing is hard-coded elsewhere.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Base palette
# ---------------------------------------------------------------------------

BLACK       = (0,   0,   0)
WHITE       = (255, 255, 255)
TRANSPARENT = (0,   0,   0,   0)

# UI chrome
BG_DARK        = (10,  12,  18)    # main background
PANEL_BG       = (16,  20,  30)    # side panel background
PANEL_BORDER   = (40,  55,  80)    # panel borders / dividers
HEADER_BG      = (20,  26,  42)    # panel header bar
TITLE_TEXT     = (180, 210, 255)   # panel titles
BODY_TEXT      = (190, 200, 215)   # regular text
DIM_TEXT       = (90,  100, 120)   # timestamps / dim labels
INPUT_BG       = (12,  16,  26)    # admin input bar background
INPUT_BORDER   = (60,  80,  130)   # admin input border
INPUT_CURSOR   = (100, 160, 255)   # cursor colour
SCROLLBAR_BG   = (25,  30,  45)
SCROLLBAR_FG   = (55,  70,  110)
TOOLTIP_BG     = (18,  22,  35)
TOOLTIP_BORDER = (80,  100, 160)

# HUD / overlay
HUD_BG         = (10,  14,  22,  200)  # semi-transparent
HUD_TEXT       = (220, 235, 255)
HUD_ACCENT     = (100, 200, 255)
HUD_DANGER     = (255,  60,  60)
HUD_WARNING    = (255, 190,  40)
HUD_OK         = ( 80, 220, 120)

# Selection / highlight
SELECT_OUTLINE = (255, 230,  80)    # selected creature ring
TRACK_OUTLINE  = (120, 255, 200)    # tracked creature ring
POSSESS_OUTLINE= (255, 100, 255)    # possessed creature ring
HOVER_TINT     = (255, 255, 255,  40)

# ---------------------------------------------------------------------------
# Terrain colours  (base ground fill)
# ---------------------------------------------------------------------------

TERRAIN_COLORS: dict[str, tuple[int, int, int]] = {
    "FLOODPLAIN":    ( 58, 110,  48),
    "FOREST":        ( 22,  68,  22),
    "OPEN_WOODLAND": ( 72, 128,  40),
    "SWAMP":         ( 30,  80,  60),
    "RIVER":         ( 30,  80, 170),
    "LAKE":          ( 20,  55, 150),
    "ROCKY_HILLS":   ( 95,  90,  80),
    "MUD_FLATS":     ( 90,  78,  52),
}

# Water shimmer tint layered on top
WATER_SHIMMER  = (80, 150, 255)
WATER_DEEP     = (10,  35, 120)

# ---------------------------------------------------------------------------
# Biome overlay tints  (blended over terrain based on plant biomass)
# ---------------------------------------------------------------------------

PLANT_TINT     = (30, 160,  30)     # lush green tint when biomass high
NUTRIENT_TINT  = (180, 130,  10)    # golden tint on high-nutrient soil

# ---------------------------------------------------------------------------
# Hazard overlays
# ---------------------------------------------------------------------------

FIRE_COLORS    = [(255, 60, 0), (255, 140, 0), (255, 220, 40)]   # animated
FLOOD_COLOR    = (30,  90, 200,  140)   # semi-transparent blue
SMOKE_COLOR    = (60,  55,  50,  100)

# ---------------------------------------------------------------------------
# Species colours  (RGB, matches theme.yaml but concrete values)
# ---------------------------------------------------------------------------

SPECIES_COLORS: dict[str, tuple[int, int, int]] = {
    "tyrannosaurus_rex":  (220,  40,  40),
    "dakotaraptor":       (230, 120,  20),
    "acheroraptor":       (220, 200,  20),
    "anzu_wyliei":        (200,  60, 200),
    "triceratops":        ( 60, 200,  60),
    "edmontosaurus":      ( 40, 200, 200),
    "ankylosaurus":       ( 60,  80, 220),
    "pachycephalosaurus": (160,  60, 220),
    "thescelosaurus":     (100, 220,  80),
    "deinosuchus":        ( 30, 130,  50),
    "freshwater_fish":    ( 80, 200, 220),
    "freshwater_turtle":  ( 90, 140,  50),
    "quetzalcoatlus":     (100, 180, 255),
    "didelphodon":        (140, 140, 150),
    "insect_swarm":       (200, 200,  40),
    "default":            (200, 200, 200),
}

# Diet-based fallback dot colours
DIET_COLORS: dict[str, tuple[int, int, int]] = {
    "CARNIVORE":    (220,  50,  50),
    "HERBIVORE":    ( 60, 200,  80),
    "OMNIVORE":     (200, 160,  40),
    "INSECTIVORE":  (180, 180,  40),
    "PISCIVORE":    ( 60, 160, 220),
}

# ---------------------------------------------------------------------------
# Life-stage sizing multipliers (for dot radius)
# ---------------------------------------------------------------------------

STAGE_RADIUS: dict[str, float] = {
    "HATCHLING": 0.30,
    "JUVENILE":  0.50,
    "SUBADULT":  0.75,
    "ADULT":     1.00,
    "SENESCENT": 0.90,
}

# ---------------------------------------------------------------------------
# Action glow colours (faint aura while doing an action)
# ---------------------------------------------------------------------------

ACTION_COLORS: dict[str, tuple[int, int, int]] = {
    "HUNT":       (255,  40,  40),
    "FLEE":       (255, 200,  40),
    "FIGHT":      (255,  80,  20),
    "EAT":        (255, 140,  20),
    "SCAVENGE":   (180, 100,  20),
    "DRINK":      ( 60, 140, 255),
    "GRAZE":      ( 80, 200,  80),
    "MATE":       (255, 100, 220),
    "GUARD_NEST": (160, 240, 160),
    "SLEEP":      ( 80,  80, 160),
    "REST":       (100, 100, 180),
    "WANDER":     (120, 120, 140),
    "MIGRATE":    (180, 180,  60),
    "default":    (120, 120, 140),
}

# ---------------------------------------------------------------------------
# Event log category colours
# ---------------------------------------------------------------------------

EVENT_COLORS: dict[str, tuple[int, int, int]] = {
    "LIFECYCLE_BIRTH":        ( 80, 230, 100),
    "LIFECYCLE_DEATH":        (220,  50,  50),
    "LIFECYCLE_STAGE_CHANGE": (100, 200, 100),
    "LIFECYCLE_EGG_LAID":     (240, 220,  80),
    "LIFECYCLE_HATCHING":     (255, 240, 100),
    "LIFECYCLE_MATING":       (255, 120, 200),
    "LIFECYCLE_CARCASS_FORMED":(160,  60,  60),
    "INTERACTION_HUNT_SUCCESS":(255, 120,  20),
    "INTERACTION_HUNT_FAIL":  (200, 160,  60),
    "INTERACTION_FIGHT":      (220,  40,  40),
    "INTERACTION_FLEE":       (255, 200,  40),
    "INTERACTION_ALARM_CALL": (255, 210,  40),
    "INTERACTION_DRINK":      ( 80, 160, 255),
    "INTERACTION_EAT":        (200, 140,  40),
    "WORLD_DAWN":             (255, 220, 100),
    "WORLD_DUSK":             (180, 100, 200),
    "WORLD_SEASON_CHANGE":    (200, 160, 255),
    "WORLD_WEATHER_START":    (100, 160, 255),
    "WORLD_FIRE_SPREAD":      (255,  80,  20),
    "WORLD_FLOOD_EXPAND":     ( 60, 120, 255),
    "ADMIN_ADMIN_COMMAND":    (255, 230,  60),
    "SYSTEM_POP_CAP":         (255,  60,  60),
    "SYSTEM_SPECIES_EXTINCT": (220,  40,  40),
    "default":                (180, 190, 210),
}

# ---------------------------------------------------------------------------
# Day / night sky colours  (interpolated based on hour_of_day)
# ---------------------------------------------------------------------------

SKY_NIGHT  = ( 8,   8,  25)
SKY_DAWN   = ( 60,  30,  60)
SKY_DAY    = ( 30,  60, 120)
SKY_DUSK   = ( 80,  40,  20)
