"""
dashboard.py — Periodic world summary panels.

Prints a rich table showing population by species and stage,
plant biomass, weather, temperature, and recent birth/death counts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.table import Table
from rich.text import Text

from prehistoric_sim.ui.theme import Theme

if TYPE_CHECKING:
    from prehistoric_sim.engine.simulation import Simulation


class Dashboard:
    """Renders periodic world summary panels."""

    def __init__(self, console: Console, theme: Theme) -> None:
        self.console = console
        self.theme = theme
        self._last_births: int = 0
        self._last_deaths: int = 0

    def render(self, sim: "Simulation") -> None:
        """Print a full world summary panel."""
        world = sim.world
        self.console.print()
        self.console.rule(f"[bold bright_white]📊 WORLD SUMMARY — Day {world.day} | {world.season} | {world.temperature:.1f}°C | {world.weather.current.value}[/bold bright_white]")

        # Population table
        pop_table = Table(title="Population", show_header=True, header_style="bold cyan", box=None)
        pop_table.add_column("Species", style="bold", min_width=22)
        pop_table.add_column("Hatchling", justify="right")
        pop_table.add_column("Juvenile", justify="right")
        pop_table.add_column("Subadult", justify="right")
        pop_table.add_column("Adult", justify="right")
        pop_table.add_column("Senescent", justify="right")
        pop_table.add_column("Total", justify="right", style="bold")

        census = sim.census()
        for sp, stages in sorted(census.items()):
            color = self.theme.species_color(sp)
            glyph = self.theme.species_glyph(sp)
            sp_text = Text(f"{glyph} {sp}", style=f"bold {color}")
            pop_table.add_row(
                sp_text,
                str(stages.get("HATCHLING", 0)),
                str(stages.get("JUVENILE", 0)),
                str(stages.get("SUBADULT", 0)),
                str(stages.get("ADULT", 0)),
                str(stages.get("SENESCENT", 0)),
                str(sum(stages.values())),
            )

        total = len(sim.agents)
        pop_table.add_row(
            Text("TOTAL", style="bold white"), "", "", "", "", "", Text(str(total), style="bold white")
        )
        self.console.print(pop_table)

        # World stats
        import numpy as np  # noqa: PLC0415
        total_plant = float(np.sum(world.plant_biomass))
        max_plant = float(world.plant_biomass.size)
        plant_pct = total_plant / max(1.0, max_plant) * 100

        stats = Table(show_header=False, box=None)
        stats.add_column("Key", style="dim", min_width=20)
        stats.add_column("Value")
        stats.add_row("🌿 Plant biomass", f"{plant_pct:.1f}%")
        stats.add_row("☠️  Carcasses", str(len(sim.carcasses)))
        stats.add_row("🥚 Eggs", str(len(sim.eggs)))
        stats.add_row("🏕️  Nests", str(len(sim.nests)))
        stats.add_row("🔥 Fire cells", str(len(world.weather.fire_cells)))
        stats.add_row("🌊 Flood cells", str(len(world.weather.flood_cells)))
        stats.add_row("👥 Population", f"{total} / {sim.config.population_cap}")
        stats.add_row("🌡️  Temperature", f"{world.temperature:.1f}°C")
        stats.add_row("💨 Wind", f"{world.weather.wind_direction:.0f}° @ {world.weather.wind_speed:.2f}")

        self.console.print(stats)
        self.console.rule()
        self.console.print()

    def render_map(self, sim: "Simulation", radius: int = 30) -> None:
        """Render an ASCII mini-map centered on the world."""
        world = sim.world
        w, h = min(world.width, 60), min(world.height, 30)
        x0 = max(0, world.width // 2 - w // 2)
        y0 = max(0, world.height // 2 - h // 2)

        # Build agent position lookup
        agent_pos: dict[tuple[int, int], list] = {}
        for agent in sim.agents.values():
            pos = agent.position
            if pos not in agent_pos:
                agent_pos[pos] = []
            agent_pos[pos].append(agent)

        from prehistoric_sim.engine.entities import TerrainType  # noqa: PLC0415
        tv = list(TerrainType)

        lines: list[str] = []
        for y in range(y0, min(y0 + h, world.height)):
            row = ""
            for x in range(x0, min(x0 + w, world.width)):
                if (x, y) in agent_pos:
                    sp = agent_pos[(x, y)][0].species_key
                    row += self.theme.species_glyph(sp)
                else:
                    t = tv[world.terrain[y, x]]
                    row += self.theme.terrain_glyph(t.name)
            lines.append(row)

        map_text = "\n".join(lines)
        self.console.print(Panel(map_text, title="🗺️  World Map", border_style="bright_blue"))
