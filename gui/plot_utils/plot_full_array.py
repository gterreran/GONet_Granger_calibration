# plot_utils.py (additions)

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any

import numpy as np
import plotly.graph_objects as go
from dash import dcc, html

from .core import _weighted_centroid, _robust_limits, _apply_initial_zoom, plot_layout
from ..server import app

CHANNEL_COLORS = {
    "red": "red",
    "green1": "forestgreen",
    "green2": "limegreen",
    "blue": "blue",
}

# Server-side cache: npz_path -> loaded dict (arrays)
_FULL_ARRAY_NPZ_CACHE: Dict[str, Dict[str, Any]] = {}


def _load_full_array_npz(npz_path: Path) -> Dict[str, Any]:
    """
    Load a full-array .npz product and cache it server-side.
    """
    key = str(npz_path)
    if key in _FULL_ARRAY_NPZ_CACHE:
        return _FULL_ARRAY_NPZ_CACHE[key]

    data = np.load(npz_path, allow_pickle=True)
    out: Dict[str, Any] = {k: data[k] for k in data.files}
    _FULL_ARRAY_NPZ_CACHE[key] = out
    return out



def _hist_overlay_figure(data: Dict[str, np.ndarray], *, prefix: str, title: str) -> go.Figure:
    """
    Build an overlaid histogram figure from stored diagnostics.

    Parameters
    ----------
    data : dict
        Loaded npz data.
    prefix : {"raw", "matched"}
        Which diagnostics to plot.
    title : str
        Figure title.
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
                name=ch,          # name kept (useful for hover)
                showlegend=False, # <-- legend removed
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
        showlegend=False,  # <-- hard-disable legends
        **plot_layout,
    )

    fig.update_xaxes(title="Pixel value")
    fig.update_yaxes(title="Density")

    return fig


def plot_full_array_product(idx: int, *, zoom_half_size: int = 250):
    """
    Render the full-array image + stored histogram diagnostics from a *_full_array.npz.

    Parameters
    ----------
    idx : int
        Index of the full-array product in the data files list.
    zoom_half_size : int, optional
        Half-size of the initial zoom window (in pixels). 250 -> 500x500.

    Returns
    -------
    dash component
        html.Div containing the interactive plots.
    """
    data_files = app.server.config.get("data_files")["full-array"] or []
    if not data_files:
        return html.Div("No data files loaded.", style={"color": "crimson"})

    if idx < 0 or idx >= len(data_files):
        return html.Div(f"Index out of range: {idx}", style={"color": "crimson"})

    npz_path = Path(data_files[idx])

    if not npz_path.exists():
        return html.Div(f"Missing file: {npz_path}", style={"color": "crimson"})

    data = _load_full_array_npz(npz_path)

    if "image" not in data:
        return html.Div(f"'{npz_path.name}' has no 'image' key.", style={"color": "crimson"})

    img = np.asarray(data["image"])
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
                showscale=False,  # <-- remove color bar
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
        uirevision=f"full-array-{npz_path}",  # keep zoom while logs update
        dragmode="pan",
        **plot_layout,
    )

    raw_hist_fig = _hist_overlay_figure(data, prefix="raw", title="RAW channel histograms (from diagnostics)")
    matched_hist_fig = _hist_overlay_figure(data, prefix="matched", title="Matched channel histograms (from diagnostics)")

    return html.Div(
        [
            # OUTER ROW
            html.Div(
                [
                    # LEFT: full-array image
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
                            "flex": "3",              # <-- main visual weight
                            "minWidth": "0",          # important for flex + Plotly
                            "height": "100%",
                        },
                    ),

                    # RIGHT: histograms column
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
                            "flex": "1",              # <-- narrower column
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
                    "height": "70vh",               # <-- match your other plot areas
                    "width": "100%",
                    "gap": "8px",
                },
            )
        ],
        style={"width": "100%"},
    )

