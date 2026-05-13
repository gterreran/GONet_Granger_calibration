# grid_calibration/gui/callbacks/viewer.py
from __future__ import annotations

from dash import Input, Output, ALL, no_update

from ..server import app
from .. import ids
from ..workflow.registry import STEP_BY_ID, ORDERED_STEPS


@app.callback(
    Output(ids.PLOTTING_AREA, "children", allow_duplicate=True),
    Input(ids.STORE_SELECTED_STEP, "data"),
    Input({"type": "options", "step": ALL}, "value"),
    prevent_initial_call=True,
)
def update_plotting_area(selected_step, idx_values):
    if not selected_step:
        return no_update

    plotting_function = STEP_BY_ID[selected_step].viewer_func
    if plotting_function is None:
        return no_update

    try:
        step_index = ORDERED_STEPS.index(selected_step)
    except ValueError:
        return no_update

    if not idx_values or step_index >= len(idx_values):
        return no_update

    idx = idx_values[step_index]

    # If there is no selected option yet, default to the first entry
    if idx is None:
        idx = 0

    return plotting_function(idx)