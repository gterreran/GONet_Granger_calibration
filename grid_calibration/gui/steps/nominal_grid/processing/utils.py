"""
Small numerical utilities for nominal-grid processing.
"""

from __future__ import annotations

import numpy as np


def wrap_delta(a: float, b: float, period: float) -> float:
    """Return the smallest absolute difference between two circular values.

    Parameters
    ----------
    a, b : float
        Values to compare.
    period : float
        Circular period.

    Returns
    -------
    float
        Smallest absolute wrapped separation.
    """
    d = abs(b - a) % period
    return min(d, period - d)


def wrap_deg(theta_deg: np.ndarray) -> np.ndarray:
    """Wrap angles to the interval ``[0, 360)``.

    Parameters
    ----------
    theta_deg : numpy.ndarray
        Input angles in degrees.

    Returns
    -------
    numpy.ndarray
        Wrapped angles in degrees.
    """
    return np.asarray(theta_deg) % 360.0


def robust_median_spacing(
    values: np.ndarray,
    *,
    min_sep: float = 2.0,
    max_sep: float = 200.0,
) -> float:
    """Estimate a typical spacing from sorted one-dimensional values.

    Parameters
    ----------
    values : numpy.ndarray
        One-dimensional values whose consecutive spacings should be estimated.
    min_sep, max_sep : float, optional
        Inclusive bounds used to reject implausible consecutive spacings.

    Returns
    -------
    float
        Median accepted spacing, or ``nan`` if fewer than two values are given.
    """
    values = np.sort(np.asarray(values, dtype=float))
    if values.size < 2:
        return float("nan")

    dv = np.diff(values)
    good = (dv >= min_sep) & (dv <= max_sep)

    if np.any(good):
        return float(np.median(dv[good]))
    return float(np.median(dv))


def circular_mean_deg(theta_deg: np.ndarray) -> float:
    """Compute a circular mean in degrees.

    Parameters
    ----------
    theta_deg : numpy.ndarray
        Angles in degrees.

    Returns
    -------
    float
        Circular mean, wrapped to ``[0, 360)``.
    """
    ang = np.deg2rad(theta_deg)
    s = np.sin(ang).mean()
    c = np.cos(ang).mean()
    return float(np.rad2deg(np.arctan2(s, c)) % 360.0)
