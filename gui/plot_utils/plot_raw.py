# plot_utils.py
from __future__ import annotations

from pathlib import Path
from typing import Dict

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import dcc, html

from .core import _weighted_centroid, _robust_limits, _apply_initial_zoom
from ..server import app
from GONet_Wizard.GONet_utils import GONetFileRaw # type: ignore


# Server-side cache: filepath -> channel -> float32 2D array
_RAW_CHANNEL_CACHE: Dict[str, Dict[str, np.ndarray]] = {}


def _load_raw_channels(file_path: Path) -> Dict[str, np.ndarray]:
    key = str(file_path)
    if key in _RAW_CHANNEL_CACHE:
        return _RAW_CHANNEL_CACHE[key]

    go_raw = GONetFileRaw.from_file(file_path, meta=False)
    go_raw.remove_overscan()

    channels = ["red", "green1", "green2", "blue"]
    out: Dict[str, np.ndarray] = {}
    for c in channels:
        arr = np.asarray(go_raw.get_channel(c), dtype=np.float32)
        out[c] = arr

    _RAW_CHANNEL_CACHE[key] = out
    return out





def plot_raw_image(idx: int):
    data_files = app.server.config["data_files"]["raw"]
    if not data_files:
        return html.Div("No data files loaded.", style={"color": "crimson"})

    if idx < 0 or idx >= len(data_files):
        return html.Div(f"Index out of range: {idx}", style={"color": "crimson"})

    file_path = Path(data_files[idx])
    chans = _load_raw_channels(file_path)

    order = [("red", 1, 1), ("green1", 1, 2), ("green2", 2, 1), ("blue", 2, 2)]

    fig = make_subplots(
        rows=2,
        cols=2,
        subplot_titles=[c for c, _, _ in order],
        horizontal_spacing=0.03,
        vertical_spacing=0.08,
    )

    ny, nx = chans["green1"].shape

    full_xrange = [0, nx - 1]
    full_yrange = [ny - 1, 0]  # reversed

    # Add each channel as a heatmap (more robust than go.Image for float data)
    for c, r, col in order:
        img = chans[c]
        vmin, vmax = _robust_limits(img, 1, 99)

        fig.add_trace(
            go.Heatmap(
                z=img,
                zmin=vmin,
                zmax=vmax,
                colorscale="Gray",
                showscale=False,
                hovertemplate="x=%{x}<br>y=%{y}<br>val=%{z}<extra></extra>",
            ),
            row=r,
            col=col,
        )

    # Make it behave like images (origin upper-left) + square pixels + synced zoom
    # Subplot axis names in Plotly:
    # (1,1): xaxis,  yaxis
    # (1,2): xaxis2, yaxis2
    # (2,1): xaxis3, yaxis3
    # (2,2): xaxis4, yaxis4

    # 1) Hide grids/zero lines
    for i in range(1, 5):
        fig.update_xaxes(showgrid=False, zeroline=False, row=(1 if i <= 2 else 2), col=(1 if i in (1, 3) else 2))
        fig.update_yaxes(showgrid=False, zeroline=False, row=(1 if i <= 2 else 2), col=(1 if i in (1, 3) else 2))

    # 2) Link axes explicitly to the first subplot
    fig.update_xaxes(matches="x", row=1, col=1)
    fig.update_xaxes(matches="x", row=1, col=2)
    fig.update_xaxes(matches="x", row=2, col=1)
    fig.update_xaxes(matches="x", row=2, col=2)

    fig.update_yaxes(matches="y", row=1, col=1)
    fig.update_yaxes(matches="y", row=1, col=2)
    fig.update_yaxes(matches="y", row=2, col=1)
    fig.update_yaxes(matches="y", row=2, col=2)

    # 3) Force square pixels: y scale anchored to x for each subplot
    fig.update_yaxes(scaleanchor="x", scaleratio=1, row=1, col=1)
    fig.update_yaxes(scaleanchor="x2", scaleratio=1, row=1, col=2)
    fig.update_yaxes(scaleanchor="x3", scaleratio=1, row=2, col=1)
    fig.update_yaxes(scaleanchor="x4", scaleratio=1, row=2, col=2)

    fig.update_layout(
        autosize=True,
        height=None,
        margin=dict(l=10, r=10, t=40, b=10),
        uirevision="raw-image-view",
        dragmode="pan",
    )

    img_for_center = chans["green1"]
    cy, cx = _weighted_centroid(img_for_center)

    for r, c in [(1,1), (1,2), (2,1), (2,2)]:
        fig.update_xaxes(range=full_xrange, autorange=False, row=r, col=c)
        fig.update_yaxes(range=full_yrange, autorange=False, row=r, col=c)

    # Apply a 500x500 zoom (half_size=250)
    _apply_initial_zoom(fig, cy, cx, img_for_center.shape, half_size=150)

    return html.Div(
        dcc.Graph(
            id="raw-quad-graph",
            figure=fig,
            config={"displaylogo": False, "scrollZoom": True, "responsive": True},
            style={"height": "100%", "width": "100%"},
        )
    )
