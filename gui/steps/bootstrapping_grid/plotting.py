from __future__ import annotations

from typing import Dict

import numpy as np
import logging
from ...plot_utils import make_div_from_fig_dict, reset_layout
from ..unwrapped_grid.plotting import unwrapped_graph
from dash import dcc, html
from ... import ids
from ..nominal_grid.plotting import _load_unwrapped_grid, overplot_annotated_nominal_groups, nominal_groups_styling

logger = logging.getLogger(__name__)

def _load_bootstrapping_params() -> Dict[str, np.ndarray]:
    from .spec import DEFAULT_PARAMETERS
    from ...session import get_session
    session = get_session()
    product = session.get("bootstrapping-grid")
    default = False
    if product is None:
        default = True
    elif not product.exists():
        default = True
    else:
        data = np.load(product, allow_pickle=True)
        params = data.get("params", DEFAULT_PARAMETERS).item()
        if params != DEFAULT_PARAMETERS:
            logger.info(f"Loaded bootstrapping grid params from {product}: {params}")
    if default:
        logger.info(f"Using default parameters for bootstrapping grid search.")
        params = DEFAULT_PARAMETERS
    return params

def bootstrapping_fig():
    from ...session import get_session
    session = get_session()
    product = session.get("bootstrapping-grid")
    if product is None:
        product = session.get("nominal-grid")
    nominal_assignment = np.load(product, allow_pickle=True)["data"]

    data = _load_unwrapped_grid()

    fig = unwrapped_graph(data["theta"], data["r"], data["idx"])

    fig = overplot_annotated_nominal_groups(fig, nominal_assignment)

    nominal_fig, multiple_conflicts_flag = nominal_groups_styling(fig)

    return nominal_fig, multiple_conflicts_flag

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
    params = _load_bootstrapping_params()

    nominal_div = plot_bootstrapping_grid(None)
    from ...session import get_session
    session = get_session()
    nominal_assignment = np.load(session.get("nominal-grid"), allow_pickle=True)["data"]

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