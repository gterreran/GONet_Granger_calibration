"""Top-level nominal-grid assignment pipeline."""

from __future__ import annotations

import logging

import numpy as np

from .....errors import DetectionError
from ...unwrapped_grid.keys import IDX_KEY, POINTS_KEY, R_KEY, THETA_KEY
from ..params import DEFAULT_PARAMETERS

from .constants import DEG_STEP
from .grouping import detect_ring_and_spoke_groups
from .radial_shift import choose_rigid_circle_shift
from .records import build_nominal_assignment_records
from .rings import assign_nominal_circles, estimate_ring_levels_with_wave_correction
from .spokes import assign_nominal_spokes, spoke_group_theta_estimates
from .utils import robust_median_spacing

logger = logging.getLogger(__name__)


def detect_nominal(data, params: dict) -> list[dict]:
    """Detect and assign nominal polar-grid coordinates to measured points.

    The nominal-grid step converts measured polar coordinates into records that
    connect each usable detection to a nominal calibration-grid radius and angle.
    The implementation is intentionally organized as orchestration over smaller
    helper modules: grouping, ring assignment, spoke assignment, radial-shift
    diagnostics, and record construction.

    Parameters
    ----------
    data : mapping
        Input unwrapped-grid data containing original point indices, pixel
        coordinates, measured theta values, and measured radii.
    params : dict
        Nominal-grid detection parameters.

    Returns
    -------
    list[dict]
        Nominal assignment records. Each record includes original point index,
        pixel coordinates, measured polar coordinates, detected group indices,
        and assigned nominal coordinates.

    Raises
    ------
    DetectionError
        If the measured circle spacing cannot be estimated.
    """
    logger.info("Detecting nominal grid assignment...")

    base_idx = data[IDX_KEY]
    pixels = data[POINTS_KEY]
    theta = data[THETA_KEY]
    r = data[R_KEY]

    points = np.column_stack([theta, r]).astype(float, copy=False)

    ring_groups, spoke_groups = detect_ring_and_spoke_groups(points, params)

    logger.info(
        "Found %d ring fragments and %d spoke fragments.",
        len(ring_groups),
        len(spoke_groups),
    )

    logger.info("Estimating nominal circle levels with wave correction...")

    ring_levels_px, _wave, _grp_bins = estimate_ring_levels_with_wave_correction(
        points,
        ring_groups,
        bin_width_deg=DEFAULT_PARAMETERS["bin_width_deg"],
        theta_period=360.0,
        min_pts_per_bin=DEFAULT_PARAMETERS["min_pts_per_bin"],
        n_iter=DEFAULT_PARAMETERS["n_wave_iter"],
    )

    spacing_px = robust_median_spacing(
        ring_levels_px,
        min_sep=2.0,
        max_sep=200.0,
    )

    if not np.isfinite(spacing_px) or spacing_px <= 0:
        raise DetectionError("Failed to estimate circle spacing in pixels.")

    logger.info("Estimated circle spacing: %.3f px per %.1f°", spacing_px, DEG_STEP)

    _k_circle, rho_circle = assign_nominal_circles(
        ring_levels_px,
        spacing_px=spacing_px,
    )

    theta_g = spoke_group_theta_estimates(points, spoke_groups)
    _k_spoke, theta_nom, theta0 = assign_nominal_spokes(theta_g, theta0=None)

    logger.info("Chosen spoke offset theta0: %.3f deg", theta0)

    best_shift, shift_scores, _improvement_frac = choose_rigid_circle_shift(
        rho_circle.astype(float),
        ring_levels_px.astype(float),
        min_improvement_frac=0.20,
    )

    if shift_scores:
        if best_shift != 0.0:
            logger.warning(
                "Detected likely rigid circle offset: %+4.1f deg. Applying shift.",
                best_shift,
            )
            rho_circle = rho_circle + best_shift
        else:
            logger.info("No robust rigid circle offset applied.")
    else:
        logger.info("Skipping rigid circle offset check: no valid shift scores.")

    nominal_assignment = build_nominal_assignment_records(
        base_idx=base_idx,
        pixels=pixels,
        points=points,
        ring_groups=ring_groups,
        spoke_groups=spoke_groups,
        nominal_r_by_ring=rho_circle,
        nominal_theta_by_spoke=theta_nom,
    )

    logger.info("Assigned nominal values to %d points.", len(nominal_assignment))

    return nominal_assignment
