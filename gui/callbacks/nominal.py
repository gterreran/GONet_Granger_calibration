from __future__ import annotations

from typing import Optional

import numpy as np
from dash import Input, Output, State, callback, ctx, no_update, html
from dash.exceptions import PreventUpdate
import logging

from .. import ids
from ..server import app
from pathlib import Path
from ..plot_utils.plot_nominal import DEFAULT_NOMINAL_PARAMS, RING_COLOR, SPOKE_COLOR, INTERSECTION_COLOR, nominal_groups_styling
from ..plot_utils.plot_nominal import fig_nominal_grid
from ...products import ALL_PRODUCTS

logger = logging.getLogger(__name__)

# -------------------------
# Callbacks
# -------------------------

@callback(
    Output(ids.RING_MAX_DIST_ID, "value"),
    Output(ids.RING_GATE_TOL_R_ID, "value"),
    Output(ids.MIN_RING_GROUP_ID, "value"),
    Output(ids.SPOKE_MAX_DIST_ID, "value"),
    Output(ids.SPOKE_MIN_DIST_ID, "value"),
    Output(ids.SPOKE_GATE_TOL_THETA_ID, "value"),
    Output(ids.MIN_SPOKE_GROUP_ID, "value"),
    # ---------------------
    Input(ids.RESET_NOMINAL_BTN_ID, "n_clicks"),
    # ---------------------
    prevent_initial_call=True,
)
def reset_nominal_parameters(
    n_clicks: int,
) -> None:
    if n_clicks == 0:
        return no_update
    # Just return None to reset the pending nominal grid and update the status display
    return (
        DEFAULT_NOMINAL_PARAMS["ring_max_dist"],
        DEFAULT_NOMINAL_PARAMS["ring_gate_tol_r"],
        DEFAULT_NOMINAL_PARAMS["min_ring_group"],
        DEFAULT_NOMINAL_PARAMS["spoke_max_dist"],
        DEFAULT_NOMINAL_PARAMS["spoke_min_dist"],
        DEFAULT_NOMINAL_PARAMS["spoke_gate_tol_theta"],
        DEFAULT_NOMINAL_PARAMS["min_spoke_group"],
    )

@callback(
    Output(ids.GRID_GRAPH_ID, "figure", allow_duplicate=True),
    Output(ids.NOMINAL_ASSIGNMENT_ID, "data"),
    Output(ids.CONFIRM_NOMINAL_BTN_ID, "disabled"),
    Output(ids.NOMINAL_STATUS_ID, "children"),
    # ---------------------
    Input(ids.FIND_NOMINAL_BTN_ID, "n_clicks"),
    # ---------------------
    State(ids.GRID_GRAPH_ID, "figure"),
    State(ids.RING_MAX_DIST_ID, "value"),
    State(ids.RING_GATE_TOL_R_ID, "value"),
    State(ids.MIN_RING_GROUP_ID, "value"),
    State(ids.SPOKE_MAX_DIST_ID, "value"),
    State(ids.SPOKE_MIN_DIST_ID, "value"),
    State(ids.SPOKE_GATE_TOL_THETA_ID, "value"),
    State(ids.MIN_SPOKE_GROUP_ID, "value"),
    # ---------------------
    prevent_initial_call=True,
)
def find_nominal_grid(
    n_clicks: int,
    fig: dict,
    ring_max_dist: Optional[float],
    ring_gate_tol_r: Optional[float],
    min_ring_group: Optional[int],
    spoke_max_dist: Optional[float],
    spoke_min_dist: Optional[float],
    spoke_gate_tol_theta: Optional[float],
    min_spoke_group: Optional[int],
) -> None:
    if n_clicks == 0:
        return no_update

    params = {
        "ring_max_dist": ring_max_dist,
        "ring_gate_tol_r": ring_gate_tol_r,
        "min_ring_group": min_ring_group,
        "spoke_max_dist": spoke_max_dist,
        "spoke_min_dist": spoke_min_dist,
        "spoke_gate_tol_theta": spoke_gate_tol_theta,
        "min_spoke_group": min_spoke_group,
    }

    nominal_fig, nominal_assignment, multiple_conflicts_flag = fig_nominal_grid(params)

    status = [
        html.Div(f"Rings found: {len(set([a['circle_index'] for a in nominal_assignment]))}"),
        html.Div(f"Spokes found: {len(set([a['spoke_index'] for a in nominal_assignment]))}"),
    ]

    return nominal_fig, nominal_assignment, multiple_conflicts_flag, status


@callback(
    Output(ids.SELECTED_GRID_POINT_ID, "data"),
    Output(ids.SELECTION_CONTROL_DIV_ID, "style"),
    Output(ids.EDIT_NOMINAL_RING_ID, "value"),
    Output(ids.EDIT_NOMINAL_SPOKE_ID, "value"),
    # ---------------------
    Input(ids.GRID_GRAPH_ID, "selectedData"),
    # ---------------------
    State(ids.GRID_GRAPH_ID, "figure"),
    State(ids.SELECTION_CONTROL_DIV_ID, "style"),
    prevent_initial_call=True,
)
def show_selected_object(selectedData, fig, control_div_style):

    if selectedData is None:
        control_div_style["display"] = "none"
        nominal_ring_value = None
        nominal_spoke_value = None
        return None, control_div_style, nominal_ring_value, nominal_spoke_value

    pt = selectedData["points"][0]    
    
    # Assuming the nominal points are always the last trace
    if pt["curveNumber"] == len(fig["data"]) - 1:
        control_div_style["display"] = "block"
        nominal_ring_value = pt["customdata"]["nominal_r"]
        nominal_spoke_value = pt["customdata"]["nominal_theta"]
        return pt["customdata"], control_div_style, nominal_ring_value, nominal_spoke_value
    else:
        raise PreventUpdate
    

@callback(
    Output(ids.GRID_GRAPH_ID, "figure", allow_duplicate=True),
    Output(ids.CONFIRM_NOMINAL_BTN_ID, "disabled", allow_duplicate=True),
    # ---------------------
    Input(ids.SELECTED_GRID_POINT_ID, "data"),
    # ---------------------
    State(ids.GRID_GRAPH_ID, "figure"),
    # ---------------------
    prevent_initial_call=True,
)
def highlight_selected_point(selected_point, fig):
    if selected_point is None:
        raise PreventUpdate
    
    fig, multiple_conflicts_flag = nominal_groups_styling(fig, selected_point)

    return fig, multiple_conflicts_flag


@callback(
    Output(ids.SELECTED_GRID_POINT_ID, "data", allow_duplicate=True),
    Output(ids.GRID_GRAPH_ID, "figure", allow_duplicate=True),
    Output(ids.NOMINAL_ASSIGNMENT_ID, "data", allow_duplicate=True),
    # ---------------------
    Input(ids.EDIT_NOMINAL_RING_ID, "value"),
    Input(ids.EDIT_NOMINAL_SPOKE_ID, "value"),
    # ---------------------
    State(ids.SELECTED_GRID_POINT_ID, "data"),
    State(ids.GRID_GRAPH_ID, "figure"),
    State(ids.NOMINAL_ASSIGNMENT_ID, "data"),
    # ---------------------
    prevent_initial_call=True,
)
def edit_selected_point(nominal_ring_value, nominal_spoke_value, selected_point, fig, nominal_assignment):
    if selected_point is None:
        raise PreventUpdate

    selected_point["nominal_r"] = nominal_ring_value
    selected_point["nominal_theta"] = nominal_spoke_value

    for i, trace in enumerate(fig["data"][1:-1]):
        if trace["customdata"]["kind"] == "ring" and trace["customdata"]["circle_index"] == selected_point["circle_index"]:
            trace["customdata"]["nominal_r"] = nominal_ring_value
            fig["layout"]["annotations"][i]["text"] = f"{nominal_ring_value:.1f}°"
        if trace["customdata"]["kind"] == "spoke" and trace["customdata"]["spoke_index"] == selected_point["spoke_index"]:
            trace["customdata"]["nominal_theta"] = nominal_spoke_value
            fig["layout"]["annotations"][i]["text"] = f"{nominal_spoke_value:.1f}°"

    for point in nominal_assignment:
        if point["circle_index"] == selected_point["circle_index"]:
            point["nominal_r"] = nominal_ring_value
        if point["spoke_index"] == selected_point["spoke_index"]:
            point["nominal_theta"] = nominal_spoke_value
    
    return selected_point, fig, nominal_assignment


@callback(
    Output(ids.STORE_STEP_RESULT, "data", allow_duplicate=True),
    # ---------------------
    Input(ids.CONFIRM_NOMINAL_BTN_ID, "n_clicks"),
    # ---------------------
    State(ids.NOMINAL_ASSIGNMENT_ID, "data"),
    State(ids.RING_MAX_DIST_ID, "value"),
    State(ids.RING_GATE_TOL_R_ID, "value"),
    State(ids.MIN_RING_GROUP_ID, "value"),
    State(ids.SPOKE_MAX_DIST_ID, "value"),
    State(ids.SPOKE_MIN_DIST_ID, "value"),
    State(ids.SPOKE_GATE_TOL_THETA_ID, "value"),
    State(ids.MIN_SPOKE_GROUP_ID, "value"),
    # ---------------------
    prevent_initial_call=True,
)
def save_current_nominal_grid(
    n_clicks: int,
    nominal_assignment: Optional[dict],
    ring_max_dist: float,
    ring_gate_tol_r: float,
    min_ring_group: int,
    spoke_max_dist: float,
    spoke_min_dist: float,
    spoke_gate_tol_theta: float,
    min_spoke_group: int
):
    if n_clicks == 0:
        return no_update
    
    params ={
        "ring_max_dist": ring_max_dist,
        "ring_gate_tol_r": ring_gate_tol_r,
        "min_ring_group": min_ring_group,
        "spoke_max_dist": spoke_max_dist,
        "spoke_min_dist": spoke_min_dist,
        "spoke_gate_tol_theta": spoke_gate_tol_theta,
        "min_spoke_group": min_spoke_group,
    }

    infile = app.server.config["data_files"]["raw-image"][0]  # get the first raw image as input reference

    out_npz=Path(app.server.config["output_dir"]) / ALL_PRODUCTS["nominal-grid"].path(input_file=infile)
    logger.info(f"Saved nominal grid data to: {out_npz}")
    np.savez_compressed(out_npz, data=nominal_assignment, params=params)

    app.server.config["data_files"]["nominal-grid"] = out_npz

    result = {
        "step": "nominal-grid",
        "status": "completed",
        "request_token": ctx.triggered[0]["prop_id"],
    }

    return result