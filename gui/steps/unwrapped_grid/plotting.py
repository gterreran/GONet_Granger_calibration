from __future__ import annotations

from dash import dcc, html
import logging
from ..grid_points.plotting import plot_grid_array
from ... import ids
import numpy as np

from ...plot_utils import make_div_from_fig_dict, plot_layout, reset_layout

logger = logging.getLogger(__name__)

def unwrapped_graph(theta, r, idx, alpha=1.0) -> dict:
    layout = {**plot_layout,
        "margin": {"l": 50, "r": 10, "t": 40, "b": 50},
        "height": 520,
        "annotations": [],
    }

    layout["xaxis"]["title"] = {"text": "θ (deg)"}
    layout["xaxis"]["range"] = [-10, 370]

    layout["yaxis"]["title"] = {"text": "r (px)"}

    layout["title"] = {
                "text": "Unwrapped grid (θ vs r)",
                "x": 0.02,
                "xanchor": "left",
            }

    return {
        "data": [
            {
                "type": "scattergl",
                "mode": "markers",
                "x": theta,
                "y": r,
                "customdata": idx,
                "marker": {
                    "size": 3,
                    "opacity": alpha,
                    "color": "#4cc9f0",   # bright cyan, excellent on dark backgrounds
                },
                "hovertemplate": (
                    "θ=%{x:.2f}°<br>"
                    "r=%{y:.2f}px<extra></extra>"
                ),
                "showlegend": False,
            }
        ],
        "layout": layout,
    }


def plot_unwrapped_grid(_) -> html.Div:
    from ...session import get_session
    session = get_session()
    product = session.get("unwrapped-grid")
    
    logger.info(f"Loading unwrapped grid data from '{product}'...")
    data = np.load(product, allow_pickle=True)
    fig = unwrapped_graph(data["theta"], data["r"], data["idx"])
    fig = reset_layout(fig)
    unwrapped_div = make_div_from_fig_dict(fig)

    return unwrapped_div
    

        

def initialize_unwrapped_grid() -> html.Div:
    """
    Build the interactive viewer layout for selecting the grid center.

    Returns
    -------
    dash.html.Div
        A Div containing the calibration center-selection UI.

    Notes
    -----
    - The graph figure is expected to be populated by your existing viewer callback,
      or by a dedicated calibration callback, using the available pipeline products:
        * full-array image (background)
        * averaged-grid points (scatter)
    - "pending" vs "confirmed" are intentionally separate states:
        * pending updates on every click
        * confirmed updates only when the user clicks "Confirm center"
    """

    logger.info("Initializing unwrapped grid viewer...")
    img_fig = plot_grid_array(0, zoom_half_size=100, average=True, dragmode=False, cut=True)

    controls = html.Div(
        id =ids.UNWRAPPING_INTERACTIVE_CONTROLS_ID,
        children=[
            html.H4("Grid: center selection", style={"marginTop": "0.25rem"}),

            html.Div(
                [
                    html.Label("Click mode", style={"fontWeight": "600"}),
                    dcc.RadioItems(
                        id=ids.MODE_RADIO_ID,
                        options=[
                            {"label": "Snap to nearest detected grid point", "value": "snap"},
                            {"label": "Free click (use raw pixel coords)", "value": "free"},
                        ],
                        value="snap",
                        inputStyle={"marginRight": "0.4rem"},
                        labelStyle={"display": "block", "marginBottom": "0.25rem"},
                    ),
                ],
                style={"marginBottom": "0.75rem"},
            ),

            html.Div(
                [
                    html.Button(
                        "Confirm center",
                        id=ids.CONFIRM_BTN_ID,
                        n_clicks=0,
                        style={"marginRight": "0.5rem"},
                    ),
                    html.Button(
                        "Reset",
                        id=ids.RESET_BTN_ID,
                        n_clicks=0,
                    ),
                ],
                style={"marginBottom": "0.75rem"},
            ),

            html.Div(
                id=ids.UNWRAPPING_STATUS_ID,
                children=[
                    html.Div("Pending: (—, —)"),
                    html.Div("Confirmed: (—, —)"),
                ],
                style={
                    "fontFamily": "monospace",
                    "fontSize": "0.95rem",
                    "whiteSpace": "pre-wrap",
                    "border": "1px solid #ddd",
                    "borderRadius": "6px",
                    "padding": "0.5rem",
                    "background": "#fafafa",
                },
            ),

            # Stores: these make the step self-contained.
            dcc.Store(id=ids.PENDING_STORE_ID, data=None),
            dcc.Store(id=ids.CENTER_STORE_ID, data=None),
        ],
        style={
            "width": "320px",
            "minWidth": "280px",
            "padding": "0.75rem",
            "borderLeft": "1px solid #e6e6e6",
        },
    )

    return html.Div(
        children = [img_fig, controls],
        style={
            "display": "flex",
            "flexDirection": "row",
            "gap": "0.0rem",
            "width": "100%",
        },
    )
