from __future__ import annotations

from typing import Optional

from dash import Input, Output, State, ctx, no_update, html
import logging

import numpy as np
from ... import ids
from ...server import app
from .plotting import bootstrapping_fig
from .processing import bootstrapping_from_nominal
from .spec import DEFAULT_PARAMETERS

logger = logging.getLogger(__name__)

@app.callback(
    Output(ids.BOOTSTRAPPING_SPOKE_TOL_ID, "value"),
    Output(ids.BOOTSTRAPPING_CIRCLE_TOL_ID, "value"),
    Output(ids.BOOTSTRAPPING_CIRCLE_POLY_DEGREE_ID, "value"),
    Output(ids.BOOTSTRAPPING_PARALLEL_WORKERS_ID, "value"),
    # ---------------------
    Input(ids.RESET_BOOTSTRAPPING_BTN_ID, "n_clicks"),
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
        DEFAULT_PARAMETERS["spoke_final_tol_px"],
        DEFAULT_PARAMETERS["circle_snap_tol_deg"],
        DEFAULT_PARAMETERS["circle_fit_poly_degree"],
        DEFAULT_PARAMETERS["max_workers"],
    )


@app.callback(
    Output(ids.STORE_STEP_RESULT, "data", allow_duplicate=True),
    Output(ids.GRID_GRAPH_ID, "figure", allow_duplicate=True),
    Output(ids.BOOTSTRAPPING_STATUS_ID, "children", allow_duplicate=True),
    # ---------------------
    Input(ids.BOOTSTRAPPING_BTN_ID, "n_clicks"),
    # ---------------------
    State(ids.BOOTSTRAPPING_SPOKE_TOL_ID, "value"),
    State(ids.BOOTSTRAPPING_CIRCLE_TOL_ID, "value"),
    State(ids.BOOTSTRAPPING_CIRCLE_POLY_DEGREE_ID, "value"),
    State(ids.BOOTSTRAPPING_PARALLEL_WORKERS_ID, "value"),
    # ---------------------
    prevent_initial_call=True,
)
def bootstrap_grid(
    n_clicks: int,
    spoke_final_tol_px: Optional[float],
    circle_snap_tol_deg: Optional[float],
    circle_fit_poly_degree: Optional[int],
    max_workers: Optional[int],
) -> None:
    if n_clicks == 0:
        return no_update

    # copy DEFAULT_PARAMETERS to params and replace values
    # with the ones from the inputs
    params = DEFAULT_PARAMETERS.copy()
    params.update({
        "spoke_final_tol_px": spoke_final_tol_px,
        "circle_snap_tol_deg": circle_snap_tol_deg,
        "circle_fit_poly_degree": circle_fit_poly_degree,
        "max_workers": max_workers,
    })
    from ...session import get_session
    session = get_session()
    nominal_assignment_npz = session.get("nominal-grid")
    averaged_grid_npz = session.get("averaged-grid")
    center_xy = np.load(session.get("unwrapped-grid"), allow_pickle=True)["center"].item()
    bootstrapped_nominal_assignment = bootstrapping_from_nominal(nominal_assignment_npz, averaged_grid_npz, center_xy, params)

    nominal_fig, multiple_conflicts_flag = bootstrapping_fig()

    status = [
        html.Div(f"Rings found: {len(set([a['circle_index'] for a in bootstrapped_nominal_assignment]))}"),
        html.Div(f"Spokes found: {len(set([a['spoke_index'] for a in bootstrapped_nominal_assignment]))}"),
    ]

    out_npz = session.expected_path("bootstrapping-grid")

    logger.info(f"Saved nominal grid data to: {out_npz}")
    np.savez_compressed(out_npz, data=bootstrapped_nominal_assignment, params=params)

    session.set("bootstrapping-grid", out_npz)

    result = {
        "step": "bootstrapping-grid",
        "status": "completed",
        "request_token": ctx.triggered[0]["prop_id"],
    }

    return result, nominal_fig, status