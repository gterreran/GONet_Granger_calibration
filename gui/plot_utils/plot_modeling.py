from __future__ import annotations

from typing import Dict

import numpy as np
import logging

from .core import plot_layout, make_div_from_fig_dict
from .plot_unwrapped import unwrapped_graph
from dash import dcc, html
from .. import ids
from ..server import app
from ...modeling import DEFAULT_MODELING_PARAMS, GridData, FitResult
from .plot_bootstrapping import plot_bootstrapping_grid
from ..session import get_session

logger = logging.getLogger(__name__)

def _load_modeling_params():
    session = get_session(app)
    product = session.get("modeling-results")
    default = False
    if product is None:
        default = True
    elif not product.exists():
        default = True
    else:
        data = np.load(product, allow_pickle=True)
        params = data.get("fit_params", DEFAULT_MODELING_PARAMS).item()
        if params != DEFAULT_MODELING_PARAMS:
            logger.info(f"Loaded modeling params from {product}: {params}")
    if default:
        logger.info(f"Using default parameters for modeling grid search.")
        params = DEFAULT_MODELING_PARAMS
    return params

def modeling_fig(data, result):
    fig = {
        "data": [],
        "layout": {**plot_layout},
    }

    r_values = np.round(data.r_nom_deg / 2.5) * 2.5
    theta_values = np.round(data.theta_nom_deg / 2.5) * 2.5

    theta_nom_rad = np.deg2rad(data.theta_nom_deg)
    xu = data.r_nom_deg * np.cos(theta_nom_rad)
    yu = data.r_nom_deg * np.sin(theta_nom_rad)

    rx = data.x - result.pred_full["x_pred"]
    ry = data.y - result.pred_full["y_pred"]
    rn = np.hypot(rx, ry)[0]

    has_outliers = result.inlier_mask is not None and result.outlier_threshold_px is not None
    if has_outliers:
        inlier_mask = np.asarray(result.inlier_mask, dtype=bool)
        outlier_mask = ~inlier_mask
    else:
        outlier_mask = np.zeros(data.x.size, dtype=bool)

    # Reference circles
    theta_grid = np.deg2rad(np.linspace(0.0, 360.0, 720))
    for r0 in np.sort(np.unique(r_values[np.isfinite(r_values)])):
        fig["data"].append({
            "type": "scatter",
            "mode": "lines",
            "x": (r0 * np.cos(theta_grid)).tolist(),
            "y": (r0 * np.sin(theta_grid)).tolist(),
            "line": {"color": "rgba(220,220,220,0.22)", "width": 0.6},
            "hoverinfo": "skip",
            "showlegend": False,
        })

    # Reference spokes
    rmax = float(np.nanmax(r_values))
    for t0 in np.deg2rad(np.sort(np.unique(theta_values[np.isfinite(theta_values)]))):
        fig["data"].append({
            "type": "scatter",
            "mode": "lines",
            "x": [0.0, float(rmax * np.cos(t0))],
            "y": [0.0, float(rmax * np.sin(t0))],
            "line": {"color": "rgba(220,220,220,0.22)", "width": 0.6},
            "hoverinfo": "skip",
            "showlegend": False,
        })

    customdata = np.column_stack([
        data.r_nom_deg,
        data.theta_nom_deg,
        data.x,
        data.y,
    ])

    fig["data"].append({
        "type": "scatter",
        "mode": "markers",
        "x": xu.tolist(),
        "y": yu.tolist(),
        "customdata": customdata,
        "marker": {
            "color": rn.tolist(),
            "colorscale": "Viridis",
            "cmin": 0.0,
            "cmax": rn.max(),
            "size": 4,
            "opacity": 0.85,
            # remove black outlines
            "line": {"width": 0},
            "colorbar": {
                "title": {"text": "Residual<br>norm [px]"},
                "x": 1.03,
                "len": 0.75,
            },
        },
        "hovertemplate": (
            "x_nom: %{x:.2f} deg<br>"
            "y_nom: %{y:.2f} deg<br>"
            "r_nom: %{customdata[0]:.2f} deg<br>"
            "theta_nom: %{customdata[1]:.2f} deg<br>"
            "pixel_x: %{customdata[2]:.1f}<br>"
            "pixel_y: %{customdata[3]:.1f}<br>"
            "residual: %{marker.color:.2f} px"
            "<extra></extra>"
        ),
        "name": "Grid points",
    })

    if np.any(outlier_mask):
        fig["data"].append({
            "type": "scatter",
            "mode": "markers",
            "x": xu[outlier_mask].tolist(),
            "y": yu[outlier_mask].tolist(),
            "marker": {
                "color": "rgba(0,0,0,0)",
                "line": {"color": "red", "width": 1.3},
                "size": 14,
            },
            "hoverinfo": "skip",
            "name": "Rejected outliers",
        })

    fig["layout"].update({
        "title": "Undistorted nominal-grid check",
        "showlegend": True,
    })

    fig["layout"]["xaxis"].update({
        "title": r"$r_{\rm nom}\cos\theta_{\rm nom}\ {\rm [deg]}$",
        "zeroline": False,
        "scaleanchor": "y",
        "scaleratio": 1,
    })

    fig["layout"]["yaxis"].update({
        "title": r"$r_{\rm nom}\sin\theta_{\rm nom}\ {\rm [deg]}$",
        "zeroline": False,
    })

    fig["layout"].pop("aspectmode", None)
    fig["layout"]["showlegend"] = False
    return fig

def plot_modeling_results(_):
    session = get_session(app)
    bootstrapped_nominal_assignment_npz = session.get("bootstrapping-grid")
    data = GridData.from_npz(bootstrapped_nominal_assignment_npz)
    model_npz = session.get("modeling-results")
    result = FitResult.from_npz(model_npz)
    model_fig = modeling_fig(data, result)

    model_fig_div = make_div_from_fig_dict(model_fig)

    return model_fig_div

def initialize_modeling_results():
    """
    Build the interactive viewer layout for modeling fit.

    Returns
    -------
    dash.html.Div
        A Div containing the modeling UI.
    """
    
    logger.info("Initializing modeling viewer...")
    params = _load_modeling_params()

    modeling_div = plot_bootstrapping_grid(None)
    
    controls = html.Div(
        id =ids.MODELING_INTERACTIVE_CONTROLS_ID,
        children=[
            html.H4("Modeling parameters", className="section-title"),

            html.Div(
                [
                    #html.Label("Rings parameters", className="control-label"),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Label("Radial degree", className="mini-label"),
                                    dcc.Input(
                                        id=ids.MODELING_RADIAL_DEGREE_ID,
                                        type="number",
                                        value=params["radial-degree"],
                                        step=1,
                                        className="param-input",
                                    ),
                                ],
                                className="input-col",
                            ),
                            html.Div(
                                [
                                    html.Label("Harmonic radial degree", className="mini-label"),
                                    dcc.Input(
                                        id=ids.MODELING_HARMONIC_RADIAL_DEGREE_ID,
                                        type="number",
                                        value=params["harmonic-radial-degree"],
                                        step=1,
                                        className="param-input",
                                    ),
                                ],
                                className="input-col",
                            ),
                            html.Div(
                                [
                                    html.Label("Harmonic order", className="mini-label"),
                                    dcc.Input(
                                        id=ids.MODELING_HARMONIC_ORDER_ID,
                                        type="number",
                                        value=params["harmonic-order"],
                                        step=1,
                                        className="param-input",
                                    ),
                                ],
                                className="input-col",
                            ),
                            html.Div(
                                [
                                    html.Label("Sigma rejection", className="mini-label"),
                                    dcc.Input(
                                        id=ids.MODELING_SIGMA_REJECTION_ID,
                                        type="number",
                                        value=params["outlier-rejection-sigma"],
                                        step=0.1,
                                        className="param-input",
                                    ),
                                ],
                                className="input-col",
                            ),
                        ],
                        className="input-row",
                    ),
                ],
                className="control-group",
            ),

            html.Div(
                [
                    html.Button(
                        "Model grid",
                        id=ids.MODELING_BTN_ID,
                        n_clicks=0,
                        className="action-button",
                    ),
                    html.Button(
                        "Reset to default params",
                        id=ids.RESET_MODELING_BTN_ID,
                        n_clicks=0,
                        className="action-button",
                    ),
                ],
                className="button-row",
            ),

            html.Div(
                # checkbox to toggle pdf report generation on/off
                [
                    dcc.Checklist(
                        id=ids.MODELING_PDF_REPORT_CHECKLIST_ID,
                        options=[{"label": "Generate PDF report", "value": "generate"}],
                        value=["generate"],  # default to generating the report
                        className="param-input",
                    ),
                ],
                className="status-box",
            ),
        ],
        className="side-controls-panel",
    )

    return html.Div(
        [modeling_div, controls],
        className="two-panel-row",
    )