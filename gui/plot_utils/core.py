import numpy as np

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
    for key in fig.layout:
        if key.startswith("xaxis"):
            fig["layout"][key].update({"range":[x0, x1], "autorange":False})
        elif key.startswith("yaxis"):
            fig["layout"][key].update({"range":[y1, y0], "autorange":False})
    