from __future__ import annotations
from ...workflow.specs import PipelineStepSpec, ProductKind
from .plotting import plot_bootstrapping_grid, initialize_bootstrapping_grid

DEFAULT_PARAMETERS = {
    "grid_step_deg": 2.5,
    "max_nominal_r_deg": 90.0,
    "spoke_initial_pull_tol_px": 2.5,
    "spoke_extrap_tol_px": 3.0,

    "spoke_spline_smoothing": 2.0,
    "spoke_sample_count": 1200,
    "max_growth_steps": 200,

    "inner_cutoff_margin_deg": 2.0,
    "inner_cutoff_poly_degree": 2,

    "inward_aperture_deg": 20.0,
    "outward_aperture_deg": 12.0,
    "outward_perp_tol_px": 2.0,
    "outward_forward_min_px": 0.5,

    "ambiguity_ratio_tol": 1.10,
    "ambiguity_score_tol": 0.12,
    "ambiguity_point_sep_px": 3.0,

    "circle_outlier_mad_threshold": 5.0,
    "circle_fourier_harmonics": 3,
    "circle_only_mad_factor": 5.0,

    #intercative parameters
    "spoke_final_tol_px": 3.0,
    "circle_snap_tol_deg": 0.5,
    "circle_fit_poly_degree": 7,
    "max_workers": 1,

}

pipeline_step = PipelineStepSpec.from_dict({
    "key": "bootstrapping-grid",
    "label": "Bootstrapping grids",
    "order": 6,
    "mode": "interactive",
    "product": {
        "suffix": "_bootstrapped_grid.npz",
        "kind": ProductKind.SINGLETON,
    },
    "viewer_func": plot_bootstrapping_grid,
    "initialize_interactive_state": initialize_bootstrapping_grid,
})