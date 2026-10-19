"""
hud.py — Heads-Up Display matching the concept art.

Features:
  • Top Resource & Status Bar:
      - Day counter & time of day (Sun icon, Day 12, Early Morning)
      - Ecological resource pills (Plants, Meat, Water, Stone, Wood)
      - Simulation playback buttons (Pause, Play 1x, Fast 2x, Ultra 5x, Admin Gear)
  • Left Navigation Pill Toolbar:
      - [🐾 Animals]  — Creature spawner & census
      - [🌲 Habitat]  — Plant biomass overlay toggle
      - [🔨 Build]    — Nests & waterhole placement
      - [🧪 Research] — Evolution & traits
      - [🗺 Map]      — Minimap toggle
      - [⚙ Admin]    — God panel toggle
  • Top-Right Mini-Map:
      - Stylized framed overview of the entire 120x120 world with camera frustum
  • Bottom-Left Floating Creature Card:
      - Portrait thumbnail, Name, Species, Status, Health/Hunger/Energy bars
  • Bottom-Right Floating Biome Card:
      - 3D low-poly tile cube thumbnail, Biome name, Description, and fertility stats
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Callable

import pygame

from prehistoric_sim.gui.camera import Camera
from prehistoric_sim.gui.colors import (
    BG_DARK,
    BODY_TEXT,
    DIM_TEXT,
    HUD_ACCENT,
    HUD_BG,
    HUD_DANGER,
    HUD_OK,
    HUD_TEXT,
    HUD_WARNING,
    PANEL_BORDER,
    SPECIES_COLORS,
    TERRAIN_COLORS,
    TITLE_TEXT,
)

_TERRAIN_DESCRIPTIONS: dict[str, str] = {
    "FLOODPLAIN":    "Lush fertile grassland with rich vegetation. Ideal grazing grounds.",
    "FOREST":        "Dense canopy of conifer & cycad trees. Ample shelter and seeds.",
    "OPEN_WOODLAND": "Scattered trees & shrubs with open running corridors for raptors.",
    "SWAMP":         "Murky wetlands rich in fish & insects. Ambush predator habitat.",
    "RIVER":         "Freshwater stream with sparkling currents. Key hydration source.",
    "LAKE":          "Deep reservoir sustaining the central prehistoric ecosystem.",
    "ROCKY_HILLS":   "Elevated mountain crags and mineral stone ridges.",
    "MUD_FLATS":     "Arid sun-baked mud terrain with scarce food and hot winds.",
}


class HUD:
    """Renders all floating concept-art HUD elements, bars, and interactive toolbar buttons."""

    TOP_BAR_H = 46
    LEFT_NAV_W = 110
    MINIMAP_W = 175
    MINIMAP_H = 175

    def __init__(self, screen_w: int, screen_h: int, world_w: int, world_h: int) -> None:
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.world_w  = world_w
        self.world_h  = world_h
        self.show_minimap = True
        self.show_plant_heatmap = False

        # Interactive click rects for buttons
        self._click_rects: list[tuple[pygame.Rect, Callable[[], None]]] = []

        # Cached thumbnails
        self._assets_loaded: bool = False
        self._portraits: dict[str, pygame.Surface] = {}
        self._cubes: dict[str, pygame.Surface] = {}

        # Fonts
        self._font_title: pygame.font.Font | None = None
        self._font_ui:    pygame.font.Font | None = None
        self._font_small: pygame.font.Font | None = None
        self._font_bold:  pygame.font.Font | None = None

    def resize(self, screen_w: int, screen_h: int) -> None:
        self.screen_w = screen_w
        self.screen_h = screen_h

    def _ensure_assets(self) -> None:
        if self._assets_loaded:
            return
        self._assets_loaded = True
        assets_dir = Path(__file__).parent / "assets"
        if not assets_dir.exists():
            return

        def load_scaled(filename: str, size: tuple[int, int]) -> pygame.Surface | None:
            p = assets_dir / filename
            if p.exists():
                try:
                    surf = pygame.image.load(str(p))
                    if pygame.display.get_surface():
                        try:
                            surf = surf.convert()
                        except Exception:
                            pass
                    return pygame.transform.smoothscale(surf, size)
                except Exception as err:
                    return None
            return None

        # Load creature portraits
        p_raptor = load_scaled("portrait_raptor.jpg", (58, 58))
        p_trex   = load_scaled("portrait_trex.jpg", (58, 58))
        p_tri    = load_scaled("portrait_triceratops.jpg", (58, 58))
        p_stego  = load_scaled("portrait_stegosaurus.jpg", (58, 58))
        p_sauro  = load_scaled("portrait_sauropod.jpg", (58, 58))

        # Comprehensive species mapping
        if p_raptor:
            for k in ["dakotaraptor", "acheroraptor", "anzu_wyliei", "didelphodon"]:
                self._portraits[k] = p_raptor
        if p_trex:
            for k in ["tyrannosaurus_rex", "deinosuchus"]:
                self._portraits[k] = p_trex
        if p_tri:
            for k in ["triceratops"]:
                self._portraits[k] = p_tri
        if p_stego:
            for k in ["ankylosaurus", "pachycephalosaurus"]:
                self._portraits[k] = p_stego
        if p_sauro:
            for k in ["edmontosaurus", "thescelosaurus", "quetzalcoatlus", "freshwater_turtle", "freshwater_fish", "insect_swarm", "default"]:
                self._portraits[k] = p_sauro

        # Load 3D tile cubes
        c_grass = load_scaled("cube_grassland.jpg", (60, 60))
        if c_grass:
            for k in ["FLOODPLAIN", "FOREST", "OPEN_WOODLAND", "SWAMP", "RIVER", "LAKE"]:
                self._cubes[k] = c_grass

        c_volc = load_scaled("cube_volcano.jpg", (60, 60))
        if c_volc:
            for k in ["ROCKY_HILLS", "MUD_FLATS"]:
                self._cubes[k] = c_volc

    def _ensure_fonts(self) -> None:
        if self._font_ui is None:
            try:
                self._font_title = pygame.font.SysFont("segoeui", 14, bold=True)
                self._font_ui    = pygame.font.SysFont("segoeui", 12)
                self._font_small = pygame.font.SysFont("segoeui", 10)
                self._font_bold  = pygame.font.SysFont("segoeui", 11, bold=True)
            except Exception:
                self._font_title = pygame.font.Font(None, 16)
                self._font_ui    = pygame.font.Font(None, 14)
                self._font_small = pygame.font.Font(None, 12)
                self._font_bold  = pygame.font.Font(None, 13)

    # ------------------------------------------------------------------
    # Main draw
    # ------------------------------------------------------------------
    def draw(
        self,
        surface: pygame.Surface,
        state: dict[str, Any],
        camera: Camera,
        paused: bool,
        speed: float,
        selected_agent: dict | None = None,
        hovered_agent: dict | None = None,
        hovered_screen_pos: tuple[int, int] | None = None,
        on_speed_change: Callable[[float], None] | None = None,
        on_toggle_pause: Callable[[], None] | None = None,
        on_open_admin: Callable[[], None] | None = None,
    ) -> None:
        self._ensure_fonts()
        self._ensure_assets()
        self._click_rects.clear()

        world_state = state.get("world", {})
        agents = state.get("agents", {})

        # 1. Top Resource & Controls Bar
        self._draw_top_bar(surface, world_state, len(agents), paused, speed,
                           on_speed_change, on_toggle_pause, on_open_admin)

        # 2. Left Navigation Pill Toolbar
        self._draw_left_nav(surface, on_open_admin)

        # 3. Top-Right Mini-Map
        if self.show_minimap:
            self._draw_minimap(surface, state, camera)

        # 4. Bottom-Left Creature Card (if creature is selected or hovered)
        active_creature = selected_agent or hovered_agent
        if active_creature:
            self._draw_creature_card(surface, active_creature)

        # 5. Bottom-Right Biome / Tile Card
        self._draw_biome_card(surface, world_state, camera)

    # ------------------------------------------------------------------
    # 1. Top Resource & Controls Bar
    # ------------------------------------------------------------------
    def _draw_top_bar(
        self, surface: pygame.Surface, world_state: dict, pop_count: int,
        paused: bool, speed: float,
        on_speed_change: Callable[[float], None] | None,
        on_toggle_pause: Callable[[], None] | None,
        on_open_admin: Callable[[], None] | None,
    ) -> None:
        canvas_w = surface.get_width()
        bar_rect = pygame.Rect(0, 0, canvas_w, self.TOP_BAR_H)

        # Glassmorphic dark header
        glass_surf = pygame.Surface((canvas_w, self.TOP_BAR_H), pygame.SRCALPHA)
        glass_surf.fill((14, 18, 28, 220))
        surface.blit(glass_surf, (0, 0))
        pygame.draw.line(surface, (45, 60, 90), (0, self.TOP_BAR_H), (canvas_w, self.TOP_BAR_H), 1)

        x = 14
        # Left: Sun Icon & Day / Time
        pygame.draw.circle(surface, (255, 215, 60), (x + 12, 23), 10)
        pygame.draw.circle(surface, (255, 175, 30), (x + 12, 23), 7)
        x += 30

        day = world_state.get("day", 1)
        hour = world_state.get("hour_of_day", 12.0)
        if 5.0 <= hour < 9.0:
            tod_name = "Early Morning"
        elif 9.0 <= hour < 17.0:
            tod_name = "Day"
        elif 17.0 <= hour < 20.0:
            tod_name = "Dusk"
        else:
            tod_name = "Night"

        if self._font_title:
            surface.blit(self._font_title.render(f"Day {day}", True, (245, 245, 255)), (x, 10))
        if self._font_small:
            surface.blit(self._font_small.render(tod_name, True, HUD_ACCENT), (x, 26))
        x += 80

        # Center: Resource pills (Plants, Meat, Water, Stone, Wood)
        resources = [
            ("🌿", "Plants", int(sum(world_state.get("plant_biomass_total", [120])) * 2.5), (80, 220, 110)),
            ("🥩", "Meat", pop_count * 12, (255, 110, 90)),
            ("💧", "Water", 320, (70, 190, 255)),
            ("🪨", "Stone", 60, (180, 180, 195)),
            ("🪵", "Wood", 120, (190, 140, 85)),
        ]

        pill_x = x + 30
        for icon, name, val, col in resources:
            pill_w = 90
            pr = pygame.Rect(pill_x, 8, pill_w, 30)
            pygame.draw.rect(surface, (22, 28, 42, 180), pr, border_radius=15)
            pygame.draw.rect(surface, (45, 58, 85), pr, 1, border_radius=15)

            # Mini icon / dot
            pygame.draw.circle(surface, col, (pill_x + 14, 23), 5)
            if self._font_bold:
                val_s = self._font_bold.render(str(val), True, (255, 255, 255))
                surface.blit(val_s, (pill_x + 24, 11))
            if self._font_small:
                name_s = self._font_small.render(name, True, DIM_TEXT)
                surface.blit(name_s, (pill_x + 24, 24))
            pill_x += pill_w + 10

        # Right: Playback Speed & Admin Controls
        ctrl_x = canvas_w - 180
        # Pause button [||]
        p_btn = pygame.Rect(ctrl_x, 10, 28, 26)
        p_bg = (180, 60, 60) if paused else (35, 45, 65)
        pygame.draw.rect(surface, p_bg, p_btn, border_radius=4)
        pygame.draw.rect(surface, (70, 90, 130), p_btn, 1, border_radius=4)
        if self._font_bold:
            surface.blit(self._font_bold.render("||", True, (255, 255, 255)), (ctrl_x + 9, 14))
        if on_toggle_pause:
            self._click_rects.append((p_btn, on_toggle_pause))

        # Play 1x [>]
        play_btn = pygame.Rect(ctrl_x + 34, 10, 28, 26)
        play_bg = (45, 110, 65) if (not paused and speed == 1.0) else (35, 45, 65)
        pygame.draw.rect(surface, play_bg, play_btn, border_radius=4)
        pygame.draw.rect(surface, (70, 90, 130), play_btn, 1, border_radius=4)
        if self._font_bold:
            surface.blit(self._font_bold.render(">", True, (255, 255, 255)), (ctrl_x + 44, 14))
        if on_speed_change:
            self._click_rects.append((play_btn, lambda: on_speed_change(1.0)))

        # Fast 2x [>>]
        fast_btn = pygame.Rect(ctrl_x + 68, 10, 32, 26)
        fast_bg = (45, 110, 165) if (speed >= 2.0) else (35, 45, 65)
        pygame.draw.rect(surface, fast_bg, fast_btn, border_radius=4)
        pygame.draw.rect(surface, (70, 90, 130), fast_btn, 1, border_radius=4)
        if self._font_bold:
            surface.blit(self._font_bold.render(">>", True, (255, 255, 255)), (ctrl_x + 76, 14))
        if on_speed_change:
            self._click_rects.append((fast_btn, lambda: on_speed_change(2.0 if speed < 2.0 else 5.0)))

        # Admin Gear [⚙]
        gear_btn = pygame.Rect(ctrl_x + 106, 10, 32, 26)
        pygame.draw.rect(surface, (55, 65, 95), gear_btn, border_radius=4)
        pygame.draw.rect(surface, (255, 215, 60), gear_btn, 1, border_radius=4)
        if self._font_bold:
            surface.blit(self._font_bold.render("⚙", True, (255, 215, 60)), (ctrl_x + 116, 14))
        if on_open_admin:
            self._click_rects.append((gear_btn, on_open_admin))

    # ------------------------------------------------------------------
    # 2. Left Navigation Pill Toolbar
    # ------------------------------------------------------------------
    def _draw_left_nav(self, surface: pygame.Surface, on_open_admin: Callable[[], None] | None) -> None:
        nav_x = 12
        nav_y = self.TOP_BAR_H + 16
        items = [
            ("ANIMALS", (245, 160, 45), on_open_admin),
            ("HABITAT", (75, 215, 110), self._toggle_habitat),
            ("BUILD",   (235, 195, 65), on_open_admin),
            ("EVOLVE",  (190, 100, 245), None),
            ("MAP",     (70, 180, 255), self._toggle_minimap),
            ("ADMIN",   (255, 215, 60), on_open_admin),
        ]

        for label, dot_col, callback in items:
            btn_rect = pygame.Rect(nav_x, nav_y, 96, 30)
            pygame.draw.rect(surface, (18, 24, 38, 220), btn_rect, border_radius=8)
            pygame.draw.rect(surface, (50, 68, 105), btn_rect, 1, border_radius=8)

            # Colored indicator icon dot
            pygame.draw.circle(surface, dot_col, (nav_x + 12, nav_y + 15), 4)

            if self._font_bold:
                txt = self._font_bold.render(label, True, (240, 245, 255) if label != "ADMIN" else (255, 220, 80))
                surface.blit(txt, (nav_x + 22, nav_y + 8))

            if callback:
                self._click_rects.append((btn_rect, callback))
            nav_y += 36

    def _toggle_habitat(self) -> None:
        self.show_plant_heatmap = not self.show_plant_heatmap

    def _toggle_minimap(self) -> None:
        self.show_minimap = not self.show_minimap

    # ------------------------------------------------------------------
    # 3. Top-Right Mini-Map
    # ------------------------------------------------------------------
    def _draw_minimap(self, surface: pygame.Surface, state: dict[str, Any], camera: Camera) -> None:
        canvas_w = surface.get_width()
        mx = canvas_w - self.MINIMAP_W - 14
        my = self.TOP_BAR_H + 12

        # Outer ornate frame
        frame_r = pygame.Rect(mx - 4, my - 4, self.MINIMAP_W + 8, self.MINIMAP_H + 8)
        pygame.draw.rect(surface, (20, 26, 40, 230), frame_r, border_radius=10)
        pygame.draw.rect(surface, (80, 110, 165), frame_r, 2, border_radius=10)

        # Mini-map world surface
        m_surf = pygame.Surface((self.MINIMAP_W, self.MINIMAP_H))
        m_surf.fill((15, 25, 45))

        # Terrain sampling
        world_st = state.get("world", {})
        terrain = world_st.get("terrain")
        if terrain:
            step = 120 // self.MINIMAP_W
            scale = self.MINIMAP_W / 120.0
            # Draw quick terrain base
            for ty in range(0, 120, 2):
                for tx in range(0, 120, 2):
                    t_idx = terrain[ty * 120 + tx]
                    col = (45, 110, 50) if t_idx in (0, 1, 2) else ((30, 80, 160) if t_idx in (4, 5) else (110, 95, 75))
                    px = int(tx * scale)
                    py = int(ty * scale)
                    m_surf.set_at((px, py), col)

        # Agents on minimap
        agents = state.get("agents", {})
        scale = self.MINIMAP_W / 120.0
        for a in agents.values():
            pos = a.get("position")
            if pos:
                sp = a.get("species_key", "default")
                dot_col = SPECIES_COLORS.get(sp, (220, 220, 220))
                ax = int(pos[0] * scale)
                ay = int(pos[1] * scale)
                pygame.draw.circle(m_surf, dot_col, (ax, ay), 2)

        # Camera viewport frustum rectangle
        min_gx, min_gy, max_gx, max_gy = camera.visible_cells()
        vx = int(min_gx * scale)
        vy = int(min_gy * scale)
        vw = max(4, int((max_gx - min_gx) * scale))
        vh = max(4, int((max_gy - min_gy) * scale))
        pygame.draw.rect(m_surf, (255, 255, 255), (vx, vy, vw, vh), 1)

        surface.blit(m_surf, (mx, my))

    # ------------------------------------------------------------------
    # 4. Bottom-Left Floating Creature Card (Matching Concept Art)
    # ------------------------------------------------------------------
    def _draw_creature_card(self, surface: pygame.Surface, agent: dict[str, Any]) -> None:
        card_w = 260
        card_h = 135
        cx = 14
        cy = surface.get_height() - card_h - 14

        # Rounded dark glassmorphism card
        glass = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
        glass.fill((16, 22, 34, 235))
        surface.blit(glass, (cx, cy))
        pygame.draw.rect(surface, (55, 75, 115), (cx, cy, card_w, card_h), 1, border_radius=12)

        # Portrait thumbnail (left)
        p_rect = pygame.Rect(cx + 10, cy + 10, 58, 58)
        sp_key = agent.get("species_key", "default")
        portrait = self._portraits.get(sp_key)
        if portrait:
            surface.blit(portrait, (p_rect.x, p_rect.y))
        else:
            pygame.draw.rect(surface, (30, 40, 60), p_rect, border_radius=8)
            pygame.draw.circle(surface, SPECIES_COLORS.get(sp_key, (200, 200, 200)), p_rect.center, 20)
        pygame.draw.rect(surface, (80, 105, 155), p_rect, 1, border_radius=8)

        # Name, Species, Status (right of portrait)
        tx = cx + 76
        name = agent.get("name") or agent.get("display_id", "Unknown")
        species = sp_key.replace("_", " ").title()
        health = agent.get("health", 1.0)
        status = "Healthy" if health > 0.6 else ("Injured" if health > 0.25 else "Critical")

        if self._font_title:
            surface.blit(self._font_title.render(name[:16], True, (255, 255, 255)), (tx, cy + 10))
        if self._font_small:
            surface.blit(self._font_small.render(f"Species: {species}", True, DIM_TEXT), (tx, cy + 28))
            stat_col = HUD_OK if health > 0.6 else (HUD_WARNING if health > 0.25 else HUD_DANGER)
            surface.blit(self._font_small.render(f"Status: {status}", True, stat_col), (tx, cy + 42))

        # Progress Bars: Health, Hunger, Energy
        by = cy + 74
        bw = card_w - 20
        # Health bar (green)
        self._draw_mini_bar(surface, cx + 10, by, bw, "Health", health, (75, 215, 110))
        by += 18
        # Hunger bar (orange)
        hunger = agent.get("drives", {}).get("hunger", 0.0)
        self._draw_mini_bar(surface, cx + 10, by, bw, "Hunger", hunger, (255, 160, 45))
        by += 18
        # Energy bar (blue)
        energy = agent.get("energy", 1.0)
        self._draw_mini_bar(surface, cx + 10, by, bw, "Energy", energy, (65, 180, 255))

    def _draw_mini_bar(
        self, surface: pygame.Surface, x: int, y: int, w: int,
        label: str, val: float, color: tuple[int, int, int]
    ) -> None:
        val = max(0.0, min(1.0, val))
        if self._font_small:
            surface.blit(self._font_small.render(label[:6], True, BODY_TEXT), (x, y - 2))
            pct_s = self._font_small.render(f"{int(val * 100)}%", True, DIM_TEXT)
            surface.blit(pct_s, (x + w - pct_s.get_width(), y - 2))
        bar_x = x + 50
        bar_w = w - 85
        pygame.draw.rect(surface, (25, 32, 48), (bar_x, y + 2, bar_w, 6), border_radius=3)
        if val > 0:
            pygame.draw.rect(surface, color, (bar_x, y + 2, int(bar_w * val), 6), border_radius=3)

    # ------------------------------------------------------------------
    # 5. Bottom-Right Biome / Tile Card (Matching Concept Art)
    # ------------------------------------------------------------------
    def _draw_biome_card(self, surface: pygame.Surface, world_state: dict, camera: Camera) -> None:
        card_w = 260
        card_h = 95
        cx = surface.get_width() - card_w - 14
        cy = surface.get_height() - card_h - 14

        glass = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
        glass.fill((16, 22, 34, 235))
        surface.blit(glass, (cx, cy))
        pygame.draw.rect(surface, (55, 75, 115), (cx, cy, card_w, card_h), 1, border_radius=12)

        # Active center biome
        cgx, cgy = camera.screen_to_world(camera.screen_w / 2, camera.screen_h / 2)
        center_gx = int(max(0, min(self.world_w - 1, cgx)))
        center_gy = int(max(0, min(self.world_h - 1, cgy)))
        terrain = world_state.get("terrain")
        t_name = "FLOODPLAIN"
        if terrain:
            idx = max(0, min(len(terrain) - 1, center_gy * self.world_w + center_gx))
            t_names = ["FLOODPLAIN", "FOREST", "OPEN_WOODLAND", "SWAMP", "RIVER", "LAKE", "ROCKY_HILLS", "MUD_FLATS"]
            t_idx = terrain[idx]
            if 0 <= t_idx < len(t_names):
                t_name = t_names[t_idx]

        # 3D Tile Cube (left)
        cube_rect = pygame.Rect(cx + 10, cy + 12, 60, 60)
        cube_img = self._cubes.get(t_name)
        if cube_img:
            surface.blit(cube_img, (cube_rect.x, cube_rect.y))
        else:
            pygame.draw.rect(surface, TERRAIN_COLORS.get(t_name, (60, 60, 60)), cube_rect, border_radius=8)

        # Title & Description
        tx = cx + 80
        display_biome = t_name.replace("_", " ").title()
        if self._font_title:
            surface.blit(self._font_title.render(display_biome, True, (255, 255, 255)), (tx, cy + 12))
        desc = _TERRAIN_DESCRIPTIONS.get(t_name, "Ancient Cretaceous ground.")
        if self._font_small:
            # Word wrap description
            words = desc.split()
            line1 = " ".join(words[:6])
            line2 = " ".join(words[6:12])
            surface.blit(self._font_small.render(line1, True, DIM_TEXT), (tx, cy + 34))
            surface.blit(self._font_small.render(line2, True, DIM_TEXT), (tx, cy + 48))

    # ------------------------------------------------------------------
    # Mouse interaction
    # ------------------------------------------------------------------
    def handle_click(self, mx: int, my: int) -> bool:
        for r, action in self._click_rects:
            if r.collidepoint(mx, my):
                action()
                return True
        return False
