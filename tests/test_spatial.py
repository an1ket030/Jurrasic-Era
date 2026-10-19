"""
test_spatial.py — Tests for the 2D SpatialHash grid.
"""

from __future__ import annotations

import pytest

from prehistoric_sim.engine.entities import Entity
from prehistoric_sim.engine.spatial import SpatialHash


def test_insert_and_query_radius():
    sh: SpatialHash[Entity] = SpatialHash(cell_size=10)
    e1 = Entity(id="e1", position=(5, 5))
    e2 = Entity(id="e2", position=(7, 7))
    e3 = Entity(id="e3", position=(50, 50))  # Far away

    sh.insert(e1, 5, 5)
    sh.insert(e2, 7, 7)
    sh.insert(e3, 50, 50)

    # e1 and e2 should be within radius 5 of (5,5)
    nearby = sh.query_radius(5, 5, 5.0)
    assert e1 in nearby
    assert e2 in nearby
    assert e3 not in nearby


def test_exclude_in_query():
    sh: SpatialHash[Entity] = SpatialHash(cell_size=10)
    e1 = Entity(id="e1", position=(10, 10))
    e2 = Entity(id="e2", position=(11, 10))

    sh.insert(e1, 10, 10)
    sh.insert(e2, 11, 10)

    res = sh.query_radius(10, 10, 5.0, exclude=e1)
    assert e1 not in res
    assert e2 in res


def test_query_cone():
    sh: SpatialHash[Entity] = SpatialHash(cell_size=10)
    center = Entity(id="c", position=(20, 20))
    # Directly East (0 deg)
    in_front = Entity(id="front", position=(25, 20))
    # Directly West (180 deg)
    behind = Entity(id="behind", position=(15, 20))

    sh.insert(center, 20, 20)
    sh.insert(in_front, 25, 20)
    sh.insert(behind, 15, 20)

    # Looking East (0 deg) with a 90 deg FOV
    cone_results = sh.query_cone(20, 20, radius=10.0, direction_deg=0.0, fov_deg=90.0)
    assert in_front in cone_results
    assert behind not in cone_results


def test_remove():
    sh: SpatialHash[Entity] = SpatialHash(cell_size=10)
    e1 = Entity(id="e1", position=(5, 5))
    sh.insert(e1, 5, 5)
    assert len(sh) == 1

    sh.remove(e1)
    assert len(sh) == 0
    assert len(sh.query_radius(5, 5, 10.0)) == 0
