# grid_calibration/gui/steps/modeling_results/callbacks.py
"""Interactive Dash callbacks for the modeling-results step."""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
from dash import Input, Output, State, ctx, no_update

from grid_calibration.calibration import GridCalibration

from ... import ids
from ...server import app
from ..bootstrapping_grid import product_io as bootstrapping_product_io
from ..bootstrapping_grid.keys import DATA_KEY as BOOTSTRAPPING_DATA_KEY
from ..full_array import product_io as full_array_product_io
from ..full_array.keys import IMAGE_KEY as FULL_ARRAY_IMAGE_KEY
from .keys import STEP_KEY
from .params import DEFAULT_PARAMETERS
from .plotting import modeling_fig
from .processing import make_report, model_nominal_grid
from .spec import DATA_KEY, PARAMS_KEY
from .spec import product_io as modeling_product_io

logger = logging.getLogger(__name__)


def _sensor_shape_from_full_array_product() -> tuple[int, int]:
    """Return ``(height, width)`` in the coordinate system used by the fit."""
    paths = full_array_product_io.get()
    if not paths:
        raise ValueError(
            "Cannot export the portable calibration artifact because no "
            "full-array products are registered."
        )

    path = paths[0]
    image = np.asarray(full_array_product_io.load(path)[FULL_ARRAY_IMAGE_KEY])
    if image.ndim != 2:
        raise ValueError(
            f"Full-array product {path} has non-2D image shape {image.shape}."
        )
    return int(image.shape[0]), int(image.shape[1])


@app.callback(
    Output(ids.MODELING_RADIAL_DEGREE_ID, "value"),
    Output(ids.MODELING_HARMONIC_RADIAL_DEGREE_ID, "value"),
    Output(ids.MODELING_HARMONIC_ORDER_ID, "value"),
    Output(ids.MODELING_TANGENTIAL_HARMONIC_RADIAL_DEGREE_ID, "value"),
    Output(ids.MODELING_TANGENTIAL_HARMONIC_ORDER_ID, "value"),
    Output(ids.MODELING_TWIST_KIND_ID, "value"),
    Output(ids.MODELING_TWIST_SCALE_ID, "value"),
    Output(ids.MODELING_SIGMA_REJECTION_ID, "value"),
    Input(ids.RESET_MODELING_BTN_ID, "n_clicks"),
    prevent_initial_call=True,
)
def reset_modeling_parameters(n_clicks: int):
    if n_clicks == 0:
        return (no_update,) * 8
    return (
        DEFAULT_PARAMETERS["radial-degree"],
        DEFAULT_PARAMETERS["radial-harmonic-radial-degree"],
        DEFAULT_PARAMETERS["radial-harmonic-order"],
        DEFAULT_PARAMETERS["tangential-harmonic-radial-degree"],
        DEFAULT_PARAMETERS["tangential-harmonic-order"],
        DEFAULT_PARAMETERS["axisymmetric-twist-kind"],
        DEFAULT_PARAMETERS["axisymmetric-twist-scale-deg"],
        DEFAULT_PARAMETERS["outlier-rejection-sigma"],
    )


@app.callback(
    Output(ids.STORE_STEP_RESULT, "data", allow_duplicate=True),
    Output(ids.GRID_GRAPH_ID, "figure", allow_duplicate=True),
    Input(ids.MODELING_BTN_ID, "n_clicks"),
    State(ids.MODELING_RADIAL_DEGREE_ID, "value"),
    State(ids.MODELING_HARMONIC_RADIAL_DEGREE_ID, "value"),
    State(ids.MODELING_HARMONIC_ORDER_ID, "value"),
    State(ids.MODELING_TANGENTIAL_HARMONIC_RADIAL_DEGREE_ID, "value"),
    State(ids.MODELING_TANGENTIAL_HARMONIC_ORDER_ID, "value"),
    State(ids.MODELING_TWIST_KIND_ID, "value"),
    State(ids.MODELING_TWIST_SCALE_ID, "value"),
    State(ids.MODELING_SIGMA_REJECTION_ID, "value"),
    State(ids.MODELING_PDF_REPORT_CHECKLIST_ID, "value"),
    prevent_initial_call=True,
)
def bootstrap_grid(
    n_clicks: int,
    radial_degree: Optional[int],
    radial_harmonic_radial_degree: Optional[int],
    radial_harmonic_order: Optional[int],
    tangential_harmonic_radial_degree: Optional[int],
    tangential_harmonic_order: Optional[int],
    twist_kind: Optional[str],
    twist_scale_deg: Optional[float],
    sigma_rejection: Optional[float],
    pdf_report_checklist: Optional[list[str]],
):
    if n_clicks == 0:
        return no_update

    params = DEFAULT_PARAMETERS.copy()
    params.update(
        {
            "radial-degree": radial_degree,
            "radial-harmonic-radial-degree": radial_harmonic_radial_degree,
            "radial-harmonic-order": radial_harmonic_order,
            "tangential-harmonic-radial-degree": (
                tangential_harmonic_radial_degree
            ),
            "tangential-harmonic-order": tangential_harmonic_order,
            "axisymmetric-twist-kind": twist_kind,
            "axisymmetric-twist-scale-deg": twist_scale_deg,
            "outlier-rejection-sigma": sigma_rejection,
        }
    )

    bootstrapped_nominal_assignment = bootstrapping_product_io.load()[
        BOOTSTRAPPING_DATA_KEY
    ]

    out_npz = modeling_product_io.expected_path()
    pdf_path = out_npz.with_name(
        out_npz.stem.replace("_modeling_results", "_modeling_report")
    ).with_suffix(".pdf")

    fit_result, model, data = model_nominal_grid(
        bootstrapped_nominal_assignment, params
    )

    # Build the portable evaluator before report generation so the PDF can use
    # the exact same public inverse transform that downstream applications use.
    calibration_path = out_npz.with_name(
        out_npz.stem.replace("_modeling_results", "_calibration")
    ).with_suffix(".npz")
    calibration = GridCalibration.from_fit(
        fit_result=fit_result,
        model=model,
        data=data,
        sensor_shape=_sensor_shape_from_full_array_product(),
        inverse_validation_max_r_deg=float(
            params["inverse-validation-max-r-deg"]
        ),
    )

    if "generate" in (pdf_report_checklist or []):
        logger.info("Writing PDF report.")
        make_report(
            pdf_path=pdf_path,
            data=data,
            pred_sym=fit_result.pred_sym,
            pred_full=fit_result.pred_full,
            summary_sym=fit_result.summary_sym,
            summary_full=fit_result.summary_full,
            params_full=fit_result.params_full,
            param_names=model.param_names,
            inlier_mask=fit_result.inlier_mask,
            outlier_threshold_px=fit_result.outlier_threshold_px,
            summary_full_inliers=fit_result.summary_full_inliers,
            model=model,
            calibration=calibration,
            inverse_validation_max_r_deg=float(
                params["inverse-validation-max-r-deg"]
            ),
        )

    model_fig = modeling_fig(data, fit_result)

    output_packet = {DATA_KEY: fit_result, PARAMS_KEY: params}
    modeling_product_io.save(**output_packet)

    calibration.save(calibration_path)
    logger.info("Wrote portable calibration artifact: %s", calibration_path)

    modeling_product_io.register()

    result = {
        "step": STEP_KEY,
        "status": "completed",
        "request_token": ctx.triggered[0]["prop_id"],
    }
    return result, model_fig
