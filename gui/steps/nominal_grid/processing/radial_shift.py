"""Rigid nominal-circle shift diagnostics."""

from __future__ import annotations

import numpy as np

from .constants import DEG_STEP


def fit_no_intercept_odd_cubic(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Fit ``y = a1*x + a3*x**3`` with no intercept.

    Parameters
    ----------
    x, y : numpy.ndarray
        Input coordinates for the radial relation.

    Returns
    -------
    tuple[numpy.ndarray, numpy.ndarray]
        Fitted values and fitted coefficients ``[a1, a3]``.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)

    A = np.column_stack([x, x**3])
    coeff, *_ = np.linalg.lstsq(A, y, rcond=None)
    fitted = A @ coeff
    return fitted, coeff


def score_circle_shifts(
    nominal_r: np.ndarray,
    measured_r: np.ndarray,
    *,
    shifts: np.ndarray | None = None,
) -> dict[float, float]:
    """Score candidate rigid shifts of nominal circle radii.

    Parameters
    ----------
    nominal_r : numpy.ndarray
        Assigned nominal circle radii in degrees.
    measured_r : numpy.ndarray
        Representative measured circle radii in pixels.
    shifts : numpy.ndarray, optional
        Candidate shifts in degrees.

    Returns
    -------
    dict[float, float]
        Mapping from candidate shift to robust MAD score.
    """
    nominal_r = np.asarray(nominal_r, dtype=float)
    measured_r = np.asarray(measured_r, dtype=float)

    if shifts is None:
        shifts = np.arange(-5.0, 7.5, DEG_STEP)

    shift_scores: dict[float, float] = {}

    for shift in shifts:
        shifted_r = nominal_r + shift
        valid = shifted_r >= 0.0

        if np.sum(valid) < 4:
            continue

        fitted, _ = fit_no_intercept_odd_cubic(
            shifted_r[valid],
            measured_r[valid],
        )

        resid = measured_r[valid] - fitted
        mad = float(1.4826 * np.median(np.abs(resid - np.median(resid))))
        shift_scores[float(shift)] = mad

    return shift_scores


def choose_rigid_circle_shift(
    nominal_r: np.ndarray,
    measured_r: np.ndarray,
    *,
    min_improvement_frac: float = 0.20,
) -> tuple[float, dict[float, float], float]:
    """Choose whether to apply a rigid radial circle-label shift.

    Parameters
    ----------
    nominal_r : numpy.ndarray
        Assigned nominal circle radii in degrees.
    measured_r : numpy.ndarray
        Representative measured circle radii in pixels.
    min_improvement_frac : float, optional
        Minimum fractional MAD improvement over the zero-shift solution needed
        before a non-zero shift is accepted.

    Returns
    -------
    tuple[float, dict[float, float], float]
        Chosen shift, all candidate scores, and improvement fraction relative to
        the zero-shift score.
    """
    shift_scores = score_circle_shifts(nominal_r, measured_r)

    if not shift_scores:
        return 0.0, shift_scores, 0.0

    best_shift = min(shift_scores, key=shift_scores.get)
    zero_mad = shift_scores.get(0.0)
    best_mad = shift_scores[best_shift]

    if zero_mad is not None and zero_mad > 0:
        improvement_frac = (zero_mad - best_mad) / zero_mad
    else:
        improvement_frac = 0.0

    if best_shift != 0.0 and improvement_frac >= min_improvement_frac:
        return float(best_shift), shift_scores, float(improvement_frac)

    return 0.0, shift_scores, float(improvement_frac)
