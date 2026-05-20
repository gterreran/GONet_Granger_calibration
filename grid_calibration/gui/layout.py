# grid_calibration/gui/layout.py
"""
Dash layout construction for the grid-calibration GUI.

The layout is generated from the workflow registry and the active
:class:`~grid_calibration.gui.session.CalibrationSession`.  This means the left
control panel reflects the products discovered at startup or refresh time, while
the right panel is initialized with the viewer for the latest available step.

The module intentionally keeps layout assembly separate from callback behavior.
Callbacks update the stores, styles, product options, plotting area, and log
window after the initial component tree has been created.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dash import dcc, html

from . import ids
from .session import get_session
from .workflow.registry import CLICKABLE_RULES, ENABLE_RULES, ORDERED_STEPS, STEP_BY_ID


# Small helper for a "row": button + dropdown/label
def control_row(step: str, button: Any, right: Any, clickable: bool) -> html.Div:
    """
    Build one row in the left-hand workflow control panel.

    Each row contains an optional run button and a right-side option widget.  The
    row itself is also clickable when the corresponding product can be viewed.
    Row clicks are handled by the general viewer callbacks using Dash
    pattern-matching IDs.

    Parameters
    ----------
    step : :class:`str`
        Workflow step key associated with the row.
    button : object
        Dash component used as the left-side run button, or :class:`None` for
        rows that do not expose a run button.
    right : object
        Dash component displayed on the right side of the row, typically a
        :class:`dash.dcc.Dropdown`.
    clickable : :class:`bool`
        Whether the row should respond to row-click selection events.

    Returns
    -------
    :class:`dash.html.Div`
        Row component with a pattern-matching ID of type ``"control-row"``.
    """
    return html.Div(
        [
            html.Div(button, style={"flex": "0 0 auto", "marginRight": "8px"}) if button else None,
            html.Div(right, style={"flex": "1 1 auto"}),
        ],
        id={"type": "control-row", "step": step},
        n_clicks=0,
        disable_n_clicks=not clickable,
        style={
            "display": "flex",
            "alignItems": "center",
            "marginBottom": "10px",
            "padding": "6px 6px",
            "borderRadius": "8px",
            "border": "1px solid transparent",
            "cursor": "pointer" if clickable else "default",
            "opacity": 1.0 if clickable else 0.55,
        },
        className="control-row"
    )


def file_list_for_step(data_files: dict[str, Any], step: str) -> list[Path]:
    """
    Normalize a registered product entry into a list of paths.

    Dropdown-style steps store one product path per raw input, while label-style
    steps store a single singleton path.  This helper gives the layout a common
    list interface when building dropdown options.

    Parameters
    ----------
    data_files : dict[str, Any]
        Product registry from
        :attr:`~grid_calibration.gui.session.CalibrationSession.products`.
    step : :class:`str`
        Workflow step key to read from ``data_files``.

    Returns
    -------
    list[pathlib.Path]
        Existing paths for the requested step.  Missing products are returned as
        an empty list.
    """
    v = data_files.get(step, [])
    if v is None:
        return []
    if isinstance(v, list):
        return v
    # label-based steps store a single Path
    return [v]


def build_layout() -> html.Div:
    """
    Build the complete Dash layout for the extraction GUI.

    The initial selected/active step is the latest step with a registered
    product, falling back to ``"raw-image"``.  This lets sessions resume from an
    existing output directory without forcing users to rerun earlier steps.

    Returns
    -------
    :class:`dash.html.Div`
        Root Dash component for the GUI.
    """
    session = get_session()

    first_available_step = "raw-image"
    for step in list(reversed(ORDERED_STEPS)):
        if session.get(step):
            first_available_step = step
            break

    rows = []

    data_files = session.products
    for step in ORDERED_STEPS:
        enabled = ENABLE_RULES[step](data_files)
        clickable = CLICKABLE_RULES[step](data_files)

        # button
        button = None
        if step != "raw-image":
            button = html.Button(
                STEP_BY_ID[step].button_label,
                id=ids.step_button_id(step),
                disabled=not enabled,
                n_clicks=0,
            )

        # right-hand widget
        if STEP_BY_ID[step].option_kind == "dropdown":
            paths = file_list_for_step(data_files, step)
            if paths:
                options = [{"label": p.name, "value": i} for i, p in enumerate(paths)]
            else:
                options = [{"label": f"No {STEP_BY_ID[step].label.lower()} yet", "value": 0}]
            right = dcc.Dropdown(
                id=ids.step_dropdown_id(step),
                options=options,
                value=0,
                disabled=not enabled or not paths,
                clearable=False,
                className="dropdown-real",
            )
        else:
            value = data_files.get(step)
            if value:
                options = [{"label": value.name, "value": 0}]
            else:
                options = [{"label": f"No {STEP_BY_ID[step].label.lower()} yet", "value": 0}]
            right = dcc.Dropdown(
                id=ids.step_dropdown_id(step),
                options=options,
                value=0,
                clearable=False,
                searchable=False,
                disabled=not enabled or not value,
                className="dropdown-label",
            )

        rows.append(control_row(step, button, right, clickable=clickable))

    layout = html.Div(
        [
            html.Div(id=ids.LOG_AUTOSCROLL_DUMMY, style={"display": "none"}),

            dcc.Store(id=ids.STORE_CONTROL_STEPS, data=ORDERED_STEPS),
            dcc.Store(id=ids.STORE_ACTIVE_STEP, data=first_available_step),
            dcc.Store(id=ids.STORE_RUN_STEP, data=None),
            dcc.Store(id=ids.STORE_STEP_REQUEST, data=None),
            dcc.Store(id=ids.STORE_STEP_RESULT, data=None),
            dcc.Store(id=ids.STORE_SELECTED_STEP, data=first_available_step),

            dcc.Interval(id=ids.LOG_POLL_INTERVAL, interval=800, n_intervals=0),

            html.Div(
                [
                    # LEFT COLUMN: controls
                    html.Div(
                        [
                            html.H3("Grid Calibration Extraction"),
                            html.Label("Raw images"),
                            *rows,
                            html.Hr(),

                            html.Button(
                                "Exit",
                                id=ids.BTN_EXIT,
                                n_clicks=0,
                                className="button-exit",
                            ),
                            html.Div(id=ids.STATUS_TEXT, className="status-text"),
                        ],
                        className="control-panel",
                    ),

                    # RIGHT COLUMN: image + log
                    html.Div(
                        [
                            html.Div(
                                dcc.Loading(
                                    type="default",
                                    parent_className="plot-loading",
                                    children=html.Div(
                                        children=STEP_BY_ID[first_available_step].viewer_func(0),
                                        id=ids.PLOTTING_AREA,
                                        className="plot-area",
                                    ),
                                ),
                                className="plot-panel",
                            ),

                            html.Div(
                                id=ids.LOG_WINDOW,
                                children="Log output will appear here...",
                                className="log-window",
                            ),
                        ],
                        className="content-panel",
                    )
                ],
                className="app-main",
            ),
        ],
        className="app-shell",
    )

    return layout
