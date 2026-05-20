# grid_calibration/gui/callbacks/system.py
"""
Dash callbacks and clientside callbacks for application-level behavior.

This module handles behavior that is not specific to one pipeline product:

- polling the GUI log buffer and rendering it in the log window;
- keeping the log window pinned to the bottom unless the user scrolls away;
- closing the PyWebView window through the exposed ``window.pywebview`` API;
- selecting a step by clicking its control row; and
- styling step rows so the selected step is visually highlighted.

The distinction between the active step and the selected step is important:

``STORE_ACTIVE_STEP``
    Tracks the latest step being processed or initialized.

``STORE_SELECTED_STEP``
    Tracks the step currently being viewed in the plotting panel.

The row highlight follows ``STORE_SELECTED_STEP`` when it is set, falling back to
``STORE_ACTIVE_STEP`` during initial page load.
"""

from __future__ import annotations

from dash import Input, Output, State, clientside_callback, ALL

from ..server import app
from ..logging_utils import global_log_handler
from .. import ids

@app.callback(
    Output(ids.LOG_WINDOW, "children"),
    #---------------------
    Input(ids.LOG_POLL_INTERVAL, "n_intervals"),
    #---------------------
    prevent_initial_call=True
)
def update_log_window(_):
    """
    Poll the in-memory GUI log buffer and update the visible log window.

    Parameters
    ----------
    _ : :class:`int`
        Interval tick count from :class:`dash.dcc.Interval`. The value is not
        used; it only triggers the polling callback.

    Returns
    -------
    :class:`str`
        The accumulated log text from
        :data:`grid_calibration.gui.logging_utils.global_log_handler`, or a
        placeholder message when the buffer is empty.
    """
    text = global_log_handler.get_logs()
    return text or "Log output will appear here..."

clientside_callback(
    """
    function(logText) {
        const getEl = () => document.getElementById("log-window");

        const bindScrollListener = (el) => {
            // Avoid binding multiple times to the same DOM node
            if (el.dataset.autoScrollBound === "1") return;

            const updateFlag = () => {
                const nearBottom =
                    (el.scrollTop + el.clientHeight) >= (el.scrollHeight - 30);
                window.__logShouldAutoScroll = nearBottom;
            };

            el.addEventListener("scroll", updateFlag, { passive: true });
            el.dataset.autoScrollBound = "1";

            // Initialize the flag at bind time
            updateFlag();
        };

        const scrollToBottomIfNeeded = () => {
            const el = getEl();
            if (!el) return;

            bindScrollListener(el);

            // Default to autoscroll if we've never set the flag
            const should = (window.__logShouldAutoScroll !== false);

            if (should) {
                el.scrollTop = el.scrollHeight;
                // Keep flag consistent after we move it
                window.__logShouldAutoScroll = true;
            }
        };

        // Wait for DOM/layout to settle; also include a small timeout fallback
        requestAnimationFrame(() => {
            requestAnimationFrame(scrollToBottomIfNeeded);
        });
        setTimeout(scrollToBottomIfNeeded, 50);

        return "";
    }
    """,
    Output(ids.LOG_AUTOSCROLL_DUMMY, "children"),
    Input(ids.LOG_WINDOW, "children"),
)




@app.callback(
    Output(ids.BTN_EXIT, "disabled"),  # dummy output
    #---------------------
    Input(ids.BTN_EXIT, "n_clicks"),
    #---------------------
    prevent_initial_call=True
)
def exit_app(_):
    """
    Request that the embedded PyWebView window close.

    The callback uses :mod:`webview` to evaluate JavaScript in the active
    PyWebView window. The JavaScript calls the exposed
    ``window.pywebview.api.close_window()`` method. The Dash output is only a
    dummy output used to satisfy Dash's callback contract.

    Parameters
    ----------
    _ : :class:`int` or :class:`None`
        Click count of the exit button. The value is ignored.

    Returns
    -------
    :class:`bool`
        Always returns ``True`` to disable the exit button after it is clicked.
    """
    import webview
    webview.windows[0].evaluate_js("window.pywebview.api.close_window()")
    return True

clientside_callback(
    """
    function(rowClicks, disabledList, steps) {
        const trig = dash_clientside.callback_context.triggered_id;
        if (!trig) return window.dash_clientside.no_update;

        if (typeof trig === "object" && trig.type === "control-row") {
            const step = trig.step;
            const i = steps.indexOf(step);
            if (i === -1) return window.dash_clientside.no_update;

            if (disabledList[i]) return window.dash_clientside.no_update;

            return step;
        }

        return window.dash_clientside.no_update;
    }
    """,
    Output(ids.STORE_SELECTED_STEP, "data", allow_duplicate=True),
    Input({"type": "control-row", "step": ALL}, "n_clicks"),
    State({"type": "control-row", "step": ALL}, "disable_n_clicks"),
    State(ids.STORE_CONTROL_STEPS, "data"),
    prevent_initial_call=True,
)

clientside_callback(
    """
    function(selectedStep, activeStep, disabledList, steps) {
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

        const highlightedStep = selectedStep || activeStep;

        return steps.map((step, i) => {
            const isDisabled = disabledList[i];
            const isActive = (step === highlightedStep);

            let s = isActive ? Object.assign({}, active) : Object.assign({}, base);

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
    Input(ids.STORE_SELECTED_STEP, "data"),
    Input(ids.STORE_ACTIVE_STEP, "data"),
    Input({"type": "control-row", "step": ALL}, "disable_n_clicks"),
    Input(ids.STORE_CONTROL_STEPS, "data"),
)
