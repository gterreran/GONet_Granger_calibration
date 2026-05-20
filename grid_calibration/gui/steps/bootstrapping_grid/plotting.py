# grid_calibration/gui/steps/bootstrapping_grid/plotting.py
"""
Plotting and interactive-layout helpers for the bootstrapping-grid step.

This module renders bootstrapped assignments and exposes the initialization UI
used by the interactive workflow. Numerical bootstrapping logic lives in the
:mod:`grid_calibration.gui.steps.bootstrapping_grid.processing` package.
"""

from __future__ import annotations

import logging
from ...plot_utils import make_div_from_fig_dict, reset_layout
from ..unwrapped_grid.plotting import unwrapped_graph
from dash import dcc, html
from ... import ids
from ..nominal_grid.plotting import overplot_annotated_nominal_groups, nominal_groups_styling

from .spec import product_io as bootstrapping_grid_io
from ..unwrapped_grid import product_io as unwrapped_grid_io
from ..unwrapped_grid.keys import THETA_KEY, R_KEY, IDX_KEY
from ..nominal_grid.keys import DATA_KEY as NOMINAL_DATA_KEY
from ..nominal_grid.spec import product_io as nominal_grid_io

from ....errors import MissingProductError
from .params import load_parameters
from .keys import DATA_KEY

logger = logging.getLogger(__name__)

def bootstrapping_fig():
    try:
        nominal_assignment = bootstrapping_grid_io.load()[DATA_KEY]
    except MissingProductError:
        nominal_assignment = nominal_grid_io.load()[NOMINAL_DATA_KEY]
    data = unwrapped_grid_io.load()

    fig = unwrapped_graph(data[THETA_KEY], data[R_KEY], data[IDX_KEY])
    fig = overplot_annotated_nominal_groups(fig, nominal_assignment)

    return nominal_groups_styling(fig)

def plot_bootstrapping_grid(_) -> html.Div:

    nominal_fig, multiple_conflicts_flag = bootstrapping_fig()
    nominal_fig = reset_layout(nominal_fig)
    nominal_div = make_div_from_fig_dict(nominal_fig)

    return nominal_div

def initialize_bootstrapping_grid():
    """
    Build the interactive viewer layout for bootstrapping values 
    from the current nominal values of the grid.

    Returns
    -------
    dash.html.Div
        A Div containing the bootstrapping  UI.
    """
    
    logger.info("Initializing bootstrapping viewer...")
    
    params = load_parameters()

    nominal_div = plot_bootstrapping_grid(None)
    nominal_assignment = nominal_grid_io.load()[NOMINAL_DATA_KEY]

    n_rings = len(set([a["circle_index"] for a in nominal_assignment]))
    n_spokes = len(set([a["spoke_index"] for a in nominal_assignment]))

    controls = html.Div(
        id =ids.BOOTSTRAPPING_INTERACTIVE_CONTROLS_ID,
        children=[
            html.H4("Bootstrapping parameters", className="section-title"),

            html.Div(
                [
                    #html.Label("Rings parameters", className="control-label"),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Label("spoke toll. (px)", className="mini-label"),
                                    dcc.Input(
                                        id=ids.BOOTSTRAPPING_SPOKE_TOL_ID,
                                        type="number",
                                        value=params["spoke_final_tol_px"],
                                        step=0.1,
                                        className="param-input",
                                    ),
                                ],
                                className="input-col",
                            ),
                            html.Div(
                                [
                                    html.Label("circle toll. (deg)", className="mini-label"),
                                    dcc.Input(
                                        id=ids.BOOTSTRAPPING_CIRCLE_TOL_ID,
                                        type="number",
                                        value=params["circle_snap_tol_deg"],
                                        step=0.1,
                                        className="param-input",
                                    ),
                                ],
                                className="input-col",
                            ),
                            html.Div(
                                [
                                    html.Label("circle poly degree", className="mini-label"),
                                    dcc.Input(
                                        id=ids.BOOTSTRAPPING_CIRCLE_POLY_DEGREE_ID,
                                        type="number",
                                        value=params["circle_fit_poly_degree"],
                                        step=1,
                                        className="param-input",
                                    ),
                                ],
                                className="input-col",
                            ),
                            html.Div(
                                [
                                    html.Label("parallel workers", className="mini-label"),
                                    dcc.Input(
                                        id=ids.BOOTSTRAPPING_PARALLEL_WORKERS_ID,
                                        type="number",
                                        value=params["max_workers"],
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
                        "Bootstrap grid",
                        id=ids.BOOTSTRAPPING_BTN_ID,
                        n_clicks=0,
                        className="action-button",
                    ),
                    html.Button(
                        "Reset to default params",
                        id=ids.RESET_BOOTSTRAPPING_BTN_ID,
                        n_clicks=0,
                        className="action-button",
                    ),
                ],
                className="button-row",
            ),

            html.Div(
                id=ids.BOOTSTRAPPING_STATUS_ID,
                children=[
                    html.Div(f"Rings found: {n_rings}"),
                    html.Div(f"Spokes found: {n_spokes}"),
                ],
                className="status-box",
            ),
        ],
        className="side-controls-panel",
    )

    return html.Div(
        [nominal_div, controls],
        className="two-panel-row",
    )
