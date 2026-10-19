"""
spatial.py — Spatial hash grid for O(1) neighbourhood queries.

Divides the world into buckets of size `cell_size`. Each entity is stored
in its bucket. Radius queries collect from the relevant overlapping buckets
in O(k) where k is the number of nearby entities — no O(n^2) global loops.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Generic, Iterator, TypeVar

T = TypeVar("T")


class SpatialHash(Generic[T]):
    """2D spatial hash mapping (x, y) positions to sets of objects.

    Args:
        cell_size: Width/height of each hash bucket in world cells.
                   Larger = fewer buckets but more items per bucket.
                   Rule of thumb: ~2× your typical query radius.
    """

    def __init__(self, cell_size: int = 10) -> None:
        self._cell_size: int = max(1, cell_size)
        self._buckets: dict[tuple[int, int], set[T]] = defaultdict(set)
        self._positions: dict[int, tuple[int, int]] = {}  # id(obj) → (x, y)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _bucket_key(self, x: int, y: int) -> tuple[int, int]:
        return (x // self._cell_size, y // self._cell_size)

    def _buckets_in_range(self, cx: int, cy: int, radius: float) -> Iterator[tuple[int, int]]:
        """Yield all bucket keys that could overlap a circle of given radius."""
        br = int(math.ceil(radius / self._cell_size))
        bx = cx // self._cell_size
        by = cy // self._cell_size
        for dx in range(-br - 1, br + 2):
            for dy in range(-br - 1, br + 2):
                yield (bx + dx, by + dy)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def insert(self, obj: T, x: int, y: int) -> None:
        """Insert or update the position of an object."""
        oid = id(obj)
        # Remove from old bucket if already tracked
        old_pos = self._positions.get(oid)
        if old_pos is not None:
            old_key = self._bucket_key(*old_pos)
            self._buckets[old_key].discard(obj)

        new_key = self._bucket_key(x, y)
        self._buckets[new_key].add(obj)
        self._positions[oid] = (x, y)

    def remove(self, obj: T) -> None:
        """Remove an object entirely."""
        oid = id(obj)
        pos = self._positions.pop(oid, None)
        if pos is not None:
            key = self._bucket_key(*pos)
            self._buckets[key].discard(obj)

    def query_radius(
        self,
        cx: int,
        cy: int,
        radius: float,
        exclude: T | None = None,
    ) -> list[T]:
        """Return all objects within *radius* cells of (cx, cy).

        Args:
            cx, cy:  Centre of query circle.
            radius:  Search radius in grid cells.
            exclude: Optionally exclude this specific object.

        Returns:
            List of objects (order not guaranteed).
        """
        r2 = radius * radius
        seen: set[int] = set()
        results: list[T] = []

        for bkey in self._buckets_in_range(cx, cy, radius):
            bucket = self._buckets.get(bkey)
            if not bucket:
                continue
            for obj in bucket:
                oid = id(obj)
                if oid in seen:
                    continue
                seen.add(oid)
                if obj is exclude:
                    continue
                pos = self._positions.get(oid)
                if pos is None:
                    continue
                dx = pos[0] - cx
                dy = pos[1] - cy
                if dx * dx + dy * dy <= r2:
                    results.append(obj)

        results.sort(key=lambda o: getattr(o, "id", ""))
        return results

    def query_cone(
        self,
        cx: int,
        cy: int,
        radius: float,
        direction_deg: float,
        fov_deg: float,
        exclude: T | None = None,
    ) -> list[T]:
        """Return objects within a cone (vision arc).

        Args:
            cx, cy:        Observer position.
            radius:        Maximum distance.
            direction_deg: Centre of vision arc in degrees (0 = +x axis).
            fov_deg:       Full angular width of the cone in degrees.
            exclude:       Optionally exclude this object.

        Returns:
            List of objects in the cone.
        """
        import math  # noqa: PLC0415

        half_fov = math.radians(fov_deg / 2.0)
        dir_rad = math.radians(direction_deg)

        candidates = self.query_radius(cx, cy, radius, exclude=exclude)
        results: list[T] = []

        for obj in candidates:
            oid = id(obj)
            pos = self._positions.get(oid)
            if pos is None:
                continue
            dx = pos[0] - cx
            dy = pos[1] - cy
            if dx == 0 and dy == 0:
                results.append(obj)
                continue
            angle = math.atan2(dy, dx)
            diff = abs((angle - dir_rad + math.pi) % (2 * math.pi) - math.pi)
            if diff <= half_fov:
                results.append(obj)

        return results

    def query_cell(self, x: int, y: int) -> list[T]:
        """Return all objects in the exact bucket containing (x, y)."""
        key = self._bucket_key(x, y)
        return list(self._buckets.get(key, []))

    def all_objects(self) -> list[T]:
        """Return every tracked object."""
        seen: set[int] = set()
        results: list[T] = []
        for bucket in self._buckets.values():
            for obj in bucket:
                oid = id(obj)
                if oid not in seen:
                    seen.add(oid)
                    results.append(obj)
        return results

    def clear(self) -> None:
        """Remove all entries."""
        self._buckets.clear()
        self._positions.clear()

    def __len__(self) -> int:
        seen: set[int] = set()
        for bucket in self._buckets.values():
            for obj in bucket:
                seen.add(id(obj))
        return len(seen)
