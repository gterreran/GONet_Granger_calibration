# grid_calibration/gui/steps/bootstrapping_grid/params.py
"""
Default parameters for bootstrapping-grid processing.

These parameters control spoke growth, circle assignment, outlier rejection, and
parallel execution behavior. They are developer-facing defaults used by the
interactive controls and saved alongside the generated product.
"""


from .keys import PARAMS_KEY

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

def load_parameters() -> dict:
    from ....errors import MissingProductError
    from .spec import product_io

    try:
        return product_io.load()[PARAMS_KEY]
    except MissingProductError:
        return DEFAULT_PARAMETERS.copy()
