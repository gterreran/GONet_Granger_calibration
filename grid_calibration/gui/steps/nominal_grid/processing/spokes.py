"""
Spoke-angle estimation and nominal-spoke assignment helpers.
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from .constants import DEG_STEP
from .utils import circular_mean_deg, wrap_deg


def spoke_group_theta_estimates(points: np.ndarray, spoke_groups: list[np.ndarray]) -> np.ndarray:
    """Estimate one representative theta for each spoke group.

    Parameters
    ----------
    points : numpy.ndarray
        Polar point coordinates with columns ``theta`` and ``r``.
    spoke_groups : list[numpy.ndarray]
        Candidate spoke fragments.

    Returns
    -------
    numpy.ndarray
        Circular-mean theta estimate for each spoke group.
    """
    return np.array([circular_mean_deg(points[g, 0]) for g in spoke_groups], dtype=float)


def best_theta_offset(theta_g: np.ndarray, *, step: float = DEG_STEP) -> float:
    """Find the offset that best aligns spoke estimates to a regular grid.

    Parameters
    ----------
    theta_g : numpy.ndarray
        Representative spoke angles in degrees.
    step : float, optional
        Angular grid step in degrees.

    Returns
    -------
    float
        Best offset, wrapped to ``[0, 360)``.
    """
    theta_g = wrap_deg(theta_g)
    if theta_g.size == 0:
        return 0.0

    candidates = theta_g if theta_g.size <= 500 else np.random.choice(theta_g, size=500, replace=False)

    def score(theta0: float) -> float:
        x = (theta_g - theta0) % 360.0
        resid = ((x + step / 2) % step) - step / 2
        return float(np.median(np.abs(resid)))

    best0 = float(candidates[0])
    bests = score(best0)

    for t0 in candidates[1:]:
        s = score(float(t0))
        if s < bests:
            bests = s
            best0 = float(t0)

    return float(best0 % 360.0)


def assign_nominal_spokes(
    theta_g: np.ndarray,
    *,
    theta0: Optional[float] = None,
) -> tuple[np.ndarray, np.ndarray, float]:
    """Assign spoke groups to nearest nominal spoke angles.

    Parameters
    ----------
    theta_g : numpy.ndarray
        Representative spoke angles in degrees.
    theta0 : float, optional
        Explicit grid offset. If omitted, the best offset is estimated.

    Returns
    -------
    tuple[numpy.ndarray, numpy.ndarray, float]
        Integer spoke indices, nominal spoke angles, and chosen offset.
    """
    theta_g = wrap_deg(theta_g)

    if theta0 is None:
        theta0 = best_theta_offset(theta_g, step=DEG_STEP)

    nspokes = int(round(360.0 / DEG_STEP))
    x = (theta_g - theta0) % 360.0
    k_spoke = np.rint(x / DEG_STEP).astype(int) % nspokes
    theta_nom = (k_spoke * DEG_STEP) % 360.0

    return k_spoke, theta_nom, float(theta0)


def _radial_overlap_fraction(r_a: np.ndarray, r_b: np.ndarray) -> float:
    """Return radial interval overlap relative to the shorter interval."""
    a_min, a_max = float(np.min(r_a)), float(np.max(r_a))
    b_min, b_max = float(np.min(r_b)), float(np.max(r_b))

    span_a = a_max - a_min
    span_b = b_max - b_min
    shorter_span = min(span_a, span_b)

    if shorter_span <= 0:
        return 1.0

    overlap = max(0.0, min(a_max, b_max) - max(a_min, b_min))
    return overlap / shorter_span


def _straddles_theta_wrap(theta_a: np.ndarray, theta_b: np.ndarray, margin_deg: float) -> bool:
    """Return True when two groups occupy opposite sides of the 0/360 seam."""
    median_a = float(np.median(wrap_deg(theta_a)))
    median_b = float(np.median(wrap_deg(theta_b)))

    a_low = median_a <= margin_deg
    a_high = median_a >= 360.0 - margin_deg
    b_low = median_b <= margin_deg
    b_high = median_b >= 360.0 - margin_deg

    return (a_low and b_high) or (a_high and b_low)


def _has_periodic_cross_group_connection(
    points_a: np.ndarray,
    points_b: np.ndarray,
    *,
    max_dist: float,
    gate_tol_theta: float,
) -> bool:
    """Check whether two fragments contain a plausible local continuation.

    This applies the spoke grouping geometry across the angular branch cut. The
    original KD-tree grouping uses ordinary Euclidean theta coordinates and
    therefore cannot connect points near 359.x degrees to points near 0.x
    degrees even though their circular angular separation is small.
    """
    theta_a = points_a[:, 0][:, None]
    theta_b = points_b[:, 0][None, :]
    r_a = points_a[:, 1][:, None]
    r_b = points_b[:, 1][None, :]

    dtheta = np.abs(((theta_a - theta_b + 180.0) % 360.0) - 180.0)
    candidate = dtheta <= gate_tol_theta
    if not np.any(candidate):
        return False

    dr = np.abs(r_a - r_b)
    periodic_distance = np.hypot(dtheta, dr)
    return bool(np.any(candidate & (periodic_distance <= max_dist)))


def _looks_like_wrap_split_pair(
    points: np.ndarray,
    group_a: np.ndarray,
    group_b: np.ndarray,
    *,
    max_dist: float,
    gate_tol_theta: float,
    max_radial_overlap_fraction: float,
    boundary_margin_deg: float,
) -> bool:
    """Return True when two groups look like complementary pieces of one spoke."""
    pts_a = points[group_a]
    pts_b = points[group_b]

    if not _straddles_theta_wrap(pts_a[:, 0], pts_b[:, 0], boundary_margin_deg):
        return False

    r_a = pts_a[:, 1]
    r_b = pts_b[:, 1]

    # A genuine seam split should add radial coverage on both sides of the
    # transition. If one fragment mostly duplicates the radial range of the
    # other, keep the duplicate conflict visible instead of silently accepting
    # two complete/repeated spokes at the plot edges.
    a_extends_lower = float(np.min(r_a)) < float(np.min(r_b))
    b_extends_lower = float(np.min(r_b)) < float(np.min(r_a))
    a_extends_upper = float(np.max(r_a)) > float(np.max(r_b))
    b_extends_upper = float(np.max(r_b)) > float(np.max(r_a))

    complementary = (a_extends_lower and b_extends_upper) or (
        b_extends_lower and a_extends_upper
    )
    if not complementary:
        return False

    if _radial_overlap_fraction(r_a, r_b) > max_radial_overlap_fraction:
        return False

    return _has_periodic_cross_group_connection(
        pts_a,
        pts_b,
        max_dist=max_dist,
        gate_tol_theta=gate_tol_theta,
    )


def merge_wrap_split_spoke_groups(
    points: np.ndarray,
    spoke_groups: list[np.ndarray],
    nominal_theta_by_spoke: np.ndarray,
    *,
    max_dist: float,
    gate_tol_theta: float,
    max_radial_overlap_fraction: float = 0.5,
    boundary_margin_deg: Optional[float] = None,
) -> tuple[list[np.ndarray], int]:
    """Merge duplicate-labelled spoke fragments split by the theta branch cut.

    A curved/distorted spoke can cross the ``0/360`` branch cut as radius
    changes. The ordinary KD-tree used during grouping sees the two sides as
    roughly 360 degrees apart, so one physical spoke may become two groups and
    both groups can receive the same nominal spoke label.

    Duplicate labels are *not* accepted blindly. Two groups are merged only if
    all of the following are true:

    * they already have the same nominal spoke value;
    * they lie on opposite sides of the measured-theta branch cut;
    * each group contributes radial coverage beyond the other group;
    * their radial overlap is no more than ``max_radial_overlap_fraction`` of
      the shorter group's radial span; and
    * at least one cross-boundary point pair satisfies the same angular gate
      and distance scale used by spoke grouping when theta is treated
      periodically.

    This deliberately leaves two substantially overlapping/complete spokes as
    separate groups so the existing duplicate-label validation still blocks
    confirmation in that ambiguous case.

    Parameters
    ----------
    points : numpy.ndarray
        Polar point coordinates with columns ``theta`` and ``r``.
    spoke_groups : list[numpy.ndarray]
        Detected spoke groups containing indices into ``points``.
    nominal_theta_by_spoke : numpy.ndarray
        Nominal theta assigned to each group.
    max_dist : float
        Maximum local point-to-point distance used for spoke grouping.
    gate_tol_theta : float
        Maximum circular theta difference for a local continuation.
    max_radial_overlap_fraction : float, optional
        Maximum allowed overlap of the two radial intervals, normalized by the
        shorter interval. Defaults to 0.5.
    boundary_margin_deg : float, optional
        Width of the region on either side of 0/360 considered the branch-cut
        edge. Defaults to ``max(DEG_STEP, 2 * gate_tol_theta)``.

    Returns
    -------
    tuple[list[numpy.ndarray], int]
        Updated spoke groups and the number of fragment-pair merges performed.
    """
    groups = [np.asarray(group, dtype=int).copy() for group in spoke_groups]
    labels = np.asarray(nominal_theta_by_spoke, dtype=float).copy()

    if len(groups) != labels.size:
        raise ValueError("spoke_groups and nominal_theta_by_spoke must have matching lengths")
    if not 0.0 <= max_radial_overlap_fraction <= 1.0:
        raise ValueError("max_radial_overlap_fraction must be between 0 and 1")

    if boundary_margin_deg is None:
        boundary_margin_deg = max(DEG_STEP, 2.0 * gate_tol_theta)

    merge_count = 0

    while True:
        best_pair: tuple[float, int, int] | None = None

        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                if not np.isclose(labels[i], labels[j], atol=1e-9, rtol=0.0):
                    continue

                if not _looks_like_wrap_split_pair(
                    points,
                    groups[i],
                    groups[j],
                    max_dist=max_dist,
                    gate_tol_theta=gate_tol_theta,
                    max_radial_overlap_fraction=max_radial_overlap_fraction,
                    boundary_margin_deg=boundary_margin_deg,
                ):
                    continue

                overlap_fraction = _radial_overlap_fraction(
                    points[groups[i], 1],
                    points[groups[j], 1],
                )
                if best_pair is None or overlap_fraction < best_pair[0]:
                    best_pair = (overlap_fraction, i, j)

        if best_pair is None:
            break

        _, i, j = best_pair
        merged = np.concatenate([groups[i], groups[j]])
        merged = merged[np.argsort(points[merged, 1])]
        groups[i] = merged
        del groups[j]
        labels = np.delete(labels, j)
        merge_count += 1

    return groups, merge_count
