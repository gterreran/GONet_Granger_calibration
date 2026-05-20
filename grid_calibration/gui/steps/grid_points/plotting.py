# grid_calibration/gui/steps/grid_points/plotting.py
"""
Viewer functions for grid-point products.

This module overlays detected grid points on top of the corresponding
full-array image. The plotting layer is intentionally read-only: it retrieves
products through the step
:class:`~grid_calibration.gui.workflow.product_io.ProductIO` descriptors but
does not create or register products itself.
"""

from __future__ import annotations

import numpy as np
from dash import dcc, html
from ...plot_utils import _weighted_centroid, _robust_limits, _apply_initial_zoom, colorscale, plot_layout
from ... import ids

from ..full_array import product_io as full_array_io
from ..full_array.keys import IMAGE_KEY
from .keys import GRID_KEY
from .spec import product_io as grid_points_io

def plot_grid_array(
    idx: int,
    *,
    zoom_half_size: int = 250,
    average: bool = False,
    dragmode: str = "pan",
    cut: bool = False,
) -> html.Div:
    """
    Render detected grid points over the corresponding full-array image.

    Parameters
    ----------
    idx : :class:`int`
        Index of the selected per-input product.
    zoom_half_size : :class:`int`, optional
        Half-size of the initial zoom window in pixels.
    average : :class:`bool`, optional
        If ``True``, overlay the singleton averaged-grid product instead of the
        selected per-input grid-points product.
    dragmode : :class:`str`, optional
        Plotly drag mode for the image viewer.
    cut : :class:`bool`, optional
        If ``True``, crop the displayed image around the weighted centroid to
        reduce rendering cost and focus on the central region.

    Returns
    -------
    :class:`dash.html.Div`
        Dash container holding the Plotly image viewer and scatter overlay.
        Returns a small error placeholder if required products are unavailable.
    """

    full_array_paths = full_array_io.get()
    if not full_array_paths:
        return html.Div("No full-array files loaded.", style={"color": "crimson"})

    if idx < 0 or idx >= len(full_array_paths):
        return html.Div(f"Index out of range: {idx}", style={"color": "crimson"})

    npz_path = full_array_paths[idx]
    data = full_array_io.load(npz_path)

    img_full = np.asarray(data[IMAGE_KEY])

    ny_full, nx_full = img_full.shape

    # Determine zoom/cut region centered on weighted centroid
    cy, cx = _weighted_centroid(img_full)
    y0 = int(max(0, np.floor(cy - zoom_half_size)))
    y1 = int(min(ny_full, np.ceil(cy + zoom_half_size + 1)))
    x0 = int(max(0, np.floor(cx - zoom_half_size)))
    x1 = int(min(nx_full, np.ceil(cx + zoom_half_size + 1)))

    # --- Choose whether to crop (cut) or keep full image
    if cut:
        img = img_full[y0:y1, x0:x1]
        # Keep original pixel coordinates by specifying x/y grids
        heatmap_x = np.arange(x0, x1)
        heatmap_y = np.arange(y0, y1)
    else:
        img = img_full
        heatmap_x = None
        heatmap_y = None

    vmin, vmax = _robust_limits(img, 1, 99)

    # --- Full-array image figure
    heatmap_trace = dict(
        type="heatmap",
        z=img,
        zmin=vmin,
        zmax=vmax,
        colorscale=colorscale,
        showscale=False,
        hovertemplate="x=%{x}<br>y=%{y}<br>val=%{z}<extra></extra>",
    )
    if cut:
        heatmap_trace["x"] = heatmap_x
        heatmap_trace["y"] = heatmap_y

    img_fig = {
        "data": [heatmap_trace],
        "layout": {**plot_layout},
    }

    # --- Load grid points layer
    if average:
        from ..averaged_grid import product_io as averaged_grid_io
        grid_data = averaged_grid_io.load()
    else:
        grid_files = grid_points_io.get()
        if not grid_files:
            return html.Div("No grid files loaded.", style={"color": "crimson"})
        if idx < 0 or idx >= len(grid_files):
            return html.Div(f"Index out of range: {idx}", style={"color": "crimson"})
        grid_data = grid_points_io.load(grid_files[idx])

    grid = grid_data[GRID_KEY]

    grid_x_full = grid[:, 1]
    grid_y_full = grid[:, 0]

    # If we cut, filter points to the visible region to keep scatter light-weight
    if cut:
        m = (grid_x_full >= x0) & (grid_x_full <= (x1 - 1)) & (grid_y_full >= y0) & (grid_y_full <= (y1 - 1))
        grid_x = grid_x_full[m]
        grid_y = grid_y_full[m]
    else:
        grid_x = grid_x_full
        grid_y = grid_y_full

    img_fig["data"].append(
        dict(
            type="scatter",
            x=grid_x,
            y=grid_y,
            mode="markers",
            marker=dict(color="red", size=6, symbol="x"),
            name="Detected Grid Points",
            line=dict(color="red", width=2),
            showlegend=False,
            hovertemplate="x=%{x}<br>y=%{y}<extra></extra>",
        )
    )

    # Image-like axes (origin upper-left) + square pixels
    img_fig["layout"]["yaxis"] = dict(
        autorange="reversed",
        showgrid=False,
        zeroline=False,
        scaleanchor="x",
        scaleratio=1,
    )
    img_fig["layout"]["xaxis"] = dict(showgrid=False, zeroline=False)

    if cut:
        img_fig["layout"]["xaxis"]["range"] = [x0, x1 - 1]
        img_fig["layout"]["yaxis"]["range"] = [y1 - 1, y0]
    else:
        img_fig["layout"]["xaxis"]["range"] = [0, nx_full - 1]
        img_fig["layout"]["yaxis"]["range"] = [ny_full - 1, 0]
        _apply_initial_zoom(img_fig, cy, cx, img_full.shape, half_size=zoom_half_size)

    img_fig["layout"].update(
        margin=dict(l=10, r=10, t=40, b=10),
        height=520,
        uirevision=f"full-array-{npz_path}-cut={cut}-box={x0},{y0},{x1},{y1}",
        dragmode=dragmode,
    )

    return html.Div(
        [
            html.Div(
                id=ids.FIGURE_CONTAINER_ID,
                children=dcc.Graph(
                    id=ids.GRID_GRAPH_ID,
                    figure=img_fig,
                    config={
                        "displaylogo": False,
                        "scrollZoom": True,
                        "responsive": True,
                    },
                    style={"height": "100%", "width": "100%"},
                ),
                style={
                    "display": "flex",
                    "flexDirection": "row",
                    "height": "70vh",
                    "width": "100%",
                    "gap": "8px",
                },
            )
        ],
        style={"width": "100%"},
    )
