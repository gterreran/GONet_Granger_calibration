# grid_calibration/gui/steps/nominal_grid/params.py
"""
Default parameter values for nominal-grid assignment.

The values in this module are developer-facing defaults used by the interactive
nominal-grid UI and by the processing pipeline. They are stored alongside the
nominal-grid product so downstream steps can reconstruct how the assignment was
created.
"""


from .keys import PARAMS_KEY

DEFAULT_PARAMETERS = {
    # ring grouping
    "ring_max_dist": 10.0, # max distance in pixels for chaining ring points
    "ring_gate_tol_r": 1.5, # gate tolerance in r for chaining ring points
    "min_ring_group": 150, # minimum points to keep a ring group after chaining

    # spoke grouping
    "spoke_max_dist": 35.0, # max distance in pixels for chaining spoke points
    "spoke_min_dist": 2.0, # minimum increase in r for chaining spoke points
    "spoke_gate_tol_theta": 0.3, # gate tolerance in theta (degrees) for chaining spoke points
    "min_spoke_group": 20, # minimum points to keep a spoke group after chaining

    # ring level estimation
    "bin_width_deg": 30.0, # width of theta bins (degrees) for estimating ring levels and wave
    "min_pts_per_bin": 10, # minimum points in a theta bin to use it for ring level estimation
    "n_wave_iter": 3, # number of iterations to perform for wave correction in ring level estimation
}

def load_parameters() -> dict:
    from ....errors import MissingProductError
    from .spec import product_io

    try:
        return product_io.load()[PARAMS_KEY]
    except MissingProductError:
        return DEFAULT_PARAMETERS.copy()
