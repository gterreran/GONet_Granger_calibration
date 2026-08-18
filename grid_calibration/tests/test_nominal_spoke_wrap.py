from __future__ import annotations

import numpy as np

from grid_calibration.gui.steps.nominal_grid.processing.spokes import (
    merge_wrap_split_spoke_groups,
)


def _group(points: list[tuple[float, float]], start: int) -> tuple[list[list[float]], np.ndarray]:
    rows = [[theta, radius] for theta, radius in points]
    return rows, np.arange(start, start + len(rows), dtype=int)


def test_wrap_split_fragments_with_complementary_radial_coverage_are_merged() -> None:
    low_rows, low_group = _group(
        [(0.12, radius) for radius in np.linspace(100.0, 600.0, 26)],
        start=0,
    )
    high_rows, high_group = _group(
        [(359.90, radius) for radius in np.linspace(580.0, 1000.0, 22)],
        start=len(low_rows),
    )
    points = np.asarray(low_rows + high_rows, dtype=float)

    groups, merge_count = merge_wrap_split_spoke_groups(
        points,
        [low_group, high_group],
        np.array([92.5, 92.5]),
        max_dist=35.0,
        gate_tol_theta=0.3,
    )

    assert merge_count == 1
    assert len(groups) == 1
    assert set(groups[0]) == set(range(points.shape[0]))


def test_two_complete_edge_spokes_with_same_nominal_value_remain_a_conflict() -> None:
    low_rows, low_group = _group(
        [(0.12, radius) for radius in np.linspace(100.0, 1000.0, 40)],
        start=0,
    )
    high_rows, high_group = _group(
        [(359.90, radius) for radius in np.linspace(110.0, 990.0, 40)],
        start=len(low_rows),
    )
    points = np.asarray(low_rows + high_rows, dtype=float)

    groups, merge_count = merge_wrap_split_spoke_groups(
        points,
        [low_group, high_group],
        np.array([92.5, 92.5]),
        max_dist=35.0,
        gate_tol_theta=0.3,
    )

    assert merge_count == 0
    assert len(groups) == 2


def test_edge_fragments_with_different_nominal_values_are_not_merged() -> None:
    low_rows, low_group = _group(
        [(0.12, radius) for radius in np.linspace(100.0, 600.0, 26)],
        start=0,
    )
    high_rows, high_group = _group(
        [(359.90, radius) for radius in np.linspace(580.0, 1000.0, 22)],
        start=len(low_rows),
    )
    points = np.asarray(low_rows + high_rows, dtype=float)

    groups, merge_count = merge_wrap_split_spoke_groups(
        points,
        [low_group, high_group],
        np.array([92.5, 95.0]),
        max_dist=35.0,
        gate_tol_theta=0.3,
    )

    assert merge_count == 0
    assert len(groups) == 2


def test_duplicate_fragments_away_from_theta_wrap_are_not_merged() -> None:
    first_rows, first_group = _group(
        [(120.0, radius) for radius in np.linspace(100.0, 600.0, 26)],
        start=0,
    )
    second_rows, second_group = _group(
        [(120.1, radius) for radius in np.linspace(580.0, 1000.0, 22)],
        start=len(first_rows),
    )
    points = np.asarray(first_rows + second_rows, dtype=float)

    groups, merge_count = merge_wrap_split_spoke_groups(
        points,
        [first_group, second_group],
        np.array([92.5, 92.5]),
        max_dist=35.0,
        gate_tol_theta=0.3,
    )

    assert merge_count == 0
    assert len(groups) == 2
