"""
Least-squares fitting and optional outlier-refit logic for the distortion model.
"""

from __future__ import annotations

import logging

import numpy as np
from scipy.optimize import least_squares

from .config import ModelConfig
from .data import GridData
from .model import PolarDistortionModel
from .results import (
    FitResult,
    FitSummary,
    add_center_to_prediction,
    print_fit_report,
    summarize_fit,
)
from .utils import outlier_threshold_from_residual_norm

logger = logging.getLogger(__name__)


def fit_model(
    data: GridData,
    config: ModelConfig,
    max_nfev: int,
    outlier_rejection_sigma: float | None = None,
    outlier_rejection_floor_px: float = 2.5,
    min_inlier_fraction: float = 0.90,
) -> tuple[FitResult, PolarDistortionModel]:
    """Fit the symmetric and full distortion models."""
    model = PolarDistortionModel(config=config, r_nom_max_deg=float(np.max(data.r_nom_deg)))
    p0 = model.initial_parameters(data)

    logger.info("Initial guess:")
    logger.info(f"  cx     = {p0[0]:.4f} px")
    logger.info(f"  cy     = {p0[1]:.4f} px")
    logger.info(f"  theta0 = {p0[2]:.6f} deg")
    for i, name in enumerate(model.sym_names[3:], start=3):
        logger.info(f"  {name:<6s} = {p0[i]:.6e}")

    logger.info("\nStage 1: fitting symmetric near-equidistant model...")

    # Optimize only the parameters that actually participate in the symmetric
    # stage. The previous implementation passed the entire harmonic parameter
    # vector even though those coefficients were zeroed inside the residual
    # function. With the validated 159-parameter production model that creates
    # a large, unnecessary rank-deficient Jacobian.
    def symmetric_residuals(p_sym_short: np.ndarray) -> np.ndarray:
        p = np.zeros(model.n_total, dtype=float)
        p[: model.n_sym] = p_sym_short
        return model.residuals(p, data, include_field=False)

    res_sym = least_squares(
        fun=symmetric_residuals,
        x0=p0[: model.n_sym],
        loss="soft_l1",
        f_scale=2.0,
        max_nfev=max_nfev,
        verbose=2 if logger.isEnabledFor(logging.DEBUG) else 0,
    )
    p_sym = np.zeros(model.n_total, dtype=float)
    p_sym[: model.n_sym] = np.asarray(res_sym.x, dtype=float)
    pred_sym = add_center_to_prediction(model.predict(p_sym, data), p_sym)
    summary_sym, _ = summarize_fit(data, pred_sym)
    print_fit_report("symmetric model", summary_sym)

    logger.info("\nStage 2: fitting polar radial/tangential harmonic correction...")
    res_full = least_squares(
        fun=lambda p: model.residuals(p, data, include_field=True),
        x0=p_sym,
        loss="soft_l1",
        f_scale=2.0,
        max_nfev=max_nfev,
        verbose=2 if logger.isEnabledFor(logging.DEBUG) else 0,
    )
    p_full = np.array(res_full.x, copy=True)
    pred_full = add_center_to_prediction(model.predict(p_full, data), p_full)
    summary_full_all, details_full = summarize_fit(data, pred_full)
    print_fit_report("full model (all points)", summary_full_all)

    inlier_mask = np.ones(data.x.size, dtype=bool)
    outlier_threshold_px: float | None = None
    summary_full_inliers: FitSummary | None = None

    if outlier_rejection_sigma is not None and outlier_rejection_sigma > 0:
        outlier_threshold_px = outlier_threshold_from_residual_norm(
            residual_norm=details_full["resid_norm"],
            sigma=outlier_rejection_sigma,
            floor_px=outlier_rejection_floor_px,
        )
        inlier_mask = details_full["resid_norm"] <= outlier_threshold_px
        min_inliers = max(1, int(np.ceil(min_inlier_fraction * data.x.size)))

        logger.info("\nOutlier rejection pass:")
        logger.info(f"  threshold       : {outlier_threshold_px:.4f} px")
        logger.info(f"  inliers kept    : {int(np.sum(inlier_mask))} / {data.x.size}")
        logger.info(f"  outliers removed: {int(np.sum(~inlier_mask))}")

        if np.sum(inlier_mask) >= min_inliers and np.any(~inlier_mask):
            data_inliers = data.subset(inlier_mask)
            logger.info("\nStage 3: refitting full model on inliers only...")
            res_refit = least_squares(
                fun=lambda p: model.residuals(p, data_inliers, include_field=True),
                x0=p_full,
                loss="soft_l1",
                f_scale=2.0,
                max_nfev=max_nfev,
                verbose=2 if logger.isEnabledFor(logging.DEBUG) else 0,
            )
            p_full = np.array(res_refit.x, copy=True)
            pred_full = add_center_to_prediction(model.predict(p_full, data), p_full)
            summary_full_all, _ = summarize_fit(data, pred_full)

            pred_full_in = add_center_to_prediction(model.predict(p_full, data_inliers), p_full)
            summary_full_inliers, _ = summarize_fit(data_inliers, pred_full_in)
            print_fit_report("final full model (all points)", summary_full_all)
            print_fit_report("final full model (inliers only)", summary_full_inliers)
        else:
            logger.info("  skipping outlier-refit because too few outliers were found or too many points would be removed.")

    improvement = summary_sym.rms - summary_full_all.rms
    frac = 100.0 * improvement / summary_sym.rms if summary_sym.rms > 0 else 0.0
    logger.info(f"\nRMS improvement: {improvement:.4f} px ({frac:.2f}%)")

    logger.info("\nFinal fitted parameters:")
    for name, value in zip(model.param_names, p_full, strict=True):
        logger.info(f"  {name:<16s} = {value: .8e}")

    result = FitResult(
        params_sym=p_sym,
        params_full=p_full,
        summary_sym=summary_sym,
        summary_full=summary_full_all,
        pred_sym=pred_sym,
        pred_full=pred_full,
        inlier_mask=inlier_mask,
        outlier_threshold_px=outlier_threshold_px,
        n_inliers=int(np.sum(inlier_mask)),
        n_outliers=int(np.sum(~inlier_mask)),
        summary_full_inliers=summary_full_inliers,
    )
    return result, model

