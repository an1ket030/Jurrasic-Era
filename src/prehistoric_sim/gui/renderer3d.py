"""Perspective 3D scene renderer for the Phase 3 viewport.

The simulation remains a 2D ecological grid; this module projects terrain,
vegetation height, and creatures into a navigable perspective scene.
"""
from __future__ import annotations

import math
from typing import Any

import pygame

from prehistoric_sim.gui.colors import POSSESS_OUTLINE, SELECT_OUTLINE, TERRAIN_COLORS


class World3DRenderer:
    """Small software 3D renderer with orbit, pitch, and perspective zoom."""

    TERRAIN_NAMES = ("FLOODPLAIN", "FOREST", "OPEN_WOODLAND", "SWAMP", "RIVER", "LAKE", "ROCKY_HILLS", "MUD_FLATS")

    def __init__(self, width: int, height: int) -> None:
        self.width, self.height = width, height
        self.yaw = -0.55
        self.pitch = 0.72
        self.distance = max(width, height) * 1.15
        self.target = (width / 2, height / 2)
        self.drag_origin: tuple[int, int] | None = None

    def begin_orbit(self, x: int, y: int) -> None:
        self.drag_origin = (x, y)

    def orbit(self, x: int, y: int) -> None:
        if self.drag_origin is None:
            return
        ox, oy = self.drag_origin
        self.yaw += (x - ox) * 0.008
        self.pitch = max(0.22, min(1.25, self.pitch + (y - oy) * 0.006))
        self.drag_origin = (x, y)

    def end_orbit(self) -> None:
        self.drag_origin = None

    def zoom(self, amount: int) -> None:
        self.distance = max(24.0, min(max(self.width, self.height) * 3.0,
                                      self.distance * (0.88 if amount > 0 else 1.14)))

    def agent_at(self, px: int, py: int, size: tuple[int, int], agents: dict[str, Any]) -> str | None:
        best_id, best_dist = None, 15.0
        for aid, agent in agents.items():
            pos = agent.get("position")
            if not pos:
                continue
            projected = self._project(pos[0] + 0.5, pos[1] + 0.5, 2.5, size)
            if projected:
                dist = math.hypot(projected[0] - px, projected[1] - py)
                if dist < best_dist:
                    best_id, best_dist = aid, dist
        return best_id

    def _project(self, x: float, y: float, z: float, size: tuple[int, int]) -> tuple[int, int] | None:
        w, h = size
        dx, dy = x - self.target[0], y - self.target[1]
        cy, sy = math.cos(self.yaw), math.sin(self.yaw)
        rx, ry = dx * cy - dy * sy, dx * sy + dy * cy
        cp, sp = math.cos(self.pitch), math.sin(self.pitch)
        depth = self.distance + ry * cp - z * sp
        vertical = ry * sp + z * cp
        if depth <= 5:
            return None
        scale = min(w, h) * 0.9 / depth
        return int(w / 2 + rx * scale), int(h * 0.57 - vertical * scale)

    def draw(self, surface: pygame.Surface, state: dict[str, Any], selected_id: str | None = None) -> None:
        surface.fill((119, 163, 198))
        w, h = surface.get_size()
        world = state.get("world", {})
        terrain = world.get("terrain", [])
        plants = world.get("plant_biomass_total", [])
        stride = max(1, math.ceil(max(self.width, self.height) / 72))
        polygons: list[tuple[float, list[tuple[int, int]], tuple[int, int, int]]] = []
        for y in range(0, self.height, stride):
            for x in range(0, self.width, stride):
                i = y * self.width + x
                if i >= len(terrain):
                    continue
                ti = max(0, min(len(self.TERRAIN_NAMES) - 1, int(terrain[i])))
                base = TERRAIN_COLORS[self.TERRAIN_NAMES[ti]]
                biomass = float(plants[i]) if i < len(plants) else 0.0
                z = (0.0, 1.5, 0.6, 0.2, -0.3, -0.6, 4.0, -0.2)[ti]
                corners = [(x, y, z), (min(self.width, x + stride), y, z),
                           (min(self.width, x + stride), min(self.height, y + stride), z),
                           (x, min(self.height, y + stride), z)]
                pts = [self._project(*p, (w, h)) for p in corners]
                if all(p is not None for p in pts):
                    shade = min(1.18, 0.82 + biomass * 0.16 + max(0, z) * 0.025)
                    color = tuple(max(0, min(255, int(c * shade))) for c in base)
                    polygons.append((sum(p[1] for p in pts) / 4, pts, color))  # painter's order
        for _, pts, color in sorted(polygons, key=lambda item: item[0]):
            pygame.draw.polygon(surface, color, pts)
            pygame.draw.polygon(surface, tuple(max(0, c - 18) for c in color), pts, 1)

        # Vegetation is represented by upright low-poly tree forms whose height
        # and density come from the live biomass grid.
        for y in range(stride // 2, self.height, stride * 3):
            for x in range(stride // 2, self.width, stride * 3):
                i = y * self.width + x
                if i >= len(terrain) or int(terrain[i]) not in (1, 2, 6):
                    continue
                biomass = float(plants[i]) if i < len(plants) else 0.0
                if biomass < 0.35:
                    continue
                ground = self._project(x + 0.5, y + 0.5, 0.5, (w, h))
                crown = self._project(x + 0.5, y + 0.5, 2.2 + biomass * 2.5, (w, h))
                if ground and crown:
                    radius = max(2, abs(crown[1] - ground[1]) // 3)
                    green = (38, 99, 43) if int(terrain[i]) == 1 else (67, 124, 54)
                    pygame.draw.line(surface, (83, 65, 42), ground, (ground[0], crown[1] + radius), max(2, radius // 3))
                    pygame.draw.polygon(surface, green, [(crown[0], crown[1] - radius),
                                     (crown[0] - radius, crown[1] + radius),
                                     (crown[0] + radius, crown[1] + radius)])

        colors = {"tyrannosaurus_rex": (210, 75, 55), "triceratops": (106, 194, 111),
                  "edmontosaurus": (74, 174, 195), "ankylosaurus": (76, 111, 204),
                  "dakotaraptor": (230, 132, 54)}
        agents = state.get("agents", {})
        for aid, agent in sorted(agents.items(), key=lambda item: item[1].get("position", (0, 0))[1]):
            pos = agent.get("position")
            if not pos:
                continue
            x, y = pos
            size = 2.0 if agent.get("life_stage") in ("HATCHLING", "JUVENILE") else 3.4
            base = self._project(x + 0.5, y + 0.5, 0, (w, h))
            top = self._project(x + 0.5, y + 0.5, size * 1.8, (w, h))
            head = self._project(x + 1.1, y + 0.5, size * 1.25, (w, h))
            if not (base and top and head):
                continue
            color = colors.get(agent.get("species_key"), (204, 180, 111))
            pygame.draw.polygon(surface, color, [(base[0] - 5, base[1]), (base[0] + 5, base[1]),
                                                  (top[0] + 3, top[1]), (top[0] - 3, top[1])])
            pygame.draw.circle(surface, tuple(min(255, c + 35) for c in color), head, 4)
            if aid == selected_id or agent.get("possessed"):
                marker = POSSESS_OUTLINE if agent.get("possessed") else SELECT_OUTLINE
                pygame.draw.ellipse(surface, marker, (base[0] - 10, base[1] - 3, 20, 7), 2)

