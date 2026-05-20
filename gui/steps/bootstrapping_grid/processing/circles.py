"""
Circle-assignment helpers for bootstrapped grid records.

This module estimates missing nominal radii along assigned spokes, rejects
circle outliers, and assigns circle-only points using recovered circle models.
"""

from __future__ import annotations

import logging

import numpy as np

from .containers import DenseGrid, GridData
from .geometry import point_radius_from_center, xy_to_polar_about_center
from ..params import DEFAULT_PARAMETERS
from .....errors import DetectionError

logger = logging.getLogger(__name__)


def fit_spoke_radius_to_nominal_r(
    nominal_points: GridData,
    mask: np.ndarray,
    center_xy: np.ndarray,
    poly_degree: int,
) -> np.poly1d:
    """
    Fit nominal radius as a polynomial of pixel radius along one spoke.
    """
    valid = mask & np.isfinite(nominal_points.r_nom_deg)
    if np.sum(valid) < 3:
        raise DetectionError("Not enough points to fit spoke radius model.")

    r_pix = point_radius_from_center(nominal_points.x[valid], nominal_points.y[valid], center_xy)
    r_nom = nominal_points.r_nom_deg[valid]

    order = np.argsort(r_pix)
    r_pix = r_pix[order]
    r_nom = r_nom[order]

    # Anchor spokes at the center. This is especially important for central tiers.
    r_pix = np.concatenate([[0.0], r_pix])
    r_nom = np.concatenate([[0.0], r_nom])

    deg = min(int(poly_degree), max(1, r_pix.size - 1))
    coeff = np.polyfit(r_pix, r_nom, deg)
    return np.poly1d(coeff)


def fit_circle_radial_model(
    theta_deg: np.ndarray,
    r_pix: np.ndarray,
    n_harmonics: int = DEFAULT_PARAMETERS["circle_fourier_harmonics"],
) -> np.ndarray:
    """Fit a Fourier model ``r_pix(theta)`` for one circle."""
    theta_rad = np.deg2rad(theta_deg)
    cols = [np.ones_like(theta_rad)]
    for k in range(1, n_harmonics + 1):
        cols.append(np.cos(k * theta_rad))
        cols.append(np.sin(k * theta_rad))
    A = np.column_stack(cols)
    coeffs, *_ = np.linalg.lstsq(A, r_pix, rcond=None)
    return coeffs


def eval_circle_radial_model(
    theta_deg: np.ndarray,
    coeffs: np.ndarray,
    n_harmonics: int = DEFAULT_PARAMETERS["circle_fourier_harmonics"],
) -> np.ndarray:
    """Evaluate a Fourier circle-radius model."""
    theta_rad = np.deg2rad(theta_deg)
    cols = [np.ones_like(theta_rad)]
    for k in range(1, n_harmonics + 1):
        cols.append(np.cos(k * theta_rad))
        cols.append(np.sin(k * theta_rad))
    return np.column_stack(cols) @ coeffs


def revert_circle_outliers(
    nominal_points: GridData,
    center_xy: np.ndarray,
    r_deg: float,
    mad_threshold: float = DEFAULT_PARAMETERS["circle_outlier_mad_threshold"],
) -> int:
    """
    Remove inconsistent assignments on one circle using a Fourier circle model.
    """
    n_harmonics = DEFAULT_PARAMETERS["circle_fourier_harmonics"]   
    total = 0

    while True:
        assigned = nominal_points.r_nom_deg == r_deg

        if np.sum(assigned) < 2 * n_harmonics + 2:
            return total

        theta_nom = nominal_points.theta_nom_deg[assigned]
        valid = np.isfinite(theta_nom)

        if np.sum(valid) < 2 * n_harmonics + 2:
            return total

        idx_assigned = nominal_points.idx[assigned][valid]
        theta_nom = theta_nom[valid]
        x = nominal_points.x[assigned][valid]
        y = nominal_points.y[assigned][valid]

        order = np.argsort(theta_nom)
        idx_assigned = idx_assigned[order]
        theta_nom = theta_nom[order]
        r_pix = point_radius_from_center(x[order], y[order], center_xy)

        coeffs = fit_circle_radial_model(theta_nom, r_pix)
        residuals = np.abs(r_pix - eval_circle_radial_model(theta_nom, coeffs))
        mad = np.median(residuals)

        if mad <= 0:
            return total

        outliers = residuals > mad_threshold * mad
        bad_idxs = idx_assigned[outliers]

        if bad_idxs.size == 0:
            return total

        for idx, res in zip(bad_idxs, residuals[outliers], strict=True):
            logger.info(
                f"  Reverting idx={idx} assigned to r={r_deg:.1f}: "
                f"residual={res:.1f}px (MAD={mad:.1f}px)"
            )
            nominal_points.set_radius(int(idx), np.nan)
            total += 1


def assign_intersection_radii_from_spokes(
    nominal_points: GridData,
    center_xy: np.ndarray,
    circle_snap_tol_deg: float,
    poly_degree: int,
) -> GridData:
    """
    Bootstrap missing circle labels for spoke-assigned points.

    The algorithm grows known circles inward and outward from the current set of
    confidently labeled circles.
    """
    unique_spokes = np.unique(nominal_points.theta_nom_deg[np.isfinite(nominal_points.theta_nom_deg)])
    unique_rings = np.sort(np.unique(nominal_points.r_nom_deg[np.isfinite(nominal_points.r_nom_deg)]))

    while True:
        if unique_rings.size == 0:
            break

        inner_ring = float(np.min(unique_rings))
        next_upper_rings = [r for r in np.arange(inner_ring, DEFAULT_PARAMETERS["max_nominal_r_deg"] + DEFAULT_PARAMETERS["grid_step_deg"], DEFAULT_PARAMETERS["grid_step_deg"])
                            if not np.any(np.isclose(unique_rings, r))]

        next_lower = None if np.isclose(inner_ring, DEFAULT_PARAMETERS["grid_step_deg"]) else inner_ring - DEFAULT_PARAMETERS["grid_step_deg"]
        next_upper = None if len(next_upper_rings) == 0 else float(next_upper_rings[0])

        logger.info(f"Next lower circle: {next_lower}, next upper circle: {next_upper}")

        if next_lower is None and next_upper is None:
            break

        target_rings = [r for r in (next_lower, next_upper) if r is not None]

        for theta in unique_spokes:
            mask = nominal_points.theta_nom_deg == theta
            try:
                spoke_model = fit_spoke_radius_to_nominal_r(nominal_points, mask, center_xy, poly_degree)
            except ValueError:
                continue

            distances = point_radius_from_center(nominal_points.x[mask], nominal_points.y[mask], center_xy)
            local_idx = np.where(mask)[0]
            order = np.argsort(distances)
            distances = distances[order]
            local_idx = local_idx[order]

            r_est = spoke_model(distances)
            snapped = DEFAULT_PARAMETERS["grid_step_deg"] * np.round(r_est / DEFAULT_PARAMETERS["grid_step_deg"])

            for r in target_rings:
                candidates = np.where((np.abs(r_est - snapped) <= circle_snap_tol_deg) & np.isclose(snapped, r))[0]

                if candidates.size == 0:
                    continue

                # Choose the candidate whose model estimate is closest to the target radius.
                best_local = candidates[np.argmin(np.abs(r_est[candidates] - r))]
                pos = local_idx[best_local]

                existing = nominal_points.r_nom_deg[pos]
                if np.isfinite(existing) and not np.isclose(existing, r):
                    logger.info(
                        f"  Warning: idx={nominal_points.idx[pos]} has conflicting "
                        f"circle {existing:.1f} vs {r:.1f}; keeping existing."
                    )
                    continue

                nominal_points.r_nom_deg[pos] = r

        reverted = 0
        for r in target_rings:
            reverted += revert_circle_outliers(nominal_points, center_xy, r)

        if reverted > 0:
            logger.info(f"  Reverted {reverted} point(s).")

        if next_lower is not None:
            unique_rings = np.append(unique_rings, next_lower)
        if next_upper is not None:
            unique_rings = np.append(unique_rings, next_upper)

        unique_rings = np.sort(np.unique(unique_rings))

    return nominal_points


def assign_circle_only_points(
    nominal_points: GridData,
    dense_points: DenseGrid,
    center_xy: np.ndarray,
) -> GridData:
    """
    Assign circle-only dense points using Fourier models of recovered circles.
    """
    theta_all, r_all = xy_to_polar_about_center(dense_points.x, dense_points.y, center_xy)
    unique_circles = np.sort(np.unique(nominal_points.r_nom_deg[np.isfinite(nominal_points.r_nom_deg)]))

    for r_deg in unique_circles:
        mask = nominal_points.r_nom_deg == r_deg
        valid = np.isfinite(nominal_points.theta_nom_deg[mask])

        if np.sum(valid) < 2 * DEFAULT_PARAMETERS["circle_fourier_harmonics"] + 2:
            continue

        theta_nom = nominal_points.theta_nom_deg[mask][valid]
        x = nominal_points.x[mask][valid]
        y = nominal_points.y[mask][valid]
        r_pix = point_radius_from_center(x, y, center_xy)

        coeffs = fit_circle_radial_model(theta_nom, r_pix)
        residual = np.abs(r_pix - eval_circle_radial_model(theta_nom, coeffs))
        mad = np.median(residual)

        if mad <= 0:
            continue

        unassigned_mask = ~np.isin(dense_points.idx, nominal_points.idx)
        idx_unassigned = dense_points.idx[unassigned_mask]

        r_pred = eval_circle_radial_model(theta_all[unassigned_mask], coeffs)
        good = np.abs(r_all[unassigned_mask] - r_pred) <= DEFAULT_PARAMETERS["circle_only_mad_factor"] * mad

        for idx in idx_unassigned[good]:
            nominal_points.add_or_update(
                idx=int(idx),
                x=float(dense_points.x[idx]),
                y=float(dense_points.y[idx]),
                theta_nom_deg=None,
                r_nom_deg=float(r_deg),
            )

    return nominal_points
