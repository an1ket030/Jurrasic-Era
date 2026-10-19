"""
world_canvas.py — Real-time World Canvas with Smooth Interpolation & Low-Poly Rendering.

Features:
  • Continuous 60 FPS visual interpolation (creatures smoothly glide and turn, no teleporting dots!)
  • Sinusoidal walking animation (stepping limbs, swaying tails, breathing body bob)
  • Stylized low-poly faceted terrain with 3D conifer trees, rocks, and sparkling water
  • Ground drop-shadows giving realistic 3D depth
  • Overlays: Plant biomass heatmap, fire sparks, floods, eggs, carcasses, and nests
  • Accurate mouse picking for creature selection
"""

from __future__ import annotations

import math
import random
import threading
import time
from typing import Any

import pygame

from prehistoric_sim.gui.camera import Camera
from prehistoric_sim.gui.colors import (
    ACTION_COLORS,
    FLOOD_COLOR,
    FIRE_COLORS,
    PLANT_TINT,
    POSSESS_OUTLINE,
    SELECT_OUTLINE,
    SPECIES_COLORS,
    TRACK_OUTLINE,
    WATER_SHIMMER,
)
from prehistoric_sim.gui.creature_renderer import creature_renderer
from prehistoric_sim.gui.iso_renderer import terrain_renderer


class VisualAgent:
    __slots__ = (
        "agent_id", "cur_x", "cur_y", "target_x", "target_y",
        "heading_rad", "walk_phase", "species_key", "life_stage",
        "health", "action", "possessed", "tracked", "last_update"
    )

    def __init__(self, agent_id: str, x: float, y: float, species_key: str) -> None:
        self.agent_id = agent_id
        self.cur_x = x
        self.cur_y = y
        self.target_x = x
        self.target_y = y
        self.heading_rad = random.uniform(0, math.pi * 2)
        self.walk_phase = random.uniform(0, 10.0)
        self.species_key = species_key
        self.life_stage = "ADULT"
        self.health = 1.0
        self.action = "WANDER"
        self.possessed = False
        self.tracked = False
        self.last_update = time.time()


class WorldCanvas:
    """Renders the entire prehistoric world with smooth movement and low-poly graphics."""

    def __init__(self, world_w: int, world_h: int) -> None:
        self.world_w = world_w
        self.world_h = world_h

        # State snapshot
        self._state: dict[str, Any] | None = None
        self._lock = threading.Lock()

        # Visual agents for smooth 60fps lerping
        self._visual_agents: dict[str, VisualAgent] = {}
        self._last_frame_time: float = time.time()

        # Selection
        self.selected_id: str | None = None
        self.hovered_id:  str | None = None
        self.hovered_pos: tuple[int, int] | None = None

        # Toggles
        self.show_plant_overlay: bool = False

        # Fonts
        self._font_small: pygame.font.Font | None = None

    def update_state(self, state: dict[str, Any]) -> None:
        """Update simulation state and targets for all creatures."""
        with self._lock:
            self._state = state

        terrain_renderer.update_tick()
        now = time.time()
        agents = state.get("agents", {})

        # Synchronize visual agents with live simulation
        for aid, a in agents.items():
            pos = a.get("position")
            if pos is None:
                continue
            tx, ty = pos[0] + 0.5, pos[1] + 0.5

            va = self._visual_agents.get(aid)
            if va is None:
                va = VisualAgent(aid, tx, ty, a.get("species_key", "default"))
                self._visual_agents[aid] = va

            va.target_x = tx
            va.target_y = ty
            va.species_key = a.get("species_key", "default")
            va.life_stage = a.get("life_stage", "ADULT")
            va.health = a.get("health", 1.0)
            va.action = a.get("current_action", "WANDER")
            va.possessed = a.get("possessed", False)
            va.tracked = a.get("tracked", False)
            va.last_update = now

        # Prune dead agents
        active_ids = set(agents.keys())
        dead_ids = [aid for aid in self._visual_agents if aid not in active_ids]
        for did in dead_ids:
            del self._visual_agents[did]

    def draw(self, surface: pygame.Surface, camera: Camera) -> None:
        """Render the complete world onto surface."""
        with self._lock:
            state = self._state
        if state is None:
            return

        now = time.time()
        dt = min(0.08, max(0.001, now - self._last_frame_time))
        self._last_frame_time = now

        world_state = state.get("world", {})

        # 1. Low-Poly Stylized Faceted Terrain
        terrain_renderer.draw_terrain(surface, camera, world_state)

        # 2. Plant Biomass Overlay (if toggled)
        if self.show_plant_overlay:
            self._draw_plant_overlay(surface, camera, world_state)

        # 3. Hazard Overlays (Fire, Flood)
        self._draw_flood_overlay(surface, camera, world_state)
        self._draw_fire_overlay(surface, camera, world_state)

        # 4. Nests, Carcasses, Eggs
        self._draw_nests(surface, camera, state)
        self._draw_carcasses(surface, camera, state)
        self._draw_eggs(surface, camera, state)

        # 5. Smooth Low-Poly Animated Creatures
        self._draw_smooth_creatures(surface, camera, dt)

        # 6. Weather Overlay (Rain streaks / Fog)
        self._draw_weather_overlay(surface, camera, world_state)

    # ------------------------------------------------------------------
    # Smooth 60 FPS Visual Creature Movement & Low-Poly Rendering
    # ------------------------------------------------------------------
    def _draw_smooth_creatures(self, surface: pygame.Surface, camera: Camera, dt: float) -> None:
        cell_px = camera.cell_px
        lerp_speed = 6.0  # Smooth visual gliding speed

        # Sort visual agents so creatures higher up are drawn first (depth sorting)
        sorted_agents = sorted(self._visual_agents.values(), key=lambda a: a.cur_y)

        for va in sorted_agents:
            # 1. Smooth position interpolation
            dx = va.target_x - va.cur_x
            dy = va.target_y - va.cur_y
            dist = math.hypot(dx, dy)

            if dist > 0.005:
                # Gliding towards destination
                step = min(1.0, dt * lerp_speed)
                va.cur_x += dx * step
                va.cur_y += dy * step

                # Smooth heading rotation towards movement vector
                target_ang = math.atan2(dy, dx)
                ang_diff = (target_ang - va.heading_rad + math.pi) % (2 * math.pi) - math.pi
                va.heading_rad += ang_diff * min(1.0, dt * 8.0)

                # Advance walk cycle
                va.walk_phase += dist * 12.0 * dt + dt * 2.5
            else:
                # Gentle idle breathing bob
                va.walk_phase += dt * 1.8

            # 2. Convert world position to screen position
            sx, sy = camera.world_to_screen(va.cur_x, va.cur_y)

            # Culling check
            if not (-100 <= sx <= surface.get_width() + 100 and -100 <= sy <= surface.get_height() + 100):
                continue

            # 3. Draw distinct 2.5D low-poly creature model
            is_sel = (va.agent_id == self.selected_id)
            is_tr = va.tracked
            is_pos = va.possessed

            creature_renderer.draw_creature(
                surface=surface,
                screen_x=sx,
                screen_y=sy,
                species_key=va.species_key,
                life_stage=va.life_stage,
                heading_rad=va.heading_rad,
                walk_phase=va.walk_phase,
                cell_px=cell_px,
                health=va.health,
                action=va.action,
                is_selected=is_sel,
                is_tracked=is_tr,
                is_possessed=is_pos,
            )

    # ------------------------------------------------------------------
    # Nests, Carcasses, Eggs
    # ------------------------------------------------------------------
    def _draw_nests(self, surface: pygame.Surface, camera: Camera, state: dict) -> None:
        nests = state.get("nests", {})
        if not nests or camera.cell_px < 5:
            return

        for nest in nests.values():
            pos = nest.get("position")
            if not pos:
                continue
            sx, sy = camera.world_to_screen(pos[0] + 0.5, pos[1] + 0.5)
            r = max(3, int(camera.cell_px * 0.4))
            pygame.draw.circle(surface, (140, 105, 55), (int(sx), int(sy)), r)
            pygame.draw.circle(surface, (215, 180, 95), (int(sx), int(sy)), r, 1)

    def _draw_carcasses(self, surface: pygame.Surface, camera: Camera, state: dict) -> None:
        carcasses = state.get("carcasses", {})
        if not carcasses:
            return

        for carc in carcasses.values():
            pos = carc.get("position")
            if not pos:
                continue
            sx, sy = camera.world_to_screen(pos[0] + 0.5, pos[1] + 0.5)
            r = max(2, int(camera.cell_px * 0.35))
            decay = carc.get("decay_progress", 0.0)
            col = (int(160 * (1 - decay * 0.5)), int(70 * (1 - decay)), int(50 * (1 - decay)))
            # Low-poly rib cage shape
            pygame.draw.ellipse(surface, col, (int(sx - r), int(sy - r // 2), r * 2, r))
            if camera.cell_px >= 8:
                pygame.draw.line(surface, (230, 225, 210), (int(sx - r * 0.5), int(sy)), (int(sx + r * 0.5), int(sy)), 1)

    def _draw_eggs(self, surface: pygame.Surface, camera: Camera, state: dict) -> None:
        eggs = state.get("eggs", {})
        if not eggs or camera.cell_px < 6:
            return

        for egg in eggs.values():
            pos = egg.get("position")
            if not pos:
                continue
            sx, sy = camera.world_to_screen(pos[0] + 0.5, pos[1] + 0.5)
            r = max(2, int(camera.cell_px * 0.22))
            pygame.draw.ellipse(surface, (245, 240, 215), (int(sx - r), int(sy - r * 1.3), r * 2, int(r * 2.6)))

    # ------------------------------------------------------------------
    # Hazard Overlays (Fire & Flood)
    # ------------------------------------------------------------------
    def _draw_flood_overlay(self, surface: pygame.Surface, camera: Camera, world_state: dict) -> None:
        flood_cells = world_state.get("flood_cells", [])
        if not flood_cells:
            return
        cell_px = max(1, int(camera.cell_px))
        overlay = pygame.Surface((cell_px, cell_px), pygame.SRCALPHA)
        overlay.fill((35, 120, 230, 130))
        for cx, cy in flood_cells:
            sx, sy = camera.world_to_screen(cx, cy)
            surface.blit(overlay, (int(sx), int(sy)))

    def _draw_fire_overlay(self, surface: pygame.Surface, camera: Camera, world_state: dict) -> None:
        fire_cells = world_state.get("fire_cells", [])
        if not fire_cells:
            return
        cell_px = max(1, int(camera.cell_px))
        t = time.time() * 8.0

        for cx, cy in fire_cells:
            sx, sy = camera.world_to_screen(cx, cy)
            fi = int(t + cx * 3 + cy * 7) % len(FIRE_COLORS)
            col = FIRE_COLORS[fi]
            fire_surf = pygame.Surface((cell_px, cell_px), pygame.SRCALPHA)
            fire_surf.fill((*col, 195))
            surface.blit(fire_surf, (int(sx), int(sy)))

            # Rising glowing sparks
            if cell_px >= 6:
                for i in range(2):
                    spark_x = int(sx) + (int(t * 12 + cx * 5 + i * 7) % cell_px)
                    spark_y = int(sy) - (int(t * 15 + cy * 3 + i * 11) % cell_px)
                    pygame.draw.circle(surface, (255, 235, 110), (spark_x, spark_y), 1)

    def _draw_plant_overlay(self, surface: pygame.Surface, camera: Camera, world_state: dict) -> None:
        plant_flat = world_state.get("plant_biomass_total")
        if not plant_flat:
            return
        cell_px = max(1, int(camera.cell_px))
        min_gx, min_gy, max_gx, max_gy = camera.visible_cells()

        for gy in range(min_gy, max_gy + 1):
            for gx in range(min_gx, max_gx + 1):
                idx = gy * self.world_w + gx
                if idx >= len(plant_flat):
                    continue
                biomass = plant_flat[idx]
                if biomass < 0.1:
                    continue
                alpha = int(min(1.0, biomass / 3.0) * 85)
                overlay = pygame.Surface((cell_px, cell_px), pygame.SRCALPHA)
                overlay.fill((*PLANT_TINT, alpha))
                sx, sy = camera.world_to_screen(gx, gy)
                surface.blit(overlay, (int(sx), int(sy)))

    def _draw_weather_overlay(self, surface: pygame.Surface, camera: Camera, world_state: dict) -> None:
        weather = world_state.get("weather", "CLEAR")
        w, h = surface.get_size()
        if weather in ("RAIN", "STORM"):
            # Subtle diagonal rain streaks
            rain_surf = pygame.Surface((w, h), pygame.SRCALPHA)
            t = time.time() * 25.0
            num_drops = 140 if weather == "STORM" else 75
            for i in range(num_drops):
                rx = (int(i * 37 + t * 18) % w)
                ry = (int(i * 59 + t * 45) % h)
                pygame.draw.line(rain_surf, (190, 225, 255, 140), (rx, ry), (rx - 4, ry + 12), 1)
            surface.blit(rain_surf, (0, 0))

    # ------------------------------------------------------------------
    # Mouse Picking
    # ------------------------------------------------------------------
    def agent_at_screen(
        self, mx: int, my: int, camera: Camera, state: dict[str, Any]
    ) -> str | None:
        """Find creature closest to screen coordinates (mx, my)."""
        hit_id: str | None = None
        min_d = 26.0  # Click tolerance radius in screen pixels

        for aid, va in self._visual_agents.items():
            sx, sy = camera.world_to_screen(va.cur_x, va.cur_y)
            d = math.hypot(mx - sx, my - sy)
            if d < min_d:
                min_d = d
                hit_id = aid

        return hit_id
