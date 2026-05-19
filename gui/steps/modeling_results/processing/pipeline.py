from __future__ import annotations

import logging

from .config import ModelConfig
from .data import GridData
from .fitting import fit_model

logger = logging.getLogger(__name__)


def model_nominal_grid(raw_assignment, params):
    """
    Fit the distortion model from raw nominal-assignment records.
    """
    logger.info("Loading data...")

    data = GridData.from_records(raw_assignment)

    logger.info(f"Loaded {data.x.size} valid points.")  

    config = ModelConfig(
        radial_degree=params["radial-degree"],
        harmonic_radial_degree=params["harmonic-radial-degree"],
        harmonic_order=params["harmonic-order"],
        regularization=params["regularization"],
        fit_constant_terms=params["fit-constant-terms"],
    )

    result, model = fit_model(
        data=data,
        config=config,
        max_nfev=params["max-nfev"],
        outlier_rejection_sigma=params["outlier-rejection-sigma"],
        outlier_rejection_floor_px=params["outlier-rejection-floor-px"],
        min_inlier_fraction=params["min-inlier-fraction"],
    )

    return result, model, data

