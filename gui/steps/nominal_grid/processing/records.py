"""Output-record construction for nominal-grid assignments."""

from __future__ import annotations

import numpy as np


def build_group_lookup(
    n_points: int,
    groups: list[np.ndarray],
) -> np.ndarray:
    """Build a point-to-group lookup array.

    Parameters
    ----------
    n_points : int
        Number of measured points.
    groups : list[numpy.ndarray]
        Groups represented by point indices.

    Returns
    -------
    numpy.ndarray
        Integer array of length ``n_points``. Ungrouped points are marked ``-1``.
    """
    lookup = np.full(n_points, -1, dtype=int)
    for i, group in enumerate(groups):
        lookup[group] = i
    return lookup


def build_nominal_assignment_records(
    *,
    base_idx: np.ndarray,
    pixels: np.ndarray,
    points: np.ndarray,
    ring_groups: list[np.ndarray],
    spoke_groups: list[np.ndarray],
    nominal_r_by_ring: np.ndarray,
    nominal_theta_by_spoke: np.ndarray,
) -> list[dict]:
    """Build final nominal-grid assignment records.

    Parameters
    ----------
    base_idx : numpy.ndarray
        Original point indices.
    pixels : numpy.ndarray
        Pixel coordinates using the existing ``(row, col)`` convention.
    points : numpy.ndarray
        Polar point coordinates with columns ``theta`` and ``r``.
    ring_groups, spoke_groups : list[numpy.ndarray]
        Kept ring and spoke fragments.
    nominal_r_by_ring : numpy.ndarray
        Assigned nominal radius for each ring group.
    nominal_theta_by_spoke : numpy.ndarray
        Assigned nominal angle for each spoke group.

    Returns
    -------
    list[dict]
        Nominal assignment records, one per point assigned to both a ring and a
        spoke.
    """
    n_pts = points.shape[0]
    ring_id = build_group_lookup(n_pts, ring_groups)
    spoke_id = build_group_lookup(n_pts, spoke_groups)

    valid = (ring_id >= 0) & (spoke_id >= 0)
    valid_idx = np.nonzero(valid)[0]

    nominal_assignment: list[dict] = []

    for idx in valid_idx:
        i_ring = ring_id[idx]
        i_spoke = spoke_id[idx]

        nominal_assignment.append(
            {
                "idx": int(base_idx[idx]),
                "pixel_x": float(pixels[idx, 1]),
                "pixel_y": float(pixels[idx, 0]),
                "r": float(points[idx, 1]),
                "theta": float(points[idx, 0]),
                "circle_index": int(i_ring),
                "spoke_index": int(i_spoke),
                "nominal_r": float(nominal_r_by_ring[i_ring]),
                "nominal_theta": float(nominal_theta_by_spoke[i_spoke]),
            }
        )

    return nominal_assignment
