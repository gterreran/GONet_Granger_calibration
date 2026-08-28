"""Top-level modeling-results processing pipeline."""

from __future__ import annotations

import logging

from .config import ModelConfig
from .data import GridData
from .fitting import fit_model

logger = logging.getLogger(__name__)


def model_nominal_grid(raw_assignment, params):
    """Fit the distortion model from raw nominal-assignment records."""
    logger.info("Loading data...")
    data = GridData.from_records(raw_assignment)
    logger.info("Loaded %d valid points.", data.x.size)

    config = ModelConfig(
        radial_degree=int(params["radial-degree"]),
        radial_harmonic_radial_degree=int(
            params["radial-harmonic-radial-degree"]
        ),
        radial_harmonic_order=int(params["radial-harmonic-order"]),
        tangential_harmonic_radial_degree=int(
            params["tangential-harmonic-radial-degree"]
        ),
        tangential_harmonic_order=int(params["tangential-harmonic-order"]),
        axisymmetric_twist_kind=str(params["axisymmetric-twist-kind"]),
        axisymmetric_twist_scale_deg=float(
            params["axisymmetric-twist-scale-deg"]
        ),
        regularization=float(params["regularization"]),
        fit_constant_terms=bool(params["fit-constant-terms"]),
    )

    result, model = fit_model(
        data=data,
        config=config,
        max_nfev=int(params["max-nfev"]),
        outlier_rejection_sigma=float(params["outlier-rejection-sigma"]),
        outlier_rejection_floor_px=float(params["outlier-rejection-floor-px"]),
        min_inlier_fraction=float(params["min-inlier-fraction"]),
    )
    return result, model, data
