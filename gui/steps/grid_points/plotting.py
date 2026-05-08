from typing import Dict, Any
import numpy as np
from ..full_array.plotting import _load_full_array_npz
from dash import dcc, html
from ...plot_utils import _weighted_centroid, _robust_limits, _apply_initial_zoom, colorscale, plot_layout
from ...server import app
from ... import ids
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

def plot_grid_array(
    idx: int,
    *,
    zoom_half_size: int = 250,
    average: bool = False,
    dragmode: str = "pan",
    cut: bool = False,
) -> html.Div:
    from ...session import get_session
    session = get_session()
    data_files = session.get("full-array") or []
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

    img_full = np.asarray(data["image"])
    if img_full.ndim != 2:
        return html.Div("Expected 2D full-array image.", style={"color": "crimson"})

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
        # This preserves original coordinate reporting for clicks/hover
        heatmap_trace["x"] = heatmap_x
        heatmap_trace["y"] = heatmap_y

    img_fig = {
        "data": [heatmap_trace],
        "layout": {**plot_layout},
    }

    # --- Load grid points layer
    if average:
        grid_npz_path = session.get("averaged-grid")
    else:
        grid_files = session.get("grid-points") or []
        if not grid_files:
            return html.Div("No grid files loaded.", style={"color": "crimson"})
        if idx < 0 or idx >= len(grid_files):
            return html.Div(f"Index out of range: {idx}", style={"color": "crimson"})
        grid_npz_path = Path(grid_files[idx])

    if not grid_npz_path.exists():
        return html.Div(f"Missing file: {grid_npz_path}", style={"color": "crimson"})

    grid_data = _load_grid(grid_npz_path)

    if "grid" not in grid_data:
        return html.Div(f"'{grid_npz_path.name}' has no 'grid' key.", style={"color": "crimson"})

    grid = grid_data["grid"]
    if grid.ndim != 2 or grid.shape[1] != 2:
        return html.Div("Expected 'grid' to be Nx2 array.", style={"color": "crimson"})

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
        # When cut, the figure "full extent" is the cropped region (but in original coords)
        img_fig["layout"]["xaxis"]["range"] = [x0, x1 - 1]
        img_fig["layout"]["yaxis"]["range"] = [y1 - 1, y0]
    else:
        # Full extent is the full image
        img_fig["layout"]["xaxis"]["range"] = [0, nx_full - 1]
        img_fig["layout"]["yaxis"]["range"] = [ny_full - 1, 0]
        # Then apply initial zoom to centroid region
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
