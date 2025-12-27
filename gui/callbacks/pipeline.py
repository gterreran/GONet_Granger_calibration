from __future__ import annotations

from dash import Input, Output, State, ctx, no_update, ALL
from ..steps import PIPELINE_FUNCS, ORDERED_STEPS
from ..server import app
from .. import ids

@app.callback(
    Output(ids.STATUS_TEXT, "children", allow_duplicate=True),
    Output(ids.STORE_ACTIVE_STEP, "data", allow_duplicate=True),
    Output({"type": "button", "step": ALL}, "disabled"),
    Output({"type": "options", "step": ALL}, "options"),
    Output({"type": "options", "step": ALL}, "disabled"),
    Output({"type": "control-row", "step": ALL}, "disable_n_clicks"),
    #---------------------
    Input(ids.STORE_RUN_STEP, "data"),
    #---------------------
    State({"type": "options", "step": ALL}, "options"),
    #---------------------
    prevent_initial_call=True,
)
def run_step(step, options):

    if not step or step not in PIPELINE_FUNCS:
        return no_update, no_update, [no_update]*(len(ORDERED_STEPS)-1), [no_update]*len(ORDERED_STEPS), [no_update]*len(ORDERED_STEPS), [no_update]*len(ORDERED_STEPS)

    func = PIPELINE_FUNCS[step]

    out = func(
        app.server.config["data_files"]["raw-image"],
        app.server.config["output_dir"],
    )

    step_order = ORDERED_STEPS.index(step)
    disable_buttons_list = [i > step_order+1 for i in range(1,len(ORDERED_STEPS))]

    if isinstance(out, list):
        new_options = [{"label": p.name, "value": i} for i, p in enumerate(out)]
    else:
        new_options = [{"label": out.name, "value": 0}]
    options[step_order] = new_options

    disable_options_list = [i > step_order for i in range(len(ORDERED_STEPS))]

    app.server.config["data_files"][step] = out

    status = f"Completed step: {step}"

    return status, step, disable_buttons_list, options, disable_options_list, disable_options_list


@app.callback(
    Output(ids.STATUS_TEXT, "children", allow_duplicate=True),
    Output(ids.STORE_RUN_STEP, "data"),
    #---------------------
    Input({"type": "button", "step": ALL}, "n_clicks"),
    #---------------------
    prevent_initial_call=True,
)
def update_status_on_click(*_):
    trig = ctx.triggered_id

    if not trig or trig["step"] not in PIPELINE_FUNCS:
        return no_update

    step = trig["step"]
    status = f"Running step: {step}..."

    return status, step