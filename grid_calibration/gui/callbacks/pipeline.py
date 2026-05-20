# grid_calibration/gui/callbacks/pipeline.py
"""
Dash callbacks that orchestrate pipeline step execution.

This module owns the control flow that turns a button click in the left-hand
control panel into a batch or interactive pipeline action. It deliberately
separates the workflow into three stages:

1. :func:`request_step_start`
   Converts a button click into a serializable request stored in
   :data:`grid_calibration.gui.ids.STORE_STEP_REQUEST`.

2. :func:`start_step`
   Resolves the requested :class:`~grid_calibration.gui.workflow.specs.PipelineStepSpec`
   from :data:`~grid_calibration.gui.workflow.registry.STEP_BY_ID` and either
   runs the step's batch pipeline function or initializes its interactive UI.

3. :func:`finalize_step`
   Rebuilds the visible step controls after a step completes and updates the
   selected step so the viewer follows the newly produced product.

The callbacks communicate through Dash stores rather than directly invoking one
another. This makes batch and interactive steps use the same completion path:
interactive callbacks only need to update the
:class:`~grid_calibration.gui.session.CalibrationSession` and emit a
``STORE_STEP_RESULT`` event.
"""

from __future__ import annotations

from dash import Input, Output, State, ctx, no_update, ALL
from ..workflow.registry import ORDERED_STEPS, RUNNABLE_STEPS, STEP_BY_ID
from ..server import app
from .. import ids

from ..session import get_session
from ..logging_utils import log_step


def _empty_outputs():
    """
    Return no-op values for the outputs of :func:`finalize_step`.

    This helper centralizes the exact output shape required by the finalization
    callback. It is used whenever the callback receives an empty, malformed, or
    non-completion event.

    Returns
    -------
    :class:`tuple`
        A tuple matching the six outputs of :func:`finalize_step`. Scalar
        outputs are :data:`dash.no_update`; pattern-matched outputs are lists of
        :data:`dash.no_update` with the appropriate lengths.
    """
    n_buttons = len(RUNNABLE_STEPS)
    n_steps = len(ORDERED_STEPS)
    return (
        no_update,                  # status text
        no_update,                  # selected step
        [no_update] * n_buttons,    # button disabled
        [no_update] * n_steps,      # options
        [no_update] * n_steps,      # options disabled
        [no_update] * n_steps,      # control-row disable_n_clicks
    )

# -----------------------------------------------------------------------------
# 1) Button click -> request step start
# -----------------------------------------------------------------------------
@app.callback(
    Output(ids.STATUS_TEXT, "children", allow_duplicate=True),
    Output(ids.STORE_STEP_REQUEST, "data"),
    # ---------------------
    Input({"type": "button", "step": ALL}, "n_clicks"),
    # ---------------------
    prevent_initial_call=True,
)
def request_step_start(*_):
    """
    Convert a pipeline button click into a step-start request.

    The callback inspects :data:`dash.ctx.triggered_id` to determine which
    pattern-matched button fired. Valid runnable step keys are serialized into
    :data:`grid_calibration.gui.ids.STORE_STEP_REQUEST`; invalid or unrelated
    triggers are ignored.

    Parameters
    ----------
    *_ : :class:`object`
        Pattern-matched button click counts supplied by Dash. The values are
        ignored because the triggering component is read from
        :data:`dash.ctx`.

    Returns
    -------
    :class:`tuple`
        ``(status_text, request)``. ``request`` is a dictionary containing the
        requested step key and a request token, or :data:`dash.no_update` when
        no runnable step was triggered.
    """
    trig = ctx.triggered_id
    if not trig or trig.get("step") not in RUNNABLE_STEPS:
        return no_update, no_update

    step = trig["step"]
    status = f"Starting step: {step}..."

    request = {
        "step": step,
        "request_token": ctx.triggered[0]["prop_id"],
    }
    return status, request


# -----------------------------------------------------------------------------
# 2) Start step
# -----------------------------------------------------------------------------
@app.callback(
    Output(ids.STATUS_TEXT, "children", allow_duplicate=True),
    Output(ids.STORE_ACTIVE_STEP, "data", allow_duplicate=True),
    Output(ids.STORE_STEP_RESULT, "data", allow_duplicate=True),
    Output(ids.PLOTTING_AREA, "children", allow_duplicate=True),
    # ---------------------
    Input(ids.STORE_STEP_REQUEST, "data"),
    # ---------------------
    prevent_initial_call=True,
)
def start_step(request):
    """
    Execute or initialize the requested pipeline step.

    Batch steps are run immediately by resolving
    :attr:`~grid_calibration.gui.workflow.specs.PipelineStepSpec.pipeline_func`
    and passing the session's raw files. Their returned product path or list of
    paths is stored in the active
    :class:`~grid_calibration.gui.session.CalibrationSession`.

    Interactive steps are not marked complete here. Instead, their
    :attr:`~grid_calibration.gui.workflow.specs.PipelineStepSpec.initialize_interactive_state`
    callable is resolved and its returned Dash component is placed in the
    plotting area. A later interactive callback is responsible for saving the
    product, updating the session, and emitting a completion event.

    Parameters
    ----------
    request : :class:`dict` or :class:`None`
        Step-start request emitted by :func:`request_step_start`. Expected to
        contain a ``"step"`` key and, optionally, a ``"request_token"``.

    Returns
    -------
    :class:`tuple`
        ``(status_text, active_step, result_event, plotting_children)``. For
        batch steps, ``result_event`` is a completion dictionary. For
        interactive steps, ``plotting_children`` contains the initialized
        interactive layout and ``result_event`` is :data:`dash.no_update`.
    """
    if not request:
        return no_update, no_update, no_update, no_update

    step = request.get("step")
    if not step or step not in STEP_BY_ID:
        return no_update, no_update, no_update, no_update

    spec = STEP_BY_ID[step]

    session = get_session()
    if spec.mode == "batch":

        with log_step(step):
            out = spec.pipeline_func(
                session.raw_files
            )

        session.set(step, out)

        result = {
            "step": step,
            "status": "completed",
            "request_token": request.get("request_token"),
        }
        return f"Step {step} completed.", step, result, no_update

    if spec.mode == "interactive":

        with log_step(step):
            interactive_div = spec.initialize_interactive_state()

        status = f"Step {step} started. Waiting for user input."
        return status, step, no_update, interactive_div

# -----------------------------------------------------------------------------
# 3) Finalize step result
# -----------------------------------------------------------------------------
@app.callback(
    Output(ids.STATUS_TEXT, "children", allow_duplicate=True),
    Output(ids.STORE_SELECTED_STEP, "data", allow_duplicate=True),  
    Output({"type": "button", "step": ALL}, "disabled"),
    Output({"type": "options", "step": ALL}, "options"),
    Output({"type": "options", "step": ALL}, "disabled"),
    Output({"type": "control-row", "step": ALL}, "disable_n_clicks"),
    # ---------------------
    Input(ids.STORE_STEP_RESULT, "data"),
    # ---------------------
    State({"type": "options", "step": ALL}, "options"),
    prevent_initial_call=True,
)
def finalize_step(result, options):
    """
    Rebuild step controls after a pipeline step completes.

    This callback is the shared completion path for batch and interactive steps.
    It reads the completed step's product registration from the active
    :class:`~grid_calibration.gui.session.CalibrationSession`, updates the
    corresponding dropdown options, enables the next runnable button, updates
    row clickability, and selects the completed step for viewing.

    Parameters
    ----------
    result : :class:`dict` or :class:`None`
        Completion event. Valid events contain ``{"step": <step_key>,
        "status": "completed"}``.
    options : :class:`list`
        Current option lists for all step dropdown or label controls.

    Returns
    -------
    :class:`tuple`
        ``(status_text, selected_step, button_disabled, options,
        option_disabled, row_disable_n_clicks)``. If the event is not a valid
        completion event, returns the no-op tuple from :func:`_empty_outputs`.
    """
    if not result:
        return _empty_outputs()

    step = result.get("step")
    status = result.get("status")

    if status != "completed":
        return _empty_outputs()

    step_order = ORDERED_STEPS.index(step)
    disable_buttons_list = [i > step_order+1 for i in range(1,len(ORDERED_STEPS))]

    session = get_session()
    out = session.get(step)

    if out is None:
        return _empty_outputs()

    if isinstance(out, list):
        new_options = [{"label": p.name, "value": i} for i, p in enumerate(out)]
    else:
        new_options = [{"label": out.name, "value": 0}]
    options[step_order] = new_options

    disable_options_list = [i > step_order for i in range(len(ORDERED_STEPS))]
    # In case of interactive steps, the pipeline func returns an empty path, 
    # so we should keep the options dropdown for that step disabled.

    if not isinstance(out, list) and out.name=='':
        disable_options_list[step_order] = True

    session.set(step, out)

    status = f"Completed step: {step}"

    return status, step, disable_buttons_list, options, disable_options_list, disable_options_list
