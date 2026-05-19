"""Bootstrapping-grid processing package.

This package preserves the public API that used to live in
``bootstrapping_grid.processing`` while splitting the implementation into
focused modules:

- ``containers`` for mutable assignment tables and result dataclasses.
- ``geometry`` for shared coordinate helpers.
- ``spokes`` for spoke spline fitting and spoke bootstrapping.
- ``circles`` for circle-label propagation and Fourier circle models.
- ``tiers`` for parallel spoke-tier execution.
- ``records`` for output conversion.
- ``pipeline`` for top-level orchestration.
"""

from __future__ import annotations

from .containers import DenseGrid, GridData, SpokeBootstrapResult
from .geometry import load_center, point_radius_from_center, xy_to_polar_about_center
from .spokes import (
    angle_deg_between,
    bootstrap_spoke_pair,
    candidate_score,
    choose_inward_candidate,
    choose_outward_candidate,
    deduplicate_ordered_points,
    estimate_inner_cutoff_pix,
    fit_parametric_spoke_spline,
    get_inner_endpoint,
    get_outer_endpoint,
    order_seed_points,
    project_points_to_spline,
    sample_spline,
    signed_axis_coordinate,
    spoke_min_nominal_r,
    tangent_from_curve_samples,
    unit_direction_from_seed,
)
from .tiers import build_spoke_tiers, run_spoke_tier
from .circles import (
    assign_circle_only_points,
    assign_intersection_radii_from_spokes,
    eval_circle_radial_model,
    fit_circle_radial_model,
    fit_spoke_radius_to_nominal_r,
    revert_circle_outliers,
)
from .records import build_output_records
from .pipeline import bootstrapping_from_nominal

__all__ = ['DenseGrid', 'GridData', 'SpokeBootstrapResult', 'load_center', 'point_radius_from_center', 'xy_to_polar_about_center', 'spoke_min_nominal_r', 'build_spoke_tiers', 'unit_direction_from_seed', 'signed_axis_coordinate', 'order_seed_points', 'deduplicate_ordered_points', 'fit_parametric_spoke_spline', 'sample_spline', 'project_points_to_spline', 'tangent_from_curve_samples', 'angle_deg_between', 'get_inner_endpoint', 'get_outer_endpoint', 'estimate_inner_cutoff_pix', 'candidate_score', 'choose_inward_candidate', 'choose_outward_candidate', 'bootstrap_spoke_pair', 'fit_spoke_radius_to_nominal_r', 'fit_circle_radial_model', 'eval_circle_radial_model', 'revert_circle_outliers', 'assign_intersection_radii_from_spokes', 'assign_circle_only_points', 'run_spoke_tier', 'build_output_records', 'bootstrapping_from_nominal']
