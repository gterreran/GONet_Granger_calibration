"""
Small numerical utilities used by modeling-results processing.
"""

from __future__ import annotations

import numpy as np


def wrap_angle_deg(angle_deg: np.ndarray) -> np.ndarray:
    """Wrap angles to ``[-180, 180)`` degrees."""
    return (np.asarray(angle_deg, dtype=float) + 180.0) % 360.0 - 180.0


def robust_rms(values: np.ndarray) -> float:
    """Return the root-mean-square of an array."""
    values = np.asarray(values, dtype=float)
    return float(np.sqrt(np.mean(values**2)))


def circ_median_deg(angle_deg: np.ndarray) -> float:
    """Estimate a circular central value in degrees."""
    angle_rad = np.deg2rad(np.asarray(angle_deg, dtype=float))
    return float(np.rad2deg(np.arctan2(np.median(np.sin(angle_rad)), np.median(np.cos(angle_rad)))))


def cartesian_center_from_measured_polar(
    x: np.ndarray,
    y: np.ndarray,
    r: np.ndarray,
    theta_deg: np.ndarray,
) -> tuple[float, float]:
    """Estimate the polar origin implied by measured pixel and polar coordinates."""
    theta = np.deg2rad(theta_deg)
    cx = np.median(x - r * np.cos(theta))
    cy = np.median(y - r * np.sin(theta))
    return float(cx), float(cy)


def outlier_threshold_from_residual_norm(
    residual_norm: np.ndarray,
    sigma: float,
    floor_px: float,
) -> float:
    """Return an outlier threshold from the residual norm distribution."""
    residual_norm = np.asarray(residual_norm, dtype=float)
    med = float(np.median(residual_norm))
    mad = float(np.median(np.abs(residual_norm - med)))
    sigma_est = 1.4826 * mad
    return max(float(floor_px), med + float(sigma) * sigma_est)

