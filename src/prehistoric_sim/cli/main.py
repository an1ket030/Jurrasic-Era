"""
main.py — CLI entry point for prehistoric-sim.

Commands:
- sim run: Start live simulation with interactive admin console
- sim replay: Replay recorded admin commands deterministically
- sim species list: List all defined species and traits
- sim species validate: Validate all YAML data files
- sim docs: Show planning documents and project paths
"""

from __future__ import annotations

import json
import logging
import sys
import threading
import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from prehistoric_sim.admin.console import AdminConsole
from prehistoric_sim.engine.simulation import SimConfig, Simulation
from prehistoric_sim.io.event_log import EventLogger
from prehistoric_sim.io.plant_loader import load_all_plants, validate_plant
from prehistoric_sim.io.species_loader import (
    SpeciesValidationError,
    load_all_species,
    load_species_file,
    load_world_config,
)
from prehistoric_sim.ui.dashboard import Dashboard
from prehistoric_sim.ui.renderer import EventRenderer
from prehistoric_sim.ui.theme import Theme

app = typer.Typer(
    name="sim",
    help="Prehistoric Ecosystem Simulation — Hell Creek (~67 Ma)",
    add_completion=False,
)
species_app = typer.Typer(name="species", help="Manage and inspect species definitions")
app.add_typer(species_app, name="species")

if sys.platform == "win32":
    try:
        if sys.stdout and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if sys.stderr and hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

console = Console()
logger = logging.getLogger("prehistoric_sim")


def _get_base_dirs() -> tuple[Path, Path, Path, Path]:
    """Find data, docs, outputs root directories."""
    # Find repository root from current working dir or package location
    cwd = Path.cwd()
    if (cwd / "data").exists():
        base = cwd
    else:
        base = Path(__file__).resolve().parent.parent.parent.parent

    species_dir = base / "data" / "species"
    plants_dir = base / "data" / "plants"
    worlds_dir = base / "data" / "worlds"
    theme_path = base / "data" / "theme.yaml"
    return species_dir, plants_dir, worlds_dir, theme_path


@app.command("gui")
def gui_cmd(
    world: str = typer.Option("hell_creek", "--world", "-w", help="World configuration name"),
    seed: int = typer.Option(42, "--seed", "-s", help="Random number generator seed"),
    days: int = typer.Option(200, "--days", "-d", help="Total simulation days to run"),
    aging_scale: float = typer.Option(50.0, "--aging-scale", help="Aging speed multiplier"),
    speed: float = typer.Option(1.0, "--speed", help="Initial simulation speed multiplier"),
    empty: bool = typer.Option(False, "--empty", help="Start with an empty world"),
    load: Optional[Path] = typer.Option(None, "--load", "-l", help="Load world state from snapshot JSON"),
    verbosity: int = typer.Option(2, "--verbosity", "-v", help="Engine verbosity 0-3"),
) -> None:
    """Launch the Phase 2 Pygame GUI — real-time interactive world viewport."""
    import json  # noqa: PLC0415

    species_dir, plants_dir, worlds_dir, theme_path = _get_base_dirs()
    species_data = load_all_species(species_dir)
    world_cfg = load_world_config(worlds_dir, world)

    if not species_data:
        console.print(f"[bold red]Error: No species found in {species_dir}[/bold red]")
        raise typer.Exit(1)

    cfg = SimConfig(
        seed=seed,
        world_width=world_cfg.get("width", 120),
        world_height=world_cfg.get("height", 120),
        days_per_season=world_cfg.get("days_per_season", 90),
        aging_scale=aging_scale,
        population_cap=world_cfg.get("population_cap", 1500),
        verbosity=verbosity,
        world_name=world,
    )

    sim = Simulation(config=cfg, species_data=species_data, world_config=world_cfg)
    sim.speed_multiplier = speed

    if load and load.exists():
        console.print(f"[dim]Loading snapshot from {load}...[/dim]")
        with open(load, encoding="utf-8") as f:
            snap_state = json.load(f)
        sim.set_state(snap_state)
    elif not empty:
        sim.populate()

    console.print(
        f"[bold bright_green]Launching JurassicEra GUI[/bold bright_green] — "
        f"World: [cyan]{world}[/cyan] | Seed: [cyan]{seed}[/cyan] | "
        f"Pop: [cyan]{len(sim.agents)}[/cyan]"
    )
    console.print("[dim]Close the window or type 'quit' in the admin bar to exit.[/dim]")

    try:
        from prehistoric_sim.gui.app import GuiApp  # noqa: PLC0415
        app_instance = GuiApp(sim, title=f"JurassicEra — {world} (seed={seed})")
        app_instance.run()
    except ImportError as e:
        console.print(f"[bold red]Pygame not installed: {e}[/bold red]")
        console.print("[yellow]Run:  pip install pygame pygame-gui[/yellow]")
        raise typer.Exit(1)


@app.command("run")
def run_cmd(
    world: str = typer.Option("hell_creek", "--world", "-w", help="World configuration name"),
    seed: int = typer.Option(42, "--seed", "-s", help="Random number generator seed"),
    days: int = typer.Option(200, "--days", "-d", help="Total simulation days to run"),
    verbosity: int = typer.Option(2, "--verbosity", "-v", help="Verbosity level 0-3"),
    aging_scale: float = typer.Option(50.0, "--aging-scale", help="Aging speed multiplier"),
    empty: bool = typer.Option(False, "--empty", help="Start with an empty world (spawn manually)"),
    load: Optional[Path] = typer.Option(None, "--load", "-l", help="Load world state from snapshot JSON"),
    speed: float = typer.Option(1.0, "--speed", help="Initial simulation speed multiplier"),
    auto_name: bool = typer.Option(False, "--auto-name", help="Automatically assign names to newborns"),
    ascii_glyphs: bool = typer.Option(False, "--ascii-glyphs", help="Use plain ASCII glyphs fallback"),
    no_color: bool = typer.Option(False, "--no-color", help="Disable ANSI color styling"),
    batch: bool = typer.Option(False, "--batch", help="Non-interactive headless batch run"),
) -> None:
    """Start the prehistoric ecosystem simulation."""
    rich_console = Console(no_color=no_color)
    species_dir, plants_dir, worlds_dir, theme_path = _get_base_dirs()

    # Load data
    species_data = load_all_species(species_dir)
    world_cfg = load_world_config(worlds_dir, world)

    if not species_data:
        rich_console.print(f"[bold red]Error: No species found in {species_dir}[/bold red]")
        raise typer.Exit(1)

    # Initialize configuration
    cfg = SimConfig(
        seed=seed,
        world_width=world_cfg.get("width", 120),
        world_height=world_cfg.get("height", 120),
        days_per_season=world_cfg.get("days_per_season", 90),
        aging_scale=aging_scale,
        population_cap=world_cfg.get("population_cap", 1500),
        verbosity=verbosity,
        auto_name=auto_name,
        ascii_glyphs=ascii_glyphs,
        no_color=no_color,
        world_name=world,
    )

    sim = Simulation(config=cfg, species_data=species_data, world_config=world_cfg)
    sim.speed_multiplier = speed

    # Snapshot load or populate
    if load and load.exists():
        rich_console.print(f"[dim]Loading snapshot from {load}...[/dim]")
        with open(load, encoding="utf-8") as f:
            snap_state = json.load(f)
        sim.set_state(snap_state)
    elif not empty:
        sim.populate()

    # UI Theme and components
    theme = Theme(theme_path=theme_path, ascii_glyphs=ascii_glyphs, no_color=no_color)
    renderer = EventRenderer(
        console=rich_console,
        theme=theme,
        verbosity=verbosity,
        world_ref=sim.world,
    )
    renderer.subscribe(sim.event_bus)
    dashboard = Dashboard(console=rich_console, theme=theme)

    # Output logging
    run_id = f"run_{int(time.time())}_s{seed}"
    run_dir = Path.cwd() / "outputs" / run_id
    event_logger = EventLogger(run_dir)
    sim.event_bus.subscribe(event_logger.log_event)

    total_ticks = days * 48

    # Banner
    rich_console.print(Panel(
        f"[bold bright_green]PREHISTORIC ECOSYSTEM SIMULATION[/bold bright_green]\n"
        f"[dim]World:[/dim] [cyan]{world}[/cyan] | [dim]Seed:[/dim] [cyan]{seed}[/cyan] | "
        f"[dim]Days:[/dim] [cyan]{days}[/cyan] | [dim]Aging Scale:[/dim] [cyan]{aging_scale}[/cyan] | "
        f"[dim]Initial Population:[/dim] [cyan]{len(sim.agents)}[/cyan]\n"
        f"[dim]Log Directory:[/dim] {run_dir}",
        border_style="bright_blue",
    ))

    if batch:
        rich_console.print(f"[yellow]Running in batch mode for {total_ticks} ticks...[/yellow]")
        sim.run(total_ticks)
        dashboard.render(sim)
        event_logger.write_summary(run_id, sim.census())
        rich_console.print(f"[green]Batch run complete! Results saved in {run_dir}[/green]")
        return

    # Interactive Console mode
    sim._running = True

    def sim_worker() -> None:
        ticks_done = 0
        last_day = sim.world.day
        while sim._running and ticks_done < total_ticks:
            if not sim.paused:
                sim.step()
                ticks_done += 1
                # Daily dashboard trigger
                if sim.world.day != last_day:
                    last_day = sim.world.day
                    dashboard.render(sim)
                    event_logger.snapshot_population(sim.tick, sim.census())

            # Adjust sleep according to speed multiplier
            sleep_time = max(0.001, 0.05 / sim.speed_multiplier)
            time.sleep(sleep_time)

        sim._running = False

    sim_thread = threading.Thread(target=sim_worker, daemon=True)
    sim_thread.start()

    # Interactive Prompt
    admin_console = AdminConsole(sim, renderer, dashboard, rich_console)
    try:
        admin_console.run_sync()
    finally:
        sim.stop()
        if sim_thread.is_alive():
            sim_thread.join(timeout=1.0)
        event_logger.write_summary(run_id, sim.census())
        rich_console.print(f"[dim]Saved session summary to {run_dir}[/dim]")


@app.command("replay")
def replay_cmd(
    commands_file: Path = typer.Argument(..., help="Path to commands.log or recorded replay file"),
    speed: float = typer.Option(5.0, "--speed", help="Playback speed multiplier"),
) -> None:
    """Replay an admin command log deterministically."""
    if not commands_file.exists():
        console.print(f"[bold red]Command log file not found: {commands_file}[/bold red]")
        raise typer.Exit(1)

    species_dir, plants_dir, worlds_dir, theme_path = _get_base_dirs()
    species_data = load_all_species(species_dir)
    world_cfg = load_world_config(worlds_dir, "hell_creek")

    # Parse commands
    commands: list[dict] = []
    with open(commands_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                commands.append(json.loads(line))

    cfg = SimConfig(seed=42)
    sim = Simulation(config=cfg, species_data=species_data, world_config=world_cfg)
    sim.populate()

    theme = Theme(theme_path=theme_path)
    renderer = EventRenderer(console=console, theme=theme, verbosity=2, world_ref=sim.world)
    renderer.subscribe(sim.event_bus)

    console.print(f"[bold green]Replaying {len(commands)} admin commands from {commands_file}...[/bold green]")
    cmd_idx = 0
    while cmd_idx < len(commands):
        target_tick = commands[cmd_idx]["tick"]
        while sim.tick < target_tick:
            sim.step()
        cmd = commands[cmd_idx]["command"]
        args = commands[cmd_idx]["args"]
        console.print(f"[bold yellow]Replay at tick {sim.tick}: {cmd} {args}[/bold yellow]")
        sim.apply_admin_command(cmd, args)
        cmd_idx += 1

    console.print("[bold green]Replay completed successfully![/bold green]")


@species_app.command("list")
def species_list_cmd() -> None:
    """List all available species in the data catalog."""
    species_dir, _, _, _ = _get_base_dirs()
    species = load_all_species(species_dir)

    table = Table(title="Late Cretaceous Species Roster (Hell Creek)", show_header=True, header_style="bold cyan")
    table.add_column("Key", style="bold")
    table.add_column("Common Name")
    table.add_column("Scientific Name", style="italic")
    table.add_column("Diet")
    table.add_column("Mass (kg)", justify="right")
    table.add_column("Lifespan (yr)", justify="right")
    table.add_column("Activity")

    for key, sp in sorted(species.items()):
        table.add_row(
            key,
            sp.get("common_name", ""),
            sp.get("scientific_name", ""),
            sp.get("diet", ""),
            f"{sp.get('body_mass_kg', 0):,.1f}",
            f"{sp.get('lifespan_years', 0):.1f}",
            sp.get("activity_pattern", ""),
        )

    console.print(table)


@species_app.command("validate")
def species_validate_cmd() -> None:
    """Validate all species and plant YAML files."""
    species_dir, plants_dir, _, _ = _get_base_dirs()

    species_files = sorted(species_dir.glob("*.yaml"))
    plant_files = sorted(plants_dir.glob("*.yaml"))

    console.print(f"\n[bold]Validating {len(species_files)} species and {len(plant_files)} plant files...[/bold]\n")

    errors = 0
    for sf in species_files:
        try:
            load_species_file(sf)
            console.print(f"  [bold green][OK][/bold green] Species: [cyan]{sf.stem}[/cyan]")
        except Exception as e:
            errors += 1
            console.print(f"  [bold red][FAIL][/bold red] Species: {sf.name} -> {e}")

    for pf in plant_files:
        try:
            with open(pf, encoding="utf-8") as f:
                import yaml  # noqa: PLC0415
                data = yaml.safe_load(f)
            validate_plant(data, str(pf))
            console.print(f"  [bold green][OK][/bold green] Plant:   [green]{pf.stem}[/green]")
        except Exception as e:
            errors += 1
            console.print(f"  [bold red][FAIL][/bold red] Plant: {pf.name} -> {e}")

    if errors == 0:
        console.print(f"\n[bold bright_green]All {len(species_files) + len(plant_files)} data files passed validation![/bold bright_green]\n")
    else:
        console.print(f"\n[bold red]Validation failed with {errors} error(s)![/bold red]\n")
        raise typer.Exit(1)


@app.command("docs")
def docs_cmd() -> None:
    """Print documentation files and project design resources."""
    base = Path.cwd()
    docs = [
        ("WORLD_ELEMENTS.md", "Catalogue of living & non-living elements, interactions, terrain, and hazards"),
        ("SPECIES_CHECKLIST.md", "Checklist of animals, plants, and roles in the ecosystem"),
        ("PHASE1_CHECKLIST.md", "Living task breakdown and status tracking for Phase 1"),
        ("DESIGN.md", "Architecture, utility AI decision formulas, and design patterns"),
        ("README.md", "User manual, CLI commands, and admin reference"),
    ]

    table = Table(title="Project Documentation & Specifications", show_header=True, header_style="bold magenta")
    table.add_column("Document", style="bold")
    table.add_column("Path", style="dim")
    table.add_column("Description")

    for name, desc in docs:
        p = base / "docs" / name if name.endswith("_CHECKLIST.md") or name == "WORLD_ELEMENTS.md" else base / name
        status = "[green]exists[/green]" if p.exists() else "[red]missing[/red]"
        table.add_row(f"{name} ({status})", str(p), desc)

    console.print(table)


if __name__ == "__main__":
    app()
