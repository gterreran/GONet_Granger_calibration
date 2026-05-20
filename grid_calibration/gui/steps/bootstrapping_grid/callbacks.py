# grid_calibration/gui/steps/bootstrapping_grid/callbacks.py
"""
Interactive Dash callbacks for the bootstrapping-grid step.

The callbacks in this module connect the step controls to the processing
pipeline, update the active
:class:`~grid_calibration.gui.session.CalibrationSession`, and emit the shared
step-completion event consumed by the generic pipeline callbacks.
"""

from __future__ import annotations

from typing import Optional

from dash import Input, Output, State, ctx, no_update, html
import logging

from .spec import product_io as bootstrapping_grid_io
from ..averaged_grid.spec import product_io as averaged_grid_io
from ..averaged_grid.keys import GRID_KEY
from ..nominal_grid.spec import product_io as nominal_grid_io
from ..nominal_grid.spec import DATA_KEY as NOMINAL_DATA_KEY
from ..unwrapped_grid import product_io as unwrapped_grid_io
from ..unwrapped_grid.keys import CENTER_KEY
from .keys import STEP_KEY
from ... import ids
from ...server import app
from .plotting import bootstrapping_fig
from .processing import bootstrapping_from_nominal
from .params import DEFAULT_PARAMETERS
from .spec import DATA_KEY, PARAMS_KEY

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
    nominal_assignment = nominal_grid_io.load()[NOMINAL_DATA_KEY]
    averaged_grid = averaged_grid_io.load()[GRID_KEY]
    center_xy = unwrapped_grid_io.load()[CENTER_KEY]

    bootstrapped_nominal_assignment = bootstrapping_from_nominal(
        nominal_assignment,
        averaged_grid,
        center_xy,
        params,
    )

    nominal_fig, multiple_conflicts_flag = bootstrapping_fig()

    status = [
        html.Div(f"Rings found: {len(set([a['circle_index'] for a in bootstrapped_nominal_assignment]))}"),
        html.Div(f"Spokes found: {len(set([a['spoke_index'] for a in bootstrapped_nominal_assignment]))}"),
    ]

    output_packet = {
        DATA_KEY: bootstrapped_nominal_assignment,
        PARAMS_KEY: params,
    }

    bootstrapping_grid_io.save(
        **output_packet,
    )

    bootstrapping_grid_io.register()

    result = {
        "step": STEP_KEY,
        "status": "completed",
        "request_token": ctx.triggered[0]["prop_id"],
    }

    return result, nominal_fig, status
