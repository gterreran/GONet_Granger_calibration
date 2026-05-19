# grid_calibration/gui/callbacks/pipeline.py

from __future__ import annotations

from dash import Input, Output, State, ctx, no_update, ALL
from ..workflow.registry import ORDERED_STEPS, RUNNABLE_STEPS, STEP_BY_ID
from ..server import app
from .. import ids

from ..session import get_session
from ..logging_utils import log_step


def _empty_outputs():
    """
    Return a full no_update tuple matching the outputs of finalize_step().
    """
    n_buttons = len(RUNNABLE_STEPS)
    n_steps = len(ORDERED_STEPS)
    return (
        no_update,                  # status text
        no_update,                  # active step
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
    Convert a button click into a step-start request.

    This decouples the UI (button clicks) from the actual step execution.

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
    Start a batch or interactive step.

    Batch steps:
        - run immediately
        - write payload into the session
        - emit STORE_STEP_RESULT so finalize_step can rebuild the UI

    Interactive steps:
        - mark as active
        - optionally initialize interactive state
        - do not complete yet
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
    Finalize a completed step and rebuild the whole step UI from data_files.

    This is the single shared completion path for both batch and interactive
    steps. Any callback that finishes an interactive workflow should:

        1. write the payload into the session (session.set(step, payload))
        2. emit ids.STORE_STEP_RESULT with {"step": step, "status": "completed"}

    Parameters
    ----------
    result : dict
        Result event emitted after a step completes.

    Returns
    -------
    tuple
        Dash outputs updating status, active step, buttons, options, and
        control-row state.
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
