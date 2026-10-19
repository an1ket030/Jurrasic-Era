"""
admin_bar.py — Bottom admin command input bar.

A custom single-line text input with:
  • Command history (up/down arrows)
  • Blinking cursor
  • Autocomplete suggestions (tab)
  • Visual feedback: success (green flash), error (red flash)
"""

from __future__ import annotations

import time
from typing import Callable

import pygame

from prehistoric_sim.gui.colors import (
    BODY_TEXT,
    DIM_TEXT,
    HUD_ACCENT,
    HUD_DANGER,
    HUD_OK,
    HUD_WARNING,
    INPUT_BG,
    INPUT_BORDER,
    INPUT_CURSOR,
    PANEL_BORDER,
    TITLE_TEXT,
)

# All known admin commands (for autocomplete hints)
_ALL_COMMANDS = [
    "spawn", "kill", "starve", "heal", "injure",
    "possess", "unpossess", "act", "inspect", "name",
    "track", "untrack", "weather", "season", "fire",
    "flood", "pause", "resume", "speed", "step",
    "stats", "save", "load", "clear_carcasses", "help", "quit",
]

# Tab-completions for argument values
_ARG_COMPLETIONS: dict[str, list[str]] = {
    "spawn":   [
        "tyrannosaurus_rex", "dakotaraptor", "acheroraptor", "anzu_wyliei",
        "triceratops", "edmontosaurus", "ankylosaurus", "pachycephalosaurus",
        "thescelosaurus", "deinosuchus", "freshwater_fish", "freshwater_turtle",
        "quetzalcoatlus", "didelphodon", "insect_swarm",
    ],
    "weather": ["CLEAR", "RAIN", "STORM", "DROUGHT"],
    "season":  ["SPRING", "SUMMER", "AUTUMN", "WINTER"],
    "act":     [
        "HUNT", "FLEE", "FIGHT", "GRAZE", "DRINK", "EAT", "SCAVENGE",
        "WANDER", "REST", "SLEEP", "MATE", "GUARD_NEST", "MIGRATE",
    ],
}

BAR_HEIGHT = 34


class AdminBar:
    """Single-line admin command bar drawn at the bottom of the canvas."""

    def __init__(
        self,
        x: int,
        y: int,
        width: int,
        on_submit: Callable[[str], str],
    ) -> None:
        self.rect = pygame.Rect(x, y, width, BAR_HEIGHT)
        self._on_submit = on_submit

        self._text: str = ""
        self._cursor: int = 0
        self._history: list[str] = []
        self._history_idx: int = -1
        self._active: bool = True

        # Feedback flash
        self._feedback_msg:   str   = ""
        self._feedback_col:   tuple = HUD_OK
        self._feedback_until: float = 0.0

        # Blink state
        self._blink_on:  bool  = True
        self._blink_time: float = time.time()
        self._BLINK_RATE = 0.5

        # Autocomplete suggestion
        self._suggestion: str = ""

        # Font (lazy)
        self._font:       pygame.font.Font | None = None
        self._font_small: pygame.font.Font | None = None

    # ------------------------------------------------------------------
    # Resize
    # ------------------------------------------------------------------

    def resize(self, x: int, y: int, width: int) -> None:
        self.rect = pygame.Rect(x, y, width, BAR_HEIGHT)

    # ------------------------------------------------------------------
    # Draw
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        self._ensure_fonts()
        assert self._font and self._font_small
        r = self.rect

        # Background
        pygame.draw.rect(surface, INPUT_BG, r)
        border_col = INPUT_BORDER if self._active else PANEL_BORDER
        pygame.draw.rect(surface, border_col, r, 1)

        # Prompt
        prompt_col = HUD_ACCENT
        ps = self._font.render("> ", True, prompt_col)
        surface.blit(ps, (r.x + 6, r.y + 8))
        px_off = r.x + 6 + ps.get_width()

        # Input text
        ts = self._font.render(self._text, True, TITLE_TEXT)
        surface.blit(ts, (px_off, r.y + 8))

        # Blinking cursor
        now = time.time()
        if now - self._blink_time >= self._BLINK_RATE:
            self._blink_on = not self._blink_on
            self._blink_time = now
        if self._blink_on and self._active:
            cursor_x = px_off + self._font.size(self._text[:self._cursor])[0]
            pygame.draw.line(
                surface, INPUT_CURSOR,
                (cursor_x, r.y + 6),
                (cursor_x, r.y + r.h - 6),
                2,
            )

        # Autocomplete suggestion (dim)
        if self._suggestion and self._suggestion != self._text:
            rem = self._suggestion[len(self._text):]
            sug_s = self._font.render(rem, True, DIM_TEXT)
            sx = px_off + ts.get_width()
            surface.blit(sug_s, (sx, r.y + 8))

        # Feedback message
        if self._feedback_msg and time.time() < self._feedback_until:
            fs = self._font_small.render(self._feedback_msg[:60], True, self._feedback_col)
            surface.blit(fs, (r.x + r.w - fs.get_width() - 10, r.y + 10))

        # Keybind hints (very dim, far right when no feedback)
        elif not self._text:
            hint = "↑↓ history  Tab autocomplete  Enter submit"
            hs = self._font_small.render(hint, True, DIM_TEXT)
            surface.blit(hs, (r.x + r.w - hs.get_width() - 10, r.y + 10))

    # ------------------------------------------------------------------
    # Input event handling
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle a pygame key event. Returns True if consumed."""
        if event.type != pygame.KEYDOWN:
            return False

        key = event.key
        mod = event.mod

        if key == pygame.K_RETURN or key == pygame.K_KP_ENTER:
            self._submit()
            return True

        if key == pygame.K_BACKSPACE:
            if self._cursor > 0:
                self._text = self._text[:self._cursor - 1] + self._text[self._cursor:]
                self._cursor -= 1
                self._update_suggestion()
            return True

        if key == pygame.K_DELETE:
            if self._cursor < len(self._text):
                self._text = self._text[:self._cursor] + self._text[self._cursor + 1:]
                self._update_suggestion()
            return True

        if key == pygame.K_LEFT:
            self._cursor = max(0, self._cursor - 1)
            return True

        if key == pygame.K_RIGHT:
            if self._suggestion and self._cursor == len(self._text):
                # Accept suggestion
                self._text = self._suggestion
                self._cursor = len(self._text)
            else:
                self._cursor = min(len(self._text), self._cursor + 1)
            return True

        if key == pygame.K_TAB:
            self._do_autocomplete()
            return True

        if key == pygame.K_UP:
            if self._history:
                self._history_idx = min(len(self._history) - 1, self._history_idx + 1)
                self._text = self._history[-(self._history_idx + 1)]
                self._cursor = len(self._text)
                self._update_suggestion()
            return True

        if key == pygame.K_DOWN:
            if self._history_idx > 0:
                self._history_idx -= 1
                self._text = self._history[-(self._history_idx + 1)]
            else:
                self._history_idx = -1
                self._text = ""
            self._cursor = len(self._text)
            self._update_suggestion()
            return True

        if key == pygame.K_ESCAPE:
            self._text = ""
            self._cursor = 0
            self._suggestion = ""
            self._history_idx = -1
            return True

        if key == pygame.K_HOME:
            self._cursor = 0
            return True

        if key == pygame.K_END:
            self._cursor = len(self._text)
            return True

        # Printable characters
        char = event.unicode
        if char and char.isprintable():
            self._text = self._text[:self._cursor] + char + self._text[self._cursor:]
            self._cursor += 1
            self._update_suggestion()
            self._history_idx = -1
            return True

        return False

    # ------------------------------------------------------------------
    # Submit
    # ------------------------------------------------------------------

    def _submit(self) -> None:
        cmd = self._text.strip()
        if not cmd:
            return
        self._history.append(cmd)
        self._history_idx = -1
        self._text = ""
        self._cursor = 0
        self._suggestion = ""

        try:
            result = self._on_submit(cmd)
            self._set_feedback(f"✓ {result}", HUD_OK, 3.0)
        except Exception as e:
            self._set_feedback(f"✗ {e}", HUD_DANGER, 4.0)

    # ------------------------------------------------------------------
    # Autocomplete
    # ------------------------------------------------------------------

    def _update_suggestion(self) -> None:
        """Update the grey autocomplete suggestion."""
        parts = self._text.split()
        if not parts:
            self._suggestion = ""
            return

        if len(parts) == 1 and not self._text.endswith(" "):
            # Complete command name
            for cmd in _ALL_COMMANDS:
                if cmd.startswith(parts[0]) and cmd != parts[0]:
                    self._suggestion = cmd
                    return
        elif len(parts) >= 1:
            # Complete argument
            cmd = parts[0]
            completions = _ARG_COMPLETIONS.get(cmd, [])
            prefix = parts[-1] if not self._text.endswith(" ") else ""
            for opt in completions:
                if opt.lower().startswith(prefix.lower()) and opt != prefix:
                    base = " ".join(parts[:-1]) + (" " if parts else "") + opt
                    self._suggestion = base
                    return

        self._suggestion = ""

    def _do_autocomplete(self) -> None:
        """Accept the current suggestion."""
        if self._suggestion:
            self._text = self._suggestion + " "
            self._cursor = len(self._text)
            self._suggestion = ""
            self._update_suggestion()

    # ------------------------------------------------------------------
    # Feedback
    # ------------------------------------------------------------------

    def _set_feedback(self, msg: str, col: tuple, duration: float) -> None:
        self._feedback_msg = msg
        self._feedback_col = col
        self._feedback_until = time.time() + duration

    def set_feedback(self, msg: str, ok: bool = True) -> None:
        col = HUD_OK if ok else HUD_DANGER
        self._set_feedback(msg, col, 3.5)

    # ------------------------------------------------------------------
    # Lazy fonts
    # ------------------------------------------------------------------

    def _ensure_fonts(self) -> None:
        if self._font is None:
            try:
                self._font       = pygame.font.SysFont("consolas", 13)
                self._font_small = pygame.font.SysFont("segoeui", 11)
            except Exception:
                self._font       = pygame.font.Font(None, 15)
                self._font_small = pygame.font.Font(None, 13)
