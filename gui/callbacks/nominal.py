from __future__ import annotations

from typing import Optional

import numpy as np
from dash import Input, Output, State, ctx, no_update, html
from dash.exceptions import PreventUpdate
import logging

from .. import ids
from ..server import app
from pathlib import Path
from ..plot_utils.plot_nominal import DEFAULT_NOMINAL_PARAMS, nominal_groups_styling, fig_nominal_grid
from ...products import ALL_PRODUCTS

logger = logging.getLogger(__name__)


# Validation callbacks: coerce numeric inputs to multiples of 2.5 and clamp to 0-90
def _coerce_to_step_and_bounds(val, step: float, minv: float, maxv: float):
    try:
        v = float(val)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid input value: {val}")
    v = max(minv, min(maxv, v))
    v = round(v / step) * step
    return v

# -------------------------
# Callbacks
# -------------------------

@app.callback(
        Output(ids.VALID_NOMINAL_RING_ID, "data"),
        Input(ids.EDIT_NOMINAL_RING_ID, "value"),
        prevent_initial_call=True
    )
def enforce_edit_nominal_ring(val):
    try:
        return _coerce_to_step_and_bounds(val, step=2.5, minv=2.5, maxv=90.0)
    except Exception as e:
        return None


@app.callback(
        Output(ids.VALID_NOMINAL_SPOKE_ID, "data"),
        Input(ids.EDIT_NOMINAL_SPOKE_ID, "value"),
        prevent_initial_call=True
    )
def enforce_edit_nominal_spoke(val):
    try:
        return _coerce_to_step_and_bounds(val, step=2.5, minv=0.0, maxv=360.0)
    except Exception as e:
        return None


# Callback to reset nominal grid parameters to defaults when "Reset" button is clicked
@app.callback(
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

@app.callback(
    Output(ids.GRID_GRAPH_ID, "figure", allow_duplicate=True),
    Output(ids.NOMINAL_ASSIGNMENT_ID, "data", allow_duplicate=True),
    Output(ids.CONFIRM_NOMINAL_BTN_ID, "disabled", allow_duplicate=True),
    Output(ids.NOMINAL_STATUS_ID, "children", allow_duplicate=True),
    # ---------------------
    Input(ids.FIND_NOMINAL_BTN_ID, "n_clicks"),
    # ---------------------
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


@app.callback(
    Output(ids.SELECTION_CONTROL_DIV_ID, "style"),
    Output(ids.EDIT_NOMINAL_RING_ID, "value", allow_duplicate=True),
    Output(ids.EDIT_NOMINAL_SPOKE_ID, "value", allow_duplicate=True),
    # ---------------------
    Input(ids.GRID_GRAPH_ID, "selectedData"),
    # ---------------------
    State(ids.GRID_GRAPH_ID, "figure"),
    State(ids.SELECTION_CONTROL_DIV_ID, "style"),
    State(ids.SELECTED_GRID_POINT_ID, "data"),
    prevent_initial_call=True,
)
def show_selected_object(selectedData, fig, control_div_style, previous_selection):
    if selectedData is None or selectedData["points"][0]["customdata"] == previous_selection:
        control_div_style["display"] = "none"
        nominal_ring_value = None
        nominal_spoke_value = None
        return control_div_style, nominal_ring_value, nominal_spoke_value

    pt = selectedData["points"][0]    
    
    # Assuming the nominal points are always the last trace
    if pt["curveNumber"] == len(fig["data"]) - 1:
        control_div_style["display"] = "block"
        nominal_ring_value = pt["customdata"]["nominal_r"]
        nominal_spoke_value = pt["customdata"]["nominal_theta"]
        return control_div_style, nominal_ring_value, nominal_spoke_value
    else:
        raise PreventUpdate
    

@app.callback(
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
    
    fig, multiple_conflicts_flag = nominal_groups_styling(fig, selected_point)

    return fig, multiple_conflicts_flag


@app.callback(
    Output(ids.SELECTED_GRID_POINT_ID, "data", allow_duplicate=True),
    Output(ids.GRID_GRAPH_ID, "figure", allow_duplicate=True),
    Output(ids.NOMINAL_ASSIGNMENT_ID, "data", allow_duplicate=True),
    # ---------------------
    Input(ids.VALID_NOMINAL_RING_ID, "data"),
    Input(ids.VALID_NOMINAL_SPOKE_ID, "data"),
    # ---------------------
    State(ids.GRID_GRAPH_ID, "selectedData"),
    State(ids.SELECTED_GRID_POINT_ID, "data"),
    State(ids.GRID_GRAPH_ID, "figure"),
    State(ids.NOMINAL_ASSIGNMENT_ID, "data"),
    # ---------------------
    prevent_initial_call=True,
)
def edit_selected_point(nominal_ring_value, nominal_spoke_value, selected_point, previous_selection, fig, nominal_assignment):
    if nominal_ring_value is None or nominal_spoke_value is None:
        if previous_selection is not None:
            # If we had a previous selection but now the input is invalid,
            # hide the controls and keep the previous selection
            return None, fig, nominal_assignment
        raise PreventUpdate

    if selected_point is None:
        raise PreventUpdate
    else:
        selected_point = selected_point["points"][0]["customdata"]

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


@app.callback(
    Output(ids.GRID_GRAPH_ID, "figure", allow_duplicate=True),
    Output(ids.NOMINAL_ASSIGNMENT_ID, "data", allow_duplicate=True),
    Output(ids.SHIFT_RINGS_DEC_ID, "disabled"),
    Output(ids.SHIFT_RINGS_INC_ID, "disabled"),
    Output(ids.EDIT_NOMINAL_RING_ID, "value", allow_duplicate=True),
    Output(ids.EDIT_NOMINAL_SPOKE_ID, "value", allow_duplicate=True),
    # ---------------------
    Input(ids.SHIFT_SPOKES_DEC_ID, "n_clicks"),
    Input(ids.SHIFT_SPOKES_INC_ID, "n_clicks"),
    Input(ids.SHIFT_RINGS_DEC_ID, "n_clicks"),
    Input(ids.SHIFT_RINGS_INC_ID, "n_clicks"),
    # ---------------------
    State(ids.GRID_GRAPH_ID, "figure"),
    State(ids.NOMINAL_ASSIGNMENT_ID, "data"),
    State(ids.EDIT_NOMINAL_RING_ID, "value"),
    State(ids.EDIT_NOMINAL_SPOKE_ID, "value"),
    # ---------------------
    prevent_initial_call=True,
)
def shift_all_nominals(shift_spokes_dec, shift_spokes_inc, shift_rings_dec, shift_rings_inc, fig, nominal_assignment, edit_ring_value, edit_spoke_value):
    # Check which button was clicked
    button_id = ctx.triggered[0]["prop_id"].split(".")[0]
    if button_id == ids.SHIFT_SPOKES_DEC_ID:
        shift_spokes = -2.5
        shift_rings = 0
    elif button_id == ids.SHIFT_SPOKES_INC_ID:
        shift_spokes = 2.5
        shift_rings = 0
    elif button_id == ids.SHIFT_RINGS_DEC_ID:
        shift_spokes = 0
        shift_rings = -2.5
    elif button_id == ids.SHIFT_RINGS_INC_ID:
        shift_spokes = 0
        shift_rings = 2.5
    else:
        raise PreventUpdate

    for i, trace in enumerate(fig["data"][1:-1]):
        if trace["customdata"]["kind"] == "ring" and shift_rings:
            new_r = (trace["customdata"]["nominal_r"] + shift_rings) % 360
            fig["data"][i+1]["customdata"]["nominal_r"] = new_r
            fig["layout"]["annotations"][i]["text"] = f"{new_r:.1f}°"
        if trace["customdata"]["kind"] == "spoke" and shift_spokes:
            new_theta = (trace["customdata"]["nominal_theta"] + shift_spokes) % 360
            fig["data"][i+1]["customdata"]["nominal_theta"] = new_theta
            fig["layout"]["annotations"][i]["text"] = f"{new_theta:.1f}°"

    min_ring = 90
    max_ring = 0
    for point in nominal_assignment:
        point["nominal_r"] = (point["nominal_r"] + shift_rings) % 360
        point["nominal_theta"] = (point["nominal_theta"] + shift_spokes) % 360
        if point["nominal_r"] < min_ring:
            min_ring = point["nominal_r"]
        if point["nominal_r"] > max_ring:
            max_ring = point["nominal_r"]
    
    if max_ring >= 90:
        shift_rings_inc_disabled = True
    else:
        shift_rings_inc_disabled = False
    
    if min_ring <= 2.5:
        shift_rings_dec_disabled = True
    else:
        shift_rings_dec_disabled = False
    
    if edit_ring_value is not None:
        edit_ring_value = (edit_ring_value + shift_rings) % 360
    if edit_spoke_value is not None:
        edit_spoke_value = (edit_spoke_value + shift_spokes) % 360

    # Ensure the intersection trace carries the updated per-point customdata
    try:
        fig["data"][-1]["customdata"] = nominal_assignment
    except Exception:
        logger.debug("Could not update intersection trace customdata; skipping.")

    logger.info(f"Shifted nominal grid: spokes shift={shift_spokes}, rings shift={shift_rings}")

    return fig, nominal_assignment, shift_rings_dec_disabled, shift_rings_inc_disabled, edit_ring_value, edit_spoke_value


@app.callback(
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