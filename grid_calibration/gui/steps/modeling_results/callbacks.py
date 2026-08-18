# grid_calibration/gui/steps/modeling_results/callbacks.py
"""
Interactive Dash callbacks for the modeling-results step.

The callbacks in this module connect the modeling controls to the fitting
pipeline, create diagnostic report products, update the active
:class:`~grid_calibration.gui.session.CalibrationSession`, and emit the shared
step-completion event consumed by the generic pipeline callbacks.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
from dash import Input, Output, State, ctx, no_update
import logging

from ... import ids
from ...server import app
from .plotting import modeling_fig
from .processing import model_nominal_grid, make_report
from .params import DEFAULT_PARAMETERS
from .spec import product_io as modeling_product_io
from ..bootstrapping_grid import product_io as bootstrapping_product_io
from ..bootstrapping_grid.keys import DATA_KEY as BOOTSTRAPPING_DATA_KEY
from .keys import STEP_KEY
from .spec import DATA_KEY, PARAMS_KEY
from ..full_array import product_io as full_array_product_io
from ..full_array.keys import IMAGE_KEY as FULL_ARRAY_IMAGE_KEY
from grid_calibration.calibration import GridCalibration

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
    Output(ids.MODELING_SIGMA_REJECTION_ID, "value"),
    # ---------------------
    Input(ids.RESET_MODELING_BTN_ID, "n_clicks"),
    # ---------------------
    prevent_initial_call=True,
)
def reset_bootstrapping_parameters(
    n_clicks: int,
) -> None:

    if n_clicks == 0:
        return no_update
    # Just return None to reset the pending nominal grid and update the status display
    return (
        DEFAULT_PARAMETERS["radial-degree"],
        DEFAULT_PARAMETERS["harmonic-radial-degree"],
        DEFAULT_PARAMETERS["harmonic-order"],
        DEFAULT_PARAMETERS["outlier-rejection-sigma"],
    )


@app.callback(
    Output(ids.STORE_STEP_RESULT, "data", allow_duplicate=True),
    Output(ids.GRID_GRAPH_ID, "figure", allow_duplicate=True),
    # ---------------------
    Input(ids.MODELING_BTN_ID, "n_clicks"),
    # ---------------------
    State(ids.MODELING_RADIAL_DEGREE_ID, "value"),
    State(ids.MODELING_HARMONIC_RADIAL_DEGREE_ID, "value"),
    State(ids.MODELING_HARMONIC_ORDER_ID, "value"),
    State(ids.MODELING_SIGMA_REJECTION_ID, "value"),
    State(ids.MODELING_PDF_REPORT_CHECKLIST_ID, "value"),
    # ---------------------
    prevent_initial_call=True,
)
def bootstrap_grid(
    n_clicks: int,
    radial_degree: Optional[int],
    harmonic_radial_degree: Optional[int],
    harmonic_order: Optional[int],
    sigma_rejection: Optional[float],
    pdf_report_checklist: Optional[list[str]],
) -> None:
    if n_clicks == 0:
        return no_update

    # copy DEFAULT_PARAMETERS to params and replace values
    # with the ones from the inputs
    params = DEFAULT_PARAMETERS.copy()
    params.update({
        "radial-degree": radial_degree,
        "harmonic-radial-degree": harmonic_radial_degree,
        "harmonic-order": harmonic_order,
        "outlier-rejection-sigma": sigma_rejection,
    })

    bootstrapped_nominal_assignment = bootstrapping_product_io.load()[BOOTSTRAPPING_DATA_KEY]

    out_npz = modeling_product_io.expected_path()
    # keep the same path but change file name 
    pdf_path = out_npz.with_name(out_npz.stem.replace("_modeling_results", "_modeling_report")).with_suffix(".pdf")
    
    fit_result, model, data = model_nominal_grid(bootstrapped_nominal_assignment, params)

    if "generate" in (pdf_report_checklist or []):
        logger.info(f"\nWriting PDF report.")
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
        )

    model_fig = modeling_fig(data, fit_result)

    output_packet = {
        DATA_KEY: fit_result,
        PARAMS_KEY: params,
    }

    modeling_product_io.save(
        **output_packet,
    )

    calibration_path = out_npz.with_name(
        out_npz.stem.replace("_modeling_results", "_calibration")
    ).with_suffix(".npz")
    calibration = GridCalibration.from_fit(
        fit_result=fit_result,
        model=model,
        data=data,
        sensor_shape=_sensor_shape_from_full_array_product(),
    )
    calibration.save(calibration_path)
    logger.info("Wrote portable calibration artifact: %s", calibration_path)

    modeling_product_io.register()

    result = {
        "step": STEP_KEY,
        "status": "completed",
        "request_token": ctx.triggered[0]["prop_id"],
    }

    return result, model_fig
