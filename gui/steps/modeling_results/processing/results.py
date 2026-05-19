from __future__ import annotations

from dataclasses import dataclass
import logging

import numpy as np

from .data import GridData
from .utils import robust_rms

logger = logging.getLogger(__name__)

@dataclass
class FitSummary:
    """Summary of fit quality."""

    rms: float
    median: float
    p95: float
    max_abs: float

@dataclass
class FitResult:
    """Container for optimization outputs."""

    params_sym: np.ndarray
    params_full: np.ndarray
    summary_sym: FitSummary
    summary_full: FitSummary
    pred_sym: dict[str, np.ndarray]
    pred_full: dict[str, np.ndarray]
    inlier_mask: np.ndarray
    outlier_threshold_px: float | None
    n_inliers: int
    n_outliers: int
    summary_full_inliers: FitSummary | None = None


def summarize_fit(data: GridData, pred: dict[str, np.ndarray]) -> tuple[FitSummary, dict[str, np.ndarray]]:
    """Compute summary diagnostics for a fit."""
    rx = data.x - pred["x_pred"]
    ry = data.y - pred["y_pred"]
    rvec = np.hypot(rx, ry)

    summary = FitSummary(
        rms=robust_rms(rvec),
        median=float(np.median(rvec)),
        p95=float(np.percentile(rvec, 95.0)),
        max_abs=float(np.max(rvec)),
    )
    details = {
        "resid_x": rx,
        "resid_y": ry,
        "resid_norm": rvec,
    }
    return summary, details


def add_center_to_prediction(pred: dict[str, np.ndarray], params: np.ndarray) -> dict[str, np.ndarray]:
    """Return a copy of the prediction dictionary augmented with center terms."""
    out = dict(pred)
    out["cx"] = np.full_like(pred["x_pred"], params[0], dtype=float)
    out["cy"] = np.full_like(pred["y_pred"], params[1], dtype=float)
    out["theta0_deg"] = np.full_like(pred["x_pred"], params[2], dtype=float)
    return out


def print_fit_report(label: str, summary: FitSummary) -> None:
    """Print a compact fit report to the terminal."""
    logger.info(f"\n[{label}]")
    logger.info(f"  RMS residual    : {summary.rms:10.4f} px")
    logger.info(f"  Median residual : {summary.median:10.4f} px")
    logger.info(f"  95th percentile : {summary.p95:10.4f} px")
    logger.info(f"  Max residual    : {summary.max_abs:10.4f} px")

