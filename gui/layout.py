# GONet_Wizard/grid_calibration/gui/layout.py

from dash import html, dcc
from .server import app
from .plot_utils import pipeline_plotters
from . import ids
from .steps import ORDERED_STEPS, StepSpec, STEPS, ENABLE_RULES, CLICKABLE_RULES
from .data_index import file_list_for_step

raw_files_options = [{"label": f"{p.name}", "value": i}
                      for i, p in enumerate(app.server.config["data_files"]["raw-image"])
                      ]

full_array_files_options = [{"label": f"{p.name}", "value": i}
                           for i, p in enumerate(app.server.config["data_files"].get("full-array", []))
                           ]

grid_points_files_options = [{"label": f"{p.name}", "value": i}
                            for i, p in enumerate(app.server.config["data_files"].get("grid-points", []))
                            ]
averaged_grid_files = app.server.config.get("data_files").get("averaged-grid", None)

calibrated_grid_files = app.server.config.get("data_files").get("calibrated-grid", None)

first_available_step = "raw-image"
for step in list(reversed(ORDERED_STEPS)):
    if app.server.config["data_files"].get(step):
        first_available_step = step
        break

# Small helper for a "row": button + dropdown/label
def control_row(step: StepSpec, button, right, clickable: bool):
    return html.Div(
        [
            html.Div(button, style={"flex": "0 0 auto", "marginRight": "8px"}) if button else None,
            html.Div(right, style={"flex": "1 1 auto"}),
        ],
        id={"type": "control-row", "step": step.step},
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
    )

rows = []

data_files = app.server.config["data_files"]
for step in STEPS:
    enabled = ENABLE_RULES[step.step](data_files)
    clickable = CLICKABLE_RULES[step.step](data_files)

    # button
    button = None
    if step.step != "raw-image":
        button = html.Button(
            step.button_label,
            id=ids.step_button_id(step.step),
            disabled=not enabled,
            n_clicks=0,
        )

    # right-hand widget
    if step.option_kind == "dropdown":
        paths = file_list_for_step(data_files, step.step)
        if paths:
            options = [{"label": p.name, "value": i} for i, p in enumerate(paths)]
        else:
            options = [{"label": f"No {step.label.lower()} yet", "value": 0}]
        right = dcc.Dropdown(
            id=ids.step_dropdown_id(step.step),
            options=options,
            value=0,
            disabled=not enabled or not paths,
            clearable=False,
            className="dropdown-real",
        )
    else:
        value = data_files.get(step.step)
        label = value.name if value else f"No {step.label.lower()} yet"
        if value:
            options = [{"label": value.name, "value": 0}]
            disabled = False   # data exists
        else:
            options = [{"label": f"No {step.label.lower()} yet", "value": 0}]
            disabled = True
        right = dcc.Dropdown(
            id=ids.step_dropdown_id(step.step),
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
        # hidden stores for lists of files (to be filled by callbacks)
        dcc.Store(
            id=ids.STORE_CONTROL_STEPS,
            data=ORDERED_STEPS,
        ),
        dcc.Store(id=ids.STORE_ACTIVE_STEP, data=first_available_step),
        dcc.Store(id=ids.STORE_RUN_STEP, data=None),
        dcc.Interval(id=ids.LOG_POLL_INTERVAL, interval=800, n_intervals=0),
        html.Div(
            [
                # LEFT COLUMN: controls
                html.Div(
                    [
                        html.H3("Grid Calibration Extraction"),

                        # Row 0 – raw images selection (no button, just a dropdown)
                        html.Label("Raw images"),

                        *rows,

                        html.Hr(),

                        # Row 5 – Exit
                        html.Button(
                            "Exit",
                            id=ids.BTN_EXIT,
                            n_clicks=0,
                            style={"width": "100%"},
                        ),

                        html.Div(id=ids.STATUS_TEXT, style={"marginTop": "10px"}),
                    ],
                    style={
                        "width": "28%",
                        "display": "inline-block",
                        "verticalAlign": "top",
                        "padding": "10px",
                        "boxSizing": "border-box",
                    },
                ),

                # RIGHT COLUMN: image + log
                html.Div(
                    [
                        html.Div(   # <-- wrapper that owns the space
                            dcc.Loading(
                                type="default",
                                children=html.Div(
                                    children = pipeline_plotters[first_available_step](0),
                                    id=ids.PLOTTING_AREA,
                                    style={
                                        "width": "100%",
                                        "height": "100%"
                                    }
                                ),
                            ),
                            style={
                                "flex": "1 1 auto",     # take remaining vertical space
                                "minHeight": 0,         # IMPORTANT for plotly in flexbox
                                "border": "0px",
                            },
                        ),

                        html.Div(
                            id=ids.LOG_WINDOW,
                            children="Log output will appear here...",
                            style={
                                "flex": "0 0 15vh",     # fixed height
                                "height": "15vh",
                                "marginTop": "10px",
                                "padding": "6px 8px",
                                "border": "1px solid #ccc",
                                "borderRadius": "4px",
                                "backgroundColor": "#111",
                                "color": "#eee",
                                "fontFamily": "monospace",
                                "fontSize": "12px",
                                "overflowY": "scroll",
                                "whiteSpace": "pre-wrap",
                            },
                        ),
                    ],
                    style={
                        "width": "72%",
                        "display": "flex",
                        "flexDirection": "column",
                        "verticalAlign": "top",
                        "padding": "10px",
                        "boxSizing": "border-box",
                        "height": "calc(100vh - 20px)",  # pin the column height
                        "minHeight": 0,                  # IMPORTANT
                    },
                )
            ],
            style={"width": "100%", "display": "flex", "flexDirection": "row"},
        ),
    ]
)
