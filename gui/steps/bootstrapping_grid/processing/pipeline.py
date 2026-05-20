"""
Top-level bootstrapping-grid processing pipeline.

The pipeline orchestrates dense-grid loading, spoke bootstrapping, circle
assignment, cleanup, and conversion into distortion-model-ready records.
"""

from __future__ import annotations

import logging
import os

import numpy as np

from .....errors import DetectionError
from .containers import DenseGrid, GridData, SpokeBootstrapResult
from .geometry import load_center, point_radius_from_center
from .spokes import spoke_min_nominal_r
from .circles import (
    assign_circle_only_points,
    assign_intersection_radii_from_spokes,
    fit_spoke_radius_to_nominal_r,
)
from .records import build_output_records
from .tiers import build_spoke_tiers, run_spoke_tier
from ..params import DEFAULT_PARAMETERS

logger = logging.getLogger(__name__)


def bootstrapping_from_nominal(
    nominal_assignment: list[dict],
    averaged_grid: np.ndarray,
    center_xy: dict[str, float],
    params: dict | None = None,
):
    
    params = DEFAULT_PARAMETERS.copy() if params is None else params

    max_workers = int(params["max_workers"])
    if max_workers < 1:
        max_workers = max(1, (os.cpu_count() or 2) - 1)


    all_points = DenseGrid.load(averaged_grid)
    logger.info(f"  loaded {all_points.idx.size} dense points")

    nominal_points = GridData.load(nominal_assignment)
    logger.info(f"  loaded {nominal_points.idx.size} labeled points")

    center_xy = load_center(center_xy)

    assigned_spoke_deg = np.full(all_points.idx.size, -1.0, dtype=float)
    for pos, idx in enumerate(nominal_points.idx):
        if np.isfinite(nominal_points.theta_nom_deg[pos]):
            assigned_spoke_deg[int(idx)] = nominal_points.theta_nom_deg[pos]

    spoke_results: list[SpokeBootstrapResult] = []

    for i_tier, spoke_group in enumerate(build_spoke_tiers(), start=1):
        logger.info(f"\n=== Processing spoke tier {i_tier} ({len(spoke_group)} spoke pairs) ===")
        tier_results = run_spoke_tier(
            spoke_group=spoke_group,
            nominal_points=nominal_points,
            dense_points=all_points,
            center_xy=center_xy,
            assigned_spoke_deg=assigned_spoke_deg,
            max_workers=max_workers,
            spoke_tol_px=params["spoke_final_tol_px"],
        )

        for result in tier_results:
            assigned_spoke_deg[result.assigned_idx] = result.spoke_deg
            spoke_results.append(result)

            logger.info(
                f"  spoke {result.spoke_deg:5.1f}/{result.opposite_deg:5.1f}: "
                f"assigned={result.assigned_idx.size:4d}, "
                f"in={result.inward_growth_steps:3d}, out={result.outward_growth_steps:3d}"
            )

            for i, idx in enumerate(result.assigned_idx):
                if result.assigned_side[i] == "main":
                    theta = result.spoke_deg
                elif result.assigned_side[i] == "opp":
                    theta = result.opposite_deg
                else:
                    continue

                if nominal_points.has_idx(int(idx)):
                    existing = nominal_points.get_theta(int(idx))
                    if np.isfinite(existing) and not np.isclose(existing, theta):
                        raise DetectionError(
                            f"Assigned spoke angle {theta} does not match existing "
                            f"nominal angle {existing} for idx={idx}."
                        )
                    nominal_points.set_theta(int(idx), theta)
                else:
                    nominal_points.append(
                        idx=int(idx),
                        x=float(all_points.x[idx]),
                        y=float(all_points.y[idx]),
                        theta_nom_deg=float(theta),
                        r_nom_deg=np.nan,
                    )

    # Sanity-clean points whose implied nominal radius is outside the expected
    # radial support of their spoke.
    logger.info("\nCleaning spoke assignments outside expected radial support...")
    for spoke_deg in np.unique(nominal_points.theta_nom_deg[np.isfinite(nominal_points.theta_nom_deg)]):
        mask = nominal_points.theta_nom_deg == spoke_deg
        try:
            spoke_model = fit_spoke_radius_to_nominal_r(nominal_points, mask, center_xy, params["circle_fit_poly_degree"])
        except (ValueError, DetectionError):
            continue

        distances = point_radius_from_center(nominal_points.x[mask], nominal_points.y[mask], center_xy)
        r_est = spoke_model(distances)
        bad = (r_est < spoke_min_nominal_r(spoke_deg) - 1.0) | (r_est > params["max_nominal_r_deg"] + 1.0)

        for idx in nominal_points.idx[mask][bad]:
            logger.info(f"  clearing idx={idx} on spoke {spoke_deg:.1f}: implied r outside valid range")
            nominal_points.clear_assignment(int(idx))

    logger.info("\nBootstrapping circle labels from spoke-assigned points...")
    nominal_points = assign_intersection_radii_from_spokes(
        nominal_points=nominal_points,
        center_xy=center_xy,
        circle_snap_tol_deg=params["circle_snap_tol_deg"],
        poly_degree=params["circle_fit_poly_degree"],
    )

    logger.info("\nAssigning circle-only points...")
    nominal_points = assign_circle_only_points(
        nominal_points=nominal_points,
        dense_points=all_points,
        center_xy=center_xy,
    )

    bootstrapped_nominal_assignment = build_output_records(nominal_points, center_xy)

    return bootstrapped_nominal_assignment
