# GONet_Wizard/grid_calibration/gui/layout.py

from dash import html, dcc
from .server import app
from .plot_utils import pipeline_plotters

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

ordered_steps = ["averaged-grid", "grid-points", "full-array", "raw-image"]

for step in ordered_steps:
    if app.server.config["data_files"].get(step):
        first_available_step = step
        break

print("First available step:", first_available_step)

# Small helper for a "row": button + dropdown/label
def control_row(step, button, right_component, clickable=True):
    style = {
        "display": "flex",
        "alignItems": "center",
        "marginBottom": "10px",
        "padding": "6px 6px",
        "borderRadius": "8px",
        "border": "1px solid transparent",
        "userSelect": "none",
        "cursor": "pointer" if clickable else "default",
        "opacity": 1.0 if clickable else 0.55,
    }

    return html.Div(
        [
            html.Div(button, style={"flex": "0 0 auto", "marginRight": "8px"}) if button else None,
            html.Div(right_component, style={"flex": "1 1 auto"}),
        ],
        id={"type": "control-row", "step": step},
        n_clicks=0,
        disable_n_clicks=not clickable,
        style=style,
    )


layout = html.Div(
    [
        html.Div(id="log-autoscroll-dummy", style={"display": "none"}),
        html.Div(id="run_full_pipeline_trigger", style={"display": "none"}),
        # hidden stores for lists of files (to be filled by callbacks)
        dcc.Store(id="raw-files-store"),
        dcc.Store(id="full-array-files-store"),
        dcc.Store(id="grid-points-files-store"),
        dcc.Store(id="averaged-grid-store"),
        dcc.Store(id="log-store"),
        dcc.Store(
            id="control-row-steps-store",
            data=["raw-image", "full-array", "grid-points", "averaged-grid"],
        ),
        dcc.Store(id="active-step-store", data=first_available_step),
        dcc.Store(id="pipeline-run", data=False),
        dcc.Interval(id="log-poll-interval", interval=800, n_intervals=0),
        html.Div(
            [
                # LEFT COLUMN: controls
                html.Div(
                    [
                        html.H3("Grid Calibration Extraction"),

                        # Row 0 – raw images selection (no button, just a dropdown)
                        html.Label("Raw images"),
                        control_row(
                            "raw-image",
                            html.Div(style={"width": "1px"}),  # placeholder, keeps alignment
                            dcc.Dropdown(
                                id="raw-image-dropdown",
                                options=raw_files_options,
                                value=raw_files_options[0]["value"],
                                clearable=False,
                                placeholder="No images loaded yet",
                            ),
                        ),
                        html.Hr(),

                        # Row 1 – Build full arrays
                        control_row(
                            "full-array",
                            html.Button(
                                "1. Build full arrays",
                                id="btn-full-array",
                                n_clicks=0,
                            ),
                            dcc.Dropdown(
                                id="full-array-dropdown",
                                disabled= False if full_array_files_options else True,
                                options=full_array_files_options,
                                value=0 if full_array_files_options else None,
                                clearable=False,
                                placeholder="No full-array files yet",
                            ),
                            clickable = True if full_array_files_options else False,
                        ),

                        # Row 2 – Detect grid points
                        control_row(
                            "grid-points",
                            html.Button(
                                "2. Detect grid points",
                                id="btn-detect-grid",
                                disabled=False if full_array_files_options else True,
                                n_clicks=0,
                            ),
                            dcc.Dropdown(
                                id="grid-points-dropdown",
                                disabled=False if grid_points_files_options else True,
                                options=grid_points_files_options,
                                value=0 if grid_points_files_options else None,
                                clearable=False,
                                placeholder="No grid-points files yet",
                            ),
                            clickable = True if grid_points_files_options else False
                        ),

                        # Row 3 – Average grids
                        control_row(
                            "averaged-grid",
                            html.Button(
                                "3. Average grids",
                                id="btn-average-grid",
                                disabled=False if grid_points_files_options else True,
                                n_clicks=0,
                            ),
                            html.Div(
                                id="averaged-grid-label",
                                children= averaged_grid_files if averaged_grid_files else "No averaged grid yet",
                                style={
                                    "border": "1px solid #ccc",
                                    "padding": "4px 6px",
                                    "borderRadius": "4px",
                                    "minHeight": "32px",
                                    "display": "flex",
                                    "alignItems": "center",
                                },
                            ),
                            clickable = True if averaged_grid_files else False
                        ),

                        html.Hr(),

                        # Row 4 – Run all steps
                        html.Button(
                            "Run all steps",
                            id="btn-run-all",
                            n_clicks=0,
                            style={"width": "100%"},
                        ),

                        html.Hr(),

                        # Row 5 – Exit
                        html.Button(
                            "Exit",
                            id="btn-exit",
                            n_clicks=0,
                            style={"width": "100%"},
                        ),

                        html.Div(id="status-text", style={"marginTop": "10px"}),
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
                                id="load-main-image",
                                type="default",
                                children=html.Div(
                                    children = pipeline_plotters[first_available_step](0),
                                    id="plotting-area",
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
                            id="log-window",
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
