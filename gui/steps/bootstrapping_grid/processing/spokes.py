"""Spoke-tier geometry, spline fitting, and spoke bootstrapping helpers."""

from __future__ import annotations

import numpy as np
from scipy.interpolate import splprep, splev
from scipy.spatial import cKDTree

from .....errors import DetectionError
from .containers import DenseGrid, GridData, SpokeBootstrapResult
from .geometry import point_radius_from_center
from ..params import DEFAULT_PARAMETERS


def spoke_min_nominal_r(theta_deg: float) -> float:
    """
    Return the innermost nominal circle reached by a spoke.

    The grid has tiered spoke density:
    - 30 deg spokes reach the center
    - 10 deg spokes start at 2.5 deg
    - 5 deg spokes start at 10 deg
    - 2.5 deg spokes start at 20 deg
    """
    t = theta_deg % 180.0
    if np.isclose((t / 30.0) % 1.0, 0.0, atol=1e-8):
        return 0.0
    if np.isclose((t / 10.0) % 1.0, 0.0, atol=1e-8):
        return 2.5
    if np.isclose((t / 5.0) % 1.0, 0.0, atol=1e-8):
        return 10.0
    return 20.0


def unit_direction_from_seed(x: np.ndarray, y: np.ndarray, center_xy: np.ndarray) -> np.ndarray:
    """Infer the main-axis unit vector for one spoke from seed points."""
    pts = np.column_stack([x, y])
    rel = pts - center_xy[None, :]
    norms = np.hypot(rel[:, 0], rel[:, 1])
    valid = norms > 0

    if not np.any(valid):
        raise DetectionError("Cannot infer spoke direction from empty/non-finite seed set.")

    mean_vec = np.mean(rel[valid] / norms[valid, None], axis=0)
    norm = np.hypot(mean_vec[0], mean_vec[1])

    if norm == 0:
        raise DetectionError("Degenerate spoke direction.")

    return mean_vec / norm


def signed_axis_coordinate(
    x: np.ndarray,
    y: np.ndarray,
    center_xy: np.ndarray,
    axis_u: np.ndarray,
) -> np.ndarray:
    """Project points onto the signed spoke axis."""
    pts = np.column_stack([x, y])
    return (pts - center_xy[None, :]) @ axis_u


def order_seed_points(
    x_main: np.ndarray,
    y_main: np.ndarray,
    x_opp: np.ndarray,
    y_opp: np.ndarray,
    center_xy: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Order opposite-spoke seeds with the center between them."""
    axis_u = unit_direction_from_seed(x_main, y_main, center_xy)
    x_ordered = np.concatenate([x_opp, np.array([center_xy[0]]), x_main])
    y_ordered = np.concatenate([y_opp, np.array([center_xy[1]]), y_main])
    s_ordered = signed_axis_coordinate(x_ordered, y_ordered, center_xy, axis_u)
    order = np.argsort(s_ordered)
    return x_ordered[order], y_ordered[order], s_ordered[order], axis_u


def deduplicate_ordered_points(
    x: np.ndarray,
    y: np.ndarray,
    s: np.ndarray,
    min_sep_px: float = 0.5,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Drop adjacent duplicates in ordered spoke samples."""
    if x.size == 0:
        return x, y, s

    keep = np.ones(x.size, dtype=bool)
    for i in range(1, x.size):
        if np.hypot(x[i] - x[i - 1], y[i] - y[i - 1]) < min_sep_px:
            keep[i] = False

    return x[keep], y[keep], s[keep]


def fit_parametric_spoke_spline(
    x: np.ndarray,
    y: np.ndarray,
    smoothing: float = DEFAULT_PARAMETERS["spoke_spline_smoothing"],
    spline_order: int = 3,
):
    """Fit a parametric spline through spoke samples."""
    if x.size < 4:
        raise DetectionError("Need at least 4 points to fit a spline.")

    ds = np.hypot(np.diff(x), np.diff(y))
    t = np.concatenate([[0.0], np.cumsum(ds)])

    if t[-1] == 0:
        raise DetectionError("Degenerate seed geometry.")

    u = t / t[-1]
    k = min(int(spline_order), x.size - 1)
    tck, _ = splprep([x, y], u=u, s=float(smoothing), k=k)
    return tck


def sample_spline(tck, n_samples: int = DEFAULT_PARAMETERS["spoke_sample_count"]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Sample a fitted parametric spline."""
    u = np.linspace(0.0, 1.0, int(n_samples))
    x_s, y_s = splev(u, tck)
    return np.asarray(x_s), np.asarray(y_s), u


def project_points_to_spline(
    points_xy: np.ndarray,
    x_curve: np.ndarray,
    y_curve: np.ndarray,
    u_curve: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Project points to the nearest sampled point on a spline."""
    if points_xy.size == 0:
        return np.array([]), np.array([]), np.array([], dtype=int)

    tree = cKDTree(np.column_stack([x_curve, y_curve]))
    dist, idx = tree.query(points_xy, k=1)
    return dist, u_curve[idx], idx


def tangent_from_curve_samples(
    x_curve: np.ndarray,
    y_curve: np.ndarray,
    idx: np.ndarray | int,
    half_window: int = 4,
) -> np.ndarray:
    """Estimate local tangent vectors from sampled curve indices."""
    idx_arr = np.atleast_1d(np.asarray(idx, dtype=int))
    tangents = np.zeros((idx_arr.size, 2), dtype=float)
    n = x_curve.size

    for i, ii in enumerate(idx_arr):
        i0 = max(0, ii - half_window)
        i1 = min(n - 1, ii + half_window)
        dx = x_curve[i1] - x_curve[i0]
        dy = y_curve[i1] - y_curve[i0]
        norm = np.hypot(dx, dy)
        tangents[i] = np.array([1.0, 0.0]) if norm == 0 else np.array([dx / norm, dy / norm])

    if np.ndim(idx) == 0:
        return tangents[0]
    return tangents


def angle_deg_between(v1: np.ndarray, v2: np.ndarray) -> np.ndarray:
    """Return unsigned angle between vectors in degrees."""
    v1 = np.asarray(v1, dtype=float)
    v2 = np.asarray(v2, dtype=float)
    dot = np.sum(v1 * v2, axis=-1)
    n1 = np.linalg.norm(v1, axis=-1)
    n2 = np.linalg.norm(v2, axis=-1)
    denom = np.maximum(n1 * n2, 1e-12)
    cosang = np.clip(dot / denom, -1.0, 1.0)
    return np.degrees(np.arccos(cosang))


def get_inner_endpoint(
    all_x: np.ndarray,
    all_y: np.ndarray,
    all_s: np.ndarray,
    side: str,
) -> tuple[np.ndarray, float]:
    """Return the endpoint closest to center on one side of the spoke."""
    if side == "main":
        mask = all_s > 0
        idx = np.argmin(all_s[mask])
        pts = np.column_stack([all_x[mask], all_y[mask]])
        return pts[idx], float(np.min(all_s[mask]))

    if side == "opp":
        mask = all_s < 0
        idx = np.argmax(all_s[mask])
        pts = np.column_stack([all_x[mask], all_y[mask]])
        return pts[idx], float(np.max(all_s[mask]))

    raise DetectionError("side must be 'main' or 'opp'.")


def get_outer_endpoint(
    all_x: np.ndarray,
    all_y: np.ndarray,
    all_s: np.ndarray,
    side: str,
) -> tuple[np.ndarray, float]:
    """Return the outermost endpoint on one side of the spoke."""
    if side == "main":
        mask = all_s > 0
        idx = np.argmax(all_s[mask])
        pts = np.column_stack([all_x[mask], all_y[mask]])
        return pts[idx], float(np.max(all_s[mask]))

    if side == "opp":
        mask = all_s < 0
        idx = np.argmin(all_s[mask])
        pts = np.column_stack([all_x[mask], all_y[mask]])
        return pts[idx], float(np.min(all_s[mask]))

    raise DetectionError("side must be 'main' or 'opp'.")


def estimate_inner_cutoff_pix(
    x_seed: np.ndarray,
    y_seed: np.ndarray,
    r_nom_seed_deg: np.ndarray,
    center_xy: np.ndarray,
    spoke_deg: float,
) -> tuple[float, float]:
    """
    Estimate the pixel radius below which this spoke should not be searched.
    """
    rmin_nom = spoke_min_nominal_r(spoke_deg)
    cutoff_nom = max(rmin_nom - DEFAULT_PARAMETERS["inner_cutoff_margin_deg"], 0.0)

    if rmin_nom <= 0:
        return cutoff_nom, 0.0

    pix_r = point_radius_from_center(x_seed, y_seed, center_xy)
    valid = np.isfinite(pix_r) & np.isfinite(r_nom_seed_deg)

    if np.sum(valid) < 3:
        return cutoff_nom, 0.0

    rr = r_nom_seed_deg[valid]
    pp = pix_r[valid]
    deg = min(DEFAULT_PARAMETERS["inner_cutoff_poly_degree"], max(1, rr.size - 1))
    coeff = np.polyfit(rr, pp, deg)
    cutoff_pix = float(np.polyval(coeff, cutoff_nom))

    return cutoff_nom, max(cutoff_pix, 0.0)


def candidate_score(dist_px: np.ndarray, angle_deg: np.ndarray, dist_tol_px: float, aperture_deg: float) -> np.ndarray:
    """Score candidates by normalized distance and tangent-angle mismatch."""
    return dist_px / max(dist_tol_px, 1e-6) + angle_deg / max(aperture_deg, 1e-6)


def _reject_ambiguous_best(cand: np.ndarray, score: np.ndarray, rem_xy: np.ndarray) -> bool:
    """Return True if the best candidate is ambiguous with the second best."""
    if cand.size < 2:
        return False

    c0, c1 = cand[0], cand[1]
    score1, score2 = score[0], score[1]
    score_diff = abs(score2 - score1)
    score_ratio = score2 / max(score1, 1e-12)
    point_sep = np.hypot(rem_xy[c1, 0] - rem_xy[c0, 0], rem_xy[c1, 1] - rem_xy[c0, 1])

    return (
        ((score_diff < DEFAULT_PARAMETERS["ambiguity_score_tol"]) or (score_ratio < DEFAULT_PARAMETERS["ambiguity_ratio_tol"]))
        and (point_sep < DEFAULT_PARAMETERS["ambiguity_point_sep_px"])
    )


def choose_inward_candidate(
    side: str,
    rem_xy: np.ndarray,
    rem_s: np.ndarray,
    rem_radius: np.ndarray,
    curve_x: np.ndarray,
    curve_y: np.ndarray,
    curve_u: np.ndarray,
    endpoint_xy: np.ndarray,
    endpoint_s: float,
    cutoff_pix: float,
) -> int | None:
    """
    Choose one inward candidate without trial-spline refitting.

    This is intentionally much faster than the older scoring scheme. It uses
    distance to spline and local tangent aperture only.
    """
    if rem_xy.size == 0:
        return None

    dist_px, _, idx_proj = project_points_to_spline(rem_xy, curve_x, curve_y, curve_u)
    tangent = tangent_from_curve_samples(curve_x, curve_y, idx_proj)
    vec_from_endpoint = rem_xy - endpoint_xy[None, :]

    angle_deg = np.minimum(
        angle_deg_between(vec_from_endpoint, tangent),
        angle_deg_between(vec_from_endpoint, -tangent),
    )

    if side == "main":
        side_mask = rem_s > 0
        inward_mask = rem_s < endpoint_s
    else:
        side_mask = rem_s < 0
        inward_mask = rem_s > endpoint_s

    cand = np.where(
        side_mask
        & inward_mask
        & (rem_radius >= cutoff_pix)
        & (dist_px <= DEFAULT_PARAMETERS["spoke_extrap_tol_px"])
        & (angle_deg <= DEFAULT_PARAMETERS["inward_aperture_deg"])
    )[0]

    if cand.size == 0:
        return None

    score = candidate_score(dist_px[cand], angle_deg[cand], DEFAULT_PARAMETERS["spoke_extrap_tol_px"], DEFAULT_PARAMETERS["inward_aperture_deg"])
    order = np.argsort(score)
    cand = cand[order]
    score = score[order]

    if _reject_ambiguous_best(cand, score, rem_xy):
        return None

    return int(cand[0])


def choose_outward_candidate(
    side: str,
    rem_xy: np.ndarray,
    rem_s: np.ndarray,
    curve_x: np.ndarray,
    curve_y: np.ndarray,
    curve_u: np.ndarray,
    endpoint_xy: np.ndarray,
    endpoint_s: float,
    axis_u: np.ndarray,
) -> int | None:
    """
    Choose one outward candidate using tangent-line extrapolation.
    """
    if rem_xy.size == 0:
        return None

    if side == "main":
        side_mask = rem_s > 0
        outward_mask = rem_s > endpoint_s
    else:
        side_mask = rem_s < 0
        outward_mask = rem_s < endpoint_s

    _, _, idx_ep = project_points_to_spline(endpoint_xy[None, :], curve_x, curve_y, curve_u)
    tangent_ep = tangent_from_curve_samples(curve_x, curve_y, idx_ep[0])

    if side == "main" and np.dot(tangent_ep, axis_u) < 0:
        tangent_ep = -tangent_ep
    if side == "opp" and np.dot(tangent_ep, axis_u) > 0:
        tangent_ep = -tangent_ep

    v = rem_xy - endpoint_xy[None, :]
    d_parallel = v @ tangent_ep
    v_perp = v - d_parallel[:, None] * tangent_ep[None, :]
    d_perp = np.hypot(v_perp[:, 0], v_perp[:, 1])

    angle_deg = np.minimum(
        angle_deg_between(v, tangent_ep),
        angle_deg_between(v, -tangent_ep),
    )

    cand = np.where(
        side_mask
        & outward_mask
        & (d_parallel > DEFAULT_PARAMETERS["outward_forward_min_px"])
        & (d_perp <= DEFAULT_PARAMETERS["outward_perp_tol_px"])
        & (angle_deg <= DEFAULT_PARAMETERS["outward_aperture_deg"])
    )[0]

    if cand.size == 0:
        return None

    score = candidate_score(d_perp[cand], angle_deg[cand], DEFAULT_PARAMETERS["outward_perp_tol_px"], DEFAULT_PARAMETERS["outward_aperture_deg"])
    order = np.argsort(score)
    cand = cand[order]
    score = score[order]

    if _reject_ambiguous_best(cand, score, rem_xy):
        return None

    return int(cand[0])


def bootstrap_spoke_pair(
    spoke_deg: float,
    nominal_points: GridData,
    dense_points: DenseGrid,
    center_xy: np.ndarray,
    available_mask: np.ndarray,
    *,
    spoke_tol_px: float = DEFAULT_PARAMETERS["spoke_final_tol_px"],
) -> SpokeBootstrapResult:
    """
    Bootstrap one opposite-spoke pair from dense detections.
    """
    opposite_deg = (spoke_deg + 180.0) % 360.0

    mask_main = nominal_points.theta_nom_deg == (spoke_deg % 360.0)
    mask_opp = nominal_points.theta_nom_deg == opposite_deg

    if np.sum(mask_main) < 2 or np.sum(mask_opp) < 2:
        raise DetectionError(f"Not enough nominal seeds for spoke {spoke_deg:.1f}.")

    x_seed, y_seed, s_seed, axis_u = order_seed_points(
        nominal_points.x[mask_main],
        nominal_points.y[mask_main],
        nominal_points.x[mask_opp],
        nominal_points.y[mask_opp],
        center_xy,
    )
    x_seed, y_seed, s_seed = deduplicate_ordered_points(x_seed, y_seed, s_seed)

    r_nom_seed_deg = np.concatenate([nominal_points.r_nom_deg[mask_opp], nominal_points.r_nom_deg[mask_main]])
    x_seed_cut = np.concatenate([nominal_points.x[mask_opp], nominal_points.x[mask_main]])
    y_seed_cut = np.concatenate([nominal_points.y[mask_opp], nominal_points.y[mask_main]])
    cutoff_nominal_r_deg, cutoff_pix = estimate_inner_cutoff_pix(
        x_seed_cut,
        y_seed_cut,
        r_nom_seed_deg,
        center_xy,
        spoke_deg,
    )

    tck = fit_parametric_spoke_spline(x_seed, y_seed)
    curve_x, curve_y, curve_u = sample_spline(tck)

    pts_xy = np.column_stack([dense_points.x[available_mask], dense_points.y[available_mask]])
    pts_idx = dense_points.idx[available_mask]
    pts_radius = point_radius_from_center(pts_xy[:, 0], pts_xy[:, 1], center_xy)

    dist0, _, _ = project_points_to_spline(pts_xy, curve_x, curve_y, curve_u)
    initial_keep = (dist0 <= DEFAULT_PARAMETERS["spoke_initial_pull_tol_px"]) & (pts_radius >= cutoff_pix)

    assigned_idx = list(pts_idx[initial_keep])
    assigned_x = list(pts_xy[initial_keep, 0])
    assigned_y = list(pts_xy[initial_keep, 1])

    inward_growth_steps = 0
    outward_growth_steps = 0

    for _ in range(DEFAULT_PARAMETERS["max_growth_steps"]):
        all_x = np.concatenate([x_seed, np.asarray(assigned_x, dtype=float)])
        all_y = np.concatenate([y_seed, np.asarray(assigned_y, dtype=float)])
        all_s = signed_axis_coordinate(all_x, all_y, center_xy, axis_u)
        order = np.argsort(all_s)
        all_x, all_y, all_s = all_x[order], all_y[order], all_s[order]
        all_x, all_y, all_s = deduplicate_ordered_points(all_x, all_y, all_s)

        if all_x.size < 4:
            break

        tck = fit_parametric_spoke_spline(all_x, all_y)
        curve_x, curve_y, curve_u = sample_spline(tck)

        remaining_mask = available_mask.copy()
        if assigned_idx:
            remaining_mask[np.asarray(assigned_idx, dtype=int)] = False

        rem_xy = np.column_stack([dense_points.x[remaining_mask], dense_points.y[remaining_mask]])
        rem_idx = dense_points.idx[remaining_mask]

        if rem_xy.size == 0:
            break

        rem_s = signed_axis_coordinate(rem_xy[:, 0], rem_xy[:, 1], center_xy, axis_u)
        rem_radius = point_radius_from_center(rem_xy[:, 0], rem_xy[:, 1], center_xy)

        chosen: list[int] = []

        if np.any(all_s > 0):
            endpoint_xy, endpoint_s = get_inner_endpoint(all_x, all_y, all_s, "main")
            cand = choose_inward_candidate(
                "main",
                rem_xy,
                rem_s,
                rem_radius,
                curve_x,
                curve_y,
                curve_u,
                endpoint_xy,
                endpoint_s,
                cutoff_pix,
            )
            if cand is not None:
                chosen.append(cand)
                inward_growth_steps += 1

            outer_xy, outer_s = get_outer_endpoint(all_x, all_y, all_s, "main")
            cand = choose_outward_candidate(
                "main",
                rem_xy,
                rem_s,
                curve_x,
                curve_y,
                curve_u,
                outer_xy,
                outer_s,
                axis_u,
            )
            if cand is not None:
                chosen.append(cand)
                outward_growth_steps += 1

        if np.any(all_s < 0):
            endpoint_xy, endpoint_s = get_inner_endpoint(all_x, all_y, all_s, "opp")
            cand = choose_inward_candidate(
                "opp",
                rem_xy,
                rem_s,
                rem_radius,
                curve_x,
                curve_y,
                curve_u,
                endpoint_xy,
                endpoint_s,
                cutoff_pix,
            )
            if cand is not None:
                chosen.append(cand)
                inward_growth_steps += 1

            outer_xy, outer_s = get_outer_endpoint(all_x, all_y, all_s, "opp")
            cand = choose_outward_candidate(
                "opp",
                rem_xy,
                rem_s,
                curve_x,
                curve_y,
                curve_u,
                outer_xy,
                outer_s,
                axis_u,
            )
            if cand is not None:
                chosen.append(cand)
                outward_growth_steps += 1

        if not chosen:
            break

        chosen = np.unique(np.asarray(chosen, dtype=int))
        assigned_idx.extend(rem_idx[chosen].tolist())
        assigned_x.extend(rem_xy[chosen, 0].tolist())
        assigned_y.extend(rem_xy[chosen, 1].tolist())

    # Final spline and final consistency filter.
    all_x = np.concatenate([x_seed, np.asarray(assigned_x, dtype=float)])
    all_y = np.concatenate([y_seed, np.asarray(assigned_y, dtype=float)])
    all_s = signed_axis_coordinate(all_x, all_y, center_xy, axis_u)
    order = np.argsort(all_s)
    all_x, all_y, all_s = all_x[order], all_y[order], all_s[order]
    all_x, all_y, all_s = deduplicate_ordered_points(all_x, all_y, all_s)

    tck = fit_parametric_spoke_spline(all_x, all_y)
    curve_x, curve_y, curve_u = sample_spline(tck)

    assigned_idx_arr = np.asarray(assigned_idx, dtype=int)
    assigned_x_arr = np.asarray(assigned_x, dtype=float)
    assigned_y_arr = np.asarray(assigned_y, dtype=float)
    assigned_s = signed_axis_coordinate(assigned_x_arr, assigned_y_arr, center_xy, axis_u)
    assigned_side_arr = np.array(
        ["main" if s > 0 else "opp" if s < 0 else "center" for s in assigned_s],
        dtype=object,
    )

    if assigned_idx_arr.size:
        final_dist, _, _ = project_points_to_spline(
            np.column_stack([assigned_x_arr, assigned_y_arr]),
            curve_x,
            curve_y,
            curve_u,
        )
        final_radius = point_radius_from_center(assigned_x_arr, assigned_y_arr, center_xy)
        keep = (final_dist <= spoke_tol_px) & (final_radius >= cutoff_pix)
    else:
        keep = np.zeros(0, dtype=bool)

    return SpokeBootstrapResult(
        spoke_deg=float(spoke_deg),
        opposite_deg=float(opposite_deg),
        seed_count=int(x_seed.size),
        assigned_idx=assigned_idx_arr[keep],
        assigned_x=assigned_x_arr[keep],
        assigned_y=assigned_y_arr[keep],
        assigned_side=assigned_side_arr[keep],
        curve_x=curve_x,
        curve_y=curve_y,
        curve_u=curve_u,
        inward_growth_steps=int(inward_growth_steps),
        outward_growth_steps=int(outward_growth_steps),
        cutoff_nominal_r_deg=float(cutoff_nominal_r_deg),
        cutoff_pix=float(cutoff_pix),
    )
