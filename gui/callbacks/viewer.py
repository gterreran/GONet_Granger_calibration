from __future__ import annotations

from dash import Input, Output, ALL

from ..server import app
from .. import ids
from ..steps import VIEWER_FUNCS, ORDERED_STEPS

@app.callback(
    Output(ids.PLOTTING_AREA, "children"),
    Input(ids.STORE_ACTIVE_STEP, "data"),
    Input({"type": "options", "step": ALL}, "value"),
    prevent_initial_call=True,
)
def update_plotting_area(active_step, idx_values):

    plotting_function = VIEWER_FUNCS.get(active_step)
    idx = idx_values[ORDERED_STEPS.index(active_step)]

    return plotting_function(idx)
