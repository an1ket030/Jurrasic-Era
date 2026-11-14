"""
app.py — Main Pygame 2 application for the JurassicEra Phase 2 GUI.

Architecture:
  ┌────────────────────────────────────────────────────────┐
  │                   GuiApp (main thread)                 │
  │  ┌───────────────────────┐ ┌─────────────────────────┐ │
  │  │      WorldCanvas       │ │       SidePanel         │ │
  │  │ (smooth 60fps lerp +  │ │ (ADMIN / INSPECT /       │ │
  │  │  low-poly models +     │ │  CENSUS / LOG)          │ │
  │  │  faceted terrain)     │ └─────────────────────────┘ │
  │  └───────────────────────┘                             │
  │  ┌───────────────────────┐ ┌─────────────────────────┐ │
  │  │          HUD          │ │        AdminBar         │ │
  │  │ (concept art UI bars) │ └─────────────────────────┘ │
  │  └───────────────────────┘                             │
  └──────────────────────────┬─────────────────────────────┘
                             │ Simulation Thread (smooth pacing)
                             ▼
  ┌────────────────────────────────────────────────────────┐
  │                 Simulation Engine                      │
  │         EventBus → GUI event queue (thread-safe)       │
  └────────────────────────────────────────────────────────┘

Keybindings:
  Space        — Pause / Resume
  + / =        — Speed up (0.5x, 1x, 2x, 5x, 10x)
  - / _        — Speed down
  1 / 2 / 3 / 4— Switch panel tabs (ADMIN / INSPECT / CENSUS / LOG)
  M            — Mute / Unmute ambient music
  N            — Next ambient music track
  B            — Previous ambient music track
  R            — Reset camera to centre
  F            — Follow selected creature
  Escape       — Deselect creature
  Scroll wheel — Zoom in/out (pivot at mouse)
  Middle-drag  — Pan camera
  Left-click   — Select creature / Interact with buttons
  Right-click  — Context admin info at cursor
"""

from __future__ import annotations

import queue
import threading
import time
from pathlib import Path
from typing import Any

import pygame

from prehistoric_sim.admin.commands import execute_command
from prehistoric_sim.engine.events import Event
from prehistoric_sim.engine.simulation import Simulation
from prehistoric_sim.gui.admin_bar import AdminBar
from prehistoric_sim.gui.audio import sound_engine
from prehistoric_sim.gui.camera import Camera
from prehistoric_sim.gui.colors import BG_DARK, HUD_DANGER, HUD_OK, HUD_WARNING
from prehistoric_sim.gui.hud import HUD
from prehistoric_sim.gui.side_panel import SidePanel
from prehistoric_sim.gui.world_canvas import WorldCanvas
from prehistoric_sim.gui.renderer3d import World3DRenderer

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------

SIDE_PANEL_W   = 340
ADMIN_BAR_H    = 34
FPS_TARGET     = 60
BASE_TICK_SECS = 0.85  # Normal 1.0x speed: 1 tick every 0.85s (smooth gliding)


def _flatten_terrain(terrain_array: Any) -> list[int]:
    try:
        return terrain_array.flatten().tolist()
    except Exception:
        return []


def _flatten_2d(arr: Any) -> list[float]:
    try:
        return arr.flatten().tolist()
    except Exception:
        return []


def _build_render_state(sim: "Simulation") -> dict[str, Any]:
    world = sim.world
    ws = {
        "tick":            world.tick,
        "day":             world.day,
        "season":          world.season,
        "hour_of_day":     world.hour_of_day,
        "temperature":     world.temperature,
        "weather":         world.weather.current.value,
        "fire_cells":      list(world.weather.fire_cells),
        "flood_cells":     list(world.weather.flood_cells),
        "terrain":         _flatten_terrain(world.terrain),
        "plant_biomass_total": _flatten_2d(world.plant_biomass.sum(axis=0)),
        "nutrients":       _flatten_2d(world.nutrients),
        "wind_direction":  world.weather.wind_direction,
        "wind_speed":      world.weather.wind_speed,
    }

    agents_dict: dict[str, Any] = {}
    for aid, a in sim.agents.items():
        agents_dict[aid] = {
            "id":             a.id,
            "position":       a.position,
            "species_key":    a.species_key,
            "name":           a.name,
            "display_id":     a.display_id,
            "life_stage":     a.life_stage.value,
            "health":         a.health,
            "energy":         a.energy,
            "hydration":      a.hydration,
            "stamina":        a.stamina,
            "injury_level":   a.injury_level,
            "current_action": a.current_action,
            "drives": {
                "hunger":           a.drives.hunger,
                "thirst":           a.drives.thirst,
                "fatigue":          a.drives.fatigue,
                "fear":             a.drives.fear,
                "reproductive_urge":a.drives.reproductive_urge,
                "social_need":      a.drives.social_need,
                "curiosity":        a.drives.curiosity,
                "parental_drive":   a.drives.parental_drive,
            },
            "traits": {
                "boldness":    a.traits.boldness,
                "aggression":  a.traits.aggression,
                "sociability": a.traits.sociability,
                "curiosity":   a.traits.curiosity,
            },
            "possessed":      a.possessed,
            "tracked":        a.tracked,
            "pregnant":       a.pregnant,
            "group_id":       a.group_id,
            "age_ticks":      a.age_ticks,
            "last_decision":  {
                "action":       a.last_decision.action,
                "score":        a.last_decision.score,
                "reason":       a.last_decision.reason,
                "alternatives": a.last_decision.alternatives,
            } if a.last_decision else None,
        }

    eggs_dict: dict[str, Any] = {}
    for eid, e in sim.eggs.items():
        eggs_dict[eid] = {
            "id":                        e.id,
            "position":                  e.position,
            "species_key":               e.species_key,
            "incubation_ticks_remaining":e.incubation_ticks_remaining,
            "incubation_ticks_total":    e.incubation_ticks_total,
        }

    nests_dict: dict[str, Any] = {}
    for nid, n in sim.nests.items():
        nests_dict[nid] = {
            "id":       n.id,
            "position": n.position,
            "species_key": n.species_key,
            "guarded":  n.guarded,
            "egg_ids":  n.egg_ids,
        }

    carcs_dict: dict[str, Any] = {}
    for cid, c in sim.carcasses.items():
        carcs_dict[cid] = {
            "id":             c.id,
            "position":       c.position,
            "species_key":    c.species_key,
            "decay_progress": c.decay_progress,
            "mass_remaining": c.mass_remaining,
        }

    return {
        "tick":      sim.tick,
        "world":     ws,
        "agents":    agents_dict,
        "eggs":      eggs_dict,
        "nests":     nests_dict,
        "carcasses": carcs_dict,
    }


def _parse_and_dispatch(sim: Simulation, raw_cmd: str) -> str:
    raw_cmd = raw_cmd.strip()
    if not raw_cmd:
        return ""

    parts = raw_cmd.split()
    cmd   = parts[0].lower()
    args_list = parts[1:]
    args: dict[str, Any] = {}

    if cmd == "spawn":
        args["species"] = args_list[0] if args_list else ""
        args["count"]   = int(args_list[1]) if len(args_list) > 1 else 1
        if len(args_list) > 3:
            args["x"] = int(args_list[2])
            args["y"] = int(args_list[3])
        if len(args_list) > 4:
            args["name"] = args_list[4]
    elif cmd in ("kill", "starve", "heal", "inspect", "track", "untrack",
                  "possess", "unpossess", "release"):
        args["target"] = args_list[0] if args_list else ""
    elif cmd == "injure":
        args["target"] = args_list[0] if args_list else ""
        args["amount"] = float(args_list[1]) if len(args_list) > 1 else 0.3
    elif cmd == "name":
        args["target"]   = args_list[0] if args_list else ""
        args["new_name"] = args_list[1] if len(args_list) > 1 else ""
    elif cmd == "act":
        args["action"] = args_list[0].upper() if args_list else "WANDER"
        if len(args_list) > 1:
            args["target"] = args_list[1]
    elif cmd in ("weather", "season"):
        args["value"] = args_list[0].upper() if args_list else ""
    elif cmd in ("fire", "flood"):
        args["x"] = int(args_list[0]) if args_list else 60
        args["y"] = int(args_list[1]) if len(args_list) > 1 else 60
    elif cmd == "speed":
        args["multiplier"] = float(args_list[0]) if args_list else 1.0
    elif cmd == "step":
        args["ticks"] = int(args_list[0]) if args_list else 1
    elif cmd == "set_time":
        args["day"] = sim.world.day
        args["hour"] = float(args_list[0]) if args_list else 12.0
    elif cmd == "save":
        args["filename"] = args_list[0] if args_list else "snapshot.json"
    elif cmd == "load":
        args["filename"] = args_list[0] if args_list else "snapshot.json"
    elif cmd == "help":
        args["command"] = args_list[0] if args_list else ""

    result = sim.apply_admin_command(cmd, args)
    return str(result) if result else f"OK: {cmd}"


class GuiApp:
    """The Pygame-based GUI application with Concept-Art UI and Admin Privileges."""

    def __init__(self, sim: Simulation, title: str = "JurassicEra — Prehistoric World Simulation") -> None:
        self.sim  = sim
        self.title = title
        self._running = False

        self._sim_thread: threading.Thread | None = None
        self._event_queue: queue.Queue[Event] = queue.Queue(maxsize=500)
        self._render_state: dict[str, Any] = {}

        # Screen dimensions
        self._screen_w = 1280
        self._screen_h = 800
        self._canvas_w = self._screen_w - SIDE_PANEL_W
        self._canvas_h = self._screen_h - ADMIN_BAR_H

        # State
        self._selected_id:  str | None = None
        self._hovered_id:   str | None = None
        self._hovered_pos:  tuple[int, int] | None = None
        self._follow_mode:  bool = False
        self._view_3d: bool = False

    def run(self) -> None:
        pygame.init()
        pygame.display.set_caption(self.title)

        flags = pygame.RESIZABLE
        self._screen = pygame.display.set_mode((self._screen_w, self._screen_h), flags)
        self._recalculate_layout()

        # Audio engine init (starts ambient music)
        sound_engine.init()

        # Create subsystems
        self._camera = Camera(
            self.sim.world.width,
            self.sim.world.height,
            self._canvas_w,
            self._canvas_h,
        )
        self._canvas = WorldCanvas(self.sim.world.width, self.sim.world.height)
        self._renderer3d = World3DRenderer(self.sim.world.width, self.sim.world.height)
        self._panel  = SidePanel(self._panel_rect, on_admin_cmd=self._handle_panel_admin_cmd)
        self._hud    = HUD(self._screen_w, self._screen_h, self.sim.world.width, self.sim.world.height)
        self._admin  = AdminBar(
            x=0,
            y=self._canvas_h,
            width=self._canvas_w,
            on_submit=self._handle_admin_command,
        )

        self.sim.event_bus.subscribe(self._panel.ingest_event)
        self._render_state = _build_render_state(self.sim)
        self._canvas.update_state(self._render_state)

        # Simulation thread
        self._running = True
        self._sim_thread = threading.Thread(target=self._sim_worker, daemon=True)
        self._sim_thread.start()

        self._clock = pygame.time.Clock()
        try:
            self._main_loop()
        finally:
            self._running = False
            self.sim.stop()
            if self._sim_thread and self._sim_thread.is_alive():
                self._sim_thread.join(timeout=2.0)
            pygame.quit()

    def _recalculate_layout(self) -> None:
        self._canvas_w = self._screen_w - SIDE_PANEL_W
        self._canvas_h = self._screen_h - ADMIN_BAR_H

        self._canvas_rect = pygame.Rect(0, 0, self._canvas_w, self._canvas_h)
        self._panel_rect  = pygame.Rect(self._canvas_w, 0, SIDE_PANEL_W, self._screen_h)
        self._admin_rect  = pygame.Rect(0, self._canvas_h, self._canvas_w, ADMIN_BAR_H)

    def _sim_worker(self) -> None:
        """Background simulation engine with smooth, human-watchable pacing."""
        total_ticks = 200 * 48
        ticks_done  = 0

        while self._running and ticks_done < total_ticks:
            if not self.sim.paused:
                self.sim.step()
                ticks_done += 1
            # Measured, watchable pacing (approx 0.85s per tick at 1.0x)
            sleep_s = max(0.005, BASE_TICK_SECS / max(0.1, self.sim.speed_multiplier))
            time.sleep(sleep_s)

        self._running = False

    def _main_loop(self) -> None:
        while self._running:
            dt = self._clock.tick(FPS_TARGET) / 1000.0

            # Render state snapshot
            self._render_state = _build_render_state(self.sim)
            self._canvas.update_state(self._render_state)
            self._panel.update_from_state(self._render_state, self._selected_id)

            # Camera follow mode
            if self._follow_mode and self._selected_id:
                agents = self._render_state.get("agents", {})
                a = agents.get(self._selected_id)
                if a and a.get("position"):
                    gx, gy = a["position"]
                    if self._view_3d:
                        self._renderer3d.target = (gx + 0.5, gy + 0.5)
                    else:
                        self._camera.center_on(gx + 0.5, gy + 0.5)

            self._handle_events()
            self._draw()
            pygame.display.flip()

    def _draw(self) -> None:
        screen = self._screen

        # 1. World Canvas
        canvas_surf = screen.subsurface(self._canvas_rect)
        canvas_surf.fill(BG_DARK)
        if self._view_3d:
            self._renderer3d.draw(canvas_surf, self._render_state, self._selected_id)
        else:
            self._canvas.draw(canvas_surf, self._camera)

        # 2. Concept Art HUD Overlays
        hud_surf = screen.subsurface(self._canvas_rect)
        selected_agent = self._render_state.get("agents", {}).get(self._selected_id) if self._selected_id else None
        hovered_agent = self._render_state.get("agents", {}).get(self._hovered_id) if self._hovered_id else None

        self._hud.draw(
            surface=hud_surf,
            state=self._render_state,
            camera=self._camera,
            paused=self.sim.paused,
            speed=self.sim.speed_multiplier,
            selected_agent=selected_agent,
            hovered_agent=hovered_agent,
            hovered_screen_pos=self._hovered_pos,
            on_speed_change=self._set_speed,
            on_toggle_pause=self._toggle_pause,
            on_open_admin=self._open_admin_panel,
        )

        # 3. Side Panel (Admin God Mode / Inspector / Census / Log)
        panel_surf = screen.subsurface(self._panel_rect)
        self._panel.draw(panel_surf)

        # 4. Bottom Admin Command Bar
        admin_surf = screen.subsurface(self._admin_rect)
        self._admin.draw(admin_surf)

        # 5. FPS & Audio Indicator
        fps = self._clock.get_fps()
        try:
            font = pygame.font.SysFont("segoeui", 10)
        except Exception:
            font = pygame.font.Font(None, 12)
        music_str = "[M] Muted" if sound_engine.is_muted else f"[M] Track: {sound_engine.TRACK_NAMES[sound_engine.current_track_idx]}"
        info_s = font.render(f"FPS {fps:.0f}  |  {music_str}", True, (100, 120, 160))
        screen.blit(info_s, (self._canvas_w - info_s.get_width() - 8, self._canvas_h - 18))

    def _set_speed(self, multiplier: float) -> None:
        self.sim.speed_multiplier = multiplier
        self.sim.paused = False
        sound_engine.play_sfx("footstep", 0.5)

    def _toggle_pause(self) -> None:
        self.sim.paused = not self.sim.paused
        sound_engine.play_sfx("footstep", 0.5)

    def _open_admin_panel(self) -> None:
        self._panel.active_tab = 0
        sound_engine.play_sfx("god_power", 0.7)

    def _handle_panel_admin_cmd(self, cmd: str, args: dict) -> str:
        try:
            res = self.sim.apply_admin_command(cmd, args)
            return str(res) if res else "OK"
        except Exception as e:
            return f"Error: {e}"

    def _handle_events(self) -> None:
        mouse_pos = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._running = False
                return

            if event.type == pygame.VIDEORESIZE:
                self._screen_w = max(900, event.w)
                self._screen_h = max(600, event.h)
                self._screen = pygame.display.set_mode((self._screen_w, self._screen_h), pygame.RESIZABLE)
                self._recalculate_layout()
                self._camera.resize(self._canvas_w, self._canvas_h)
                self._hud.resize(self._screen_w, self._screen_h)
                self._panel.rect = self._panel_rect
                self._admin.resize(0, self._canvas_h, self._canvas_w)
                continue

            # Admin bar handles text typing first
            if event.type == pygame.KEYDOWN:
                if self._admin.handle_event(event):
                    continue
                self._handle_keydown(event)
                continue

            # Zoom with wheel
            if event.type == pygame.MOUSEWHEEL:
                mx, my = mouse_pos
                if mx < self._canvas_w:
                    if self._view_3d:
                        self._renderer3d.zoom(event.y)
                    elif event.y > 0:
                        self._camera.zoom_in(mx, my)
                    else:
                        self._camera.zoom_out(mx, my)
                else:
                    self._panel.handle_scroll(-event.y * 3)
                continue

            # Mouse button down
            if event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos

                # Click in Side Panel
                if mx >= self._canvas_w:
                    self._panel.handle_click(mx - self._canvas_w, my)
                    continue

                # Click in Admin bottom bar
                if my >= self._canvas_h:
                    continue

                # Check HUD buttons (Top bar controls & Left navbar)
                if event.button == 1:
                    if self._hud.handle_click(mx, my):
                        continue

                # Middle click — pan
                if event.button == 2:
                    if self._view_3d:
                        self._renderer3d.begin_orbit(mx, my)
                    else:
                        self._camera.begin_drag(mx, my)
                    continue

                # Left click on canvas — select creature
                if event.button == 1:
                    hit = (self._renderer3d.agent_at(mx, my, (self._canvas_w, self._canvas_h),
                                                     self._render_state.get("agents", {}))
                           if self._view_3d else
                           self._canvas.agent_at_screen(mx, my, self._camera, self._render_state))
                    if hit:
                        self._selected_id = hit
                        self._canvas.selected_id = hit
                        self._panel.active_tab = 1  # Switch to INSPECT tab
                        sound_engine.play_sfx("chirp", 0.6)
                    else:
                        self._selected_id = None
                        self._canvas.selected_id = None
                    self._follow_mode = False
                    continue

                # Right click — coordinate info
                if event.button == 3:
                    if self._view_3d:
                        self._renderer3d.begin_orbit(mx, my)
                    else:
                        gx, gy = self._camera.screen_to_cell(mx, my)
                        self._admin.set_feedback(f"Grid sector: ({gx}, {gy})")
                    continue

            if event.type == pygame.MOUSEBUTTONUP:
                if event.button == 2 and not self._view_3d:
                    self._camera.end_drag()
                elif event.button in (2, 3) and self._view_3d:
                    self._renderer3d.end_orbit()
                continue

            # Mouse motion: drag pan & hover
            if event.type == pygame.MOUSEMOTION:
                mx, my = event.pos
                if self._camera.is_dragging():
                    self._camera.update_drag(mx, my)
                if self._view_3d and self._renderer3d.drag_origin is not None:
                    self._renderer3d.orbit(mx, my)

                if mx < self._canvas_w and my < self._canvas_h:
                    hit = (self._renderer3d.agent_at(mx, my, (self._canvas_w, self._canvas_h),
                                                     self._render_state.get("agents", {}))
                           if self._view_3d else
                           self._canvas.agent_at_screen(mx, my, self._camera, self._render_state))
                    self._hovered_id  = hit
                    self._hovered_pos = (mx, my) if hit else None
                    self._canvas.hovered_id  = hit
                else:
                    self._hovered_id  = None
                    self._hovered_pos = None

    def _handle_keydown(self, event: pygame.event.Event) -> None:
        key = event.key

        if key == pygame.K_SPACE:
            self._toggle_pause()

        elif key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
            self.sim.speed_multiplier = min(10.0, self.sim.speed_multiplier * 1.5)

        elif key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self.sim.speed_multiplier = max(0.1, self.sim.speed_multiplier / 1.5)

        elif key == pygame.K_m:
            sound_engine.toggle_mute()

        elif key == pygame.K_n:
            track = sound_engine.next_track()
            self._admin.set_feedback(f"Music: {track}")

        elif key == pygame.K_b:
            track = sound_engine.prev_track()
            self._admin.set_feedback(f"Music: {track}")

        elif key == pygame.K_1:
            self._panel.active_tab = 0  # ADMIN
        elif key == pygame.K_2:
            self._panel.active_tab = 1  # INSPECT
        elif key == pygame.K_3:
            self._panel.active_tab = 2  # CENSUS
        elif key == pygame.K_4:
            self._panel.active_tab = 3  # LOG

        elif key == pygame.K_r:
            self._camera.cell_px = 8.0
            self._camera.offset_x = (self.sim.world.width * 8.0 - self._canvas_w) / 2
            self._camera.offset_y = (self.sim.world.height * 8.0 - self._canvas_h) / 2

        elif key == pygame.K_f:
            if self._selected_id:
                self._follow_mode = not self._follow_mode

        elif key == pygame.K_v:
            self._view_3d = not self._view_3d
            self._admin.set_feedback("Perspective 3D view" if self._view_3d else "Isometric view")

        elif key == pygame.K_ESCAPE:
            self._selected_id = None
            self._canvas.selected_id = None
            self._follow_mode = False

        # WASD pan
        elif key in (pygame.K_w, pygame.K_s, pygame.K_a, pygame.K_d):
            direction = {pygame.K_w: (0, -1), pygame.K_s: (0, 1),
                         pygame.K_a: (-1, 0), pygame.K_d: (1, 0)}[key]
            selected = self._render_state.get("agents", {}).get(self._selected_id)
            if selected and selected.get("possessed"):
                x, y = selected["position"]
                gx = max(0, min(self.sim.world.width - 1, int(x) + direction[0] * 3))
                gy = max(0, min(self.sim.world.height - 1, int(y) + direction[1] * 3))
                self.sim.apply_admin_command("act", {"action": "MOVE", "possessing": self._selected_id,
                                                       "position": (gx, gy)})
            else:
                if self._view_3d:
                    if key == pygame.K_a:
                        self._renderer3d.yaw -= 0.12
                    elif key == pygame.K_d:
                        self._renderer3d.yaw += 0.12
                    elif key == pygame.K_w:
                        self._renderer3d.pitch = min(1.25, self._renderer3d.pitch + 0.06)
                    else:
                        self._renderer3d.pitch = max(0.22, self._renderer3d.pitch - 0.06)
                else:
                    delta = {pygame.K_w: (0, -35), pygame.K_s: (0, 35),
                             pygame.K_a: (-35, 0), pygame.K_d: (35, 0)}[key]
                    self._camera.pan(*delta)

    def _handle_admin_command(self, raw_cmd: str) -> str:
        cmd_lower = raw_cmd.strip().lower()

        if cmd_lower == "quit":
            self._running = False
            return "Quitting..."

        if cmd_lower == "pause":
            self.sim.paused = True
            return "Simulation paused"

        if cmd_lower == "resume":
            self.sim.paused = False
            return "Simulation resumed"

        try:
            result = _parse_and_dispatch(self.sim, raw_cmd)
            sound_engine.play_sfx("god_power")
            return result
        except Exception as e:
            return f"Error: {e}"
