"""
console.py — Interactive admin console using prompt_toolkit.

Uses patch_stdout so incoming event output doesn't break the input prompt.
Provides tab-completion for commands, species names, and creature names.
"""

from __future__ import annotations

import asyncio
import logging
import shlex
import sys
import threading
from typing import TYPE_CHECKING, Any

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.patch_stdout import patch_stdout

if TYPE_CHECKING:
    from prehistoric_sim.admin.commands import get_all_commands
    from prehistoric_sim.engine.simulation import Simulation
    from prehistoric_sim.ui.dashboard import Dashboard
    from prehistoric_sim.ui.renderer import EventRenderer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tab completer
# ---------------------------------------------------------------------------


class SimCompleter(Completer):
    """Provides tab-completion for sim commands, species names, and creature names."""

    def __init__(self, sim: "Simulation") -> None:
        self._sim = sim

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.lstrip()
        words = text.split()

        from prehistoric_sim.admin.commands import get_all_commands  # noqa: PLC0415
        all_cmds = get_all_commands()

        if not words:
            for cmd in all_cmds:
                yield Completion(cmd, start_position=0)
            return

        if len(words) == 1 and not text.endswith(" "):
            # Complete command name
            prefix = words[0]
            for cmd in all_cmds:
                if cmd.startswith(prefix):
                    yield Completion(cmd, start_position=-len(prefix))
            return

        # Complete second word: species names or creature names
        if len(words) >= 2 or text.endswith(" "):
            prefix2 = words[-1] if not text.endswith(" ") else ""
            # Species names
            for sp in self._sim.species_data.keys():
                if sp.startswith(prefix2):
                    yield Completion(sp, start_position=-len(prefix2))
            # Creature names
            for agent in self._sim.agents.values():
                n = agent.name or agent.display_id
                if n.lower().startswith(prefix2.lower()):
                    yield Completion(n, start_position=-len(prefix2))


# ---------------------------------------------------------------------------
# Command parser
# ---------------------------------------------------------------------------


def parse_command(raw: str) -> tuple[str, dict[str, Any]]:
    """Parse a raw command string into (command_name, args_dict).

    Handles: spawn tyrannosaurus_rex 3 x=10 y=20 --age JUVENILE --name Rex
    """
    try:
        tokens = shlex.split(raw.strip())
    except ValueError:
        tokens = raw.strip().split()

    if not tokens:
        return "", {}

    cmd = tokens[0].lower()
    args: dict[str, Any] = {}
    positional: list[str] = []
    i = 1

    while i < len(tokens):
        tok = tokens[i]
        if tok.startswith("--"):
            key = tok[2:]
            if i + 1 < len(tokens) and not tokens[i + 1].startswith("--"):
                args[key] = _coerce(tokens[i + 1])
                i += 2
            else:
                args[key] = True
                i += 1
        elif "=" in tok and not tok.startswith("-"):
            key, val = tok.split("=", 1)
            args[key] = _coerce(val)
            i += 1
        else:
            positional.append(tok)
            i += 1

    # Map positionals to known command patterns
    _map_positionals(cmd, positional, args)

    return cmd, args


def _coerce(val: str) -> Any:
    """Try to parse as int, then float, then return as string."""
    try:
        return int(val)
    except ValueError:
        pass
    try:
        return float(val)
    except ValueError:
        pass
    return val


def _map_positionals(cmd: str, positional: list[str], args: dict) -> None:
    """Map positional args to semantic names based on command."""
    if cmd == "spawn":
        if positional:
            args.setdefault("entity_type", positional[0])
        if len(positional) >= 2:
            args.setdefault("count", _coerce(positional[1]))
        if len(positional) >= 4:
            args.setdefault("x", _coerce(positional[2]))
            args.setdefault("y", _coerce(positional[3]))
    elif cmd in ("inspect", "kill", "heal", "injure", "feed", "water",
                 "track", "untrack", "name", "unname", "story", "possess",
                 "release", "age_up"):
        if positional:
            args.setdefault("target", positional[0])
        if cmd == "name" and len(positional) >= 2:
            args.setdefault("new_name", positional[1])
        if cmd == "age_up" and len(positional) >= 2:
            args.setdefault("amount", _coerce(positional[1]))
    elif cmd == "set":
        if len(positional) >= 1:
            args.setdefault("target", positional[0])
        if len(positional) >= 2:
            args.setdefault("field", positional[1])
        if len(positional) >= 3:
            args.setdefault("value", _coerce(positional[2]))
    elif cmd == "teleport":
        if positional:
            args.setdefault("target", positional[0])
        if len(positional) >= 3:
            args.setdefault("x", _coerce(positional[1]))
            args.setdefault("y", _coerce(positional[2]))
    elif cmd in ("find",):
        if positional:
            args.setdefault("name", positional[0])
    elif cmd == "list":
        if positional:
            args.setdefault("species", positional[0])
    elif cmd == "breed":
        if len(positional) >= 1:
            args.setdefault("target_a", positional[0])
        if len(positional) >= 2:
            args.setdefault("target_b", positional[1])
    elif cmd == "speed":
        if positional:
            args.setdefault("multiplier", _coerce(positional[0]))
    elif cmd == "step":
        if positional:
            args.setdefault("n", _coerce(positional[0]))
    elif cmd == "fastforward":
        if positional:
            args.setdefault("days", _coerce(positional[0]))
    elif cmd == "set_season":
        if positional:
            args.setdefault("season", positional[0])
    elif cmd == "set_weather":
        if positional:
            args.setdefault("weather", positional[0])
    elif cmd == "set_time":
        if len(positional) >= 1:
            args.setdefault("day", _coerce(positional[0]))
        if len(positional) >= 2:
            args.setdefault("hour", _coerce(positional[1]))
    elif cmd == "force":
        if positional:
            args.setdefault("target", positional[0])
        if len(positional) >= 2:
            args.setdefault("action", positional[1])
    elif cmd == "act":
        if positional:
            args.setdefault("action", positional[0])
    elif cmd in ("save", "load"):
        if positional:
            args.setdefault("filename", positional[0])
    elif cmd == "filter":
        if positional:
            args.setdefault("spec", " ".join(positional))
    elif cmd == "help":
        if positional:
            args.setdefault("command", positional[0])


# ---------------------------------------------------------------------------
# Console runner
# ---------------------------------------------------------------------------


class AdminConsole:
    """Interactive admin console that runs in the main thread.

    The simulation runs in a background thread. The console reads
    commands via prompt_toolkit with patch_stdout enabled so event
    output can interleave cleanly.
    """

    def __init__(
        self,
        sim: "Simulation",
        renderer: "EventRenderer",
        dashboard: "Dashboard",
        rich_console: Any,
    ) -> None:
        self._sim = sim
        self._renderer = renderer
        self._dashboard = dashboard
        self._console = rich_console
        self._quit = False

    def run_sync(self) -> None:
        """Run the console prompt loop synchronously (blocking)."""
        completer = SimCompleter(self._sim)
        session: PromptSession = PromptSession(
            completer=completer,
            complete_while_typing=True,
        )

        with patch_stdout():
            while not self._quit and self._sim._running:
                try:
                    raw = session.prompt("sim> ")
                except (EOFError, KeyboardInterrupt):
                    self._console.print("\n[dim]Interrupted. Type 'quit' to exit.[/dim]")
                    continue

                if not raw or not raw.strip():
                    continue

                cmd, args = parse_command(raw.strip())
                if not cmd:
                    continue

                result = self._sim.apply_admin_command(cmd, args)

                # Special results
                if result == "__QUIT__":
                    self._quit = True
                    self._sim.stop()
                    self._console.print("[bold yellow]Simulation stopped. Goodbye![/bold yellow]")
                    break
                elif result == "__DASHBOARD__":
                    self._dashboard.render(self._sim)
                elif result == "__MAP__":
                    self._dashboard.render_map(self._sim)
                elif result:
                    self._console.print(f"[dim cyan]{result}[/dim cyan]")
