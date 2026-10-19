"""
camera.py — Pan / zoom camera for the world canvas.

Maps world-grid coordinates to screen pixel coordinates.
Supports smooth clamped panning and zoom levels.
"""

from __future__ import annotations

import math


class Camera:
    """2D orthographic camera over the 120×120 simulation grid.

    Attributes:
        world_w / world_h  — grid dimensions in cells
        screen_w / screen_h — viewport pixel dimensions
        cell_px             — current pixels-per-cell (zoom)
        offset_x / offset_y — top-left world-pixel offset of the viewport
    """

    MIN_CELL_PX: float = 3.0
    MAX_CELL_PX: float = 32.0

    def __init__(
        self,
        world_w: int,
        world_h: int,
        screen_w: int,
        screen_h: int,
        initial_cell_px: float = 7.0,
    ) -> None:
        self.world_w = world_w
        self.world_h = world_h
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.cell_px: float = initial_cell_px

        # Centre camera on world at start
        self.offset_x: float = (world_w * initial_cell_px - screen_w) / 2
        self.offset_y: float = (world_h * initial_cell_px - screen_h) / 2

        self._drag_start: tuple[int, int] | None = None
        self._drag_offset_start: tuple[float, float] = (0.0, 0.0)

    # ------------------------------------------------------------------
    # Coordinate transforms
    # ------------------------------------------------------------------

    def world_to_screen(self, gx: float, gy: float) -> tuple[float, float]:
        """Convert grid cell (gx, gy) to screen pixel (px, py)."""
        px = gx * self.cell_px - self.offset_x
        py = gy * self.cell_px - self.offset_y
        return px, py

    def screen_to_world(self, px: float, py: float) -> tuple[float, float]:
        """Convert screen pixel to fractional grid position."""
        gx = (px + self.offset_x) / self.cell_px
        gy = (py + self.offset_y) / self.cell_px
        return gx, gy

    def screen_to_cell(self, px: int, py: int) -> tuple[int, int]:
        """Convert screen pixel to integer grid cell."""
        gx, gy = self.screen_to_world(px, py)
        return int(math.floor(gx)), int(math.floor(gy))

    # ------------------------------------------------------------------
    # Cell rect on screen
    # ------------------------------------------------------------------

    def cell_rect(self, gx: int, gy: int) -> tuple[int, int, int, int]:
        """Return (left, top, width, height) in screen pixels for a cell."""
        sx, sy = self.world_to_screen(gx, gy)
        w = max(1, int(self.cell_px))
        return int(sx), int(sy), w, w

    # ------------------------------------------------------------------
    # Visible cell range
    # ------------------------------------------------------------------

    def visible_cells(self) -> tuple[int, int, int, int]:
        """Return (min_gx, min_gy, max_gx, max_gy) of visible grid cells."""
        min_gx = max(0, int(self.offset_x / self.cell_px))
        min_gy = max(0, int(self.offset_y / self.cell_px))
        max_gx = min(self.world_w - 1, int((self.offset_x + self.screen_w) / self.cell_px) + 1)
        max_gy = min(self.world_h - 1, int((self.offset_y + self.screen_h) / self.cell_px) + 1)
        return min_gx, min_gy, max_gx, max_gy

    # ------------------------------------------------------------------
    # Pan
    # ------------------------------------------------------------------

    def pan(self, dx: float, dy: float) -> None:
        """Translate camera by (dx, dy) pixels."""
        self.offset_x += dx
        self.offset_y += dy
        self._clamp()

    def begin_drag(self, mouse_x: int, mouse_y: int) -> None:
        self._drag_start = (mouse_x, mouse_y)
        self._drag_offset_start = (self.offset_x, self.offset_y)

    def update_drag(self, mouse_x: int, mouse_y: int) -> None:
        if self._drag_start is None:
            return
        dx = mouse_x - self._drag_start[0]
        dy = mouse_y - self._drag_start[1]
        self.offset_x = self._drag_offset_start[0] - dx
        self.offset_y = self._drag_offset_start[1] - dy
        self._clamp()

    def end_drag(self) -> None:
        self._drag_start = None

    def is_dragging(self) -> bool:
        return self._drag_start is not None

    # ------------------------------------------------------------------
    # Zoom
    # ------------------------------------------------------------------

    def zoom(self, factor: float, pivot_px: int, pivot_py: int) -> None:
        """Zoom in/out around a pivot screen pixel."""
        old = self.cell_px
        new = max(self.MIN_CELL_PX, min(self.MAX_CELL_PX, old * factor))
        if new == old:
            return
        # Adjust offset so the pivot stays fixed
        ratio = new / old
        self.offset_x = (self.offset_x + pivot_px) * ratio - pivot_px
        self.offset_y = (self.offset_y + pivot_py) * ratio - pivot_py
        self.cell_px = new
        self._clamp()

    def zoom_in(self, pivot_px: int = 0, pivot_py: int = 0) -> None:
        self.zoom(1.25, pivot_px, pivot_py)

    def zoom_out(self, pivot_px: int = 0, pivot_py: int = 0) -> None:
        self.zoom(0.80, pivot_px, pivot_py)

    # ------------------------------------------------------------------
    # Centre on world cell
    # ------------------------------------------------------------------

    def center_on(self, gx: int, gy: int) -> None:
        self.offset_x = gx * self.cell_px - self.screen_w / 2
        self.offset_y = gy * self.cell_px - self.screen_h / 2
        self._clamp()

    # ------------------------------------------------------------------
    # Resize viewport
    # ------------------------------------------------------------------

    def resize(self, screen_w: int, screen_h: int) -> None:
        self.screen_w = screen_w
        self.screen_h = screen_h
        self._clamp()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _clamp(self) -> None:
        world_px_w = self.world_w * self.cell_px
        world_px_h = self.world_h * self.cell_px
        max_ox = max(0.0, world_px_w - self.screen_w)
        max_oy = max(0.0, world_px_h - self.screen_h)
        self.offset_x = max(0.0, min(max_ox, self.offset_x))
        self.offset_y = max(0.0, min(max_oy, self.offset_y))
