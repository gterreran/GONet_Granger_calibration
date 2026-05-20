# grid_calibration/gui/steps/full_array/plotting.py
"""
Viewer functions for full-array products.

The plotting layer is intentionally read-only. It obtains registered product
paths through the step's :class:`~grid_calibration.gui.workflow.product_io.ProductIO`,
loads the selected NPZ product, and returns Dash components for the shared
viewer callback.

No products are created or registered by this module.
"""

from __future__ import annotations

from typing import Dict

import numpy as np
import plotly.graph_objects as go
from dash import dcc, html
from .keys import IMAGE_KEY

from ...plot_utils import _weighted_centroid, _robust_limits, _apply_initial_zoom, plot_layout

from .spec import product_io as full_array_product_io

CHANNEL_COLORS = {
    "red": "red",
    "green1": "forestgreen",
    "green2": "limegreen",
    "blue": "blue",
}
"""
Display colors used for channel histogram overlays.
"""

def _hist_overlay_figure(data: Dict[str, np.ndarray], *, prefix: str, title: str) -> go.Figure:
    """
    Build an overlaid histogram figure from stored diagnostics.

    Parameters
    ----------
    data : :class:`dict`
        Loaded full-array product data. Histogram arrays are expected to follow
        the key pattern ``"<prefix>_hist_bins_<channel>"`` and
        ``"<prefix>_hist_density_<channel>"``.
    prefix : :class:`str`
        Histogram family to plot. Expected values are ``"raw"`` or
        ``"matched"``.
    title : :class:`str`
        Figure title.

    Returns
    -------
    :class:`plotly.graph_objects.Figure`
        Plotly figure containing one line trace per available channel.
    """
    fig = go.Figure()

    for ch, color in CHANNEL_COLORS.items():
        bins_key = f"{prefix}_hist_bins_{ch}"
        dens_key = f"{prefix}_hist_density_{ch}"

        if bins_key not in data or dens_key not in data:
            continue

        x = data[bins_key]
        y = data[dens_key]

        fig.add_trace(
            go.Scatter(
                x=x,
                y=y,
                mode="lines",
                line=dict(color=color, width=2),
                name=ch,
                showlegend=False,
                hovertemplate=(
                    f"{ch}<br>"
                    "value=%{x}<br>"
                    "density=%{y}<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        title=title,
        margin=dict(l=40, r=10, t=40, b=30),
        showlegend=False,
        **plot_layout,
    )

    fig.update_xaxes(title="Pixel value")
    fig.update_yaxes(title="Density")

    return fig


def plot_full_array_product(idx: int, *, zoom_half_size: int = 250):
    """
    Render one full-array product and its histogram diagnostics.

    Parameters
    ----------
    idx : :class:`int`
        Index of the selected full-array product in the per-input product list
        registered for the step.
    zoom_half_size : :class:`int`, optional
        Half-size of the initial image zoom window in pixels. For example,
        ``250`` gives a ``500 x 500`` initial view.

    Returns
    -------
    :class:`dash.html.Div`
        Dash container holding the image viewer and histogram figures. If the
        selected product is unavailable or malformed, returns a small error
        placeholder instead.
    """
    data_files = full_array_product_io.get()
    if not data_files:
        return html.Div("No data files loaded.", style={"color": "crimson"})

    if idx < 0 or idx >= len(data_files):
        return html.Div(f"Index out of range: {idx}", style={"color": "crimson"})

    npz_path = data_files[idx]
    data = full_array_product_io.load(npz_path)

    if IMAGE_KEY not in data:
        return html.Div(f"'{npz_path.name}' has no '{IMAGE_KEY}' key.", style={"color": "crimson"})

    img = np.asarray(data[IMAGE_KEY])
    if img.ndim != 2:
        return html.Div("Expected 2D full-array image.", style={"color": "crimson"})

    # --- Full-array image figure
    ny, nx = img.shape
    vmin, vmax = _robust_limits(img, 1, 99)

    img_fig = go.Figure(
        data=[
            go.Heatmap(
                z=img,
                zmin=vmin,
                zmax=vmax,
                colorscale="Gray",
                showscale=False,
                hovertemplate="x=%{x}<br>y=%{y}<br>val=%{z}<extra></extra>",
            )
        ]
    )

    # image-like axes (origin upper-left) + square pixels
    img_fig.update_yaxes(autorange="reversed", showgrid=False, zeroline=False, scaleanchor="x", scaleratio=1)
    img_fig.update_xaxes(showgrid=False, zeroline=False)

    # IMPORTANT: make "Reset axes" go back to FULL image, not the initial zoom
    img_fig.update_xaxes(range=[0, nx - 1], autorange=False)
    img_fig.update_yaxes(range=[ny - 1, 0], autorange=False)

    # then apply initial zoom (still reversible via Reset Axes)
    cy, cx = _weighted_centroid(img)
    _apply_initial_zoom(img_fig, cy, cx, img.shape, half_size=zoom_half_size)

    img_fig.update_layout(
        margin=dict(l=10, r=10, t=40, b=10),
        height=520,
        uirevision=f"full-array-{npz_path}",
        dragmode="pan",
        **plot_layout,
    )

    raw_hist_fig = _hist_overlay_figure(data, prefix="raw", title="RAW channel histograms (from diagnostics)")
    matched_hist_fig = _hist_overlay_figure(data, prefix="matched", title="Matched channel histograms (from diagnostics)")

    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        dcc.Graph(
                            id="full-array-image-graph",
                            figure=img_fig,
                            config={
                                "displaylogo": False,
                                "scrollZoom": True,
                                "responsive": True,
                            },
                            style={
                                "height": "100%",
                                "width": "100%",
                            },
                        ),
                        style={
                            "flex": "3",
                            "minWidth": "0",
                            "height": "100%",
                        },
                    ),

                    html.Div(
                        [
                            dcc.Graph(
                                id="full-array-raw-hist-graph",
                                figure=raw_hist_fig,
                                config={"displaylogo": False, "responsive": True},
                                style={"height": "50%", "width": "100%"},
                            ),
                            dcc.Graph(
                                id="full-array-matched-hist-graph",
                                figure=matched_hist_fig,
                                config={"displaylogo": False, "responsive": True},
                                style={"height": "50%", "width": "100%"},
                            ),
                        ],
                        style={
                            "flex": "1",
                            "minWidth": "0",
                            "display": "flex",
                            "flexDirection": "column",
                            "height": "100%",
                        },
                    ),
                ],
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
