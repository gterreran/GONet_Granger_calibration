
from __future__ import annotations

from typing import Dict, List, Optional, Tuple
import logging
import numpy as np
from scipy.spatial import cKDTree

logger = logging.getLogger(__name__)

DEFAULT_NOMINAL_PARAMS = {
    # ring grouping
    "ring_max_dist": 10.0, # max distance in pixels for chaining ring points
    "ring_gate_tol_r": 1.5, # gate tolerance in r for chaining ring points
    "min_ring_group": 150, # minimum points to keep a ring group after chaining

    # spoke grouping
    "spoke_max_dist": 35.0, # max distance in pixels for chaining spoke points
    "spoke_min_dist": 2.0, # minimum increase in r for chaining spoke points
    "spoke_gate_tol_theta": 0.3, # gate tolerance in theta (degrees) for chaining spoke points
    "min_spoke_group": 20, # minimum points to keep a spoke group after chaining

    # ring level estimation
    "bin_width_deg": 30.0, # width of theta bins (degrees) for estimating ring levels and wave
    "min_pts_per_bin": 10, # minimum points in a theta bin to use it for ring level estimation
    "n_wave_iter": 3, # number of iterations to perform for wave correction in ring level estimation
}

DEG_STEP = 2.5 # degrees per spoke, used for nominal assignment

# -----------------------------------------------------------------------------
# Small utilities
# -----------------------------------------------------------------------------
def wrap_delta(a: float, b: float, period: float) -> float:
    """Smallest absolute difference on a circle."""
    d = abs(b - a) % period
    return min(d, period - d)


def wrap_deg(theta_deg: np.ndarray) -> np.ndarray:
    """Wrap angles to [0, 360)."""
    return np.asarray(theta_deg) % 360.0

def robust_median_spacing(values: np.ndarray, *, min_sep: float = 2.0, max_sep: float = 200.0) -> float:
    """
    Estimate a typical spacing from sorted 1D values using the median of
    consecutive differences.
    """
    values = np.sort(np.asarray(values, dtype=float))
    if values.size < 2:
        return float("nan")

    dv = np.diff(values)
    good = (dv >= min_sep) & (dv <= max_sep)

    if np.any(good):
        return float(np.median(dv[good]))
    return float(np.median(dv))

def circular_mean_deg(theta_deg: np.ndarray) -> float:
    """Circular mean in degrees, returned in [0, 360)."""
    ang = np.deg2rad(theta_deg)
    s = np.sin(ang).mean()
    c = np.cos(ang).mean()
    return float(np.rad2deg(np.arctan2(s, c)) % 360.0)


def assign_nominal_circles(
    ring_levels_px: np.ndarray,
    *,
    spacing_px: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Assign each ring group to the nearest nominal circle.
    """
    k_circle = np.rint(ring_levels_px / spacing_px).astype(int)
    k_circle = np.clip(k_circle, 0, None)
    rho_circle = DEG_STEP * k_circle
    return k_circle, rho_circle


def spoke_group_theta_estimates(points: np.ndarray, groups_r: List[np.ndarray]) -> np.ndarray:
    """
    One representative theta per spoke group.
    """
    return np.array([circular_mean_deg(points[g, 0]) for g in groups_r], dtype=float)


def best_theta_offset(theta_g: np.ndarray, *, step: float = 2.5) -> float:
    """
    Find the offset theta0 that best aligns the spoke angles to a 2.5° grid.
    """
    theta_g = wrap_deg(theta_g)
    candidates = theta_g if theta_g.size <= 500 else np.random.choice(theta_g, size=500, replace=False)

    def score(theta0: float) -> float:
        x = (theta_g - theta0) % 360.0
        resid = ((x + step / 2) % step) - step / 2
        return float(np.median(np.abs(resid)))

    best0 = float(candidates[0])
    bests = score(best0)

    for t0 in candidates[1:]:
        s = score(float(t0))
        if s < bests:
            bests = s
            best0 = float(t0)

    return float(best0 % 360.0)


def assign_nominal_spokes(
    theta_g: np.ndarray,
    *,
    theta0: Optional[float] = None,
) -> Tuple[np.ndarray, np.ndarray, float]:
    """
    Assign each spoke group to the nearest nominal spoke angle.
    """
    theta_g = wrap_deg(theta_g)

    if theta0 is None:
        theta0 = best_theta_offset(theta_g, step=DEG_STEP)

    nspokes = int(round(360.0 / DEG_STEP))
    x = (theta_g - theta0) % 360.0
    k_spoke = np.rint(x / DEG_STEP).astype(int) % nspokes
    theta_nom = (k_spoke * DEG_STEP) % 360.0

    return k_spoke, theta_nom, float(theta0)

# -----------------------------------------------------------------------------
# Grouping
# -----------------------------------------------------------------------------

def chain_groups_closest_neighbor_with_axis_gate(
    points: np.ndarray,
    *,
    max_dist: float,
    gate_axis: int,
    gate_tol: float,
    gate_period: Optional[float] = None,
    min_increase_axis: Optional[int] = None,
    min_increase: float = 0.0,
    seed_sort_axis: Optional[int] = None,
    k_start: int = 32,
    k_max: int = 4096,
) -> List[np.ndarray]:
    """
    Greedy chaining:
      - start from a seed
      - repeatedly take the closest unassigned neighbor within max_dist
      - accept it only if the gate on one axis is satisfied
      - optionally require monotonic increase on another axis
    """
    n = points.shape[0]
    tree = cKDTree(points)
    unassigned = np.ones(n, dtype=bool)

    if seed_sort_axis is None:
        seed_order = np.arange(n, dtype=int)
    else:
        seed_order = np.argsort(points[:, seed_sort_axis])

    groups: List[np.ndarray] = []

    for seed in seed_order:
        if not unassigned[seed]:
            continue

        chain = [int(seed)]
        unassigned[seed] = False
        current = int(seed)

        while True:
            found_next: Optional[int] = None
            k = k_start

            while True:
                kk = min(k, n)
                dists, idxs = tree.query(points[current], k=kk)
                dists = np.atleast_1d(dists)
                idxs = np.atleast_1d(idxs)

                gate0 = points[current, gate_axis]
                inc0 = points[current, min_increase_axis] if min_increase_axis is not None else None

                for d_euclid, j in zip(dists, idxs):
                    j = int(j)

                    if j == current or not unassigned[j]:
                        continue
                    if d_euclid > max_dist:
                        break

                    if min_increase_axis is not None and inc0 is not None:
                        if (points[j, min_increase_axis] - inc0) < min_increase:
                            continue

                    gate1 = points[j, gate_axis]
                    if gate_period is None:
                        d_gate = abs(gate1 - gate0)
                    else:
                        d_gate = wrap_delta(gate0, gate1, gate_period)

                    if d_gate <= gate_tol:
                        found_next = j
                        break

                if found_next is not None:
                    break
                if k >= k_max or kk == n:
                    break

                k = min(k * 2, k_max)

            if found_next is None:
                break

            chain.append(found_next)
            unassigned[found_next] = False
            current = found_next

        groups.append(np.asarray(chain, dtype=int))

    return groups


# -----------------------------------------------------------------------------
# Ring nominal assignment
# -----------------------------------------------------------------------------
def ring_group_theta_bins(
    points: np.ndarray,
    g: np.ndarray,
    *,
    bin_width_deg: float = 30.0,
    theta_period: float = 360.0,
    min_pts_per_bin: int = 10,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    For one ring group, compute median r in theta bins.
    Returns only bins with at least min_pts_per_bin points.
    """
    theta = wrap_deg(points[g, 0])
    r = points[g, 1]

    nbins = int(round(theta_period / bin_width_deg))
    edges = np.linspace(0.0, theta_period, nbins + 1)

    b = np.digitize(theta, edges) - 1
    b[b == nbins] = nbins - 1

    bin_ids: List[int] = []
    r_med: List[float] = []

    for bi in range(nbins):
        m = (b == bi)
        if int(m.sum()) < min_pts_per_bin:
            continue
        bin_ids.append(bi)
        r_med.append(float(np.median(r[m])))

    return np.asarray(bin_ids, dtype=int), np.asarray(r_med, dtype=float)


def estimate_ring_levels_with_wave_correction(
    points: np.ndarray,
    groups_theta: List[np.ndarray],
    *,
    bin_width_deg: float = 30.0,
    theta_period: float = 360.0,
    min_pts_per_bin: int = 10,
    n_iter: int = 3,
) -> Tuple[np.ndarray, Dict[int, float], List[np.ndarray]]:
    """
    Estimate one representative 'level' in r for each ring fragment while accounting
    for a shared wave pattern as a function of theta bin.

    Model:
        r_bin ~= level_group + wave_bin
    """
    ngroups = len(groups_theta)
    nbins = int(round(theta_period / bin_width_deg))

    grp_bins: List[np.ndarray] = []
    grp_rmed: List[np.ndarray] = []
    levels = np.zeros(ngroups, dtype=float)

    for i, g in enumerate(groups_theta):
        bins_i, rmed_i = ring_group_theta_bins(
            points,
            g,
            bin_width_deg=bin_width_deg,
            theta_period=theta_period,
            min_pts_per_bin=min_pts_per_bin,
        )
        grp_bins.append(bins_i)
        grp_rmed.append(rmed_i)
        levels[i] = float(np.median(points[g, 1])) if g.size else 0.0

    wave = {bi: 0.0 for bi in range(nbins)}

    for _ in range(n_iter):
        resid_by_bin: List[List[float]] = [[] for _ in range(nbins)]

        for i in range(ngroups):
            bins_i = grp_bins[i]
            rmed_i = grp_rmed[i]
            for bi, rmed in zip(bins_i, rmed_i):
                resid_by_bin[int(bi)].append(float(rmed - levels[i]))

        for bi in range(nbins):
            if resid_by_bin[bi]:
                wave[bi] = float(np.median(resid_by_bin[bi]))

        for i in range(ngroups):
            bins_i = grp_bins[i]
            rmed_i = grp_rmed[i]
            if bins_i.size == 0:
                continue
            adjusted = np.array(
                [rmed - wave[int(bi)] for bi, rmed in zip(bins_i, rmed_i)],
                dtype=float,
            )
            levels[i] = float(np.median(adjusted))

    return levels, wave, grp_bins


def detect_nominal(data, params: dict) -> None:
    logger.info("Detecting nominal grid assignment...")
    base_idx = data["idx"]
    pixels = data["pts"]
    theta = data["theta"]
    r = data["r"]
    pts = np.column_stack([theta, r]).astype(float, copy=False)

    # -----------------------------------------------------------------
    # 1) Detect ring and spoke fragments
    # -----------------------------------------------------------------
    groups_theta = chain_groups_closest_neighbor_with_axis_gate(
        pts,
        max_dist=params["ring_max_dist"],
        gate_axis=1,
        gate_tol=params["ring_gate_tol_r"],
        gate_period=None,
        min_increase_axis=None,
        min_increase=0.0,
        seed_sort_axis=None,
        k_start=32,
        k_max=4096,
    )

    groups_r = chain_groups_closest_neighbor_with_axis_gate(
        pts,
        max_dist=params["spoke_max_dist"],
        gate_axis=0,
        gate_tol=params["spoke_gate_tol_theta"],
        gate_period=360.0,
        min_increase_axis=1,
        min_increase=params["spoke_min_dist"],
        seed_sort_axis=1,
        k_start=32,
        k_max=4096,
    )

    groups_theta = [g for g in groups_theta if g.size >= params["min_ring_group"]]
    groups_r = [g for g in groups_r if g.size >= params["min_spoke_group"]]

    logger.info(f"Found {len(groups_theta)} ring fragments and {len(groups_r)} spoke fragments.")

    # -----------------------------------------------------------------
    # 2) Assign nominal circles
    # -----------------------------------------------------------------
    logger.info("Estimating nominal circle levels with wave correction...")
    ring_levels_px, wave, grp_bins = estimate_ring_levels_with_wave_correction(
        pts,
        groups_theta,
        bin_width_deg=DEFAULT_NOMINAL_PARAMS["bin_width_deg"],
        theta_period=360.0,
        min_pts_per_bin=DEFAULT_NOMINAL_PARAMS["min_pts_per_bin"],
        n_iter=DEFAULT_NOMINAL_PARAMS["n_wave_iter"],
    )

    spacing_px = robust_median_spacing(ring_levels_px, min_sep=2.0, max_sep=200.0)
    if not np.isfinite(spacing_px) or spacing_px <= 0:
        raise RuntimeError("Failed to estimate circle spacing in pixels.")

    logger.info(f"Estimated circle spacing: {spacing_px:.3f} px per {DEG_STEP}°")

    # Assign nominal circle values
    k_circle, rho_circle = assign_nominal_circles(
        ring_levels_px,
        spacing_px=spacing_px,
    )

    # Assign nominal spoke values
    theta_g = spoke_group_theta_estimates(pts, groups_r)
    k_spoke, theta_nom, theta0 = assign_nominal_spokes(
        theta_g,
        theta0=None,
    )

    logger.info(f"Chosen spoke offset theta0: {theta0:.3f} deg")

    nominal_assignment = []
    # isolate only the points that bolongs to both a ring and a spoke group, and anf fill in the data dict
    for index_g_r, g_r in enumerate(groups_r):
        for index_g_theta, g_theta in enumerate(groups_theta):
            common = np.intersect1d(g_r, g_theta)
            for idx in common:
                nominal_assignment.append({
                    "idx": int(base_idx[idx]),
                    "pixel_x": float(pixels[idx, 1]),
                    "pixel_y": float(pixels[idx, 0]),
                    "r": float(pts[idx, 1]),
                    "theta": float(pts[idx, 0]),
                    "circle_index": int(index_g_theta),
                    "spoke_index": int(index_g_r),
                    # "k_circle": int(k_circle[index_g_theta]),
                    # "k_spoke": int(k_spoke[index_g_r]),
                    "nominal_r": float(rho_circle[index_g_theta]),
                    "nominal_theta": float(theta_nom[index_g_r]),
                })

    logger.info(f"Assigned nominal values to {len(nominal_assignment)} points.")
    return nominal_assignment