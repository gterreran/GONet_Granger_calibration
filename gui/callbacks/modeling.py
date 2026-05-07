from __future__ import annotations

from typing import Optional

from dash import Input, Output, State, ctx, no_update, html
import logging

import numpy as np
from .. import ids
from ..server import app
from pathlib import Path
from ..plot_utils.plot_modeling import DEFAULT_MODELING_PARAMS, modeling_fig
from ...modeling import model_nominal_grid, make_report
from ...products import ALL_PRODUCTS
from ..session import get_session

logger = logging.getLogger(__name__)

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
        DEFAULT_MODELING_PARAMS["radial-degree"],
        DEFAULT_MODELING_PARAMS["harmonic-radial-degree"],
        DEFAULT_MODELING_PARAMS["harmonic-order"],
        DEFAULT_MODELING_PARAMS["outlier-rejection-sigma"],
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

    # copy DEFAULT_MODELING_PARAMS to params and replace values
    # with the ones from the inputs
    params = DEFAULT_MODELING_PARAMS.copy()
    params.update({
        "radial-degree": radial_degree,
        "harmonic-radial-degree": harmonic_radial_degree,
        "harmonic-order": harmonic_order,
        "outlier-rejection-sigma": sigma_rejection,
    })

    session = get_session(app)
    bootstrapped_nominal_assignment_npz = session.get("bootstrapping-grid")
    result, model, data = model_nominal_grid(bootstrapped_nominal_assignment_npz, params)

    if "generate" in (pdf_report_checklist or []):
        logger.info(f"\nWriting PDF report.")
        make_report(
            pdf_path=session.output_dir / "modeling_report.pdf",
            data=data,
            pred_sym=result.pred_sym,
            pred_full=result.pred_full,
            summary_sym=result.summary_sym,
            summary_full=result.summary_full,
            params_full=result.params_full,
            param_names=model.param_names,
            inlier_mask=result.inlier_mask,
            outlier_threshold_px=result.outlier_threshold_px,
            summary_full_inliers=result.summary_full_inliers,
        )

    model_fig = modeling_fig(data, result)

    out_npz = session.expected_path("modeling-results")

    logger.info(f"Saved nominal grid data to: {out_npz}")
    np.savez_compressed(
        out_npz,
        fit_params=params,
        params_sym=result.params_sym,
        params_full=result.params_full,
        param_names=np.array(model.param_names, dtype=object),
        x_measured=data.x,
        y_measured=data.y,
        r_measured=data.r_meas,
        theta_measured_deg=data.theta_meas_deg,
        r_nominal_deg=data.r_nom_deg,
        theta_nominal_deg=data.theta_nom_deg,
        x_pred_sym=result.pred_sym["x_pred"],
        y_pred_sym=result.pred_sym["y_pred"],
        x_pred_full=result.pred_full["x_pred"],
        y_pred_full=result.pred_full["y_pred"],
        dr=result.pred_full["dr"],
        dtan=result.pred_full["dtan"],
        rho_sym=result.pred_full["rho_sym"],
        rho_full=result.pred_full["rho_full"],
        inlier_mask=result.inlier_mask.astype(np.uint8),
        outlier_threshold_px=np.array(-1.0 if result.outlier_threshold_px is None else result.outlier_threshold_px),
    )

    session.set("modeling-results", out_npz)

    result = {
        "step": "modeling-results",
        "status": "completed",
        "request_token": ctx.triggered[0]["prop_id"],
    }

    return result, model_fig
