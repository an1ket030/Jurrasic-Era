"""
rng.py — Single seeded random number generator.

All randomness in the simulation must go through this wrapper to ensure
full determinism given a seed.
"""

from __future__ import annotations

import random
from typing import Any, Sequence, TypeVar

import numpy as np

T = TypeVar("T")


class SimRNG:
    """Wrapper around numpy's default_rng and Python's random.Random.

    A single instance is created at simulation start with a user-supplied seed
    and passed explicitly to every component that needs randomness.

    Attributes:
        seed: The original seed used to construct this instance.
    """

    def __init__(self, seed: int) -> None:
        self.seed: int = seed
        self._np_rng: np.random.Generator = np.random.default_rng(seed)
        self._py_rng: random.Random = random.Random(seed)

    # ------------------------------------------------------------------
    # Primitive draws
    # ------------------------------------------------------------------

    def random(self) -> float:
        """Uniform float in [0, 1)."""
        return float(self._np_rng.random())

    def uniform(self, low: float, high: float) -> float:
        """Uniform float in [low, high)."""
        return float(self._np_rng.uniform(low, high))

    def randint(self, low: int, high: int) -> int:
        """Uniform integer in [low, high] (inclusive on both ends)."""
        return int(self._np_rng.integers(low, high + 1))

    def normal(self, mean: float, std: float) -> float:
        """Sample from a Gaussian distribution."""
        return float(self._np_rng.normal(mean, std))

    def clamp_normal(self, mean: float, std: float, lo: float, hi: float) -> float:
        """Gaussian sample clamped to [lo, hi]."""
        return float(np.clip(self.normal(mean, std), lo, hi))

    def chance(self, probability: float) -> bool:
        """Return True with the given probability in [0, 1]."""
        return self.random() < probability

    # ------------------------------------------------------------------
    # Collection operations
    # ------------------------------------------------------------------

    def choice(self, seq: Sequence[T]) -> T:
        """Pick a random element from a non-empty sequence."""
        idx = self.randint(0, len(seq) - 1)
        return seq[idx]

    def shuffle(self, lst: list[Any]) -> None:
        """Shuffle a list in-place deterministically."""
        self._py_rng.shuffle(lst)

    def choices(self, population: Sequence[T], weights: Sequence[float] | None = None, k: int = 1) -> list[T]:
        """Weighted sampling with replacement."""
        return self._py_rng.choices(population, weights=weights, k=k)

    def sample(self, population: Sequence[T], k: int) -> list[T]:
        """Sample k unique elements (no replacement)."""
        k = min(k, len(population))
        return self._py_rng.sample(list(population), k)

    # ------------------------------------------------------------------
    # Numpy convenience
    # ------------------------------------------------------------------

    def rand_array(self, *shape: int) -> np.ndarray:
        """Uniform [0, 1) float array."""
        return self._np_rng.random(shape)

    def noise_2d(self, height: int, width: int, scale: float = 1.0) -> np.ndarray:
        """Simple smoothed noise array via multiple octave summation."""
        arr = np.zeros((height, width), dtype=np.float32)
        amplitude = 1.0
        frequency = 1
        max_val = 0.0
        for _ in range(4):  # 4 octaves
            raw = self._np_rng.random((height // frequency + 2, width // frequency + 2)).astype(np.float32)
            # Upsample with linear interpolation
            from numpy import interp  # noqa: PLC0415
            rows = np.linspace(0, raw.shape[0] - 1, height)
            cols = np.linspace(0, raw.shape[1] - 1, width)
            # Simple bilinear upsample
            r0 = np.floor(rows).astype(int)
            r1 = np.clip(r0 + 1, 0, raw.shape[0] - 1)
            c0 = np.floor(cols).astype(int)
            c1 = np.clip(c0 + 1, 0, raw.shape[1] - 1)
            dr = (rows - r0)[:, np.newaxis]
            dc = (cols - c0)[np.newaxis, :]
            upsampled = (
                raw[r0[:, np.newaxis], c0[np.newaxis, :]] * (1 - dr) * (1 - dc)
                + raw[r1[:, np.newaxis], c0[np.newaxis, :]] * dr * (1 - dc)
                + raw[r0[:, np.newaxis], c1[np.newaxis, :]] * (1 - dr) * dc
                + raw[r1[:, np.newaxis], c1[np.newaxis, :]] * dr * dc
            )
            arr += amplitude * upsampled
            max_val += amplitude
            amplitude *= 0.5
            frequency *= 2
        return (arr / max_val * scale).astype(np.float32)

    # ------------------------------------------------------------------
    # State (for snapshot / replay)
    # ------------------------------------------------------------------

    def get_state(self) -> dict:
        """Capture RNG state for serialisation."""
        return {
            "seed": self.seed,
            "np_state": self._np_rng.bit_generator.state,
            "py_state": self._py_rng.getstate(),
        }

    def set_state(self, state: dict) -> None:
        """Restore RNG state from a deserialised snapshot."""
        self._np_rng.bit_generator.state = state["np_state"]
        py_st = state["py_state"]
        if isinstance(py_st, (list, tuple)) and len(py_st) == 3:
            version = py_st[0]
            vector = tuple(py_st[1]) if isinstance(py_st[1], (list, tuple)) else py_st[1]
            gauss = py_st[2]
            self._py_rng.setstate((version, vector, gauss))
        else:
            self._py_rng.setstate(py_st)
