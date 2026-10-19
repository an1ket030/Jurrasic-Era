"""
event_log.py — JSONL event logging and CSV summary writing.

Writes every engine event as a JSON line to outputs/<run_id>/events.jsonl.
Writes a command log for admin replay.
Produces a CSV population/birth/death summary at run end.
"""

from __future__ import annotations

import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from prehistoric_sim.engine.events import Event

logger = logging.getLogger(__name__)


class EventLogger:
    """Writes engine events to a JSONL file (unstyled, pure data)."""

    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        run_dir.mkdir(parents=True, exist_ok=True)
        self._events_path = run_dir / "events.jsonl"
        self._commands_path = run_dir / "commands.log"
        self._events_file = open(self._events_path, "w", encoding="utf-8")  # noqa: WPS515
        self._commands_file = open(self._commands_path, "w", encoding="utf-8")  # noqa: WPS515
        self._birth_count: int = 0
        self._death_count: int = 0
        self._death_causes: dict[str, int] = {}
        self._population_snapshots: list[dict] = []

    def log_event(self, event: Event) -> None:
        """Write a single event to the JSONL file."""
        record = {
            "tick": event.tick,
            "category": event.category.value,
            "subcategory": event.subcategory.value,
            "actors": event.actor_ids,
            "position": list(event.position) if event.position else None,
            "payload": event.payload,
        }
        try:
            self._events_file.write(json.dumps(record) + "\n")
        except Exception as e:
            logger.error("Failed to write event: %s", e)

        # Tally births/deaths
        from prehistoric_sim.engine.events import EventSubcategory  # noqa: PLC0415
        if event.subcategory == EventSubcategory.BIRTH:
            self._birth_count += 1
        elif event.subcategory == EventSubcategory.DEATH:
            self._death_count += 1
            cause = event.payload.get("cause", "unknown")
            self._death_causes[cause] = self._death_causes.get(cause, 0) + 1

    def log_command(self, tick: int, command: str, args: dict) -> None:
        """Write an admin command to the replay log."""
        record = {"tick": tick, "command": command, "args": args}
        self._commands_file.write(json.dumps(record) + "\n")

    def snapshot_population(self, tick: int, census: dict) -> None:
        """Record a population snapshot for the CSV summary."""
        row = {"tick": tick}
        for sp, stages in census.items():
            total = sum(stages.values())
            row[sp] = total
        self._population_snapshots.append(row)

    def write_summary(self, run_id: str, final_census: dict) -> None:
        """Write a CSV summary at the end of the run."""
        # Population summary
        pop_path = self.run_dir / "population.csv"
        if self._population_snapshots:
            all_keys = set()
            for row in self._population_snapshots:
                all_keys.update(row.keys())
            fieldnames = ["tick"] + sorted(all_keys - {"tick"})
            with open(pop_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(self._population_snapshots)

        # Summary stats
        summary_path = self.run_dir / "summary.json"
        summary = {
            "run_id": run_id,
            "total_births": self._birth_count,
            "total_deaths": self._death_count,
            "death_causes": self._death_causes,
            "final_census": final_census,
        }
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        logger.info("Summary written to %s", self.run_dir)

    def close(self) -> None:
        """Flush and close log files."""
        try:
            self._events_file.flush()
            self._events_file.close()
            self._commands_file.flush()
            self._commands_file.close()
        except Exception:
            pass

    def __del__(self) -> None:
        self.close()
