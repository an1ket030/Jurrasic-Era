"""
renderer.py — Converts engine events into styled rich terminal output.

Subscribes to the EventBus and formats each event with color, glyphs,
and layout defined by the theme. Never imports engine internals.
The engine layer is strictly isolated: renderer only sees Event objects.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.style import Style
from rich.text import Text

from prehistoric_sim.engine.events import (
    Event,
    EventBus,
    EventCategory,
    EventSubcategory,
)
from prehistoric_sim.ui.theme import Theme

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class EventRenderer:
    """Subscribes to the event bus and prints styled output to the console.

    Each event category/subcategory has its own color scheme and glyph
    defined in the Theme. Major events get panel banners.
    All timestamp prefixes use the format: D12 06:30 Spring
    """

    def __init__(
        self,
        console: Console,
        theme: Theme,
        verbosity: int = 2,
        world_ref: Any = None,  # weak reference to World for timestamps
    ) -> None:
        self.console = console
        self.theme = theme
        self.verbosity = verbosity
        self._world = world_ref

        # Category filter (None = show all)
        self._show_categories: set[str] | None = None
        self._show_species: str | None = None
        self._follow_id: str | None = None

        # Verbosity levels:
        # 0 = only major events (deaths of large animals, disasters, extinctions)
        # 1 = + life events (births, deaths, hatching, season change, weather)
        # 2 = + interactions (hunts, fights, drinking, eating)
        # 3 = + every decision change and perception tick

    def subscribe(self, bus: EventBus) -> None:
        """Register this renderer as a wildcard subscriber."""
        bus.subscribe(self.handle_event)

    def handle_event(self, event: Event) -> None:
        """Receive an event and render it."""
        # Filter checks
        if not self._should_display(event):
            return
        try:
            self._render(event)
        except Exception as e:
            logger.debug("Render error for %s: %s", event.subcategory, e)

    def _should_display(self, event: Event) -> bool:
        # Category filter
        cat_key = f"{event.category.value}_{event.subcategory.value}"
        if self._show_categories and cat_key not in self._show_categories:
            return False

        # Species filter
        if self._show_species:
            sp = event.payload.get("species", "") or event.payload.get("pred_species", "")
            if self._show_species not in (sp, event.payload.get("prey_species", "")):
                return False

        # Follow filter
        if self._follow_id and self._follow_id not in event.actor_ids:
            return False

        # Verbosity gating
        cat = event.category
        sub = event.subcategory

        if self.verbosity == 0:
            # Only disasters, extinctions, major deaths
            return sub in (
                EventSubcategory.DEATH, EventSubcategory.SPECIES_EXTINCT,
                EventSubcategory.WEATHER_START, EventSubcategory.FIRE_SPREAD,
                EventSubcategory.FLOOD_EXPAND, EventSubcategory.ADMIN_COMMAND,
                EventSubcategory.POP_CAP, EventSubcategory.SEASON_CHANGE,
            )
        elif self.verbosity == 1:
            return cat in (EventCategory.LIFECYCLE, EventCategory.WORLD, EventCategory.ADMIN, EventCategory.SYSTEM)
        elif self.verbosity == 2:
            return sub != EventSubcategory.ACTION_TICK
        else:
            return True  # verbosity 3: show everything

    def _render(self, event: Event) -> None:
        """Route event to the appropriate formatter."""
        sub = event.subcategory
        cat = event.category

        cat_key = f"{cat.value}_{sub.value}"
        style_str = self.theme.category_style(cat_key)
        glyph = self.theme.category_glyph(cat_key)
        ts = self._timestamp(event)

        # Major events get special treatment
        if sub in (EventSubcategory.DEATH, EventSubcategory.SPECIES_EXTINCT):
            self._render_death(event, ts, glyph, style_str)
            return
        if sub in (EventSubcategory.SEASON_CHANGE, EventSubcategory.WEATHER_START, EventSubcategory.FIRE_SPREAD, EventSubcategory.FLOOD_EXPAND):
            self._render_world_banner(event, ts, glyph, style_str)
            return
        if sub == EventSubcategory.ADMIN_COMMAND:
            self._render_admin(event, ts, glyph, style_str)
            return
        if sub == EventSubcategory.POP_CAP:
            self._render_banner(event, ts, glyph, style_str)
            return

        # Standard line
        msg = self._format_event(event)
        if not msg:
            return
        name_part = self._actor_styled(event)
        line = Text()
        line.append(f"{ts} ", style="dim")
        line.append(f"{glyph} ", style=style_str)
        line.append(name_part)
        line.append(msg, style=style_str)
        self.console.print(line)

    def _timestamp(self, event: Event) -> str:
        """Format: D12 06:30 Spring (uses world_ref if available)."""
        w = self._world
        if w is None:
            return f"T{event.tick}"
        day = getattr(w, "day", 0)
        h = getattr(w, "hour_of_day", 0.0)
        season = getattr(w, "season", "?")
        hour_str = f"{int(h):02d}:{int((h % 1) * 60):02d}"
        return f"D{day:04d} {hour_str} {season[:3]}"

    def _actor_styled(self, event: Event) -> Text:
        """Return styled actor name(s) from the event payload."""
        t = Text()
        sp = event.payload.get("species", "")
        name = event.payload.get("name", "") or (event.actor_ids[0] if event.actor_ids else "")
        if sp:
            color = self.theme.species_color(sp)
            t.append(name or sp, style=f"bold {color}")
            t.append(" ", style="default")
        return t

    def _format_event(self, event: Event) -> str:
        """Format the textual description of an event."""
        sub = event.subcategory
        p = event.payload

        # Lifecycle
        if sub == EventSubcategory.BIRTH:
            stage = p.get("life_stage", "")
            spawned = "(admin)" if p.get("admin_spawned") else ""
            return f"was born {spawned} [stage: {stage}]"
        if sub == EventSubcategory.STAGE_CHANGE:
            return f"grew from {p.get('old_stage')} → {p.get('new_stage')}"
        if sub == EventSubcategory.EGG_LAID:
            return f"laid a clutch of {p.get('clutch_size', '?')} eggs"
        if sub == EventSubcategory.NEST_BUILT:
            return f"built a nest at {p.get('nest_id', '')[:8]}"
        if sub == EventSubcategory.HATCHING:
            return f"hatched! (from clutch {p.get('clutch_id','')[:8]})"
        if sub == EventSubcategory.MATING:
            return f"mated with {p.get('partner_b') or p.get('partner_a', '?')}"
        if sub == EventSubcategory.PARENTING:
            return f"is {p.get('action','tending to')} offspring"
        if sub == EventSubcategory.CARCASS_FORMED:
            return f"→ carcass ({p.get('mass_kg', 0):.0f} kg)"
        if sub == EventSubcategory.CARCASS_DECAYED:
            return f"carcass fully decomposed (+{p.get('nutrients_released', 0):.3f} nutrients)"

        # Decision
        if sub == EventSubcategory.ACTION_CHANGE:
            alts = p.get("alternatives", [])
            alt_str = " | ".join(f"{a[0]} ({a[1]:.2f})" for a in alts[:2])
            old = p.get("old_action", "?")
            new = p.get("new_action", "?")
            score = p.get("score", 0.0)
            reason = p.get("reason", "")
            alt_part = f" over {alt_str}" if alt_str else ""
            return f"chose {new} ({score:.2f}){alt_part}: {reason}"
        if sub == EventSubcategory.ACTION_TICK:
            d = p.get("drives", {})
            return f"[{p.get('action')}] H:{d.get('hunger',0):.2f} T:{d.get('thirst',0):.2f} F:{d.get('fear',0):.2f}"

        # Interactions
        if sub == EventSubcategory.CHASE:
            return f"is chasing {p.get('prey','?')} (p={p.get('success_prob',0):.2f})"
        if sub == EventSubcategory.STALK:
            return f"stalking {p.get('prey','?')}"
        if sub == EventSubcategory.HUNT_SUCCESS:
            return f"killed {p.get('prey','?')}! +{p.get('energy_gained',0):.2f} energy"
        if sub == EventSubcategory.HUNT_FAIL:
            return f"hunt failed ({p.get('reason','?')})"
        if sub == EventSubcategory.FIGHT:
            return f"fighting {p.get('defender','?')} [{p.get('fight_type','?')}]"
        if sub == EventSubcategory.FLEE:
            return "is fleeing!"
        if sub == EventSubcategory.ALARM_CALL:
            return "sounds an alarm call!"
        if sub == EventSubcategory.HERD_FORM:
            return f"joins a herd of {p.get('size','?')}"
        if sub == EventSubcategory.SCAVENGE:
            return f"approaches carcass {p.get('target_id','')[:8]}"
        if sub == EventSubcategory.EAT:
            return f"eating ({p.get('amount_kg',0):.1f} kg)"
        if sub == EventSubcategory.DRINK:
            return "drinks"
        if sub == EventSubcategory.SLEEP:
            return "sleeps"
        if sub == EventSubcategory.MATE_DISPLAY:
            return f"displays to {p.get('partner','?')}"
        if sub == EventSubcategory.INJURY:
            return f"injured by {p.get('attacker','?')} [{p.get('type','?')}] ({p.get('injury',0):.2f})"
        if sub == EventSubcategory.HEAL:
            return "recovering from injury"

        # World
        if sub == EventSubcategory.DAWN:
            return f"Day {p.get('day','?')} begins. {p.get('season','?')} — {p.get('temperature','?')}°C"
        if sub == EventSubcategory.DUSK:
            return "night falls"
        if sub == EventSubcategory.DAY_START:
            return f"Day {p.get('day','?')} — {p.get('season','?')}"
        if sub == EventSubcategory.WATER_LEVEL:
            return f"water level changed: {p.get('delta',0):+.1f}"
        if sub == EventSubcategory.NUTRIENT_BOOST:
            return f"nutrients boosted at {p.get('position','?')}"

        # System
        if sub == EventSubcategory.SNAPSHOT_SAVED:
            return f"Snapshot saved: {p.get('path','?')}"
        if sub == EventSubcategory.SNAPSHOT_LOADED:
            return f"Snapshot loaded: {p.get('path','?')}"

        return ""

    def _render_death(self, event: Event, ts: str, glyph: str, style_str: str) -> None:
        p = event.payload
        sp = p.get("species", "")
        name = p.get("name", event.actor_ids[0] if event.actor_ids else "?")
        cause = p.get("cause", "unknown")
        stage = p.get("life_stage", "?")
        age = p.get("age_ticks", 0)

        color = self.theme.species_color(sp)
        is_large = any(big in sp for big in ("tyrannosaurus", "triceratops", "ankylosaurus", "edmontosaurus"))

        if event.subcategory == EventSubcategory.SPECIES_EXTINCT:
            self.console.print(Rule(f"[bold red]⚠ EXTINCTION: {sp} has vanished from the world ⚠[/bold red]"))
            return

        if is_large:
            text = f"[bold {color}]{name}[/bold {color}] [{sp}] has died — cause: {cause} | age: {age} ticks | stage: {stage}"
            self.console.print(Panel(text, style="red", title=f"{glyph} DEATH"))
        else:
            line = Text()
            line.append(f"{ts} ", style="dim")
            line.append(f"{glyph} ", style="bold red")
            line.append(name, style=f"bold {color}")
            line.append(f" [{sp}] died — {cause} (stage: {stage})", style="red")
            self.console.print(line)

    def _render_world_banner(self, event: Event, ts: str, glyph: str, style_str: str) -> None:
        p = event.payload
        sub = event.subcategory

        if sub == EventSubcategory.SEASON_CHANGE:
            msg = f"Season changed: {p.get('old_season')} → {p.get('new_season')}"
            self.console.print(Rule(f"[bold bright_magenta]{glyph} {msg}[/bold bright_magenta]"))
        elif sub == EventSubcategory.FIRE_SPREAD:
            if p.get("ignition"):
                msg = f"⚡ Lightning strike at {event.position}! WILDFIRE STARTS!"
            else:
                msg = f"🔥 Fire spreading at {event.position}"
            self.console.print(Rule(f"[bold red on dark_orange3]{msg}[/bold red on dark_orange3]"))
        elif sub == EventSubcategory.FLOOD_EXPAND:
            msg = f"🌊 Flood expanding! {p.get('cells_flooded', 0)} cells inundated"
            self.console.print(Rule(f"[bold blue]{msg}[/bold blue]"))
        elif sub == EventSubcategory.WEATHER_START:
            weather = p.get("weather", "?")
            dur = p.get("duration_ticks", 0)
            msg = f"{glyph} {weather} begins (duration: {dur} ticks)"
            self.console.print(Rule(f"[bold blue]{msg}[/bold blue]"))

    def _render_admin(self, event: Event, ts: str, glyph: str, style_str: str) -> None:
        p = event.payload
        cmd = p.get("command", "?")
        result = p.get("result", "")
        line = Text()
        line.append(f"{ts} ", style="dim")
        line.append(f"{glyph} [ADMIN] ", style="bold yellow reverse")
        line.append(f"{cmd}: {result}", style="yellow")
        self.console.print(line)

    def _render_banner(self, event: Event, ts: str, glyph: str, style_str: str) -> None:
        sub = event.subcategory
        p = event.payload
        if sub == EventSubcategory.POP_CAP:
            self.console.print(Rule(
                f"[bold red on white]{glyph} POPULATION CAP REACHED: {p.get('current')}/{p.get('cap')} agents[/bold red on white]"
            ))

    # ------------------------------------------------------------------
    # Filter control
    # ------------------------------------------------------------------

    def set_verbosity(self, level: int) -> None:
        self.verbosity = max(0, min(3, level))

    def set_category_filter(self, categories: list[str] | None) -> None:
        self._show_categories = set(categories) if categories else None

    def set_species_filter(self, species: str | None) -> None:
        self._show_species = species

    def set_follow(self, entity_id: str | None) -> None:
        self._follow_id = entity_id
