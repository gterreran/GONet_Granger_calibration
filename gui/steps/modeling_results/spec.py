from __future__ import annotations
from ...workflow.specs import PipelineStepSpec, ProductKind
from .plotting import plot_modeling_results, initialize_modeling_results

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

pipeline_step = PipelineStepSpec.from_dict({
    "key": "modeling-results",
    "label": "Modeling",
    "order": 7,
    "mode": "interactive",
    "product": {
        "suffix": "_modeling_results.npz",
        "kind": ProductKind.SINGLETON,
    },
    "viewer_func": plot_modeling_results,
    "initialize_interactive_state": initialize_modeling_results,
})