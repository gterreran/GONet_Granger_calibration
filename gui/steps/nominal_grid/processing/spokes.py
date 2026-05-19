"""Spoke-angle estimation and nominal-spoke assignment."""

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
