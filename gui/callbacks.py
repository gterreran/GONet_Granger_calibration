from .server import app
from ..pipeline import build_full_arrays_for_images#, run_full_pipeline, run_detection_on_full_arrays, compute_averaged_grid
from dash import Input, Output, State, ctx, no_update, clientside_callback, ALL
from .logging_utils import global_log_handler
from .plot_utils import plot_raw_image, plot_full_array_product

@app.callback(
    Output("plotting-area", "children"),
    #---------------------
    Input("active-step-store", "data"),
    Input("raw-image-dropdown", "value"),
    Input("full-array-dropdown", "value"),
    Input("grid-points-dropdown", "value"),
    #---------------------
    prevent_initial_call=True
)
def update_raw_image_dropdown(active_step, raw_idx, full_array_idx, grid_points_idx):
    """
    Update the plotting area with the selected raw image.

    Parameters
    ----------
    idx : :class:`int`
        Index of the selected raw image in the dropdown.

    Returns
    -------
    :class:`dash.development.base_component.Component`
        A Dash component to display the selected raw image.
    """
    trigger = ctx.triggered_id
    if trigger == "active-step-store":
        trigger = f"{active_step}-dropdown"
    if trigger == "raw-image-dropdown":
        idx = raw_idx
        plotting_function = plot_raw_image
    elif trigger == "full-array-dropdown":
        idx = full_array_idx
        plotting_function = plot_full_array_product

    img_div = plotting_function(idx)

    return img_div


@app.callback(
    Output("status-text", "children"),
    Output("full-array-dropdown", "disabled"),
    Output("full-array-dropdown", "options"),
    Output("full-array-dropdown", "value"),
    Output("btn-detect-grid", "disabled"),
    Output("btn-detect-grid", "n_clicks"),
    Output("active-step-store", "data", allow_duplicate=True),
    Output({"type": "control-row", "step": "full-array"}, "disable_n_clicks"),
    #---------------------
    Input("btn-full-array", "n_clicks"),
    Input("run_full_pipeline_trigger", "children"),
    #---------------------
    State("raw-image-dropdown", "value"),
    State("btn-detect-grid", "n_clicks"),
    #---------------------
    prevent_initial_call=True
)
def run_full_array(_, pipeline_trigger, idx, n_detect):
    output_list = build_full_arrays_for_images(app.server.config["data_files"]["raw-image"], app.server.config["output_dir"])
    app.server.config["data_files"]["full-array"] = output_list[:]
    status = "Built full arrays for all images."
    options = [{"label": f.name, "value": i} for i, f in enumerate(output_list)]
    value = idx
    disabled = False
    if ctx.triggered_id == "run_full_pipeline_trigger":
        n_detect += 1
    else:
        n_detect = no_update

    return status, disabled, options, value, disabled, n_detect, "full-array",disabled

@app.callback(
    Output("run_full_pipeline_trigger", "children"),
    Output("pipeline-run", "data"),
    #---------------------
    Input("btn-run-all", "n_clicks"),
    #---------------------
    prevent_initial_call=True
)
def run_pipeline_trigger(_):
    """
    Trigger the full pipeline to run when the "Run All" button is clicked.
    """
    return "trigger", True

    
@app.callback(
    Output("log-window", "children"),
    #---------------------
    Input("log-poll-interval", "n_intervals"),
    #---------------------
    prevent_initial_call=True
)
def update_log_window(_):
    """
    Periodically update the log window from the global log handler buffer.
    """
    text = global_log_handler.get_logs()
    return text or "Log output will appear here..."

clientside_callback(
    """
    function(logText) {
        window.setTimeout(function() {
            const el = document.getElementById("log-window");
            if (!el) return;

            // Are we near the bottom already?
            const nearBottom = (el.scrollTop + el.clientHeight) >= (el.scrollHeight - 30);

            if (nearBottom) {
                el.scrollTop = el.scrollHeight;
            }
        }, 0);
        return "";
    }
    """,
    Output("log-autoscroll-dummy", "children"),
    Input("log-window", "children"),
)


@app.callback(
    Output("btn-exit", "disabled"),  # dummy output
    #---------------------
    Input("btn-exit", "n_clicks"),
    #---------------------
    prevent_initial_call=True
)
def exit_app(_):
    """
    Callback to request closing the PyWebView window when the "Exit" button is clicked.

    This callback sends a JavaScript command to the embedded PyWebView browser,
    which calls the exposed Python API method ``close_window()`` to close the window.

    Parameters
    ----------
    _ : :class:`int` or :class:`NoneType`
        Click count of the "Exit" button (ignored).

    Returns
    -------
    :class:`bool`
        Always returns ``True`` to disable the "Exit" button after it has been clicked.
    """
    import webview
    webview.windows[0].evaluate_js("window.pywebview.api.close_window()")
    return True

clientside_callback(
    """
    function(rowClicks, disabledList, steps, currentActive) {
        const trig = dash_clientside.callback_context.triggered_id;
        if (!trig) return window.dash_clientside.no_update;

        // trig is like {type:"control-row", step:"full-array"}
        if (typeof trig === "object" && trig.type === "control-row") {
            const step = trig.step;
            const i = steps.indexOf(step);
            if (i === -1) return window.dash_clientside.no_update;

            // If this row is not clickable, ignore the click
            if (disabledList[i]) return window.dash_clientside.no_update;

            // If it's already active, don't update the store
            if (step === currentActive) return window.dash_clientside.no_update;

            return step;
        }

        return window.dash_clientside.no_update;
    }
    """,
    Output("active-step-store", "data"),
    Input({"type": "control-row", "step": ALL}, "n_clicks"),
    State({"type": "control-row", "step": ALL}, "disable_n_clicks"),
    State("control-row-steps-store", "data"),
    State("active-step-store", "data"),
)
clientside_callback(
    """
    function(activeStep, disabledList, steps) {
        const base = {
            display: "flex",
            alignItems: "center",
            marginBottom: "10px",
            padding: "6px 8px",
            borderRadius: "8px",
            userSelect: "none",
            border: "1px solid transparent"
        };

        const active = Object.assign({}, base, {
            border: "1px solid #4da3ff",
            boxShadow: "0 0 0 2px rgba(77, 163, 255, 0.25)",
            background: "rgba(77, 163, 255, 0.08)"
        });

        return steps.map((step, i) => {
            const isDisabled = disabledList[i];
            const isActive = (step === activeStep);

            let s = isActive ? Object.assign({}, active) : Object.assign({}, base);

            // cursor + dimming when not clickable
            if (isDisabled) {
                s.cursor = "default";
            } else {
                s.cursor = "pointer";
                s.opacity = 1.0;
            }

            return s;
        });
    }
    """,
    Output({"type": "control-row", "step": ALL}, "style"),
    Input("active-step-store", "data"),
    Input({"type": "control-row", "step": ALL}, "disable_n_clicks"),
    Input("control-row-steps-store", "data"),
)