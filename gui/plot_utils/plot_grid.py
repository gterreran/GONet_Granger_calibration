from typing import Dict, Any
import numpy as np
from .plot_full_array import _load_full_array_npz
import plotly.graph_objects as go
from dash import dcc, html
from .core import _weighted_centroid, _robust_limits, _apply_initial_zoom
from ..server import app
from pathlib import Path

# Server-side cache: filepath -> channel -> float32 2D array
_GRID_CACHE: Dict[str, Dict[str, np.ndarray]] = {}

def _load_grid(grid_npz_path: Path) -> Dict[str, np.ndarray]:
    key = str(grid_npz_path)
    if key in _GRID_CACHE:
        return _GRID_CACHE[key]

    data = np.load(grid_npz_path, allow_pickle=True)
    out: Dict[str, Any] = {k: data[k] for k in data.files}
    _GRID_CACHE[key] = out
    return out

def plot_grid_array(idx: int, *, zoom_half_size: int = 250, average: bool = False) -> html.Div:
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

    if average:
        grid_npz_path = Path(app.server.config.get("data_files")["averaged-grid"])
    else:
        grid_files = app.server.config.get("data_files")["grid-points"] or []

        if not grid_files:
            return html.Div("No grid files loaded.", style={"color": "crimson"})

        if idx < 0 or idx >= len(grid_files):
            return html.Div(f"Index out of range: {idx}", style={"color": "crimson"})

        grid_npz_path = Path(grid_files[idx])
    
    if not grid_npz_path.exists():
        return html.Div(f"Missing file: {grid_npz_path}", style={"color": "crimson"})

    # add grid points layer
    grid_data = _load_grid(grid_npz_path)

    if "grid" not in grid_data:
        return html.Div(f"'{grid_npz_path.name}' has no 'grid' key.", style={"color": "crimson"})

    grid = grid_data["grid"]
    if grid.ndim != 2 or grid.shape[1] != 2:
        return html.Div("Expected 'grid' to be Nx2 array.", style={"color": "crimson"})

    grid_x = grid[:, 1]
    grid_y = grid[:, 0]

    img_fig.add_trace(
        go.Scatter(
            x=grid_x,
            y=grid_y,
            mode="markers",
            marker=dict(color='red', size=6, symbol='x'),
            name="Detected Grid Points",
            line=dict(color='red', width=2),
            showlegend=False, # <-- legend removed
            hovertemplate=(
                "value=%{x}<br>"
                "density=%{y}<extra></extra>"
            ),
        )
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
        title=f"Full array: {npz_path.name}",
        margin=dict(l=10, r=10, t=40, b=10),
        height=520,
        uirevision=f"full-array-{npz_path}",  # keep zoom while logs update
        dragmode="pan",
    )

    return html.Div(
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
