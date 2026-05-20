"""
Processing API for the modeling-results calibration step.

The public entry point is
:func:`~grid_calibration.gui.steps.modeling_results.processing.pipeline.model_nominal_grid`,
which is re-exported here together with model, fitting, reporting, and result
container classes.
"""

from .config import ModelConfig
from .data import GridData
from .fitting import fit_model
from .model import PolarDistortionModel
from .pipeline import model_nominal_grid
from .reporting import make_report
from .results import (
    FitResult,
    FitSummary,
    add_center_to_prediction,
    print_fit_report,
    summarize_fit,
)
from .utils import (
    cartesian_center_from_measured_polar,
    circ_median_deg,
    outlier_threshold_from_residual_norm,
    robust_rms,
    wrap_angle_deg,
)

__all__ = [
    "FitResult",
    "FitSummary",
    "GridData",
    "ModelConfig",
    "PolarDistortionModel",
    "add_center_to_prediction",
    "cartesian_center_from_measured_polar",
    "circ_median_deg",
    "fit_model",
    "make_report",
    "model_nominal_grid",
    "outlier_threshold_from_residual_norm",
    "print_fit_report",
    "robust_rms",
    "summarize_fit",
    "wrap_angle_deg",
]

