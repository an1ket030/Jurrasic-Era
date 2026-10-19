"""
creature_renderer.py — High-detail 2.5D Low-Poly Dinosaur & Creature Renderer.

Renders distinctive low-poly polygonal models for all 15 species with:
  • Faceted geometric body parts (head, horns, frills, back plates, tail, legs)
  • Directional heading rotation & smooth orientation
  • Ground drop-shadows with realistic 3D depth
  • Sinusoidal walking animations (tail sway, stepping limbs, breathing pulse)
  • Life-stage visual scaling (Hatchling -> Juvenile -> Subadult -> Adult -> Elder)
  • Tactical selection rings & action state bubbles (Hunt, Flee, Sleep, Mate, Eat)
"""

from __future__ import annotations

import math
import random
from typing import Any

import pygame

# Sizing multipliers per species category
SPECIES_BASE_SCALE: dict[str, float] = {
    "tyrannosaurus_rex":  1.6,
    "triceratops":        1.4,
    "edmontosaurus":      1.5,
    "ankylosaurus":       1.3,
    "dakotaraptor":       1.1,
    "acheroraptor":       0.85,
    "anzu_wyliei":        1.0,
    "pachycephalosaurus": 1.0,
    "thescelosaurus":     0.8,
    "quetzalcoatlus":     1.7,
    "deinosuchus":        1.5,
    "freshwater_turtle":  0.75,
    "freshwater_fish":    0.65,
    "didelphodon":        0.6,
    "insect_swarm":       0.6,
    "default":            1.0,
}

# Color palettes with facet highlights and shadows
SPECIES_PALETTES: dict[str, dict[str, tuple[int, int, int]]] = {
    "tyrannosaurus_rex": {
        "body":       (195,  45,  38),
        "highlight":  (235,  75,  65),
        "shadow":     (120,  25,  22),
        "belly":      (220, 160, 120),
        "eye":        (255, 200,  30),
        "teeth":      (245, 240, 220),
    },
    "triceratops": {
        "body":       ( 68, 148,  62),
        "highlight":  ( 95, 185,  85),
        "shadow":     ( 38,  92,  36),
        "frill":      ( 82, 165,  75),
        "horns":      (240, 235, 205),
        "eye":        ( 20,  20,  20),
    },
    "dakotaraptor": {
        "body":       (225, 125,  35),
        "highlight":  (250, 165,  65),
        "shadow":     (150,  75,  18),
        "feathers":   (200,  55,  30),
        "eye":        (255, 220,  40),
    },
    "acheroraptor": {
        "body":       (210, 180,  35),
        "highlight":  (240, 215,  75),
        "shadow":     (140, 115,  18),
        "feathers":   (180,  85,  25),
        "eye":        (255, 220,  40),
    },
    "ankylosaurus": {
        "body":       ( 85,  95, 120),
        "highlight":  (115, 130, 160),
        "shadow":     ( 50,  58,  75),
        "spikes":     (225, 220, 190),
        "club":       ( 60,  65,  80),
    },
    "edmontosaurus": {
        "body":       ( 45, 145, 140),
        "highlight":  ( 70, 185, 175),
        "shadow":     ( 25,  95,  90),
        "crest":      (210,  90,  70),
        "bill":       ( 35,  75,  70),
    },
    "pachycephalosaurus": {
        "body":       (150,  95, 165),
        "highlight":  (185, 125, 200),
        "shadow":     ( 95,  55, 105),
        "dome":       (235, 225, 210),
    },
    "thescelosaurus": {
        "body":       (110, 180,  80),
        "highlight":  (145, 215, 110),
        "shadow":     ( 65, 115,  45),
        "belly":      (210, 225, 175),
    },
    "anzu_wyliei": {
        "body":       (175,  70, 165),
        "highlight":  (215, 105, 205),
        "shadow":     (110,  40, 105),
        "crest":      (245, 180,  40),
    },
    "quetzalcoatlus": {
        "body":       (100, 160, 220),
        "highlight":  (145, 200, 255),
        "shadow":     ( 55, 105, 155),
        "wings":      (180, 205, 235),
        "beak":       (245, 165,  40),
    },
    "deinosuchus": {
        "body":       ( 45, 105,  55),
        "highlight":  ( 70, 140,  80),
        "shadow":     ( 25,  65,  32),
        "scutes":     ( 35,  80,  40),
        "belly":      (165, 175, 125),
    },
    "didelphodon": {
        "body":       (155, 135, 120),
        "highlight":  (195, 175, 160),
        "shadow":     (100,  85,  75),
        "belly":      (220, 210, 200),
    },
    "freshwater_turtle": {
        "body":       ( 85, 125,  65),
        "highlight":  (115, 165,  90),
        "shadow":     ( 50,  80,  38),
        "shell":      (110,  95,  55),
    },
    "freshwater_fish": {
        "body":       ( 80, 175, 205),
        "highlight":  (120, 215, 245),
        "shadow":     ( 45, 115, 140),
        "fins":       (160, 225, 245),
    },
    "insect_swarm": {
        "body":       (225, 215,  60),
        "highlight":  (255, 250, 140),
        "shadow":     (150, 140,  30),
    },
}


def _rotate_point(x: float, y: float, angle_rad: float, cx: float = 0.0, cy: float = 0.0) -> tuple[float, float]:
    """Rotate (x, y) around (cx, cy) by angle_rad."""
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    nx = cx + (x - cx) * cos_a - (y - cy) * sin_a
    ny = cy + (x - cx) * sin_a + (y - cy) * cos_a
    return (nx, ny)


def _draw_polygon_rotated(
    surface: pygame.Surface,
    pts: list[tuple[float, float]],
    color: tuple[int, int, int],
    cx: float,
    cy: float,
    angle_rad: float,
) -> None:
    """Draw a rotated polygon centered at (cx, cy)."""
    rot_pts = [_rotate_point(px + cx, py + cy, angle_rad, cx, cy) for px, py in pts]
    pygame.draw.polygon(surface, color, [(int(rx), int(ry)) for rx, ry in rot_pts])


class CreatureRenderer:
    """Renders top-down 2.5D low-poly dinosaurs with walking cycles, heading, and shadows."""

    def __init__(self) -> None:
        self._font_bubble: pygame.font.Font | None = None

    def _ensure_font(self) -> None:
        if self._font_bubble is None:
            try:
                self._font_bubble = pygame.font.SysFont("segoeui", 11, bold=True)
            except Exception:
                self._font_bubble = pygame.font.Font(None, 14)

    def draw_creature(
        self,
        surface: pygame.Surface,
        screen_x: float,
        screen_y: float,
        species_key: str,
        life_stage: str,
        heading_rad: float,
        walk_phase: float,
        cell_px: float,
        health: float = 1.0,
        action: str = "WANDER",
        is_selected: bool = False,
        is_tracked: bool = False,
        is_possessed: bool = False,
    ) -> None:
        """Draw a single creature with full low-poly geometry at (screen_x, screen_y)."""
        self._ensure_font()

        # Life stage sizing multiplier
        stage_mults = {
            "HATCHLING": 0.40,
            "JUVENILE":  0.65,
            "SUBADULT":  0.85,
            "ADULT":     1.05,
            "SENESCENT": 0.98,
        }
        stage_mult = stage_mults.get(life_stage, 1.0)
        base_scale = SPECIES_BASE_SCALE.get(species_key, 1.0)
        
        # Pixels scale for this creature
        # Enlarged low-poly model for clear visibility and distinct anatomy
        size = max(8.0, cell_px * 1.35 * base_scale * stage_mult)
        
        pal = SPECIES_PALETTES.get(species_key, SPECIES_PALETTES["tyrannosaurus_rex"])
        
        # Health tinting
        if health < 0.35:
            dim = 0.5 + 0.5 * (health / 0.35)
            body_col = (int(pal["body"][0] * dim), int(pal["body"][1] * dim), int(pal["body"][2] * dim))
        else:
            body_col = pal["body"]
        hi_col  = pal.get("highlight", body_col)
        sh_col  = pal.get("shadow", body_col)

        # 1. Ground Drop Shadow (3D Depth)
        shadow_w = int(size * 1.3)
        shadow_h = int(size * 0.65)
        shadow_surf = pygame.Surface((shadow_w * 2, shadow_h * 2), pygame.SRCALPHA)
        # Cast shadow offset to bottom-left (simulating top-right sun angle like in concept art)
        pygame.draw.ellipse(shadow_surf, (15, 20, 30, 95), (0, 0, shadow_w * 2, shadow_h * 2))
        surface.blit(shadow_surf, (int(screen_x - shadow_w - size * 0.15), int(screen_y - shadow_h * 0.3 + size * 0.25)))

        # Breathing / subtle walking bob
        bob_y = math.sin(walk_phase * 2.0) * (size * 0.06)
        cy = screen_y + bob_y
        cx = screen_x

        # Tail sway angle
        tail_sway = math.sin(walk_phase) * 0.28

        # 2. Render species-specific low-poly mesh
        if species_key in ("tyrannosaurus_rex", "dakotaraptor", "acheroraptor", "anzu_wyliei", "thescelosaurus", "pachycephalosaurus"):
            self._draw_theropod(surface, cx, cy, heading_rad, size, pal, body_col, hi_col, sh_col, tail_sway, walk_phase, species_key)
        elif species_key == "triceratops":
            self._draw_ceratopsian(surface, cx, cy, heading_rad, size, pal, body_col, hi_col, sh_col, tail_sway, walk_phase)
        elif species_key == "ankylosaurus":
            self._draw_ankylosaur(surface, cx, cy, heading_rad, size, pal, body_col, hi_col, sh_col, tail_sway, walk_phase)
        elif species_key == "edmontosaurus":
            self._draw_hadrosaur(surface, cx, cy, heading_rad, size, pal, body_col, hi_col, sh_col, tail_sway, walk_phase)
        elif species_key == "quetzalcoatlus":
            self._draw_pterosaur(surface, cx, cy, heading_rad, size, pal, body_col, hi_col, sh_col, walk_phase)
        elif species_key == "deinosuchus":
            self._draw_crocodilian(surface, cx, cy, heading_rad, size, pal, body_col, hi_col, sh_col, tail_sway)
        elif species_key in ("freshwater_turtle", "freshwater_fish"):
            self._draw_aquatic(surface, cx, cy, heading_rad, size, pal, body_col, hi_col, species_key, tail_sway)
        elif species_key == "didelphodon":
            self._draw_mammal(surface, cx, cy, heading_rad, size, pal, body_col, hi_col, walk_phase)
        elif species_key == "insect_swarm":
            self._draw_swarm(surface, cx, cy, size, pal, walk_phase)
        else:
            self._draw_generic_creature(surface, cx, cy, heading_rad, size, body_col, hi_col, sh_col, tail_sway)

        # 3. Tactical Selection / Tracking Reticle
        if is_selected:
            self._draw_selection_ring(surface, screen_x, screen_y, size * 1.5, (255, 230, 80))
        elif is_tracked:
            self._draw_selection_ring(surface, screen_x, screen_y, size * 1.3, (80, 220, 255))
        elif is_possessed:
            self._draw_selection_ring(surface, screen_x, screen_y, size * 1.6, (255, 80, 255))

        # 4. Action Bubble / Visual State (shown for selected/tracked or high intensity hunt/flee)
        if (is_selected or is_tracked or is_possessed) and action in ("HUNT", "FLEE", "SLEEP", "MATE", "DRINK", "EAT"):
            self._draw_action_indicator(surface, screen_x, screen_y - size * 0.9, action)
        elif action in ("HUNT", "FLEE"):
            self._draw_action_indicator(surface, screen_x, screen_y - size * 0.9, action)

    # ------------------------------------------------------------------
    # Theropod / Raptor / T-Rex low-poly model
    # ------------------------------------------------------------------
    def _draw_theropod(
        self, surface: pygame.Surface, cx: float, cy: float, heading: float,
        size: float, pal: dict, body_col: tuple, hi_col: tuple, sh_col: tuple,
        tail_sway: float, walk: float, species: str,
    ) -> None:
        s = size * 0.5
        leg_step = math.sin(walk * 2.0) * (s * 0.4)

        # Hind legs (stepped)
        _draw_polygon_rotated(surface, [(-s*0.2, s*0.6 + leg_step), (-s*0.5, s*0.8 + leg_step), (-s*0.2, s*1.0 + leg_step)], sh_col, cx, cy, heading)
        _draw_polygon_rotated(surface, [(s*0.2, -s*0.6 - leg_step), (s*0.5, -s*0.8 - leg_step), (s*0.2, -s*1.0 - leg_step)], sh_col, cx, cy, heading)

        # Tail (faceted joint) with tail sway
        tail_ang = heading + tail_sway
        tail_mid = _rotate_point(cx - s*0.8, cy, heading, cx, cy)
        _draw_polygon_rotated(surface, [(0, -s*0.25), (-s*0.9, -s*0.1), (-s*1.4, 0), (-s*0.9, s*0.1), (0, s*0.25)], sh_col, tail_mid[0], tail_mid[1], tail_ang)
        # Tail spine highlight
        _draw_polygon_rotated(surface, [(0, -s*0.08), (-s*0.9, 0), (0, s*0.08)], hi_col, tail_mid[0], tail_mid[1], tail_ang)

        # Torso (angled low-poly hexagon)
        torso_pts = [
            ( s*0.6, -s*0.35),
            ( s*0.8,  0.0),
            ( s*0.4,  s*0.45),
            (-s*0.6,  s*0.4),
            (-s*0.8,  0.0),
            (-s*0.5, -s*0.4),
        ]
        _draw_polygon_rotated(surface, torso_pts, body_col, cx, cy, heading)
        # Torso sunlit facet
        _draw_polygon_rotated(surface, [(s*0.6, -s*0.35), (s*0.8, 0.0), (0, -s*0.1), (-s*0.5, -s*0.4)], hi_col, cx, cy, heading)

        # Neck & Head (reaching forward)
        neck_pts = [(s*0.6, -s*0.2), (s*1.2, -s*0.15), (s*1.2, s*0.15), (s*0.6, s*0.2)]
        _draw_polygon_rotated(surface, neck_pts, body_col, cx, cy, heading)

        # Distinctive species features:
        if species == "pachycephalosaurus":
            # Bone dome
            dome_pts = [(s*1.2, -s*0.3), (s*1.6, -s*0.25), (s*1.8, 0), (s*1.6, s*0.25), (s*1.2, s*0.3)]
            _draw_polygon_rotated(surface, dome_pts, pal.get("dome", (240, 230, 210)), cx, cy, heading)
        else:
            # Massive head & predatory snout
            head_pts = [
                (s*1.1, -s*0.3),
                (s*1.8, -s*0.15),
                (s*2.0,  0.0),
                (s*1.7,  s*0.25),
                (s*1.1,  s*0.3),
            ]
            _draw_polygon_rotated(surface, head_pts, hi_col, cx, cy, heading)

            # Teeth accents on T-Rex
            if species == "tyrannosaurus_rex" and s > 8:
                teeth_col = pal.get("teeth", (240, 240, 220))
                _draw_polygon_rotated(surface, [(s*1.5, -s*0.2), (s*1.7, -s*0.15), (s*1.6, 0.0)], teeth_col, cx, cy, heading)

        # Tiny forelimbs / raptor feathered arms
        if species in ("dakotaraptor", "acheroraptor", "anzu_wyliei"):
            wing_col = pal.get("feathers", (200, 80, 40))
            _draw_polygon_rotated(surface, [(s*0.3, -s*0.4), (s*0.8, -s*0.7), (s*0.6, -s*0.3)], wing_col, cx, cy, heading)
            _draw_polygon_rotated(surface, [(s*0.3,  s*0.4), (s*0.8,  s*0.7), (s*0.6,  s*0.3)], wing_col, cx, cy, heading)

    # ------------------------------------------------------------------
    # Triceratops / Ceratopsian low-poly model
    # ------------------------------------------------------------------
    def _draw_ceratopsian(
        self, surface: pygame.Surface, cx: float, cy: float, heading: float,
        size: float, pal: dict, body_col: tuple, hi_col: tuple, sh_col: tuple,
        tail_sway: float, walk: float,
    ) -> None:
        s = size * 0.5
        leg = math.sin(walk * 2.0) * (s * 0.3)

        # 4 sturdy quadruped legs
        _draw_polygon_rotated(surface, [( s*0.4, -s*0.7 - leg), ( s*0.6, -s*0.6 - leg), ( s*0.3, -s*0.5)], sh_col, cx, cy, heading)
        _draw_polygon_rotated(surface, [( s*0.4,  s*0.7 + leg), ( s*0.6,  s*0.6 + leg), ( s*0.3,  s*0.5)], sh_col, cx, cy, heading)
        _draw_polygon_rotated(surface, [(-s*0.4, -s*0.7 + leg), (-s*0.6, -s*0.6 + leg), (-s*0.3, -s*0.5)], sh_col, cx, cy, heading)
        _draw_polygon_rotated(surface, [(-s*0.4,  s*0.7 - leg), (-s*0.6,  s*0.6 - leg), (-s*0.3,  s*0.5)], sh_col, cx, cy, heading)

        # Short thick tail with sway
        tail_pts = [( -s*0.7, -s*0.25), (-s*1.3 + tail_sway*s*0.5, 0), (-s*0.7, s*0.25)]
        _draw_polygon_rotated(surface, tail_pts, sh_col, cx, cy, heading)

        # Broad armored body
        body_pts = [
            ( s*0.6, -s*0.55),
            ( s*0.8,  0.0),
            ( s*0.6,  s*0.55),
            (-s*0.6,  s*0.5),
            (-s*0.8,  0.0),
            (-s*0.6, -s*0.5),
        ]
        _draw_polygon_rotated(surface, body_pts, body_col, cx, cy, heading)
        # Highlight top facet
        _draw_polygon_rotated(surface, [(s*0.6, -s*0.55), (s*0.8, 0.0), (0, -s*0.1), (-s*0.6, -s*0.5)], hi_col, cx, cy, heading)

        # Massive curved neck frill
        frill_pts = [
            (s*0.5, -s*0.75),
            (s*1.0, -s*0.8),
            (s*1.1,  0.0),
            (s*1.0,  s*0.8),
            (s*0.5,  s*0.75),
        ]
        _draw_polygon_rotated(surface, frill_pts, pal.get("frill", (80, 160, 70)), cx, cy, heading)

        # Beak / Snout
        snout_pts = [(s*1.0, -s*0.25), (s*1.7, 0.0), (s*1.0, s*0.25)]
        _draw_polygon_rotated(surface, snout_pts, hi_col, cx, cy, heading)

        # Three prominent white horns!
        horns_col = pal.get("horns", (245, 240, 215))
        # Left brow horn
        _draw_polygon_rotated(surface, [(s*1.0, -s*0.35), (s*1.9, -s*0.45), (s*1.1, -s*0.2)], horns_col, cx, cy, heading)
        # Right brow horn
        _draw_polygon_rotated(surface, [(s*1.0,  s*0.35), (s*1.9,  s*0.45), (s*1.1,  s*0.2)], horns_col, cx, cy, heading)
        # Nose horn
        _draw_polygon_rotated(surface, [(s*1.4, -s*0.08), (s*1.8, 0.0), (s*1.4, s*0.08)], horns_col, cx, cy, heading)

    # ------------------------------------------------------------------
    # Ankylosaurus / Stegosaurus low-poly tank model
    # ------------------------------------------------------------------
    def _draw_ankylosaur(
        self, surface: pygame.Surface, cx: float, cy: float, heading: float,
        size: float, pal: dict, body_col: tuple, hi_col: tuple, sh_col: tuple,
        tail_sway: float, walk: float,
    ) -> None:
        s = size * 0.5
        # Low wide armored carapace
        body_pts = [
            ( s*0.7, -s*0.6),
            ( s*0.9,  0.0),
            ( s*0.7,  s*0.6),
            (-s*0.7,  s*0.65),
            (-s*0.9,  0.0),
            (-s*0.7, -s*0.65),
        ]
        _draw_polygon_rotated(surface, body_pts, body_col, cx, cy, heading)
        _draw_polygon_rotated(surface, [(s*0.7, -s*0.6), (s*0.9, 0), (0, -s*0.2), (-s*0.7, -s*0.65)], hi_col, cx, cy, heading)

        # Triangular lateral spikes
        spikes_col = pal.get("spikes", (230, 225, 200))
        for ox in [-s*0.4, 0.0, s*0.4]:
            _draw_polygon_rotated(surface, [(ox - s*0.1, -s*0.6), (ox, -s*0.9), (ox + s*0.1, -s*0.6)], spikes_col, cx, cy, heading)
            _draw_polygon_rotated(surface, [(ox - s*0.1,  s*0.6), (ox,  s*0.9), (ox + s*0.1,  s*0.6)], spikes_col, cx, cy, heading)

        # Tail with heavy bony club at tip
        tail_pts = [(-s*0.8, -s*0.2), (-s*1.6 + tail_sway*s*0.6, 0), (-s*0.8, s*0.2)]
        _draw_polygon_rotated(surface, tail_pts, sh_col, cx, cy, heading)
        # Heavy tail club
        club_center = _rotate_point(cx - s*1.6 + tail_sway*s*0.6, cy, heading, cx, cy)
        pygame.draw.circle(surface, pal.get("club", (60, 65, 80)), (int(club_center[0]), int(club_center[1])), max(3, int(s * 0.35)))

    # ------------------------------------------------------------------
    # Hadrosaur / Edmontosaurus
    # ------------------------------------------------------------------
    def _draw_hadrosaur(
        self, surface: pygame.Surface, cx: float, cy: float, heading: float,
        size: float, pal: dict, body_col: tuple, hi_col: tuple, sh_col: tuple,
        tail_sway: float, walk: float,
    ) -> None:
        s = size * 0.5
        # Elongated body
        body_pts = [(s*0.7, -s*0.4), (s*0.9, 0), (s*0.7, s*0.4), (-s*0.8, s*0.35), (-s*1.0, 0), (-s*0.8, -s*0.35)]
        _draw_polygon_rotated(surface, body_pts, body_col, cx, cy, heading)
        _draw_polygon_rotated(surface, [(s*0.7, -s*0.4), (s*0.9, 0), (0, -s*0.1), (-s*0.8, -s*0.35)], hi_col, cx, cy, heading)

        # Long tail
        tail_pts = [(-s*0.9, -s*0.2), (-s*1.8 + tail_sway*s*0.5, 0), (-s*0.9, s*0.2)]
        _draw_polygon_rotated(surface, tail_pts, sh_col, cx, cy, heading)

        # Duckbill head & crest
        head_pts = [(s*0.9, -s*0.25), (s*1.7, -s*0.15), (s*1.8, 0), (s*1.7, s*0.15), (s*0.9, s*0.25)]
        _draw_polygon_rotated(surface, head_pts, hi_col, cx, cy, heading)
        # Crest
        crest_pts = [(s*1.0, -s*0.35), (s*1.3, -s*0.45), (s*1.4, -s*0.2)]
        _draw_polygon_rotated(surface, crest_pts, pal.get("crest", (200, 80, 60)), cx, cy, heading)

    # ------------------------------------------------------------------
    # Quetzalcoatlus Pterosaur
    # ------------------------------------------------------------------
    def _draw_pterosaur(
        self, surface: pygame.Surface, cx: float, cy: float, heading: float,
        size: float, pal: dict, body_col: tuple, hi_col: tuple, sh_col: tuple,
        walk: float,
    ) -> None:
        s = size * 0.5
        wing_span = math.sin(walk * 1.5) * (s * 0.2)

        # Giant swept wings
        wing_col = pal.get("wings", (180, 205, 235))
        _draw_polygon_rotated(surface, [(s*0.2, 0), (0, -s*1.8 - wing_span), (-s*0.6, -s*0.9), (-s*0.3, 0)], wing_col, cx, cy, heading)
        _draw_polygon_rotated(surface, [(s*0.2, 0), (0,  s*1.8 + wing_span), (-s*0.6,  s*0.9), (-s*0.3, 0)], wing_col, cx, cy, heading)

        # Slender body
        _draw_polygon_rotated(surface, [(s*0.6, 0), (0, -s*0.25), (-s*0.8, 0), (0, s*0.25)], body_col, cx, cy, heading)

        # Sharp dagger beak & head
        beak_col = pal.get("beak", (245, 165, 40))
        _draw_polygon_rotated(surface, [(s*0.5, -s*0.15), (s*1.9, 0), (s*0.5, s*0.15)], beak_col, cx, cy, heading)

    # ------------------------------------------------------------------
    # Deinosuchus Crocodilian
    # ------------------------------------------------------------------
    def _draw_crocodilian(
        self, surface: pygame.Surface, cx: float, cy: float, heading: float,
        size: float, pal: dict, body_col: tuple, hi_col: tuple, sh_col: tuple,
        tail_sway: float,
    ) -> None:
        s = size * 0.5
        # Low elongated body
        body_pts = [(s*0.8, -s*0.35), (s*1.0, 0), (s*0.8, s*0.35), (-s*0.8, s*0.3), (-s*1.0, 0), (-s*0.8, -s*0.3)]
        _draw_polygon_rotated(surface, body_pts, body_col, cx, cy, heading)

        # Powerful swishing tail
        tail_pts = [(-s*0.9, -s*0.25), (-s*2.0 + tail_sway*s*0.7, 0), (-s*0.9, s*0.25)]
        _draw_polygon_rotated(surface, tail_pts, sh_col, cx, cy, heading)

        # Jagged scutes along back
        for ox in [-s*0.5, -s*0.2, s*0.1, s*0.4]:
            _draw_polygon_rotated(surface, [(ox, -s*0.1), (ox + s*0.1, 0), (ox, s*0.1)], pal.get("scutes", (30, 80, 40)), cx, cy, heading)

        # Broad snout
        snout_pts = [(s*0.9, -s*0.25), (s*1.9, -s*0.12), (s*2.0, 0), (s*1.9, s*0.12), (s*0.9, s*0.25)]
        _draw_polygon_rotated(surface, snout_pts, hi_col, cx, cy, heading)

    # ------------------------------------------------------------------
    # Aquatic & Small Creatures
    # ------------------------------------------------------------------
    def _draw_aquatic(
        self, surface: pygame.Surface, cx: float, cy: float, heading: float,
        size: float, pal: dict, body_col: tuple, hi_col: tuple, species: str,
        tail_sway: float,
    ) -> None:
        s = size * 0.5
        if species == "freshwater_turtle":
            # Oval shell
            shell_pts = [(s*0.6, -s*0.5), (s*0.8, 0), (s*0.6, s*0.5), (-s*0.6, s*0.5), (-s*0.8, 0), (-s*0.6, -s*0.5)]
            _draw_polygon_rotated(surface, shell_pts, pal.get("shell", (110, 95, 55)), cx, cy, heading)
            # Flippers
            _draw_polygon_rotated(surface, [(s*0.3, -s*0.5), (s*0.7, -s*0.8), (s*0.6, -s*0.4)], body_col, cx, cy, heading)
            _draw_polygon_rotated(surface, [(s*0.3,  s*0.5), (s*0.7,  s*0.8), (s*0.6,  s*0.4)], body_col, cx, cy, heading)
        else:
            # Streamlined fish
            fish_pts = [(s*0.7, 0), (0, -s*0.35), (-s*0.6, 0), (0, s*0.35)]
            _draw_polygon_rotated(surface, fish_pts, body_col, cx, cy, heading)
            # Tail fin with sway
            fin_pts = [(-s*0.6, 0), (-s*1.1, -s*0.4 + tail_sway*s*0.5), (-s*0.9, 0), (-s*1.1, s*0.4 + tail_sway*s*0.5)]
            _draw_polygon_rotated(surface, fin_pts, pal.get("fins", (150, 220, 240)), cx, cy, heading)

    def _draw_mammal(
        self, surface: pygame.Surface, cx: float, cy: float, heading: float,
        size: float, pal: dict, body_col: tuple, hi_col: tuple, walk: float,
    ) -> None:
        s = size * 0.5
        body_pts = [(s*0.6, -s*0.3), (s*0.8, 0), (s*0.6, s*0.3), (-s*0.6, s*0.25), (-s*0.8, 0), (-s*0.6, -s*0.25)]
        _draw_polygon_rotated(surface, body_pts, body_col, cx, cy, heading)
        # Snout
        _draw_polygon_rotated(surface, [(s*0.6, -s*0.15), (s*1.1, 0), (s*0.6, s*0.15)], hi_col, cx, cy, heading)

    def _draw_swarm(
        self, surface: pygame.Surface, cx: float, cy: float, size: float,
        pal: dict, walk: float,
    ) -> None:
        col = pal.get("highlight", (255, 240, 100))
        for i in range(7):
            offset_x = math.sin(walk * 3.0 + i * 1.3) * (size * 0.7)
            offset_y = math.cos(walk * 2.5 + i * 1.7) * (size * 0.7)
            pygame.draw.circle(surface, col, (int(cx + offset_x), int(cy + offset_y)), max(1, int(size * 0.15)))

    def _draw_generic_creature(
        self, surface: pygame.Surface, cx: float, cy: float, heading: float,
        size: float, body_col: tuple, hi_col: tuple, sh_col: tuple, tail_sway: float,
    ) -> None:
        s = size * 0.5
        pts = [(s*0.8, 0), (0, -s*0.4), (-s*0.8, 0), (0, s*0.4)]
        _draw_polygon_rotated(surface, pts, body_col, cx, cy, heading)

    # ------------------------------------------------------------------
    # Visual Highlights & Action Bubbles
    # ------------------------------------------------------------------
    def _draw_selection_ring(
        self, surface: pygame.Surface, cx: float, cy: float, radius: float,
        color: tuple[int, int, int],
    ) -> None:
        r = max(6, int(radius))
        pygame.draw.circle(surface, color, (int(cx), int(cy)), r, 2)
        # Crosshair notches
        for dx, dy in [(0, -r - 4), (0, r + 4), (-r - 4, 0), (r + 4, 0)]:
            pygame.draw.circle(surface, color, (int(cx + dx), int(cy + dy)), 2)

    def _draw_action_indicator(
        self, surface: pygame.Surface, x: float, y: float, action: str,
    ) -> None:
        icon_map = {
            "HUNT":  ("!", (255, 50, 50)),
            "FLEE":  ("<<", (255, 200, 40)),
            "SLEEP": ("Zz", (120, 140, 255)),
            "MATE":  ("<3", (255, 100, 200)),
            "DRINK": ("~", (60, 180, 255)),
            "EAT":   ("o", (100, 230, 80)),
        }
        text, col = icon_map.get(action, ("", (200, 200, 200)))
        if not text:
            return
        # Mini speech bubble
        bw, bh = 22, 14
        bx, by = int(x - bw // 2), int(y - bh)
        pygame.draw.rect(surface, (20, 25, 35, 220), (bx, by, bw, bh), border_radius=4)
        pygame.draw.rect(surface, col, (bx, by, bw, bh), 1, border_radius=4)
        if self._font_bubble:
            lbl = self._font_bubble.render(text, True, col)
            surface.blit(lbl, (bx + (bw - lbl.get_width()) // 2, by + (bh - lbl.get_height()) // 2))


# Global singleton
creature_renderer = CreatureRenderer()
