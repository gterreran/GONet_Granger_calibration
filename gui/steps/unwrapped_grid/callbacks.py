from __future__ import annotations

from typing import Any, Optional, Tuple
import logging
import numpy as np
from dash import Input, Output, State, ctx, no_update, html

from ... import ids
from ...server import app
from ..grid_points.plotting import _load_grid

logger = logging.getLogger(__name__)

# -------------------------
# Helpers
# -------------------------

def _extract_click_xy(click_data: Optional[dict[str, Any]]) -> Optional[Tuple[float, float]]:
    if not click_data or "points" not in click_data or not click_data["points"]:
        return None
    p0 = click_data["points"][0]
    if "x" not in p0 or "y" not in p0:
        return None
    return float(p0["x"]), float(p0["y"])


def _get_grid_points_from_figure(fig: dict[str, Any]) -> np.ndarray:
    """
    Extract (x,y) grid points from the figure's scatter trace.

    We look for the trace with name == "Detected Grid Points". If you ever change
    that name, update it here or make it an ids constant.
    """
    if not fig:
        return np.empty((0, 2), dtype=float)

    for tr in fig.get("data", []):
        # Expecting the scatter you showed: name="Detected Grid Points"
        if tr.get("type") == "scatter" and tr.get("name") == "Detected Grid Points":
            x = np.asarray(tr.get("x", []), dtype=float)
            y = np.asarray(tr.get("y", []), dtype=float)
            if x.size == 0 or y.size == 0:
                return np.empty((0, 2), dtype=float)
            n = min(x.size, y.size)
            return np.column_stack([x[:n], y[:n]])

    return np.empty((0, 2), dtype=float)


def _snap_to_nearest(x: float, y: float, pts_xy: np.ndarray) -> Tuple[float, float, int, float]:
    dx = pts_xy[:, 0] - x
    dy = pts_xy[:, 1] - y
    d2 = dx * dx + dy * dy
    i = int(np.argmin(d2))
    return float(pts_xy[i, 0]), float(pts_xy[i, 1]), i, float(np.sqrt(d2[i]))


def _format_xy(pt: Optional[dict[str, Any]]) -> str:
    if not pt or pt.get("x") is None or pt.get("y") is None:
        return "(—, —)"
    return f"({pt['x']:.2f}, {pt['y']:.2f})"


def _overlay_center_markers(
    fig: dict[str, Any],
    pending: Optional[dict[str, Any]],
    confirmed: Optional[dict[str, Any]],
) -> dict[str, Any]:
    """
    Remove and re-add marker traces for pending + confirmed center.
    """
    fig = dict(fig)  # copy
    data = list(fig.get("data", []))

    def keep_trace(tr: dict[str, Any]) -> bool:
        return tr.get("name") not in ("center:pending", "center:confirmed")

    data = [tr for tr in data if keep_trace(tr)]

    if pending and pending.get("x") is not None and pending.get("y") is not None:
        data.append(
            {
                "type": "scatter",
                "mode": "markers",
                "name": "center:pending",
                "x": [pending["x"]],
                "y": [pending["y"]],
                "marker": {"size": 14, "symbol": "x"},
                "hovertemplate": "Pending center<br>x=%{x:.2f}<br>y=%{y:.2f}<extra></extra>",
                "showlegend": False,
            }
        )

    if confirmed and confirmed.get("x") is not None and confirmed.get("y") is not None:
        data.append(
            {
                "type": "scatter",
                "mode": "markers",
                "name": "center:confirmed",
                "x": [confirmed["x"]],
                "y": [confirmed["y"]],
                "marker": {"size": 16, "symbol": "cross"},
                "hovertemplate": "Confirmed center<br>x=%{x:.2f}<br>y=%{y:.2f}<extra></extra>",
                "showlegend": False,
            }
        )

    fig["data"] = data
    return fig


# -------------------------
# Callbacks
# -------------------------

@app.callback(
    Output(ids.PENDING_STORE_ID, "data"),
    Input(ids.GRID_GRAPH_ID, "clickData"),
    State(ids.MODE_RADIO_ID, "value"),
    State(ids.GRID_GRAPH_ID, "figure"),
    prevent_initial_call=True,
)
def set_pending_center(click_data, mode, fig):
    xy = _extract_click_xy(click_data)
    logger.info(f"  extracted click xy: {xy}")
    if xy is None:
        return no_update

    x, y = xy

    if mode == "free":
        return {"x": x, "y": y, "mode": "free"}

    # snap mode: extract points from figure
    pts = _get_grid_points_from_figure(fig)
    if pts.shape[0] == 0:
        # fall back to free if no points in figure
        return {"x": x, "y": y, "mode": "free", "note": "no grid points in figure"}

    xs, ys, i_min, d_min = _snap_to_nearest(x, y, pts)
    return {"x": xs, "y": ys, "mode": "snap", "nearest_index": i_min, "distance": d_min}


@app.callback(
    Output(ids.CENTER_STORE_ID, "data"),
    Input(ids.CONFIRM_BTN_ID, "n_clicks"),
    Input(ids.RESET_BTN_ID, "n_clicks"),
    State(ids.PENDING_STORE_ID, "data"),
    prevent_initial_call=True,
)
def confirm_or_reset_center(_n_confirm, _n_reset, pending):
    trig = ctx.triggered_id
    if trig == ids.RESET_BTN_ID:
        return None
    if trig == ids.CONFIRM_BTN_ID:
        if not pending:
            return no_update
        return pending
    return no_update


@app.callback(
    Output(ids.UNWRAPPING_STATUS_ID, "children"),
    Input(ids.PENDING_STORE_ID, "data"),
    Input(ids.CENTER_STORE_ID, "data"),
)
def update_status(pending, confirmed):
    pending_txt = _format_xy(pending)
    confirmed_txt = _format_xy(confirmed)

    extra = ""
    if pending and pending.get("mode") == "snap":
        i = pending.get("nearest_index")
        d = pending.get("distance")
        if i is not None and d is not None:
            extra = f"  [snap: i={i}, d={d:.2f}px]"

    return [
        html.Div(f"Pending:   {pending_txt}{extra}"),
        html.Div(f"Confirmed: {confirmed_txt}"),
    ]


@app.callback(
    Output(ids.GRID_GRAPH_ID, "figure", allow_duplicate=True),
    Output(ids.STORE_STEP_RESULT, "data", allow_duplicate=True),
    # --------------------- 
    Input(ids.PENDING_STORE_ID, "data"),
    Input(ids.CENTER_STORE_ID, "data"),
    # ---------------------
    State(ids.GRID_GRAPH_ID, "figure"),
    # ---------------------
    prevent_initial_call=True,
)
def update_calibration_figure(pending, confirmed, fig):
    """
    Update the main calibration figure.

    - If no confirmed center: show image + grid + pending/confirmed markers
    - If confirmed center: replace figure with unwrapped grid (θ vs r)
    """
    from ...session import get_session
    session = get_session()
    # ----------------------------
    # Case 1: confirmed center → UNWRAPPED VIEW
    # ----------------------------
    if confirmed and confirmed.get("x") is not None and confirmed.get("y") is not None:
        averaged_grid_path = session.get("averaged-grid")
        logger.info(f"Loading averaged grid from {averaged_grid_path}")
        pts = _load_grid(averaged_grid_path)["grid"]

        # create and index array
        idx = np.arange(pts.shape[0])

        cx = float(confirmed["x"])
        cy = float(confirmed["y"])

        dx = pts[:, 1] - cx
        dy = pts[:, 0] - cy
        r = np.hypot(dx, dy)
        theta = np.degrees(np.arctan2(dy, dx))
        theta = np.mod(theta, 360.0)

        order = np.argsort(theta)
        idx = idx[order]
        theta = theta[order]
        r = r[order]
        pts = pts[order]

        out_npz = session.expected_path("unwrapped-grid")
        np.savez_compressed(out_npz, idx=idx, theta=theta, r=r, pts=pts, center={"x": cx, "y": cy})
        logger.info(f"Saved unwrapped grid to {out_npz}")

        session.set("unwrapped-grid", out_npz)

        result = {
            "step": "unwrapped-grid",
            "status": "completed",
            "request_token": ctx.triggered[0]["prop_id"],
        }
        return no_update, result

    # ----------------------------
    # Case 2: no confirmed center → IMAGE VIEW
    # ----------------------------
    return _overlay_center_markers(fig, pending, confirmed), no_update
