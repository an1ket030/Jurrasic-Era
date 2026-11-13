"""
side_panel.py — Admin Privileges Side Panel & Real-time Ecosystem Inspector.

Tabs:
  • ⚙ ADMIN   — Complete God Mode panel: creature spawner, selected creature powers,
                 disasters (meteor, volcano, wildfire, flood), climate/time controls.
  • 🔍 INSPECT — Detailed creature inspector card with health, hunger, energy bars,
                 brain decision tree, genetics & traits.
  • 📊 CENSUS  — Live population breakdown per species with ecological health bars.
  • 📜 LOG     — Live scrolling feed of births, deaths, hunts, mating, and disasters.
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from typing import Any, Callable

import pygame

from prehistoric_sim.gui.audio import sound_engine
from prehistoric_sim.gui.colors import (
    BODY_TEXT,
    DIM_TEXT,
    EVENT_COLORS,
    HEADER_BG,
    HUD_ACCENT,
    HUD_DANGER,
    HUD_OK,
    HUD_WARNING,
    PANEL_BG,
    PANEL_BORDER,
    SPECIES_COLORS,
    TITLE_TEXT,
)

MAX_LOG_ENTRIES = 300
PANEL_WIDTH     = 340


class EventLogEntry:
    __slots__ = ("tick", "category_key", "glyph", "message", "color", "timestamp")

    def __init__(
        self,
        tick: int,
        category_key: str,
        glyph: str,
        message: str,
        color: tuple[int, int, int],
        timestamp: float,
    ) -> None:
        self.tick = tick
        self.category_key = category_key
        self.glyph = glyph
        self.message = message
        self.color = color
        self.timestamp = timestamp


_CATEGORY_GLYPHS_ASCII: dict[str, str] = {
    "LIFECYCLE_BIRTH":         "+",
    "LIFECYCLE_DEATH":         "X",
    "LIFECYCLE_STAGE_CHANGE":  "^",
    "LIFECYCLE_EGG_LAID":      "o",
    "LIFECYCLE_HATCHING":      "*",
    "LIFECYCLE_MATING":        "<3",
    "LIFECYCLE_CARCASS_FORMED":"~",
    "INTERACTION_HUNT_SUCCESS":"!",
    "INTERACTION_HUNT_FAIL":   "x",
    "INTERACTION_FIGHT":       "v",
    "INTERACTION_FLEE":        "<",
    "WORLD_DAWN":              ":)",
    "WORLD_DUSK":              ":(",
    "WORLD_SEASON_CHANGE":     "~~",
    "WORLD_WEATHER_START":     "***",
    "WORLD_FIRE_SPREAD":       "###",
    "ADMIN_ADMIN_COMMAND":     "[A]",
    "SYSTEM_POP_CAP":          "[!]",
    "default":                 "-",
}


def _event_to_message(event_dict: dict[str, Any]) -> str:
    cat   = event_dict.get("category", "")
    sub   = event_dict.get("subcategory", "")
    pay   = event_dict.get("payload", {})
    actors = event_dict.get("actor_ids", [])
    actor_str = pay.get("name") or pay.get("display_name") or (actors[0][:12] if actors else "")

    if sub == "DEATH":
        cause = pay.get("cause", "")
        return f"{actor_str} died ({cause})"
    if sub == "BIRTH":
        sp = pay.get("species", "")
        return f"New {sp}: {actor_str}"
    if sub == "HUNT_SUCCESS":
        prey = pay.get("prey_name", pay.get("prey_id", "prey"))
        return f"{actor_str} caught {prey}"
    if sub == "HUNT_FAIL":
        return f"{actor_str} hunt failed"
    if sub == "FIGHT":
        return f"{actor_str} fighting!"
    if sub == "MATING":
        return f"{actor_str} mating"
    if sub == "EGG_LAID":
        n = pay.get("count", 1)
        return f"{actor_str} laid {n} egg(s)"
    if sub == "HATCHING":
        return f"Egg hatched: {pay.get('species', '')}"
    if sub == "STAGE_CHANGE":
        return f"{actor_str} -> {pay.get('new_stage', '')}"
    if sub == "SEASON_CHANGE":
        return f"Season: {pay.get('season', '')}"
    if sub == "WEATHER_START":
        return f"Weather: {pay.get('weather', '')}"
    if sub == "FIRE_SPREAD":
        return f"Fire spreading"
    if sub == "FLOOD_EXPAND":
        return f"Flood expanding"
    if sub == "ADMIN_COMMAND":
        cmd = pay.get("command", "")
        return f"Admin: {cmd}"
    return f"{sub.lower().replace('_', ' ')}: {actor_str}"


class SidePanel:
    """Draws the right-side panel with tabs: ADMIN / INSPECT / CENSUS / LOG."""

    TABS = ["ADMIN", "INSPECT", "CENSUS", "LOG"]
    TAB_H = 34

    # Species list for god spawner
    SPECIES_KEYS = [
        ("T-Rex", "tyrannosaurus_rex"),
        ("Triceratops", "triceratops"),
        ("Dakotaraptor", "dakotaraptor"),
        ("Acheroraptor", "acheroraptor"),
        ("Edmonto", "edmontosaurus"),
        ("Ankylo", "ankylosaurus"),
        ("Pachy", "pachycephalosaurus"),
        ("Thescelo", "thescelosaurus"),
        ("Quetzal", "quetzalcoatlus"),
        ("Deinosuchus", "deinosuchus"),
        ("Anzu", "anzu_wyliei"),
        ("Turtle", "freshwater_turtle"),
        ("Fish", "freshwater_fish"),
        ("Mammal", "didelphodon"),
        ("Insects", "insect_swarm"),
    ]

    def __init__(self, rect: pygame.Rect, on_admin_cmd: Callable[[str, dict], str] | None = None) -> None:
        self.rect = rect
        self.active_tab: int = 0   # 0=ADMIN, 1=INSPECT, 2=CENSUS, 3=LOG
        self.on_admin_cmd = on_admin_cmd

        # Event log ring buffer
        self._log: deque[EventLogEntry] = deque(maxlen=MAX_LOG_ENTRIES)
        self._log_lock = threading.Lock()
        self._log_scroll: int = 0

        # Census & Inspector
        self._census: dict[str, int] = {}
        self._species_health: dict[str, float] = {}
        self.inspect_agent: dict[str, Any] | None = None
        self._world_day = 0

        # Admin panel state
        self.selected_spawn_species: str = "tyrannosaurus_rex"
        self.selected_spawn_count: int = 1
        self.admin_feedback: str = "Admin God Mode Ready."
        self.admin_feedback_time: float = 0.0

        # Clickable button rects for active frame
        self._button_actions: list[tuple[pygame.Rect, Callable[[], None]]] = []
        self._tab_rects: list[pygame.Rect] = []

        # Fonts
        self._font_ui:    pygame.font.Font | None = None
        self._font_small: pygame.font.Font | None = None
        self._font_title: pygame.font.Font | None = None
        self._font_bold:  pygame.font.Font | None = None

    def set_feedback(self, text: str) -> None:
        self.admin_feedback = text
        self.admin_feedback_time = time.time()

    def ingest_event(self, event: Any) -> None:
        cat = str(event.category.value) if hasattr(event.category, "value") else str(event.category)
        sub = str(event.subcategory.value) if hasattr(event.subcategory, "value") else str(event.subcategory)
        key = f"{cat}_{sub}"
        col = EVENT_COLORS.get(key, EVENT_COLORS["default"])
        glyph = _CATEGORY_GLYPHS_ASCII.get(key, _CATEGORY_GLYPHS_ASCII["default"])

        ev_dict = {
            "category": cat,
            "subcategory": sub,
            "payload": dict(event.payload) if event.payload else {},
            "actor_ids": list(event.actor_ids),
            "tick": event.tick,
        }
        msg = _event_to_message(ev_dict)
        entry = EventLogEntry(
            tick=event.tick,
            category_key=key,
            glyph=glyph,
            message=msg,
            color=col,
            timestamp=time.time(),
        )
        with self._log_lock:
            self._log.append(entry)

    def update_from_state(self, state: dict[str, Any], selected_id: str | None) -> None:
        self._world_day = int(state.get("world", {}).get("day", 0))
        agents = state.get("agents", {})
        census: dict[str, int] = {}
        health_sum: dict[str, float] = {}
        for a in agents.values():
            sp = a.get("species_key", "unknown")
            census[sp] = census.get(sp, 0) + 1
            health_sum[sp] = health_sum.get(sp, 0.0) + a.get("health", 1.0)
        self._census = census
        self._species_health = {sp: health_sum[sp] / max(1, cnt) for sp, cnt in census.items()}

        if selected_id and selected_id in agents:
            self.inspect_agent = agents[selected_id]
        elif selected_id is None:
            self.inspect_agent = None

    def draw(self, surface: pygame.Surface) -> None:
        self._ensure_fonts()
        self._button_actions.clear()
        w, h = surface.get_size()

        # Background with subtle gradient & border
        surface.fill(PANEL_BG)
        pygame.draw.line(surface, PANEL_BORDER, (0, 0), (0, h), 2)

        # Tabs bar
        self._draw_tabs(surface, w)

        content_rect = pygame.Rect(0, self.TAB_H, w, h - self.TAB_H)
        if self.active_tab == 0:
            self._draw_admin(surface, content_rect)
        elif self.active_tab == 1:
            self._draw_inspector(surface, content_rect)
        elif self.active_tab == 2:
            self._draw_census(surface, content_rect)
        elif self.active_tab == 3:
            self._draw_log(surface, content_rect)

    def _draw_tabs(self, surface: pygame.Surface, w: int) -> None:
        tab_w = w // len(self.TABS)
        self._tab_rects = []
        for i, label in enumerate(self.TABS):
            tr = pygame.Rect(i * tab_w, 0, tab_w, self.TAB_H)
            self._tab_rects.append(tr)
            is_active = (i == self.active_tab)
            bg = (38, 48, 72) if is_active else HEADER_BG
            pygame.draw.rect(surface, bg, tr)
            pygame.draw.rect(surface, PANEL_BORDER, tr, 1)

            if is_active:
                # Gold/cyan highlight line under active tab
                accent = (255, 215, 60) if label == "ADMIN" else HUD_ACCENT
                pygame.draw.line(surface, accent, (tr.x, tr.bottom - 2), (tr.right, tr.bottom - 2), 2)

            text_col = (255, 220, 80) if (is_active and label == "ADMIN") else (TITLE_TEXT if is_active else DIM_TEXT)
            if self._font_ui:
                lbl = self._font_ui.render(label, True, text_col)
                surface.blit(lbl, (tr.x + (tab_w - lbl.get_width()) // 2, tr.y + 8))

    # ------------------------------------------------------------------
    # TAB 0: ADMIN GOD MODE PANEL
    # ------------------------------------------------------------------
    def _draw_admin(self, surface: pygame.Surface, r: pygame.Rect) -> None:
        pad = 12
        x = pad
        y = r.y + 10
        w = r.w - pad * 2

        # Status & Feedback pill
        fb_col = HUD_OK if (time.time() - self.admin_feedback_time < 3.0) else HUD_ACCENT
        pygame.draw.rect(surface, (22, 28, 42), (x, y, w, 28), border_radius=6)
        pygame.draw.rect(surface, PANEL_BORDER, (x, y, w, 28), 1, border_radius=6)
        if self._font_small:
            fb_surf = self._font_small.render(self.admin_feedback[:42], True, fb_col)
            surface.blit(fb_surf, (x + 8, y + 6))
        y += 34

        # SECTION: GOD SPAWNER
        self._draw_section_header(surface, x, y, w, "SPAWN CREATURES (GOD MODE)")
        y += 24

        # Species grid (3 columns)
        btn_w = (w - 8) // 3
        btn_h = 24
        for idx, (sp_name, sp_key) in enumerate(self.SPECIES_KEYS):
            col_i = idx % 3
            row_i = idx // 3
            bx = x + col_i * (btn_w + 4)
            by = y + row_i * (btn_h + 3)
            br = pygame.Rect(bx, by, btn_w, btn_h)

            is_sel = (self.selected_spawn_species == sp_key)
            bg = (55, 75, 115) if is_sel else (25, 32, 48)
            border_col = (255, 215, 60) if is_sel else (45, 60, 90)
            pygame.draw.rect(surface, bg, br, border_radius=4)
            pygame.draw.rect(surface, border_col, br, 1, border_radius=4)

            # Dot indicator
            dot_col = SPECIES_COLORS.get(sp_key, (200, 200, 200))
            pygame.draw.circle(surface, dot_col, (bx + 8, by + btn_h // 2), 4)

            if self._font_small:
                txt = self._font_small.render(sp_name[:9], True, (240, 240, 240) if is_sel else (180, 190, 205))
                surface.blit(txt, (bx + 16, by + 4))

            # Action
            def make_sel(k=sp_key):
                self.selected_spawn_species = k
            self._button_actions.append((br, make_sel))

        y += (len(self.SPECIES_KEYS) + 2) // 3 * (btn_h + 3) + 4

        # Count selector pills + Spawn Button
        count_w = 40
        for cnt in [1, 3, 5, 10]:
            cr = pygame.Rect(x + (cnt != 1) * count_w, y, count_w - 4, 26)
            # Recompute proper x
            pass
        
        # Pill selectors for count: 1x, 3x, 5x, 10x
        pill_xs = [x, x + 44, x + 88, x + 132]
        for c_idx, cnt in enumerate([1, 3, 5, 10]):
            cr = pygame.Rect(pill_xs[c_idx], y, 40, 24)
            is_sel = (self.selected_spawn_count == cnt)
            bg = (60, 90, 140) if is_sel else (24, 30, 45)
            pygame.draw.rect(surface, bg, cr, border_radius=4)
            pygame.draw.rect(surface, (255, 215, 60) if is_sel else PANEL_BORDER, cr, 1, border_radius=4)
            if self._font_small:
                lbl = self._font_small.render(f"x{cnt}", True, (255, 255, 255) if is_sel else DIM_TEXT)
                surface.blit(lbl, (cr.x + (cr.w - lbl.get_width()) // 2, cr.y + 4))
            def set_cnt(c=cnt):
                self.selected_spawn_count = c
            self._button_actions.append((cr, set_cnt))

        # Big "SPAWN AT CENTER" button
        spawn_r = pygame.Rect(x + 180, y, w - 180, 24)
        pygame.draw.rect(surface, (45, 115, 65), spawn_r, border_radius=4)
        pygame.draw.rect(surface, (80, 220, 120), spawn_r, 1, border_radius=4)
        if self._font_ui:
            sl = self._font_ui.render("SPAWN", True, (255, 255, 255))
            surface.blit(sl, (spawn_r.x + (spawn_r.w - sl.get_width()) // 2, spawn_r.y + 3))

        def do_spawn():
            if self.on_admin_cmd:
                res = self.on_admin_cmd("spawn", {"species": self.selected_spawn_species, "count": self.selected_spawn_count, "x": 60, "y": 60})
                self.set_feedback(f"Spawned {self.selected_spawn_count}x {self.selected_spawn_species}!")
                sound_engine.play_sfx("god_power")
        self._button_actions.append((spawn_r, do_spawn))

        y += 34

        # SECTION: SELECTED CREATURE POWERS
        self._draw_section_header(surface, x, y, w, "CREATURE POWERS (TARGETED)")
        y += 24

        agent = self.inspect_agent
        if agent:
            # Show target name
            target_name = agent.get("name") or agent.get("display_id") or "Selected"
            if self._font_small:
                surface.blit(self._font_small.render(f"Target: {target_name} ({agent.get('species_key')})", True, (255, 220, 100)), (x, y))
            y += 18

            # Action buttons row 1
            b_w = (w - 6) // 2
            r_heal = pygame.Rect(x, y, b_w, 24)
            self._render_admin_button(surface, r_heal, "Heal 100% & Feed", (35, 100, 60), (70, 210, 110),
                                      lambda: self._cmd_target("heal", agent["id"], "Healed 100%!"))
            r_smite = pygame.Rect(x + b_w + 6, y, b_w, 24)
            self._render_admin_button(surface, r_smite, "Smite Lightning", (120, 35, 35), (255, 60, 60),
                                      lambda: self._smite_agent(agent["id"]))
            y += 28

            # Action buttons row 2
            r_mate = pygame.Rect(x, y, b_w, 24)
            self._render_admin_button(surface, r_mate, "Force Mating", (90, 45, 100), (220, 100, 240),
                                      lambda: self._cmd_target("mate", agent["id"], "Forced mating attempt completed."))
            r_possess = pygame.Rect(x + b_w + 6, y, b_w, 24)
            is_pos = agent.get("possessed", False)
            p_label = "Unpossess" if is_pos else "Possess (WASD)"
            self._render_admin_button(surface, r_possess, p_label, (45, 80, 120), (100, 180, 255),
                                      lambda: self._cmd_target("unpossess" if is_pos else "possess", agent["id"], "Possession updated!"))
            y += 32
        else:
            if self._font_small:
                surface.blit(self._font_small.render("Click any dinosaur to cast God Powers on it.", True, DIM_TEXT), (x, y))
            y += 24

        # SECTION: NATURAL CATACLYSMS & DISASTERS
        self._draw_section_header(surface, x, y, w, "CATACLYSMS & DISASTERS")
        y += 24

        b_w = (w - 6) // 2
        # Row 1: Meteor & Volcano
        r_meteor = pygame.Rect(x, y, b_w, 24)
        self._render_admin_button(surface, r_meteor, "Meteor Strike", (125, 45, 20), (255, 120, 40), self._trigger_meteor)
        r_volcano = pygame.Rect(x + b_w + 6, y, b_w, 24)
        self._render_admin_button(surface, r_volcano, "Wildfire Blast", (110, 30, 20), (255, 80, 40),
                                  lambda: self._cmd_disaster("fire", 60, 60, "Wildfire raging!"))
        y += 28

        # Row 2: Flood & Storm
        r_flood = pygame.Rect(x, y, b_w, 24)
        self._render_admin_button(surface, r_flood, "Flash Flood", (25, 75, 120), (60, 160, 255),
                                  lambda: self._cmd_disaster("flood", 60, 60, "Flash flood rising!"))
        r_clear = pygame.Rect(x + b_w + 6, y, b_w, 24)
        self._render_admin_button(surface, r_clear, "Extinguish Hazards", (35, 75, 60), (80, 200, 140),
                                  self._extinguish_hazards)
        y += 34

        # SECTION: TIME MACHINE & CLIMATE
        self._draw_section_header(surface, x, y, w, "TIME & CLIMATE CONTROL")
        y += 24

        # Time of Day buttons (Dawn, Noon, Dusk, Night)
        tod_w = (w - 9) // 4
        tods = [("Dawn", "06:00"), ("Noon", "12:00"), ("Dusk", "19:00"), ("Night", "00:00")]
        for ti, (t_name, t_val) in enumerate(tods):
            tr = pygame.Rect(x + ti * (tod_w + 3), y, tod_w, 22)
            self._render_admin_button(surface, tr, t_name, (30, 40, 60), (120, 160, 220),
                                      lambda v=t_val: self._set_hour(v))
        y += 26

        # Season buttons (Spring, Summer, Autumn, Winter)
        seasons = ["SPRING", "SUMMER", "AUTUMN", "WINTER"]
        for si, s_name in enumerate(seasons):
            sr = pygame.Rect(x + si * (tod_w + 3), y, tod_w, 22)
            self._render_admin_button(surface, sr, s_name[:4], (35, 45, 65), (140, 180, 230),
                                      lambda sn=s_name: self._set_season(sn))
        y += 34

        # SECTION: ECOSYSTEM UTILITIES
        self._draw_section_header(surface, x, y, w, "ECOSYSTEM UTILITIES")
        y += 24

        r_bloom = pygame.Rect(x, y, b_w, 24)
        self._render_admin_button(surface, r_bloom, "Bloom Vegetation", (35, 95, 55), (80, 210, 120), self._bloom_flora)
        r_carc = pygame.Rect(x + b_w + 6, y, b_w, 24)
        self._render_admin_button(surface, r_carc, "Clean Carcasses", (50, 50, 65), (140, 140, 170),
                                  lambda: self._cmd_simple("clear_carcasses", "Carcasses cleared!"))
        y += 28

    def _draw_section_header(self, surface: pygame.Surface, x: int, y: int, w: int, title: str) -> None:
        if self._font_bold:
            st = self._font_bold.render(title, True, (255, 215, 60))
            surface.blit(st, (x, y))
        pygame.draw.line(surface, (50, 65, 95), (x, y + 16), (x + w, y + 16), 1)

    def _render_admin_button(
        self, surface: pygame.Surface, rect: pygame.Rect, label: str,
        bg_col: tuple, border_col: tuple, on_click: Callable[[], None],
    ) -> None:
        pygame.draw.rect(surface, bg_col, rect, border_radius=4)
        pygame.draw.rect(surface, border_col, rect, 1, border_radius=4)
        if self._font_small:
            lbl = self._font_small.render(label, True, (240, 245, 255))
            surface.blit(lbl, (rect.x + (rect.w - lbl.get_width()) // 2, rect.y + 4))
        self._button_actions.append((rect, on_click))

    # Admin execution helpers
    def _cmd_target(self, cmd: str, target_id: str, success_msg: str) -> None:
        if self.on_admin_cmd:
            args = ({"action": target_id, "possessing": self.inspect_agent.get("id")}
                    if cmd == "act" and self.inspect_agent
                    else {"target": target_id})
            result = self.on_admin_cmd(cmd, args)
            self.set_feedback(str(result) if str(result).startswith(("Error:", "Agent not found", "No creature")) else success_msg)
            sound_engine.play_sfx("god_power")

    def _smite_agent(self, target_id: str) -> None:
        if self.on_admin_cmd:
            self.on_admin_cmd("kill", {"target": target_id})
            self.set_feedback("Smote creature with lightning!")
            sound_engine.play_sfx("thunder")

    def _trigger_meteor(self) -> None:
        if self.on_admin_cmd:
            self.on_admin_cmd("fire", {"x": 60, "y": 60})
            self.on_admin_cmd("fire", {"x": 61, "y": 60})
            self.on_admin_cmd("fire", {"x": 60, "y": 61})
            self.set_feedback("METEOR STRIKE! Impact at sector (60, 60)")
            sound_engine.play_sfx("meteor_boom")

    def _cmd_disaster(self, dtype: str, gx: int, gy: int, msg: str) -> None:
        if self.on_admin_cmd:
            self.on_admin_cmd(dtype, {"x": gx, "y": gy})
            self.set_feedback(msg)
            sound_engine.play_sfx("thunder" if dtype == "flood" else "roar")

    def _extinguish_hazards(self) -> None:
        if self.on_admin_cmd:
            self.on_admin_cmd("weather", {"value": "RAIN"})
            self.set_feedback("Summoned rainstorm to quell fires!")
            sound_engine.play_sfx("splash")

    def _set_hour(self, hour_str: str) -> None:
        if self.on_admin_cmd:
            hour = int(hour_str.split(":", 1)[0])
            result = self.on_admin_cmd("set_time", {"day": self._world_day, "hour": hour})
            self.set_feedback(str(result))
            sound_engine.play_sfx("god_power")

    def _set_season(self, season: str) -> None:
        if self.on_admin_cmd:
            self.on_admin_cmd("season", {"value": season})
            self.set_feedback(f"Season changed to {season}")
            sound_engine.play_sfx("god_power")

    def _bloom_flora(self) -> None:
        if self.on_admin_cmd:
            result = self.on_admin_cmd("bloom", {})
            self.set_feedback(str(result))
            sound_engine.play_sfx("god_power")

    def _cmd_simple(self, cmd: str, msg: str) -> None:
        if self.on_admin_cmd:
            self.on_admin_cmd(cmd, {})
            self.set_feedback(msg)
            sound_engine.play_sfx("god_power")

    # ------------------------------------------------------------------
    # TAB 1: INSPECTOR
    # ------------------------------------------------------------------
    def _draw_inspector(self, surface: pygame.Surface, r: pygame.Rect) -> None:
        a = self.inspect_agent
        if a is None:
            if self._font_ui:
                msg = self._font_ui.render("No creature selected.", True, DIM_TEXT)
                surface.blit(msg, (r.x + (r.w - msg.get_width()) // 2, r.y + 60))
                hint = self._font_small.render("Left-click any creature to inspect.", True, DIM_TEXT) if self._font_small else None
                if hint:
                    surface.blit(hint, (r.x + (r.w - hint.get_width()) // 2, r.y + 85))
            return

        pad = 12
        x = pad
        y = r.y + 12
        w = r.w - pad * 2

        # Creature Header Card
        name = a.get("name") or a.get("display_id", "Unknown")
        species = a.get("species_key", "default").replace("_", " ").title()
        stage = a.get("life_stage", "ADULT")

        if self._font_title:
            surface.blit(self._font_title.render(name, True, (255, 230, 100)), (x, y))
        y += 20
        if self._font_small:
            surface.blit(self._font_small.render(f"{species} • {stage}", True, HUD_ACCENT), (x, y))
        y += 26

        # Vitals
        self._draw_stat_bar(surface, x, y, w, "Health", a.get("health", 1.0), (80, 220, 120))
        y += 24
        drives = a.get("drives", {})
        hunger = drives.get("hunger", 0.0)
        self._draw_stat_bar(surface, x, y, w, "Hunger", hunger, (255, 160, 40))
        y += 24
        energy = a.get("energy", 1.0)
        self._draw_stat_bar(surface, x, y, w, "Energy", energy, (80, 180, 255))
        y += 24
        hydration = a.get("hydration", 1.0)
        self._draw_stat_bar(surface, x, y, w, "Hydration", hydration, (60, 220, 240))
        y += 30

        # Action & Brain
        self._draw_section_header(surface, x, y, w, "BRAIN & CURRENT BEHAVIOR")
        y += 24
        action = a.get("current_action", "WANDER")
        if self._font_ui:
            surface.blit(self._font_ui.render(f"Action: {action}", True, (255, 255, 255)), (x, y))
        y += 20

        last_dec = a.get("last_decision")
        if last_dec and self._font_small:
            reason = last_dec.get("reason", "")
            surface.blit(self._font_small.render(f"Decision: {reason[:36]}", True, DIM_TEXT), (x, y))
            y += 18

        # Quick God buttons on inspector card
        y += 10
        b_w = (w - 6) // 2
        r_h = pygame.Rect(x, y, b_w, 24)
        self._render_admin_button(surface, r_h, "Heal & Feed", (35, 95, 55), (70, 200, 110),
                                  lambda: self._cmd_target("heal", a["id"], "Creature restored!"))
        r_s = pygame.Rect(x + b_w + 6, y, b_w, 24)
        self._render_admin_button(surface, r_s, "Smite with Lightning", (115, 35, 35), (255, 60, 60),
                                  lambda: self._smite_agent(a["id"]))

    def _draw_stat_bar(
        self, surface: pygame.Surface, x: int, y: int, w: int,
        label: str, val: float, color: tuple[int, int, int]
    ) -> None:
        val = max(0.0, min(1.0, val))
        if self._font_small:
            surface.blit(self._font_small.render(label, True, BODY_TEXT), (x, y))
            pct_s = self._font_small.render(f"{int(val * 100)}%", True, DIM_TEXT)
            surface.blit(pct_s, (x + w - pct_s.get_width(), y))
        bar_y = y + 14
        bar_h = 7
        pygame.draw.rect(surface, (25, 32, 48), (x, bar_y, w, bar_h), border_radius=3)
        fill_w = int(w * val)
        if fill_w > 0:
            pygame.draw.rect(surface, color, (x, bar_y, fill_w, bar_h), border_radius=3)

    # ------------------------------------------------------------------
    # TAB 2: CENSUS
    # ------------------------------------------------------------------
    def _draw_census(self, surface: pygame.Surface, r: pygame.Rect) -> None:
        pad = 12
        x = pad
        y = r.y + 12
        w = r.w - pad * 2

        self._draw_section_header(surface, x, y, w, "SPECIES CENSUS BREAKDOWN")
        y += 24

        total_pop = sum(self._census.values())
        if self._font_ui:
            surface.blit(self._font_ui.render(f"Total Population: {total_pop}", True, (255, 255, 255)), (x, y))
        y += 22

        for sp, cnt in sorted(self._census.items(), key=lambda item: -item[1]):
            if y > r.bottom - 20:
                break
            dot_col = SPECIES_COLORS.get(sp, (200, 200, 200))
            pygame.draw.circle(surface, dot_col, (x + 6, y + 8), 4)

            display_name = sp.replace("_", " ").title()[:18]
            if self._font_small:
                surface.blit(self._font_small.render(display_name, True, (230, 235, 245)), (x + 16, y))
                cnt_s = self._font_small.render(str(cnt), True, (255, 220, 100))
                surface.blit(cnt_s, (x + w - cnt_s.get_width(), y))
            y += 20

    # ------------------------------------------------------------------
    # TAB 3: LOG
    # ------------------------------------------------------------------
    def _draw_log(self, surface: pygame.Surface, r: pygame.Rect) -> None:
        pad = 10
        x = pad
        y = r.y + 10
        w = r.w - pad * 2

        with self._log_lock:
            entries = list(self._log)

        if not entries:
            if self._font_small:
                surface.blit(self._font_small.render("No events logged yet.", True, DIM_TEXT), (x, y))
            return

        visible_entries = entries[-28:]
        for ev in visible_entries:
            if y > r.bottom - 16:
                break
            if self._font_small:
                ts = self._font_small.render(f"T{ev.tick:04d}", True, DIM_TEXT)
                surface.blit(ts, (x, y))
                msg = self._font_small.render(ev.message[:34], True, ev.color)
                surface.blit(msg, (x + 44, y))
            y += 18

    # ------------------------------------------------------------------
    # Click handling
    # ------------------------------------------------------------------
    def handle_click(self, px: int, py: int) -> bool:
        """Handle mouse click inside the side panel."""
        # 1. Check tab clicks
        for i, tr in enumerate(self._tab_rects):
            if tr.collidepoint(px, py):
                self.active_tab = i
                sound_engine.play_sfx("footstep", 0.4)
                return True

        # 2. Check active buttons
        for br, action in self._button_actions:
            if br.collidepoint(px, py):
                action()
                return True

        return False

    def handle_scroll(self, dy: int) -> bool:
        if self.active_tab == 3:
            self._log_scroll = max(0, self._log_scroll + dy)
            return True
        return False

    def _ensure_fonts(self) -> None:
        if self._font_ui is None:
            try:
                self._font_ui    = pygame.font.SysFont("segoeui", 12, bold=True)
                self._font_small = pygame.font.SysFont("segoeui", 11)
                self._font_title = pygame.font.SysFont("segoeui", 14, bold=True)
                self._font_bold  = pygame.font.SysFont("segoeui", 11, bold=True)
            except Exception:
                self._font_ui    = pygame.font.Font(None, 14)
                self._font_small = pygame.font.Font(None, 12)
                self._font_title = pygame.font.Font(None, 16)
                self._font_bold  = pygame.font.Font(None, 13)
