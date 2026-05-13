#!/usr/bin/env python3
# grid_calibration/gui/steps/bootstrapping_grid/processing.py
"""
Bootstrap spoke and circle assignments from dense polar-grid detections.

This script starts from:

1. A dense set of detected grid points with no nominal labels.
2. A smaller set of confidently labeled intersections.
3. An approximate grid/FoV center.

It then bootstraps additional nominal labels in two stages:

1. Spokes
   Opposite spoke pairs are fit with center-anchored parametric splines. Dense
   points close to each spline are assigned a nominal spoke angle. Spokes are
   processed in tiers matching the physical grid design.

2. Circles
   Once spoke assignments are available, each spoke is used as a one-dimensional
   radius ruler. The script estimates nominal circle labels along each spoke,
   snaps likely intersections to the 2.5-degree circle grid, rejects circle
   outliers, and finally assigns circle-only points using Fourier circle models.

The output is a ``.npz`` file with a ``data`` entry containing a list of
dictionaries suitable for the distortion-model fitting script.

The script is intentionally assignment-focused. It does not fit the final lens
distortion model.
"""

from __future__ import annotations

import copy
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import logging
from scipy.interpolate import splprep, splev
from scipy.spatial import cKDTree
from .params import DEFAULT_PARAMETERS

logger = logging.getLogger(__name__)
from ....errors import DetectionError

# -----------------------------------------------------------------------------
# Data containers
# -----------------------------------------------------------------------------

@dataclass
class DenseGrid:
    """Dense set of detected grid points without nominal labels."""

    idx: np.ndarray
    x: np.ndarray
    y: np.ndarray

    @classmethod
    def load(cls, data: np.ndarray) -> "DenseGrid":
        """
        Load a dense grid from an ``(N, 2)`` array.

        Parameters
        ----------
        data
            Dense grid array. The expected convention is ``[row, col]`` or
            ``[y, x]`` per point.

        Returns
        -------
        DenseGrid
            Dense grid with explicit ``x`` and ``y`` arrays.
        """
        grid = np.asarray(data, dtype=float)
        if grid.ndim != 2 or grid.shape[1] != 2:
            raise DetectionError("Dense grid must have shape (N, 2).")

        return cls(
            idx=np.arange(grid.shape[0], dtype=int),
            x=grid[:, 1].astype(float),
            y=grid[:, 0].astype(float),
        )

    @property
    def xy(self) -> np.ndarray:
        """Return points as an ``(N, 2)`` array in ``x, y`` order."""
        return np.column_stack([self.x, self.y])


@dataclass
class GridData:
    """Mutable set of nominal grid assignments."""

    idx: np.ndarray
    x: np.ndarray
    y: np.ndarray
    r_nom_deg: np.ndarray
    theta_nom_deg: np.ndarray

    def __post_init__(self) -> None:
        self.rebuild_index()

    @classmethod
    def load(cls, data: np.ndarray) -> "GridData":
        """
        Load confidently labeled intersections from an ``.npz`` ``data`` entry.
        """
        rows = list(data)
        rows.sort(key=lambda r: int(r.get("idx", -1)))

        return cls(
            idx=np.array([row.get("idx", i) for i, row in enumerate(rows)], dtype=int),
            x=np.array([row["pixel_x"] for row in rows], dtype=float),
            y=np.array([row["pixel_y"] for row in rows], dtype=float),
            r_nom_deg=np.array([row["nominal_r"] for row in rows], dtype=float),
            theta_nom_deg=np.array([row["nominal_theta"] % 360.0 for row in rows], dtype=float),
        )

    def rebuild_index(self) -> None:
        """Rebuild the ``idx -> array position`` map."""
        self._idx_map: dict[int, int] = {int(v): i for i, v in enumerate(self.idx)}

    def has_idx(self, idx: int) -> bool:
        """Return whether ``idx`` is present."""
        return int(idx) in self._idx_map

    def position(self, idx: int) -> int:
        """Return array position for a dense-point index."""
        return self._idx_map[int(idx)]

    def get_theta(self, idx: int) -> float:
        """Return nominal theta for one point."""
        return float(self.theta_nom_deg[self.position(idx)])

    def get_radius(self, idx: int) -> float:
        """Return nominal radius for one point."""
        return float(self.r_nom_deg[self.position(idx)])

    def set_theta(self, idx: int, theta_deg: float) -> None:
        """Set nominal theta for one point."""
        self.theta_nom_deg[self.position(idx)] = theta_deg

    def set_radius(self, idx: int, r_deg: float) -> None:
        """Set nominal radius for one point."""
        self.r_nom_deg[self.position(idx)] = r_deg

    def clear_assignment(self, idx: int) -> None:
        """Clear both nominal radius and theta for one point."""
        pos = self.position(idx)
        self.r_nom_deg[pos] = np.nan
        self.theta_nom_deg[pos] = np.nan

    def append(
        self,
        *,
        idx: int,
        x: float,
        y: float,
        r_nom_deg: float = np.nan,
        theta_nom_deg: float = np.nan,
    ) -> None:
        """Append a new assigned point."""
        idx = int(idx)
        if idx in self._idx_map:
            raise DetectionError(f"Element with idx={idx} already exists.")

        self.idx = np.append(self.idx, idx)
        self.x = np.append(self.x, float(x))
        self.y = np.append(self.y, float(y))
        self.r_nom_deg = np.append(self.r_nom_deg, float(r_nom_deg))
        self.theta_nom_deg = np.append(self.theta_nom_deg, float(theta_nom_deg))
        self._idx_map[idx] = self.idx.size - 1

    def add_or_update(
        self,
        *,
        idx: int,
        x: float,
        y: float,
        r_nom_deg: float | None = None,
        theta_nom_deg: float | None = None,
    ) -> None:
        """Add a point or update existing nominal fields."""
        if self.has_idx(idx):
            pos = self.position(idx)
            if r_nom_deg is not None:
                self.r_nom_deg[pos] = r_nom_deg
            if theta_nom_deg is not None:
                self.theta_nom_deg[pos] = theta_nom_deg
        else:
            self.append(
                idx=idx,
                x=x,
                y=y,
                r_nom_deg=np.nan if r_nom_deg is None else r_nom_deg,
                theta_nom_deg=np.nan if theta_nom_deg is None else theta_nom_deg,
            )


@dataclass
class SpokeBootstrapResult:
    """Result from bootstrapping one opposite-spoke pair."""

    spoke_deg: float
    opposite_deg: float
    seed_count: int
    assigned_idx: np.ndarray
    assigned_x: np.ndarray
    assigned_y: np.ndarray
    assigned_side: np.ndarray
    curve_x: np.ndarray
    curve_y: np.ndarray
    curve_u: np.ndarray
    inward_growth_steps: int
    outward_growth_steps: int
    cutoff_nominal_r_deg: float
    cutoff_pix: float


# -----------------------------------------------------------------------------
# Basic geometry helpers
# -----------------------------------------------------------------------------

def load_center(center_obj: Path) -> np.ndarray:
    return np.array([float(center_obj["x"]), float(center_obj["y"])], dtype=float)


def point_radius_from_center(x: np.ndarray, y: np.ndarray, center_xy: np.ndarray) -> np.ndarray:
    """Return pixel radius from ``center_xy``."""
    return np.hypot(np.asarray(x) - center_xy[0], np.asarray(y) - center_xy[1])


def xy_to_polar_about_center(
    x: np.ndarray,
    y: np.ndarray,
    center_xy: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Convert pixel coordinates to polar coordinates about ``center_xy``.

    Returns
    -------
    theta_deg, r_pix
        Angle in degrees and pixel radius.
    """
    dx = np.asarray(x, dtype=float) - center_xy[0]
    dy = np.asarray(y, dtype=float) - center_xy[1]
    theta_deg = (np.degrees(np.arctan2(dy, dx)) + 360.0) % 360.0
    r_pix = np.hypot(dx, dy)
    return theta_deg, r_pix


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


def build_spoke_tiers() -> list[np.ndarray]:
    """Return hierarchical spoke tiers in the half-plane [0, 180)."""
    tier1 = np.arange(0, 180, 30.0)
    tier2 = np.setdiff1d(np.arange(0, 180, 10.0), tier1)
    tier3 = np.setdiff1d(np.arange(0, 180, 5.0), np.union1d(tier1, tier2))
    tier4 = np.setdiff1d(np.arange(0, 180, 2.5), np.union1d(tier1, np.union1d(tier2, tier3)))
    return [tier1, tier2, tier3, tier4]


# -----------------------------------------------------------------------------
# Spoke fitting helpers
# -----------------------------------------------------------------------------

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


# -----------------------------------------------------------------------------
# Circle bootstrapping
# -----------------------------------------------------------------------------

def fit_spoke_radius_to_nominal_r(
    nominal_points: GridData,
    mask: np.ndarray,
    center_xy: np.ndarray,
    poly_degree: int,
) -> np.poly1d:
    """
    Fit nominal radius as a polynomial of pixel radius along one spoke.
    """
    valid = mask & np.isfinite(nominal_points.r_nom_deg)
    if np.sum(valid) < 3:
        raise DetectionError("Not enough points to fit spoke radius model.")

    r_pix = point_radius_from_center(nominal_points.x[valid], nominal_points.y[valid], center_xy)
    r_nom = nominal_points.r_nom_deg[valid]

    order = np.argsort(r_pix)
    r_pix = r_pix[order]
    r_nom = r_nom[order]

    # Anchor spokes at the center. This is especially important for central tiers.
    r_pix = np.concatenate([[0.0], r_pix])
    r_nom = np.concatenate([[0.0], r_nom])

    deg = min(int(poly_degree), max(1, r_pix.size - 1))
    coeff = np.polyfit(r_pix, r_nom, deg)
    return np.poly1d(coeff)


def fit_circle_radial_model(
    theta_deg: np.ndarray,
    r_pix: np.ndarray,
    n_harmonics: int = DEFAULT_PARAMETERS["circle_fourier_harmonics"],
) -> np.ndarray:
    """Fit a Fourier model ``r_pix(theta)`` for one circle."""
    theta_rad = np.deg2rad(theta_deg)
    cols = [np.ones_like(theta_rad)]
    for k in range(1, n_harmonics + 1):
        cols.append(np.cos(k * theta_rad))
        cols.append(np.sin(k * theta_rad))
    A = np.column_stack(cols)
    coeffs, *_ = np.linalg.lstsq(A, r_pix, rcond=None)
    return coeffs


def eval_circle_radial_model(
    theta_deg: np.ndarray,
    coeffs: np.ndarray,
    n_harmonics: int = DEFAULT_PARAMETERS["circle_fourier_harmonics"],
) -> np.ndarray:
    """Evaluate a Fourier circle-radius model."""
    theta_rad = np.deg2rad(theta_deg)
    cols = [np.ones_like(theta_rad)]
    for k in range(1, n_harmonics + 1):
        cols.append(np.cos(k * theta_rad))
        cols.append(np.sin(k * theta_rad))
    return np.column_stack(cols) @ coeffs


def revert_circle_outliers(
    nominal_points: GridData,
    center_xy: np.ndarray,
    r_deg: float,
    mad_threshold: float = DEFAULT_PARAMETERS["circle_outlier_mad_threshold"],
) -> int:
    """
    Remove inconsistent assignments on one circle using a Fourier circle model.
    """
    n_harmonics = DEFAULT_PARAMETERS["circle_fourier_harmonics"]   
    total = 0

    while True:
        assigned = nominal_points.r_nom_deg == r_deg

        if np.sum(assigned) < 2 * n_harmonics + 2:
            return total

        theta_nom = nominal_points.theta_nom_deg[assigned]
        valid = np.isfinite(theta_nom)

        if np.sum(valid) < 2 * n_harmonics + 2:
            return total

        idx_assigned = nominal_points.idx[assigned][valid]
        theta_nom = theta_nom[valid]
        x = nominal_points.x[assigned][valid]
        y = nominal_points.y[assigned][valid]

        order = np.argsort(theta_nom)
        idx_assigned = idx_assigned[order]
        theta_nom = theta_nom[order]
        r_pix = point_radius_from_center(x[order], y[order], center_xy)

        coeffs = fit_circle_radial_model(theta_nom, r_pix)
        residuals = np.abs(r_pix - eval_circle_radial_model(theta_nom, coeffs))
        mad = np.median(residuals)

        if mad <= 0:
            return total

        outliers = residuals > mad_threshold * mad
        bad_idxs = idx_assigned[outliers]

        if bad_idxs.size == 0:
            return total

        for idx, res in zip(bad_idxs, residuals[outliers], strict=True):
            logger.info(
                f"  Reverting idx={idx} assigned to r={r_deg:.1f}: "
                f"residual={res:.1f}px (MAD={mad:.1f}px)"
            )
            nominal_points.set_radius(int(idx), np.nan)
            total += 1


def assign_intersection_radii_from_spokes(
    nominal_points: GridData,
    center_xy: np.ndarray,
    circle_snap_tol_deg: float,
    poly_degree: int,
) -> GridData:
    """
    Bootstrap missing circle labels for spoke-assigned points.

    The algorithm grows known circles inward and outward from the current set of
    confidently labeled circles.
    """
    unique_spokes = np.unique(nominal_points.theta_nom_deg[np.isfinite(nominal_points.theta_nom_deg)])
    unique_rings = np.sort(np.unique(nominal_points.r_nom_deg[np.isfinite(nominal_points.r_nom_deg)]))

    while True:
        if unique_rings.size == 0:
            break

        inner_ring = float(np.min(unique_rings))
        next_upper_rings = [r for r in np.arange(inner_ring, DEFAULT_PARAMETERS["max_nominal_r_deg"] + DEFAULT_PARAMETERS["grid_step_deg"], DEFAULT_PARAMETERS["grid_step_deg"])
                            if not np.any(np.isclose(unique_rings, r))]

        next_lower = None if np.isclose(inner_ring, DEFAULT_PARAMETERS["grid_step_deg"]) else inner_ring - DEFAULT_PARAMETERS["grid_step_deg"]
        next_upper = None if len(next_upper_rings) == 0 else float(next_upper_rings[0])

        logger.info(f"Next lower circle: {next_lower}, next upper circle: {next_upper}")

        if next_lower is None and next_upper is None:
            break

        target_rings = [r for r in (next_lower, next_upper) if r is not None]

        for theta in unique_spokes:
            mask = nominal_points.theta_nom_deg == theta
            try:
                spoke_model = fit_spoke_radius_to_nominal_r(nominal_points, mask, center_xy, poly_degree)
            except ValueError:
                continue

            distances = point_radius_from_center(nominal_points.x[mask], nominal_points.y[mask], center_xy)
            local_idx = np.where(mask)[0]
            order = np.argsort(distances)
            distances = distances[order]
            local_idx = local_idx[order]

            r_est = spoke_model(distances)
            snapped = DEFAULT_PARAMETERS["grid_step_deg"] * np.round(r_est / DEFAULT_PARAMETERS["grid_step_deg"])

            for r in target_rings:
                candidates = np.where((np.abs(r_est - snapped) <= circle_snap_tol_deg) & np.isclose(snapped, r))[0]

                if candidates.size == 0:
                    continue

                # Choose the candidate whose model estimate is closest to the target radius.
                best_local = candidates[np.argmin(np.abs(r_est[candidates] - r))]
                pos = local_idx[best_local]

                existing = nominal_points.r_nom_deg[pos]
                if np.isfinite(existing) and not np.isclose(existing, r):
                    logger.info(
                        f"  Warning: idx={nominal_points.idx[pos]} has conflicting "
                        f"circle {existing:.1f} vs {r:.1f}; keeping existing."
                    )
                    continue

                nominal_points.r_nom_deg[pos] = r

        reverted = 0
        for r in target_rings:
            reverted += revert_circle_outliers(nominal_points, center_xy, r)

        if reverted > 0:
            logger.info(f"  Reverted {reverted} point(s).")

        if next_lower is not None:
            unique_rings = np.append(unique_rings, next_lower)
        if next_upper is not None:
            unique_rings = np.append(unique_rings, next_upper)

        unique_rings = np.sort(np.unique(unique_rings))

    return nominal_points


def assign_circle_only_points(
    nominal_points: GridData,
    dense_points: DenseGrid,
    center_xy: np.ndarray,
) -> GridData:
    """
    Assign circle-only dense points using Fourier models of recovered circles.
    """
    theta_all, r_all = xy_to_polar_about_center(dense_points.x, dense_points.y, center_xy)
    unique_circles = np.sort(np.unique(nominal_points.r_nom_deg[np.isfinite(nominal_points.r_nom_deg)]))

    for r_deg in unique_circles:
        mask = nominal_points.r_nom_deg == r_deg
        valid = np.isfinite(nominal_points.theta_nom_deg[mask])

        if np.sum(valid) < 2 * DEFAULT_PARAMETERS["circle_fourier_harmonics"] + 2:
            continue

        theta_nom = nominal_points.theta_nom_deg[mask][valid]
        x = nominal_points.x[mask][valid]
        y = nominal_points.y[mask][valid]
        r_pix = point_radius_from_center(x, y, center_xy)

        coeffs = fit_circle_radial_model(theta_nom, r_pix)
        residual = np.abs(r_pix - eval_circle_radial_model(theta_nom, coeffs))
        mad = np.median(residual)

        if mad <= 0:
            continue

        unassigned_mask = ~np.isin(dense_points.idx, nominal_points.idx)
        idx_unassigned = dense_points.idx[unassigned_mask]

        r_pred = eval_circle_radial_model(theta_all[unassigned_mask], coeffs)
        good = np.abs(r_all[unassigned_mask] - r_pred) <= DEFAULT_PARAMETERS["circle_only_mad_factor"] * mad

        for idx in idx_unassigned[good]:
            nominal_points.add_or_update(
                idx=int(idx),
                x=float(dense_points.x[idx]),
                y=float(dense_points.y[idx]),
                theta_nom_deg=None,
                r_nom_deg=float(r_deg),
            )

    return nominal_points


# -----------------------------------------------------------------------------
# Parallel tier execution and merge
# -----------------------------------------------------------------------------

def _run_spoke_worker(payload: tuple) -> tuple[float, SpokeBootstrapResult | None, str | None]:
    """
    Process one spoke in a worker process.

    Returns
    -------
    spoke_deg, result, error
    """
    (
        spoke_deg,
        nominal_points,
        dense_points,
        center_xy,
        available_mask,
        spoke_tol_px,
    ) = payload

    try:
        result = bootstrap_spoke_pair(
            spoke_deg=spoke_deg,
            nominal_points=nominal_points,
            dense_points=dense_points,
            center_xy=center_xy,
            available_mask=available_mask,
            spoke_tol_px=spoke_tol_px,
        )
        return float(spoke_deg), result, None
    except Exception as exc:  # noqa: BLE001
        return float(spoke_deg), None, str(exc)


def run_spoke_tier(
    spoke_group: np.ndarray,
    nominal_points: GridData,
    dense_points: DenseGrid,
    center_xy: np.ndarray,
    assigned_spoke_deg: np.ndarray,
    max_workers: int,
    spoke_tol_px: float,
) -> list[SpokeBootstrapResult]:
    """
    Run one spoke tier, optionally in parallel.

    Each worker receives the same availability mask. After the tier finishes,
    duplicate dense-point assignments are discarded before updating the global
    assignment table.
    """
    available_mask = assigned_spoke_deg < 0
    payloads = [
        (
            float(spoke_deg),
            copy.deepcopy(nominal_points) if max_workers > 1 else nominal_points,
            dense_points,
            center_xy,
            available_mask,
            spoke_tol_px,
        )
        for spoke_deg in spoke_group
    ]

    raw_results: list[SpokeBootstrapResult] = []

    if max_workers > 1 and len(payloads) > 1:
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_run_spoke_worker, payload) for payload in payloads]
            for future in as_completed(futures):
                spoke_deg, result, error = future.result()
                if error is not None:
                    logger.info(f"  spoke {spoke_deg:.1f} failed: {error}")
                elif result is not None:
                    raw_results.append(result)
    else:
        for payload in payloads:
            spoke_deg, result, error = _run_spoke_worker(payload)
            if error is not None:
                logger.info(f"  spoke {spoke_deg:.1f} failed: {error}")
            elif result is not None:
                raw_results.append(result)

    if not raw_results:
        return []

    # Discard duplicate dense-point assignments within the tier.
    counts: dict[int, int] = {}
    for result in raw_results:
        for idx in result.assigned_idx:
            counts[int(idx)] = counts.get(int(idx), 0) + 1

    clean_results: list[SpokeBootstrapResult] = []
    n_duplicates = sum(count > 1 for count in counts.values())

    if n_duplicates:
        logger.info(f"  duplicate assignments in tier: {n_duplicates}; discarding duplicates")

    for result in raw_results:
        keep = np.array([counts[int(idx)] == 1 for idx in result.assigned_idx], dtype=bool)
        clean_results.append(
            SpokeBootstrapResult(
                spoke_deg=result.spoke_deg,
                opposite_deg=result.opposite_deg,
                seed_count=result.seed_count,
                assigned_idx=result.assigned_idx[keep],
                assigned_x=result.assigned_x[keep],
                assigned_y=result.assigned_y[keep],
                assigned_side=result.assigned_side[keep],
                curve_x=result.curve_x,
                curve_y=result.curve_y,
                curve_u=result.curve_u,
                inward_growth_steps=result.inward_growth_steps,
                outward_growth_steps=result.outward_growth_steps,
                cutoff_nominal_r_deg=result.cutoff_nominal_r_deg,
                cutoff_pix=result.cutoff_pix,
            )
        )

    clean_results.sort(key=lambda r: r.spoke_deg)
    return clean_results


def build_output_records(nominal_points: GridData, center_xy: np.ndarray) -> list[dict[str, float | int]]:
    """
    Convert complete intersection assignments to the distortion-fit ``data`` list.
    """
    data: list[dict[str, float | int]] = []

    complete = np.isfinite(nominal_points.theta_nom_deg) & np.isfinite(nominal_points.r_nom_deg)
    for pos in np.where(complete)[0]:
        x = float(nominal_points.x[pos])
        y = float(nominal_points.y[pos])
        r = float(point_radius_from_center(x, y, center_xy))
        theta = float((np.degrees(np.arctan2(y - center_xy[1], x - center_xy[0])) + 360.0) % 360.0)

        data.append(
            {
                "idx": int(nominal_points.idx[pos]),
                "pixel_x": x,
                "pixel_y": y,
                "r": r,
                "theta": theta,
                "circle_index": int(np.round(nominal_points.r_nom_deg[pos] / DEFAULT_PARAMETERS["grid_step_deg"])),
                "spoke_index": int(np.round(nominal_points.theta_nom_deg[pos] / DEFAULT_PARAMETERS["grid_step_deg"])),
                "nominal_r": float(nominal_points.r_nom_deg[pos]),
                "nominal_theta": float(nominal_points.theta_nom_deg[pos]),
            }
        )

    return data


def bootstrapping_from_nominal(
    nominal_assignment: list[dict],
    averaged_grid: np.ndarray,
    center_xy: dict[str, float],
    params: dict | None = None,
):
    
    params = DEFAULT_PARAMETERS.copy() if params is None else params

    max_workers = int(params["max_workers"])
    if max_workers < 1:
        max_workers = max(1, (os.cpu_count() or 2) - 1)


    all_points = DenseGrid.load(averaged_grid)
    logger.info(f"  loaded {all_points.idx.size} dense points")

    nominal_points = GridData.load(nominal_assignment)
    logger.info(f"  loaded {nominal_points.idx.size} labeled points")

    center_xy = load_center(center_xy)

    assigned_spoke_deg = np.full(all_points.idx.size, -1.0, dtype=float)
    for pos, idx in enumerate(nominal_points.idx):
        if np.isfinite(nominal_points.theta_nom_deg[pos]):
            assigned_spoke_deg[int(idx)] = nominal_points.theta_nom_deg[pos]

    spoke_results: list[SpokeBootstrapResult] = []

    for i_tier, spoke_group in enumerate(build_spoke_tiers(), start=1):
        logger.info(f"\n=== Processing spoke tier {i_tier} ({len(spoke_group)} spoke pairs) ===")
        tier_results = run_spoke_tier(
            spoke_group=spoke_group,
            nominal_points=nominal_points,
            dense_points=all_points,
            center_xy=center_xy,
            assigned_spoke_deg=assigned_spoke_deg,
            max_workers=max_workers,
            spoke_tol_px=params["spoke_final_tol_px"],
        )

        for result in tier_results:
            assigned_spoke_deg[result.assigned_idx] = result.spoke_deg
            spoke_results.append(result)

            logger.info(
                f"  spoke {result.spoke_deg:5.1f}/{result.opposite_deg:5.1f}: "
                f"assigned={result.assigned_idx.size:4d}, "
                f"in={result.inward_growth_steps:3d}, out={result.outward_growth_steps:3d}"
            )

            for i, idx in enumerate(result.assigned_idx):
                if result.assigned_side[i] == "main":
                    theta = result.spoke_deg
                elif result.assigned_side[i] == "opp":
                    theta = result.opposite_deg
                else:
                    continue

                if nominal_points.has_idx(int(idx)):
                    existing = nominal_points.get_theta(int(idx))
                    if np.isfinite(existing) and not np.isclose(existing, theta):
                        raise DetectionError(
                            f"Assigned spoke angle {theta} does not match existing "
                            f"nominal angle {existing} for idx={idx}."
                        )
                    nominal_points.set_theta(int(idx), theta)
                else:
                    nominal_points.append(
                        idx=int(idx),
                        x=float(all_points.x[idx]),
                        y=float(all_points.y[idx]),
                        theta_nom_deg=float(theta),
                        r_nom_deg=np.nan,
                    )

    # Sanity-clean points whose implied nominal radius is outside the expected
    # radial support of their spoke.
    logger.info("\nCleaning spoke assignments outside expected radial support...")
    for spoke_deg in np.unique(nominal_points.theta_nom_deg[np.isfinite(nominal_points.theta_nom_deg)]):
        mask = nominal_points.theta_nom_deg == spoke_deg
        try:
            spoke_model = fit_spoke_radius_to_nominal_r(nominal_points, mask, center_xy, params["circle_fit_poly_degree"])
        except (ValueError, DetectionError):
            continue

        distances = point_radius_from_center(nominal_points.x[mask], nominal_points.y[mask], center_xy)
        r_est = spoke_model(distances)
        bad = (r_est < spoke_min_nominal_r(spoke_deg) - 1.0) | (r_est > params["max_nominal_r_deg"] + 1.0)

        for idx in nominal_points.idx[mask][bad]:
            logger.info(f"  clearing idx={idx} on spoke {spoke_deg:.1f}: implied r outside valid range")
            nominal_points.clear_assignment(int(idx))

    logger.info("\nBootstrapping circle labels from spoke-assigned points...")
    nominal_points = assign_intersection_radii_from_spokes(
        nominal_points=nominal_points,
        center_xy=center_xy,
        circle_snap_tol_deg=params["circle_snap_tol_deg"],
        poly_degree=params["circle_fit_poly_degree"],
    )

    logger.info("\nAssigning circle-only points...")
    nominal_points = assign_circle_only_points(
        nominal_points=nominal_points,
        dense_points=all_points,
        center_xy=center_xy,
    )

    bootstrapped_nominal_assignment = build_output_records(nominal_points, center_xy)

    return bootstrapped_nominal_assignment
