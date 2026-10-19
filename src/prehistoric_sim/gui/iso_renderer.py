"""
iso_renderer.py — Stylized Low-Poly 2.5D Terrain & World Renderer.

Renders the prehistoric landscape with:
  • Faceted triangulated ground lighting (sunlight highlights & ambient shading)
  • 3D stylized low-poly conifer and palm trees in Forest/Woodland
  • Crystalline water with animated flowing ripple facets & turquoise shoreline foam
  • Elevated rocky mountain crags with snow-dusted peaks
  • Active volcano with glowing orange lava fissures & crater glow
  • Lush prehistoric fern blades, flower specks, and cracked dry mud facets
  • Atmospheric day/night lighting with warm sunrise/sunset tints
"""

from __future__ import annotations

import math
import random
from typing import Any

import pygame

from prehistoric_sim.gui.camera import Camera

_TERRAIN_BASE_COLORS: dict[str, tuple[int, int, int]] = {
    "FLOODPLAIN":    ( 82, 148,  64),   # Lush grassland
    "FOREST":        ( 34,  92,  38),   # Dense pine & cycad jungle
    "OPEN_WOODLAND": (102, 162,  58),   # Savanna / woodland
    "SWAMP":         ( 42,  98,  78),   # Murky wetland
    "RIVER":         ( 40, 142, 215),   # Flowing cyan water
    "LAKE":          ( 28, 105, 195),   # Deep azure lake
    "ROCKY_HILLS":   (135, 128, 118),   # Mountain stone
    "MUD_FLATS":     (190, 142,  88),   # Arid orange badlands
}

_TERRAIN_NAMES = [
    "FLOODPLAIN", "FOREST", "OPEN_WOODLAND", "SWAMP",
    "RIVER", "LAKE", "ROCKY_HILLS", "MUD_FLATS",
]


class LowPolyTerrainRenderer:
    """Renders stylized low-poly faceted terrain, vegetation, and natural features."""

    def __init__(self, world_w: int, world_h: int) -> None:
        self.world_w = world_w
        self.world_h = world_h
        self._tick: int = 0

        # Pseudo-random height map and feature offsets generated deterministically
        self._feature_seeds: list[int] = []
        rng = random.Random(1337)
        self._feature_seeds = [rng.randint(0, 10000) for _ in range(world_w * world_h)]

    def update_tick(self) -> None:
        self._tick += 1

    def draw_terrain(
        self,
        surface: pygame.Surface,
        camera: Camera,
        world_state: dict[str, Any],
    ) -> None:
        """Draw the entire visible low-poly faceted terrain grid."""
        terrain_flat = world_state.get("terrain")
        if not terrain_flat:
            return

        cell_px = max(1, int(camera.cell_px))
        min_gx, min_gy, max_gx, max_gy = camera.visible_cells()
        
        # Day/Night lighting factor
        hour = world_state.get("hour_of_day", 12.0)
        if 6.0 <= hour < 19.0:
            bright = 1.0
            tint_r, tint_g, tint_b = 1.0, 1.0, 1.0
        elif 5.0 <= hour < 6.0:  # Dawn
            f = hour - 5.0
            bright = 0.5 + 0.5 * f
            tint_r, tint_g, tint_b = 1.15, 0.95, 0.85
        elif 19.0 <= hour < 20.5: # Dusk
            f = (20.5 - hour) / 1.5
            bright = 0.45 + 0.55 * f
            tint_r, tint_g, tint_b = 1.20, 0.85, 0.80
        else: # Night
            bright = 0.35
            tint_r, tint_g, tint_b = 0.65, 0.75, 1.10

        t_anim = self._tick * 0.08

        # Pass 1: Faceted Ground Polygons
        for gy in range(min_gy, max_gy + 1):
            for gx in range(min_gx, max_gx + 1):
                idx = gy * self.world_w + gx
                if idx >= len(terrain_flat):
                    continue
                t_idx = terrain_flat[idx]
                t_name = _TERRAIN_NAMES[t_idx] if 0 <= t_idx < len(_TERRAIN_NAMES) else "FLOODPLAIN"
                base_rgb = _TERRAIN_BASE_COLORS.get(t_name, (80, 80, 80))

                sx, sy = camera.world_to_screen(gx, gy)
                isx, isy = int(sx), int(sy)

                # Low-poly faceted shading:
                # Divide cell into 2 triangles or 4 triangular quadrants
                # Top facet: sunlight (+12% brightness)
                # Bottom facet: shadow (-10% brightness)
                c_light = (
                    int(min(255, base_rgb[0] * 1.14 * bright * tint_r)),
                    int(min(255, base_rgb[1] * 1.14 * bright * tint_g)),
                    int(min(255, base_rgb[2] * 1.14 * bright * tint_b)),
                )
                c_dark = (
                    int(min(255, base_rgb[0] * 0.88 * bright * tint_r)),
                    int(min(255, base_rgb[1] * 0.88 * bright * tint_g)),
                    int(min(255, base_rgb[2] * 0.88 * bright * tint_b)),
                )

                if cell_px >= 6:
                    # Triangulated low-poly facets
                    pygame.draw.polygon(surface, c_light, [(isx, isy), (isx + cell_px, isy), (isx + cell_px, isy + cell_px)])
                    pygame.draw.polygon(surface, c_dark,  [(isx, isy), (isx + cell_px, isy + cell_px), (isx, isy + cell_px)])
                else:
                    pygame.draw.rect(surface, c_light, (isx, isy, cell_px, cell_px))

                # Water animated wave facets & shoreline sandy beach borders
                if t_name in ("RIVER", "LAKE") and cell_px >= 6:
                    wave_phase = math.sin(t_anim + gx * 0.7 + gy * 0.9)
                    if wave_phase > 0.35:
                        foam_alpha = int(min(255, 60 + 50 * wave_phase))
                        f_surf = pygame.Surface((cell_px, cell_px), pygame.SRCALPHA)
                        pygame.draw.line(f_surf, (220, 245, 255, foam_alpha), (2, cell_px // 2), (cell_px - 2, cell_px // 2), 1)
                        surface.blit(f_surf, (isx, isy))

                    # Shoreline sand border where water meets land
                    sand_col = (230, 205, 135)
                    # Check left
                    if gx > 0 and 0 <= terrain_flat[gy * self.world_w + (gx - 1)] < len(_TERRAIN_NAMES):
                        if _TERRAIN_NAMES[terrain_flat[gy * self.world_w + (gx - 1)]] not in ("RIVER", "LAKE"):
                            pygame.draw.line(surface, sand_col, (isx, isy), (isx, isy + cell_px), max(1, cell_px // 8))
                    # Check top
                    if gy > 0 and 0 <= terrain_flat[(gy - 1) * self.world_w + gx] < len(_TERRAIN_NAMES):
                        if _TERRAIN_NAMES[terrain_flat[(gy - 1) * self.world_w + gx]] not in ("RIVER", "LAKE"):
                            pygame.draw.line(surface, sand_col, (isx, isy), (isx + cell_px, isy), max(1, cell_px // 8))
                    # Check right
                    if gx < self.world_w - 1 and 0 <= terrain_flat[gy * self.world_w + (gx + 1)] < len(_TERRAIN_NAMES):
                        if _TERRAIN_NAMES[terrain_flat[gy * self.world_w + (gx + 1)]] not in ("RIVER", "LAKE"):
                            pygame.draw.line(surface, sand_col, (isx + cell_px - 1, isy), (isx + cell_px - 1, isy + cell_px), max(1, cell_px // 8))
                    # Check bottom
                    if gy < self.world_h - 1 and 0 <= terrain_flat[(gy + 1) * self.world_w + gx] < len(_TERRAIN_NAMES):
                        if _TERRAIN_NAMES[terrain_flat[(gy + 1) * self.world_w + gx]] not in ("RIVER", "LAKE"):
                            pygame.draw.line(surface, sand_col, (isx, isy + cell_px - 1), (isx + cell_px, isy + cell_px - 1), max(1, cell_px // 8))

        # Pass 2: 3D Low-Poly Trees, Mountains, and Volcanic Features (Rendered when zoomed in)
        if cell_px >= 8:
            for gy in range(min_gy, max_gy + 1):
                for gx in range(min_gx, max_gx + 1):
                    idx = gy * self.world_w + gx
                    if idx >= len(terrain_flat):
                        continue
                    t_idx = terrain_flat[idx]
                    t_name = _TERRAIN_NAMES[t_idx] if 0 <= t_idx < len(_TERRAIN_NAMES) else "FLOODPLAIN"
                    seed = self._feature_seeds[idx]

                    sx, sy = camera.world_to_screen(gx, gy)
                    isx, isy = int(sx), int(sy)

                    if t_name == "FOREST":
                        self._draw_lowpoly_tree(surface, isx + cell_px // 2, isy + cell_px // 2, cell_px, seed, is_pine=True)
                    elif t_name == "OPEN_WOODLAND" and (seed % 3 == 0):
                        self._draw_lowpoly_tree(surface, isx + cell_px // 2, isy + cell_px // 2, cell_px, seed, is_pine=False)
                    elif t_name == "ROCKY_HILLS":
                        self._draw_lowpoly_rock(surface, isx + cell_px // 2, isy + cell_px // 2, cell_px, seed)
                    elif t_name == "MUD_FLATS" and (seed % 4 == 0):
                        self._draw_mud_crag(surface, isx + cell_px // 2, isy + cell_px // 2, cell_px, seed)

    # ------------------------------------------------------------------
    # Low-Poly Tree Renderer (Pine cone / Palm / Acacia)
    # ------------------------------------------------------------------
    def _draw_lowpoly_tree(
        self, surface: pygame.Surface, cx: int, cy: int, cell_px: int, seed: int, is_pine: bool
    ) -> None:
        tree_h = int(cell_px * 0.9)
        tree_w = int(cell_px * 0.6)

        # Trunk drop shadow
        shadow_surf = pygame.Surface((tree_w + 4, tree_w // 2 + 2), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_surf, (15, 20, 25, 80), (0, 0, tree_w + 4, tree_w // 2 + 2))
        surface.blit(shadow_surf, (cx - tree_w // 2 - 2, cy + cell_px // 4))

        # Brown trunk
        trunk_w = max(2, cell_px // 6)
        trunk_h = max(3, cell_px // 3)
        pygame.draw.rect(surface, (78, 52, 34), (cx - trunk_w // 2, cy - trunk_h // 2, trunk_w, trunk_h))

        # Layered low-poly faceted canopy
        if is_pine:
            # Triangulated pine crown (light facet on right, dark on left)
            top_y = cy - tree_h
            mid_y = cy - trunk_h // 2
            # Dark facet (left)
            pygame.draw.polygon(surface, (25, 78, 30), [(cx, top_y), (cx - tree_w // 2, mid_y), (cx, mid_y)])
            # Sunlit facet (right)
            pygame.draw.polygon(surface, (52, 135, 48), [(cx, top_y), (cx, mid_y), (cx + tree_w // 2, mid_y)])
        else:
            # Rounded low-poly acacia crown
            rad = tree_w // 2
            pygame.draw.circle(surface, (68, 142, 45), (cx, cy - tree_h // 2), rad)
            pygame.draw.circle(surface, (95, 185, 62), (cx + rad // 3, cy - tree_h // 2 - rad // 3), rad // 2)

    # ------------------------------------------------------------------
    # Low-Poly Mountain / Bolder Crag
    # ------------------------------------------------------------------
    def _draw_lowpoly_rock(
        self, surface: pygame.Surface, cx: int, cy: int, cell_px: int, seed: int
    ) -> None:
        rw = int(cell_px * 0.6)
        rh = int(cell_px * 0.7)
        top_y = cy - rh

        # Shaded rock facets
        pts_left = [(cx, top_y), (cx - rw // 2, cy + rh // 3), (cx, cy + rh // 3)]
        pts_right = [(cx, top_y), (cx, cy + rh // 3), (cx + rw // 2, cy + rh // 3)]
        pygame.draw.polygon(surface, (90, 85, 80), pts_left)
        pygame.draw.polygon(surface, (165, 158, 148), pts_right)

        # Snow dust on peak if high hill
        if seed % 3 == 0:
            snow_pts = [(cx, top_y), (cx - rw // 4, top_y + rh // 4), (cx + rw // 4, top_y + rh // 4)]
            pygame.draw.polygon(surface, (235, 240, 245), snow_pts)

    def _draw_mud_crag(
        self, surface: pygame.Surface, cx: int, cy: int, cell_px: int, seed: int
    ) -> None:
        rw = int(cell_px * 0.4)
        pygame.draw.polygon(surface, (155, 110, 65), [(cx - rw, cy), (cx, cy - rw // 2), (cx + rw, cy)])
        pygame.draw.polygon(surface, (115, 80, 45), [(cx - rw, cy), (cx + rw, cy), (cx, cy + rw // 2)])


# Global singleton
terrain_renderer = LowPolyTerrainRenderer(120, 120)
