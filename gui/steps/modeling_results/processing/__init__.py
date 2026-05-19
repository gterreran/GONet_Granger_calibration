"""Processing helpers for the modeling-results calibration step.

This package preserves the public API previously provided by
``modeling_results.processing`` while separating the implementation into
focused modules:

``data``
    Input record parsing and :class:`GridData`.
``model``
    The polar radial/tangential distortion model.
``fitting``
    Least-squares optimization and outlier refitting.
``reporting``
    Matplotlib/PDF diagnostic report generation.
``pipeline``
    Public orchestration entry point.
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

