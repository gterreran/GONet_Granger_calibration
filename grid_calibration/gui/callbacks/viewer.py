# grid_calibration/gui/callbacks/viewer.py
"""
Dash callback that keeps the plotting panel synchronized with step selection.

The viewer layer is intentionally thin. It does not know how to plot any
specific product. Instead, it resolves the selected step through
:data:`grid_calibration.gui.workflow.registry.STEP_BY_ID`, obtains that step's
viewer callable from
:attr:`~grid_calibration.gui.workflow.specs.PipelineStepSpec.viewer_func`, and
passes the currently selected dropdown index to that callable.

This keeps plotting logic inside each step package while giving the application
one shared callback for switching between products.
"""

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
    """
    Render the viewer for the selected step and selected product index.

    Parameters
    ----------
    selected_step : :class:`str` or :class:`None`
        Step key stored in :data:`grid_calibration.gui.ids.STORE_SELECTED_STEP`.
        This represents the step currently being viewed, not necessarily the
        latest step that was processed.
    idx_values : :class:`list`
        Current values of all pattern-matched step option controls. The selected
        step's position in :data:`~grid_calibration.gui.workflow.registry.ORDERED_STEPS`
        is used to select the matching index value.

    Returns
    -------
    :class:`dash.development.base_component.Component` or :data:`dash.no_update`
        The Dash component returned by the selected step's viewer callable, or
        :data:`dash.no_update` if the selected step is invalid, has no viewer, or
        has no available option value.
    """
    if not selected_step:
        return no_update

    try:
        step_spec = STEP_BY_ID[selected_step]
        step_index = ORDERED_STEPS.index(selected_step)
    except (KeyError, ValueError):
        return no_update

    plotting_function = step_spec.viewer_func
    if plotting_function is None:
        return no_update

    if not idx_values or step_index >= len(idx_values):
        return no_update

    idx = idx_values[step_index]

    # If there is no selected option yet, default to the first entry
    if idx is None:
        idx = 0

    return plotting_function(idx)
