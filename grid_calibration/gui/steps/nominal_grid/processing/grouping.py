"""
Grouping utilities for nominal-grid processing.

This module identifies ring-like and spoke-like fragments in the measured
``(theta, r)`` point cloud before nominal labels are assigned.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
from scipy.spatial import cKDTree

from .utils import wrap_delta


def chain_groups_closest_neighbor_with_axis_gate(
    points: np.ndarray,
    *,
    max_dist: float,
    gate_axis: int,
    gate_tol: float,
    gate_period: Optional[float] = None,
    min_increase_axis: Optional[int] = None,
    min_increase: float = 0.0,
    seed_sort_axis: Optional[int] = None,
    k_start: int = 32,
    k_max: int = 4096,
) -> list[np.ndarray]:
    """Build greedy nearest-neighbor chains with an axis gate.

    Parameters
    ----------
    points : numpy.ndarray
        Array of point coordinates with shape ``(N, D)``.
    max_dist : float
        Maximum Euclidean neighbor distance allowed when extending a chain.
    gate_axis : int
        Axis used for the additional gate condition.
    gate_tol : float
        Maximum allowed difference along ``gate_axis``.
    gate_period : float, optional
        Circular period for the gate axis. If omitted, the gate is linear.
    min_increase_axis : int, optional
        Axis that must increase when a chain is extended.
    min_increase : float, optional
        Minimum required increase along ``min_increase_axis``.
    seed_sort_axis : int, optional
        Axis used to sort initial seed points.
    k_start, k_max : int, optional
        Initial and maximum KD-tree neighbor query sizes.

    Returns
    -------
    list[numpy.ndarray]
        Disjoint chains, each represented by indices into ``points``.
    """
    n = points.shape[0]
    tree = cKDTree(points)
    unassigned = np.ones(n, dtype=bool)

    if seed_sort_axis is None:
        seed_order = np.arange(n, dtype=int)
    else:
        seed_order = np.argsort(points[:, seed_sort_axis])

    groups: list[np.ndarray] = []

    for seed in seed_order:
        if not unassigned[seed]:
            continue

        chain = [int(seed)]
        unassigned[seed] = False
        current = int(seed)

        while True:
            found_next: Optional[int] = None
            k = k_start

            while True:
                kk = min(k, n)
                dists, idxs = tree.query(points[current], k=kk)
                dists = np.atleast_1d(dists)
                idxs = np.atleast_1d(idxs)

                gate0 = points[current, gate_axis]
                inc0 = (
                    points[current, min_increase_axis]
                    if min_increase_axis is not None
                    else None
                )

                for d_euclid, j in zip(dists, idxs):
                    j = int(j)

                    if j == current or not unassigned[j]:
                        continue
                    if d_euclid > max_dist:
                        break

                    if min_increase_axis is not None and inc0 is not None:
                        if (points[j, min_increase_axis] - inc0) < min_increase:
                            continue

                    gate1 = points[j, gate_axis]
                    if gate_period is None:
                        d_gate = abs(gate1 - gate0)
                    else:
                        d_gate = wrap_delta(gate0, gate1, gate_period)

                    if d_gate <= gate_tol:
                        found_next = j
                        break

                if found_next is not None:
                    break
                if k >= k_max or kk == n:
                    break

                k = min(k * 2, k_max)

            if found_next is None:
                break

            chain.append(found_next)
            unassigned[found_next] = False
            current = found_next

        groups.append(np.asarray(chain, dtype=int))

    return groups


def detect_ring_and_spoke_groups(
    points: np.ndarray,
    params: dict,
) -> tuple[list[np.ndarray], list[np.ndarray]]:
    """Detect candidate ring and spoke fragments.

    Parameters
    ----------
    points : numpy.ndarray
        Polar point coordinates with columns ``theta`` and ``r``.
    params : dict
        Nominal-grid grouping parameters.

    Returns
    -------
    tuple[list[numpy.ndarray], list[numpy.ndarray]]
        Ring groups followed by spoke groups.
    """
    ring_groups = chain_groups_closest_neighbor_with_axis_gate(
        points,
        max_dist=params["ring_max_dist"],
        gate_axis=1,
        gate_tol=params["ring_gate_tol_r"],
        gate_period=None,
        min_increase_axis=None,
        min_increase=0.0,
        seed_sort_axis=None,
        k_start=32,
        k_max=4096,
    )

    spoke_groups = chain_groups_closest_neighbor_with_axis_gate(
        points,
        max_dist=params["spoke_max_dist"],
        gate_axis=0,
        gate_tol=params["spoke_gate_tol_theta"],
        gate_period=360.0,
        min_increase_axis=1,
        min_increase=params["spoke_min_dist"],
        seed_sort_axis=1,
        k_start=32,
        k_max=4096,
    )

    ring_groups = [g for g in ring_groups if g.size >= params["min_ring_group"]]
    spoke_groups = [g for g in spoke_groups if g.size >= params["min_spoke_group"]]

    return ring_groups, spoke_groups
