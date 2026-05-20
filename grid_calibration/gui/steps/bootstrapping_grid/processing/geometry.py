"""
Geometry helpers for bootstrapping-grid processing.

These utilities convert between image coordinates and center-relative polar
coordinates, estimate spoke support regions, and provide small vector helpers
used by spoke and circle bootstrapping.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np


def load_center(center_obj: Path) -> np.ndarray:
    return np.array([float(center_obj["x"]), float(center_obj["y"])], dtype=float)


def point_radius_from_center(x: np.ndarray, y: np.ndarray, center_xy: np.ndarray) -> np.ndarray:
    """Return pixel radius from ``center_xy``."""
    return np.hypot(np.asarray(x) - center_xy[0], np.asarray(y) - center_xy[1])


def xy_to_polar_about_center(
    x: np.ndarray,
    y: np.ndarray,
    center_xy: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Convert pixel coordinates to polar coordinates about ``center_xy``.

    Returns
    -------
    theta_deg, r_pix
        Angle in degrees and pixel radius.
    """
    dx = np.asarray(x, dtype=float) - center_xy[0]
    dy = np.asarray(y, dtype=float) - center_xy[1]
    theta_deg = (np.degrees(np.arctan2(dy, dx)) + 360.0) % 360.0
    r_pix = np.hypot(dx, dy)
    return theta_deg, r_pix
