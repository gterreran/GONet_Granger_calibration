
from __future__ import annotations

from typing import Dict, List, Optional, Tuple
import logging
import numpy as np
from scipy.spatial import cKDTree
from .errors import DetectionError

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


def detect_nominal(data, params: dict):
    """
    Detect and assign nominal polar-grid coordinates to measured grid points.

    This function takes the detected calibration-grid points from a GONet image
    and assigns each usable point a nominal polar coordinate:

    - ``nominal_r``: the expected angular radius of the grid circle, in degrees
    - ``nominal_theta``: the expected angular position of the grid spoke, in degrees

    The input detections are assumed to already have approximate measured polar
    coordinates ``theta`` and ``r`` relative to an estimated image/grid center.
    The function then performs the following steps:

    1. Detect ring fragments
       Points are chained into approximately constant-radius groups using a
       nearest-neighbor walk with a gate on measured radius. These groups
       correspond to circular grid rings, although individual rings may be
       fragmented or distorted.

    2. Detect spoke fragments
       Points are chained into approximately constant-theta groups using a
       nearest-neighbor walk with a gate on measured theta and a required
       outward radial progression. These groups correspond to radial spokes.

    3. Estimate ring levels
       Each ring fragment is assigned a representative measured pixel radius.
       A shared wave-like radial pattern as a function of theta is estimated
       and removed iteratively, allowing ring levels to be compared even when
       fragments cover different theta ranges.

    4. Assign nominal circle radii
       The median measured spacing between ring levels is used to infer the
       nominal grid spacing. Each ring group is then assigned to the nearest
       nominal circle index, assuming the known grid spacing ``DEG_STEP``.

    5. Assign nominal spoke angles
       Each spoke group is assigned a representative theta value. A global
       spoke offset is estimated so that spokes align with the expected
       ``DEG_STEP`` angular grid.

    6. Check for a rigid radial circle-label offset
       Because the absolute nominal circle index can be ambiguous, the function
       tests candidate rigid shifts of the assigned circle radii. For each
       shift, it fits a no-intercept odd-cubic radial relation between nominal
       radius and measured pixel radius:

       ``r_pix = a1 * r_nom + a3 * r_nom**3``

       The shift with the lowest robust scatter, measured using MAD, is selected.
       The shift is applied only if it improves the zero-shift MAD by at least
       20 percent.

    7. Build final nominal assignments
       Instead of repeatedly intersecting every ring group with every spoke
       group, the function builds point-to-ring and point-to-spoke lookup arrays.
       Points that belong to both a valid ring and a valid spoke are emitted as
       nominal calibration records.

    Parameters
    ----------
    data : mapping
        Input data dictionary containing at least:

        ``"idx"``
            Original point indices.

        ``"pts"``
            Pixel coordinates. The current convention is assumed to be
            ``(row, col)``, so output ``pixel_x`` is taken from column 1 and
            ``pixel_y`` from column 0.

        ``"theta"``
            Measured polar theta values in degrees.

        ``"r"``
            Measured polar radius values in pixels.

        ``"center"``
            Object or scalar array containing the estimated center dictionary
            with ``"x"`` and ``"y"`` entries.

    params : dict
        Nominal-grid detection parameters. Expected keys include:

        ``"ring_max_dist"``
            Maximum nearest-neighbor distance for ring chaining.

        ``"ring_gate_tol_r"``
            Radius gate tolerance for ring chaining.

        ``"min_ring_group"``
            Minimum number of points required to keep a ring group.

        ``"spoke_max_dist"``
            Maximum nearest-neighbor distance for spoke chaining.

        ``"spoke_min_dist"``
            Minimum radial increase required when extending spoke chains.

        ``"spoke_gate_tol_theta"``
            Theta gate tolerance for spoke chaining.

        ``"min_spoke_group"``
            Minimum number of points required to keep a spoke group.

    Returns
    -------
    list of dict
        One dictionary per assigned grid point. Each dictionary contains:

        ``idx``
            Original point index.

        ``pixel_x, pixel_y``
            Pixel coordinates.

        ``r, theta``
            Measured polar coordinates.

        ``circle_index, spoke_index``
            Internal detected ring/spoke group indices.

        ``nominal_r, nominal_theta``
            Assigned nominal polar-grid coordinates in degrees.

    Raises
    ------
    RuntimeError
        If the measured circle spacing cannot be estimated.
    """

    logger.info("Detecting nominal grid assignment...")

    base_idx = data["idx"]
    pixels = data["pts"]
    theta = data["theta"]
    r = data["r"]
    center = data["center"].item()

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

    logger.info(
        "Found %d ring fragments and %d spoke fragments.",
        len(groups_theta),
        len(groups_r),
    )

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

    spacing_px = robust_median_spacing(
        ring_levels_px,
        min_sep=2.0,
        max_sep=200.0,
    )

    if not np.isfinite(spacing_px) or spacing_px <= 0:
        raise DetectionError("Failed to estimate circle spacing in pixels.")

    logger.info("Estimated circle spacing: %.3f px per %.1f°", spacing_px, DEG_STEP)

    k_circle, rho_circle = assign_nominal_circles(
        ring_levels_px,
        spacing_px=spacing_px,
    )

    # -----------------------------------------------------------------
    # 3) Assign nominal spokes
    # -----------------------------------------------------------------
    theta_g = spoke_group_theta_estimates(pts, groups_r)

    k_spoke, theta_nom, theta0 = assign_nominal_spokes(
        theta_g,
        theta0=None,
    )

    logger.info("Chosen spoke offset theta0: %.3f deg", theta0)

    # -----------------------------------------------------------------
    # 4) Check for rigid radial circle shift
    # -----------------------------------------------------------------
    def fit_no_intercept_odd_cubic(x, y):
        """Fit y = a1*x + a3*x**3 with no intercept."""
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)

        A = np.column_stack([x, x**3])
        coeff, *_ = np.linalg.lstsq(A, y, rcond=None)
        fitted = A @ coeff
        return fitted, coeff

    ring_r_nom = rho_circle.astype(float)
    ring_dist_med = ring_levels_px.astype(float)

    shift_scores = {}

    for shift in np.arange(-5.0, 7.5, DEG_STEP):
        shifted_r = ring_r_nom + shift
        valid = shifted_r >= 0.0

        if np.sum(valid) < 4:
            continue

        fitted, _ = fit_no_intercept_odd_cubic(
            shifted_r[valid],
            ring_dist_med[valid],
        )

        resid = ring_dist_med[valid] - fitted
        mad = float(1.4826 * np.median(np.abs(resid - np.median(resid))))

        shift_scores[float(shift)] = mad

    if shift_scores:
        best_shift = min(shift_scores, key=shift_scores.get)
        zero_mad = shift_scores.get(0.0)
        best_mad = shift_scores[best_shift]

        if zero_mad is not None and zero_mad > 0:
            improvement_frac = (zero_mad - best_mad) / zero_mad
        else:
            improvement_frac = 0.0

        if best_shift != 0.0 and improvement_frac >= 0.20:
            logger.warning(
                "Detected likely rigid circle offset: %+4.1f deg. Applying shift.",
                best_shift,
            )
            rho_circle = rho_circle + best_shift
        else:
            logger.info("No robust rigid circle offset applied.")
    else:
        logger.info("Skipping rigid circle offset check: no valid shift scores.")

    # -----------------------------------------------------------------
    # 5) Build point -> ring/spoke lookup arrays
    # -----------------------------------------------------------------
    n_pts = pts.shape[0]

    ring_id = np.full(n_pts, -1, dtype=int)
    spoke_id = np.full(n_pts, -1, dtype=int)

    for i, g in enumerate(groups_theta):
        ring_id[g] = i

    for i, g in enumerate(groups_r):
        spoke_id[g] = i

    valid = (ring_id >= 0) & (spoke_id >= 0)
    valid_idx = np.nonzero(valid)[0]

    # -----------------------------------------------------------------
    # 6) Build output records
    # -----------------------------------------------------------------
    nominal_assignment = []

    for idx in valid_idx:
        i_ring = ring_id[idx]
        i_spoke = spoke_id[idx]

        nominal_assignment.append({
            "idx": int(base_idx[idx]),
            "pixel_x": float(pixels[idx, 1]),
            "pixel_y": float(pixels[idx, 0]),
            "r": float(pts[idx, 1]),
            "theta": float(pts[idx, 0]),
            "circle_index": int(i_ring),
            "spoke_index": int(i_spoke),
            "nominal_r": float(rho_circle[i_ring]),
            "nominal_theta": float(theta_nom[i_spoke]),
        })

    logger.info("Assigned nominal values to %d points.", len(nominal_assignment))

    return nominal_assignment