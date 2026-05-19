"""Nominal-grid processing package.

This package replaces the former monolithic ``processing.py`` module while
preserving its public API. Importing from
``grid_calibration.gui.steps.nominal_grid.processing`` should continue to expose
``detect_nominal`` and the helper functions that were previously defined in the
single file.
"""

from __future__ import annotations

from .constants import DEG_STEP
from .grouping import (
    chain_groups_closest_neighbor_with_axis_gate,
    detect_ring_and_spoke_groups,
)
from .pipeline import detect_nominal
from .radial_shift import (
    choose_rigid_circle_shift,
    fit_no_intercept_odd_cubic,
    score_circle_shifts,
)
from .records import build_group_lookup, build_nominal_assignment_records
from .rings import (
    assign_nominal_circles,
    estimate_ring_levels_with_wave_correction,
    ring_group_theta_bins,
)
from .spokes import (
    assign_nominal_spokes,
    best_theta_offset,
    spoke_group_theta_estimates,
)
from .utils import (
    circular_mean_deg,
    robust_median_spacing,
    wrap_delta,
    wrap_deg,
)

__all__ = [
    "DEG_STEP",
    "assign_nominal_circles",
    "assign_nominal_spokes",
    "best_theta_offset",
    "build_group_lookup",
    "build_nominal_assignment_records",
    "chain_groups_closest_neighbor_with_axis_gate",
    "choose_rigid_circle_shift",
    "circular_mean_deg",
    "detect_nominal",
    "detect_ring_and_spoke_groups",
    "estimate_ring_levels_with_wave_correction",
    "fit_no_intercept_odd_cubic",
    "ring_group_theta_bins",
    "robust_median_spacing",
    "score_circle_shifts",
    "spoke_group_theta_estimates",
    "wrap_delta",
    "wrap_deg",
]
