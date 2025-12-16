from .server import app
from ..pipeline import build_full_arrays_for_images#, run_full_pipeline, run_detection_on_full_arrays, compute_averaged_grid
from dash import Input, Output, State, ctx, no_update, clientside_callback
from .logging_utils import global_log_handler
from .plot_utils import plot_raw_image, plot_full_array_product

@app.callback(
    Output("plotting-area", "children"),
    #---------------------
    Input("raw-image-dropdown", "value"),
    Input("full-array-dropdown", "value"),
    Input("grid-points-dropdown", "value"),
    #---------------------
)
def update_raw_image_dropdown(raw_idx, full_array_idx, grid_points_idx):
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
    if ctx.triggered_id in [None, "raw-image-dropdown"]:
        idx = raw_idx
        plotting_function = plot_raw_image
    elif ctx.triggered_id == "full-array-dropdown":
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
    #---------------------
    Input("btn-build-full", "n_clicks"),
    Input("run_full_pipeline_trigger", "children"),
    #---------------------
    State("raw-image-dropdown", "value"),
    State("btn-detect-grid", "n_clicks"),
    #---------------------
    prevent_initial_call=True
)
def run_full_array(_, pipeline_trigger, idx, n_detect):
    output_list = build_full_arrays_for_images(app.server.config["data_files"]["raw"], app.server.config["output_dir"])
    app.server.config["data_files"]["full_array"] = output_list[:]
    status = "Built full arrays for all images."
    options = [{"label": f.name, "value": i} for i, f in enumerate(output_list)]
    value = idx
    disabled = False
    if ctx.triggered_id == "run_full_pipeline_trigger":
        n_detect += 1
    else:
        n_detect = no_update

    return status, disabled, options, value, disabled, n_detect

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