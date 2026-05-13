# grid_calibration/gui/steps/modeling_results/params.py

from .keys import PARAMS_KEY

DEFAULT_PARAMETERS = {
    "regularization": 1e-3, # Ridge penalty applied to harmonic coefficients.
    "fit-constant-terms": False, # Whether to include n=0 terms in the harmonic correction fields.
    "max-nfev": 3000, # Maximum number of function evaluations per optimization stage.
    "outlier-rejection-floor-px": 2.5, # Absolute minimum residual threshold in pixels for outlier rejection.
    "min-inlier-fraction": 0.90, # Minimum fraction of points that must remain to perform the outlier-refit stage.

    #interactive parameters
    "radial-degree": 4, # Degree of the symmetric radial polynomial.
    "harmonic-radial-degree": 3, # Degree of the radius polynomial used in the harmonic correction.
    "harmonic-order": 4, # Maximum Fourier harmonic order used in the correction fields.
    "outlier-rejection-sigma": 4.5, # If >0, reject points with residual norm above median + sigma*MAD after the first full fit.
}

def load_parameters() -> dict:
    from ....errors import MissingProductError
    from .spec import product_io

    try:
        return product_io.load()[PARAMS_KEY]
    except MissingProductError:
        return DEFAULT_PARAMETERS.copy()