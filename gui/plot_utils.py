# grid_calibration/gui/plot_utils.py
import numpy as np
from dash import dcc, html
from . import ids

colorscale = [
    [0.0, 'rgb(0, 0, 0)'],
    [0.09090909090909091, 'rgb(16, 16,16)'],
    [0.18181818181818182, 'rgb(38, 38, 38)'],
    [0.2727272727272727, 'rgb(59, 59, 59)'],
    [0.36363636363636365, 'rgb(81, 80, 80)'],
    [0.45454545454545453, 'rgb(102, 101, 101)'],
    [0.5454545454545454, 'rgb(124, 123, 122)'],
    [0.6363636363636364, 'rgb(146, 146, 145)'],
    [0.7272727272727273, 'rgb(171, 171, 170)'],
    [0.8181818181818182, 'rgb(197, 197, 195)'],
    [0.9090909090909091, 'rgb(224, 224, 223)'],
    [1.0, 'rgb(254, 254, 253)'],
]

plot_layout = {
    # dark backgrounds
    "paper_bgcolor": "rgba(0,0,0,0)",   # transparent so it blends with your Dash theme
    "plot_bgcolor": "#0f1117",

    # global text color
    "font": {"color": "#e8ecf3"},

    "xaxis": {
        "gridcolor": "#2a3242",
        "zerolinecolor": "#2a3242",
        "linecolor": "#2a3242",
    },

    "yaxis": {
        "gridcolor": "#2a3242",
        "zerolinecolor": "#2a3242",
        "linecolor": "#2a3242",
    },

    "hoverlabel": {
        "bgcolor": "#1d2330",
        "font": {"color": "#e8ecf3"},
    },
}

def reset_layout(fig):
    for ax in ("xaxis", "yaxis"):
        fig["layout"].setdefault(ax, {})

        fig["layout"][ax].pop("range", None)
        fig["layout"][ax].pop("scaleanchor", None)
        fig["layout"][ax].pop("scaleratio", None)
        fig["layout"][ax].pop("matches", None)
        fig["layout"][ax].pop("constrain", None)
        fig["layout"][ax].pop("constraintoward", None)

        fig["layout"][ax]["autorange"] = True

    fig["layout"].pop("aspectmode", None)
    
    return fig


def _weighted_centroid(img: np.ndarray, lo=70.0, hi=99.7) -> tuple[float, float]:
    vmin, vmax = np.percentile(img, [lo, hi])
    w = np.clip(img, vmin, vmax) - vmin
    w = np.where(w > 0, w, 0.0)
    s = float(np.sum(w))
    if s <= 0:
        # fallback: geometric center
        ny, nx = img.shape
        return float(ny / 2), float(nx / 2)

    yy, xx = np.indices(img.shape)
    cy = float(np.sum(yy * w) / s)
    cx = float(np.sum(xx * w) / s)
    return cy, cx


def _robust_limits(img: np.ndarray, lo=1.0, hi=99.0) -> tuple[float, float]:
    """Percentile-based display limits to avoid blank/washed plots."""
    finite = img[np.isfinite(img)]
    if finite.size == 0:
        return 0.0, 1.0
    vmin, vmax = np.percentile(finite, [lo, hi])
    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmin == vmax:
        vmin = float(np.nanmin(finite))
        vmax = float(np.nanmax(finite))
        if vmin == vmax:
            vmax = vmin + 1.0
    return float(vmin), float(vmax)


def _apply_initial_zoom(fig, center_y: float, center_x: float, shape, half_size: int = 250) -> None:
    ny, nx = shape
    cx = int(round(center_x))
    cy = int(round(center_y))

    x0 = max(0, cx - half_size)
    x1 = min(nx - 1, cx + half_size)
    y0 = max(0, cy - half_size)
    y1 = min(ny - 1, cy + half_size)

    # Apply to ALL subplots (because axes are matched, setting one is usually enough,
    # but doing all avoids Plotly edge-cases with autorange/matches).
    for key in fig["layout"]:
        if key.startswith("xaxis"):
            fig["layout"][key].update({"range":[x0, x1], "autorange":False})
        elif key.startswith("yaxis"):
            fig["layout"][key].update({"range":[y1, y0], "autorange":False})
    

def make_div_from_fig_dict(img_fig) -> dict:

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