# grid_calibration/gui/steps/nominal_grid/plotting.py
"""
Plotting and interactive-layout helpers for the nominal-grid step.

This module contains the Dash components and Plotly figure builders used to
inspect nominal assignments and edit selected records. It is intentionally
separate from :mod:`grid_calibration.gui.steps.nominal_grid.processing`, which
contains the numerical assignment logic.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import logging
from ...plot_utils import make_div_from_fig_dict, reset_layout
from ..unwrapped_grid.plotting import unwrapped_graph
from dash import dcc, html
from ... import ids
from .processing import detect_nominal
from .spec import product_io as nominal_product_io
from ..unwrapped_grid.spec import product_io as unwrapped_grid_product_io
from .params import load_parameters
from .spec import DATA_KEY, PARAMS_KEY

logger = logging.getLogger(__name__)

class RGBAColor:
    """
    Utility class to manage RGBA colors with a default transparency.

    Parameters
    ----------
    r : int
        Red channel (0-255).
    g : int
        Green channel (0-255).
    b : int
        Blue channel (0-255).
    alpha : float
        Default alpha channel (0-1).
    """

    def __init__(self, r: int, g: int, b: int, alpha: float = 1.0):
        self.r = r
        self.g = g
        self.b = b
        self.alpha = alpha

    def rgba(self, alpha: float | None = None) -> str:
        """
        Return RGBA string.

        Parameters
        ----------
        alpha : float | None
            Optional alpha override.

        Returns
        -------
        str
            rgba(...) string usable by Plotly.
        """
        a = self.alpha if alpha is None else alpha
        return f"rgba({self.r},{self.g},{self.b},{a})"

    def dim(self, factor: float = 0.3) -> str:
        """
        Return a dimmed color with reduced alpha.

        Parameters
        ----------
        factor : float
            Multiplicative factor applied to alpha.

        Returns
        -------
        str
            Dimmed rgba(...) string.
        """
        return self.rgba(self.alpha * factor)

    def __str__(self):
        return self.rgba()

RING_COLOR = RGBAColor(255, 179, 71, 0.9)      # amber
SPOKE_COLOR = RGBAColor(124, 255, 107, 0.9)     # lime
INTERSECTION_COLOR = RGBAColor(255, 94, 168, 1.0)  # magenta
COMPONENT_ERROR_COLOR = RGBAColor(255, 0, 0, 0.9)         # red

def nominal_groups_styling(fig, selected_point=None):
    mulitple_rings_flag = False
    mulitple_spokes_flag = False
    ring_groups = {}
    spoke_groups = {}
    for i,trace in enumerate(fig["data"][1:-1]):
        if trace["customdata"]["kind"] == "ring":
            nominal_r = trace["customdata"]["nominal_r"]
            if nominal_r not in ring_groups:
                ring_groups[nominal_r] = []
            else:
                mulitple_rings_flag = True
            ring_groups[nominal_r].append(i)
        elif trace["customdata"]["kind"] == "spoke":
            nominal_theta = trace["customdata"]["nominal_theta"]
            if nominal_theta not in spoke_groups:
                spoke_groups[nominal_theta] = []
            else:
                mulitple_spokes_flag = True
            spoke_groups[nominal_theta].append(i)

    if mulitple_rings_flag:
        logger.warning(f"Multiple rings with the same nominal value detected.")
    if mulitple_spokes_flag:
        logger.warning(f"Multiple spokes with the same nominal value detected.")

    if (mulitple_rings_flag or mulitple_spokes_flag):
        fig["data"][-1]["marker"]["color"] = INTERSECTION_COLOR.dim()

    for i, trace in enumerate(fig["data"][1:-1]):
        if trace["customdata"]["kind"] == "ring":
            nominal_r = trace["customdata"]["nominal_r"]
            if len(ring_groups[nominal_r]) > 1:
                if selected_point is None or trace["customdata"]["circle_index"] == selected_point["circle_index"]:
                    if selected_point is None:
                        fig["layout"]["annotations"][i]["font"]["size"] = 9
                    else:
                        fig["layout"]["annotations"][i]["font"]["size"] = 12
                    trace["line"]["color"] = str(COMPONENT_ERROR_COLOR)
                    fig["layout"]["annotations"][i]["font"]["color"] = str(COMPONENT_ERROR_COLOR)
                else:
                    fig["layout"]["annotations"][i]["font"]["size"] = 9
                    trace["line"]["color"] = COMPONENT_ERROR_COLOR.dim()
                    fig["layout"]["annotations"][i]["font"]["color"] = COMPONENT_ERROR_COLOR.dim()
            
            else:
                if selected_point is None:
                    fig["layout"]["annotations"][i]["font"]["size"] = 9
                    if mulitple_rings_flag or mulitple_spokes_flag:
                        trace["line"]["color"] = RING_COLOR.dim()
                        fig["layout"]["annotations"][i]["font"]["color"] = RING_COLOR.dim()
                    else:
                        trace["line"]["color"] = str(RING_COLOR)
                        fig["layout"]["annotations"][i]["font"]["color"] = str(RING_COLOR)
                elif trace["customdata"]["circle_index"] == selected_point["circle_index"]:
                    fig["layout"]["annotations"][i]["font"]["size"] = 12
                    trace["line"]["color"] = str(RING_COLOR)
                    fig["layout"]["annotations"][i]["font"]["color"] = str(RING_COLOR)
                else:
                    fig["layout"]["annotations"][i]["font"]["size"] = 9
                    trace["line"]["color"] = RING_COLOR.dim()
                    fig["layout"]["annotations"][i]["font"]["color"] = RING_COLOR.dim()

        if trace["customdata"]["kind"] == "spoke":
            nominal_theta = trace["customdata"]["nominal_theta"]
            if len(spoke_groups[nominal_theta]) > 1:
                if selected_point is None or trace["customdata"]["spoke_index"] == selected_point["spoke_index"]:
                    if selected_point is None:
                        fig["layout"]["annotations"][i]["font"]["size"] = 9
                    else:
                        fig["layout"]["annotations"][i]["font"]["size"] = 12
                    trace["line"]["color"] = str(COMPONENT_ERROR_COLOR)
                    fig["layout"]["annotations"][i]["font"]["color"] = str(COMPONENT_ERROR_COLOR)
                else:
                    fig["layout"]["annotations"][i]["font"]["size"] = 9
                    trace["line"]["color"] = COMPONENT_ERROR_COLOR.dim()
                    fig["layout"]["annotations"][i]["font"]["color"] = COMPONENT_ERROR_COLOR.dim()
            
            else:
                if selected_point is None:
                    fig["layout"]["annotations"][i]["font"]["size"] = 9
                    if mulitple_rings_flag or mulitple_spokes_flag:
                        trace["line"]["color"] = str(SPOKE_COLOR.dim())
                        fig["layout"]["annotations"][i]["font"]["color"] = str(SPOKE_COLOR.dim())
                    else:
                        trace["line"]["color"] = str(SPOKE_COLOR)
                        fig["layout"]["annotations"][i]["font"]["color"] = str(SPOKE_COLOR)
                elif trace["customdata"]["spoke_index"] == selected_point["spoke_index"]:
                    fig["layout"]["annotations"][i]["font"]["size"] = 12
                    trace["line"]["color"] = str(SPOKE_COLOR)
                    fig["layout"]["annotations"][i]["font"]["color"] = str(SPOKE_COLOR)
                else:
                    fig["layout"]["annotations"][i]["font"]["size"] = 9
                    trace["line"]["color"] = SPOKE_COLOR.dim()
                    fig["layout"]["annotations"][i]["font"]["color"] = SPOKE_COLOR.dim()

    return fig, mulitple_rings_flag or mulitple_spokes_flag

def _unwrap_theta_for_display(theta, idx=None, split_deg=180.0):
    """
    Unwrap one theta group for display only.

    Returns
    -------
    theta_display : np.ndarray
        Possibly shifted theta values.
    shifted_idx : set
        Point indices whose theta was shifted.
    shift : float
        Applied shift: -360, 0, or +360.
    """
    theta = np.asarray(theta, dtype=float).copy()

    if idx is None:
        idx = np.arange(theta.size)
    idx = np.asarray(idx)

    if theta.size < 2:
        return theta, set(), 0.0

    if np.nanmax(theta) - np.nanmin(theta) < split_deg:
        return theta, set(), 0.0

    low = theta < split_deg
    high = theta >= split_deg

    if np.sum(high) >= np.sum(low):
        theta[low] += 360.0
        return theta, set(idx[low]), 360.0
    else:
        theta[high] -= 360.0
        return theta, set(idx[high]), -360.0

def _shift_background_points_by_idx(fig, shifted_idx, shift):
    """
    Apply the same display-only theta shift to fig['data'][0] points.
    """
    if not shifted_idx or shift == 0:
        return fig

    x = np.asarray(fig["data"][0]["x"], dtype=float).copy()
    customdata = fig["data"][0].get("customdata", None)

    if customdata is None:
        return fig

    # Supports either list of idx values or list/dict customdata entries.
    point_idx = []
    for item in customdata:
        if isinstance(item, dict):
            point_idx.append(item.get("idx", None))
        else:
            point_idx.append(item)

    point_idx = np.asarray(point_idx)
    mask = np.isin(point_idx, list(shifted_idx))

    x[mask] += shift
    fig["data"][0]["x"] = x.tolist()

    return fig

def overplot_annotated_nominal_groups(
    fig: dict,
    nominal_assignment: Optional[list[dict]],
) -> dict:

    intersections_indexes = set()

    groups_theta = {}
    for el in nominal_assignment:
        i = el["circle_index"]
        if i not in intersections_indexes:
            intersections_indexes.add(i)
        if i not in groups_theta:
            groups_theta[i] = {
                "circle_index": el["circle_index"],
                "nominal_r": el["nominal_r"],
                "theta": [],
                "r": [],
                "idx": []
            }
        groups_theta[i]["theta"].append(el["theta"])
        groups_theta[i]["r"].append(el["r"])
        groups_theta[i]["idx"].append(el["idx"])

    groups_spoke = {}
    for el in nominal_assignment:
        i = el["spoke_index"]
        if i not in intersections_indexes:
            intersections_indexes.add(i)
        if i not in groups_spoke:
            groups_spoke[i] = {
                "spoke_index": el["spoke_index"],
                "nominal_theta": el["nominal_theta"],
                "theta": [],
                "r": [],
                "idx": []
            }
        groups_spoke[i]["theta"].append(el["theta"])
        groups_spoke[i]["r"].append(el["r"])
        groups_spoke[i]["idx"].append(el["idx"])

    keep = [i for i in range(len(fig["data"][0]["x"])) if i not in intersections_indexes]

    fig["data"][0]["x"] = [fig["data"][0]["x"][i] for i in keep]
    fig["data"][0]["y"] = [fig["data"][0]["y"][i] for i in keep]

    if "customdata" in fig["data"][0]:
        fig["data"][0]["customdata"] = [fig["data"][0]["customdata"][i] for i in keep]

    fig["data"][0]["marker"]["opacity"] = 0.5

    # Determine display-only theta shifts from spoke groups first.
    theta_display_shift_by_idx = {}

    for g in groups_spoke.values():
        ordered = np.argsort(g["r"])
        x_raw = np.array(g["theta"])[ordered]
        idx = np.array(g["idx"])[ordered]

        _, shifted_idx, shift = _unwrap_theta_for_display(x_raw, idx=idx)

        for point_idx in shifted_idx:
            theta_display_shift_by_idx[int(point_idx)] = shift

        fig = _shift_background_points_by_idx(fig, shifted_idx, shift)

    # --- plot and annotate rings ---
    for i in sorted(groups_theta.keys()):
        g = groups_theta[i]
        theta = np.array(g["theta"], dtype=float)
        idx = np.array(g["idx"], dtype=int)

        x = np.array([
            t + theta_display_shift_by_idx.get(int(point_idx), 0.0)
            for t, point_idx in zip(theta, idx)
        ], dtype=float)
        y = np.array(g["r"], dtype=float)

        ordered = np.argsort(x)
        x = x[ordered]
        y = y[ordered]

        fig["data"].append({
            "type": "scatter",
            "mode": "lines",
            "x": x,
            "y": y,
            "customdata": {
                "kind": "ring",
                "circle_index": g["circle_index"],
                "nominal_r": g["nominal_r"],
            },
            "line": {"width": 1.8},
            "hoverskip": True,
            "hovertemplate": None,
            "hoverinfo": "skip",
            "showlegend": False,
        })

        # annotate near leftmost point
        x0, y0 = x[-1], y[-1]
        fig["layout"]["annotations"].append({
            "x": x0,
            "y": y0,
            "text": f"{g['nominal_r']:.1f}°",
            "showarrow": False,
            "font": {"size": 9},
            "xanchor": "left",
            "yanchor": "bottom",
        })

    # --- plot and annotate spokes ---
    for i in sorted(groups_spoke.keys()):
        g = groups_spoke[i]

        ordered = np.argsort(g["r"])
        x_raw = np.array(g["theta"])[ordered]
        y = np.array(g["r"])[ordered]
        idx = np.array(g["idx"])[ordered]

        x = np.array([
            t + theta_display_shift_by_idx.get(int(point_idx), 0.0)
            for t, point_idx in zip(x_raw, idx)
        ], dtype=float)

        fig["data"].append({
            "type": "scatter",
            "mode": "lines",
            "x": x,
            "y": y,
            "customdata": {
                "kind": "spoke",
                "spoke_index": g["spoke_index"],
                "nominal_theta": g["nominal_theta"],
            },
            "line": {"width": 1.8},
            "hoverskip": True,
            "hovertemplate": None,
            "hoverinfo": "skip",
            "showlegend": False,
        })

        # annotate near topmost point
        x0, y0 = x[-1], y[-1]
        fig["layout"]["annotations"].append({
            "x": x0,
            "y": y0,
            "text": f"{g['nominal_theta']:.1f}°",
            "showarrow": False,
            "textangle": 270,
            "font": {"size": 9},
            "xanchor": "left",
            "yanchor": "bottom",
        })

    # --- plot intersection points ---
    fig["data"].append({
        "type": "scatter",
        "mode": "markers",
        "x": [
            el["theta"] + theta_display_shift_by_idx.get(int(el["idx"]), 0.0)
            for el in nominal_assignment
        ],
        "y": [el["r"] for el in nominal_assignment],
        "marker": {"size": 5, "color": str(INTERSECTION_COLOR), "symbol": "o"},
        "customdata": nominal_assignment,
        "hovertemplate": (
            "θ=%{x:.2f}°<br>"
            "r=%{y:.2f}px<br>"
            "nominal_r""=%{customdata.nominal_r:.2f}°<br>"
            "nominal_theta=%{customdata.nominal_theta:.2f}°<extra></extra>"
        ),
        "showlegend": False,
    })

    return fig


def plot_nominal_grid(_) -> html.Div:
    nominal_assignment = nominal_product_io.load()[DATA_KEY]
    data = unwrapped_grid_product_io.load()

    fig = unwrapped_graph(data["theta"], data["r"], data["idx"])
    fig = overplot_annotated_nominal_groups(fig, nominal_assignment)

    nominal_fig, multiple_conflicts_flag = nominal_groups_styling(fig)
    nominal_fig = reset_layout(nominal_fig)

    return make_div_from_fig_dict(nominal_fig)


def fig_nominal_grid(params) -> html.Div:
    data = unwrapped_grid_product_io.load()

    nominal_assignment = detect_nominal(data, params)

    fig = unwrapped_graph(data["theta"], data["r"], data["idx"])
    nominal_fig = overplot_annotated_nominal_groups(fig, nominal_assignment)

    nominal_fig, multiple_conflicts_flag = nominal_groups_styling(nominal_fig)
    nominal_fig["layout"]["clickmode"] = "event+select"

    nominal_div = make_div_from_fig_dict(nominal_fig)

    return nominal_div, nominal_assignment, multiple_conflicts_flag



def initialize_nominal_grid() -> html.Div:
    """
    Build the interactive viewer layout for identifying the nominal values of grid and spokes.

    Returns
    -------
    dash.html.Div
        A Div containing the nominal grid identification UI.
    """
    
    logger.info("Initializing nominal grid viewer...")
    
    params = load_parameters()

    nominal_div, nominal_assignment, multiple_conflicts_flag = fig_nominal_grid(params)

    n_rings = len(set([a["circle_index"] for a in nominal_assignment]))
    n_spokes = len(set([a["spoke_index"] for a in nominal_assignment]))

    controls = html.Div(
        id =ids.NOMINAL_INTERACTIVE_CONTROLS_ID,
        children=[
            html.H4("Nominal Grid Identification", className="section-title"),

            html.Div(
                [
                    html.Label("Rings parameters", className="control-label"),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Label("max dist", className="mini-label"),
                                    dcc.Input(
                                        id=ids.RING_MAX_DIST_ID,
                                        type="number",
                                        value=params["ring_max_dist"],
                                        step=0.1,
                                        className="param-input",
                                    ),
                                ],
                                className="input-col",
                            ),
                            html.Div(
                                [
                                    html.Label("gate tol r", className="mini-label"),
                                    dcc.Input(
                                        id=ids.RING_GATE_TOL_R_ID,
                                        type="number",
                                        value=params["ring_gate_tol_r"],
                                        step=0.1,
                                        className="param-input",
                                    ),
                                ],
                                className="input-col",
                            ),
                            html.Div(
                                [
                                    html.Label("min group", className="mini-label"),
                                    dcc.Input(
                                        id=ids.MIN_RING_GROUP_ID,
                                        type="number",
                                        value=params["min_ring_group"],
                                        step=1,
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
                    html.Label("Spokes parameters", className="control-label"),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Label("max dist", className="mini-label"),
                                    dcc.Input(
                                        id=ids.SPOKE_MAX_DIST_ID,
                                        type="number",
                                        value=params["spoke_max_dist"],
                                        step=0.1,
                                        className="param-input",
                                    )
                                ],
                                className="input-col",
                            ),
                            html.Div(
                                [
                                    html.Label("min dist", className="mini-label"),
                                    dcc.Input(
                                        id=ids.SPOKE_MIN_DIST_ID,
                                        type="number",
                                        value=params["spoke_min_dist"],
                                        step=0.1,
                                        className="param-input",
                                    ),
                                ],
                                className="input-col",
                            ),
                            html.Div(
                                [
                                    html.Label("gate tol θ", className="mini-label"),
                                    dcc.Input(
                                        id=ids.SPOKE_GATE_TOL_THETA_ID,
                                        type="number",
                                        value=params["spoke_gate_tol_theta"],
                                        step=0.1,
                                        className="param-input",
                                    ),
                                ],
                                className="input-col",
                            ),
                            html.Div(
                                [
                                    html.Label("min group", className="mini-label"),
                                    dcc.Input(
                                        id=ids.MIN_SPOKE_GROUP_ID,
                                        type="number",
                                        value=params["min_spoke_group"],
                                        step=1,
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
                        "Find nominal grid",
                        id=ids.FIND_NOMINAL_BTN_ID,
                        n_clicks=0,
                        className="action-button",
                    ),
                    html.Button(
                        "Reset to default params",
                        id=ids.RESET_NOMINAL_BTN_ID,
                        n_clicks=0,
                        className="action-button",
                    ),
                    html.Button(
                        "Confirm nominal grid",
                        id=ids.CONFIRM_NOMINAL_BTN_ID,
                        n_clicks=0,
                        disabled=multiple_conflicts_flag,
                        className="action-button action-button-primary",
                    ),
                ],
                className="button-row",
            ),

            html.Div(
                id=ids.NOMINAL_STATUS_ID,
                children=[
                    html.Div(f"Rings found: {n_rings}"),
                    html.Div(f"Spokes found: {n_spokes}"),
                ],
                className="status-box",
            ),

            dcc.Store(
                id=ids.NOMINAL_ASSIGNMENT_ID,
                data=nominal_assignment,
            ),
            dcc.Store(
                id=ids.SELECTED_GRID_POINT_ID,
                data=None,
            ),

            html.Div(
                id=ids.RIGID_SHIFT_CONTROL_DIV_ID,
                children=[
                    html.Hr(className="section-divider"),

                    html.Label("Rigid shift control", className="control-label"),

                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Label("Shift θ spokes", className="sub-label"),
                                    html.Div(
                                        [
                                            html.Button("-", id=ids.SHIFT_SPOKES_DEC_ID, n_clicks=0, className="tiny-button"),
                                            html.Button("+", id=ids.SHIFT_SPOKES_INC_ID, n_clicks=0, className="tiny-button"),
                                        ],
                                        className="shift-button-row",
                                    ),
                                ],
                                className="shift-control-block",
                            ),

                            html.Div(className="vertical-divider"),

                            html.Div(
                                [
                                    html.Label("Shift r rings", className="sub-label"),
                                    html.Div(
                                        [
                                            html.Button("-", id=ids.SHIFT_RINGS_DEC_ID, n_clicks=0, className="tiny-button"),
                                            html.Button("+", id=ids.SHIFT_RINGS_INC_ID, n_clicks=0, className="tiny-button"),
                                        ],
                                        className="shift-button-row",
                                    ),
                                ],
                                className="shift-control-block",
                            ),
                        ],
                        className="shift-controls-row",
                    ),
                ],
            ),

            html.Div(
                id=ids.SELECTION_CONTROL_DIV_ID,
                children=[
                    html.Hr(className="section-divider"),

                    html.Label("Selection", className="control-label"),

                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Label("r selected ring", className="sub-label"),
                                    dcc.Input(
                                        id=ids.EDIT_NOMINAL_RING_ID,
                                        type="number",
                                        value=None,
                                        step=2.5,
                                        min=0,
                                        max=90,
                                        className="param-input",
                                    ),
                                    dcc.Store(id=ids.VALID_NOMINAL_RING_ID, data=None),
                                ],
                                className="input-col",
                            ),

                            html.Div(className="vertical-divider"),

                            html.Div(
                                [
                                    html.Label("θ selected spoke", className="sub-label"),
                                    dcc.Input(
                                        id=ids.EDIT_NOMINAL_SPOKE_ID,
                                        type="number",
                                        value=None,
                                        step=2.5,
                                        min=0,
                                        max=360,
                                        className="param-input",
                                    ),
                                    dcc.Store(id=ids.VALID_NOMINAL_SPOKE_ID, data=None),
                                ],
                                className="input-col",
                            ),
                        ],
                        className="selection-row",
                    ),
                ],
                className="selection-panel",
                style={"display": "none"},
            ),
        ],
        className="side-controls-panel",
    )

    return html.Div(
        [nominal_div, controls],
        className="two-panel-row",
    )
