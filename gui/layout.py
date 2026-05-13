# grid_calibration/gui/layout.py

from dash import html, dcc
from typing import Any
from . import ids
from .workflow.registry import ORDERED_STEPS, ENABLE_RULES, CLICKABLE_RULES, STEP_BY_ID
from .session import get_session
from pathlib import Path

# Small helper for a "row": button + dropdown/label
def control_row(step: str, button, right, clickable: bool):
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
    Return a list of files for a dropdown-based step.
    """
    v = data_files.get(step, [])
    if v is None:
        return []
    if isinstance(v, list):
        return v
    # label-based steps store a single Path
    return [v]

def build_layout() -> html.Div:
    
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
            dcc.Store(id=ids.STORE_SELECTED_STEP, data=None),

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
                                        children = STEP_BY_ID[first_available_step].viewer_func(0),
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