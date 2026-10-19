"""
test_render_inspect.py — Offscreen render test for the INSPECT tab in the side panel.
"""

import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame
pygame.init()
pygame.mixer.init()

from prehistoric_sim.cli.main import _get_base_dirs
from prehistoric_sim.io.species_loader import load_all_species, load_world_config
from prehistoric_sim.engine.simulation import SimConfig, Simulation
from prehistoric_sim.gui.app import _build_render_state
from prehistoric_sim.gui.camera import Camera
from prehistoric_sim.gui.world_canvas import WorldCanvas
from prehistoric_sim.gui.hud import HUD
from prehistoric_sim.gui.side_panel import SidePanel

species_dir, plants_dir, worlds_dir, theme_path = _get_base_dirs()
species_data = load_all_species(species_dir)
world_cfg = load_world_config(worlds_dir, "hell_creek")

cfg = SimConfig(
    seed=42,
    world_width=world_cfg.get("width", 120),
    world_height=world_cfg.get("height", 120),
    days_per_season=world_cfg.get("days_per_season", 90),
    aging_scale=50.0,
    population_cap=world_cfg.get("population_cap", 1500),
    verbosity=0,
    world_name="hell_creek",
)

sim = Simulation(config=cfg, species_data=species_data, world_config=world_cfg)
sim.populate()

screen_w, screen_h = 1280, 800
canvas_w = screen_w - 340
canvas_h = screen_h - 34

screen = pygame.Surface((screen_w, screen_h))
camera = Camera(sim.world.width, sim.world.height, canvas_w, canvas_h)
camera.cell_px = 14.0
camera.center_on(60.5, 60.5)

canvas = WorldCanvas(sim.world.width, sim.world.height)
hud = HUD(screen_w, screen_h, sim.world.width, sim.world.height)
panel = SidePanel(pygame.Rect(canvas_w, 0, 340, screen_h))

render_state = _build_render_state(sim)
first_agent_id = list(render_state["agents"].keys())[0]
canvas.update_state(render_state)
canvas.selected_id = first_agent_id

# Switch panel to INSPECT tab (tab 1)
panel.update_from_state(render_state, first_agent_id)
panel.active_tab = 1

canvas_surf = screen.subsurface((0, 0, canvas_w, canvas_h))
canvas.draw(canvas_surf, camera)

hud.draw(
    surface=canvas_surf,
    state=render_state,
    camera=camera,
    paused=False,
    speed=1.0,
    selected_agent=render_state["agents"][first_agent_id],
)

panel_surf = screen.subsurface((canvas_w, 0, 340, screen_h))
panel.draw(panel_surf)

out_path = r"C:\Users\singh\.gemini\antigravity-ide\brain\da510531-330c-4887-bd6c-9952cb028815\new_jurassic_gui_inspect.png"
pygame.image.save(screen, out_path)
print(f"Inspect render test successful! Saved to {out_path}")
