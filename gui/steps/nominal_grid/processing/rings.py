"""
Ring-level estimation and nominal-circle assignment helpers.
"""

from __future__ import annotations

import numpy as np

from .constants import DEG_STEP
from .utils import wrap_deg


def assign_nominal_circles(
    ring_levels_px: np.ndarray,
    *,
    spacing_px: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Assign ring groups to nearest nominal circle indices.

    Parameters
    ----------
    ring_levels_px : numpy.ndarray
        Representative measured pixel radius for each ring group.
    spacing_px : float
        Estimated measured pixel spacing corresponding to :data:`DEG_STEP`.

    Returns
    -------
    tuple[numpy.ndarray, numpy.ndarray]
        Integer circle indices and nominal circle radii in degrees.
    """
    k_circle = np.rint(ring_levels_px / spacing_px).astype(int)
    k_circle = np.clip(k_circle, 0, None)
    rho_circle = DEG_STEP * k_circle
    return k_circle, rho_circle


def ring_group_theta_bins(
    points: np.ndarray,
    group: np.ndarray,
    *,
    bin_width_deg: float = 30.0,
    theta_period: float = 360.0,
    min_pts_per_bin: int = 10,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute median radius values for one ring group in theta bins.

    Parameters
    ----------
    points : numpy.ndarray
        Polar point coordinates with columns ``theta`` and ``r``.
    group : numpy.ndarray
        Indices of points belonging to one ring fragment.
    bin_width_deg : float, optional
        Width of theta bins in degrees.
    theta_period : float, optional
        Period of the theta coordinate.
    min_pts_per_bin : int, optional
        Minimum number of points needed to keep a bin.

    Returns
    -------
    tuple[numpy.ndarray, numpy.ndarray]
        Kept bin indices and corresponding median measured radii.
    """
    theta = wrap_deg(points[group, 0])
    r = points[group, 1]

    nbins = int(round(theta_period / bin_width_deg))
    edges = np.linspace(0.0, theta_period, nbins + 1)

    b = np.digitize(theta, edges) - 1
    b[b == nbins] = nbins - 1

    bin_ids: list[int] = []
    r_med: list[float] = []

    for bi in range(nbins):
        m = b == bi
        if int(m.sum()) < min_pts_per_bin:
            continue
        bin_ids.append(bi)
        r_med.append(float(np.median(r[m])))

    return np.asarray(bin_ids, dtype=int), np.asarray(r_med, dtype=float)


def estimate_ring_levels_with_wave_correction(
    points: np.ndarray,
    ring_groups: list[np.ndarray],
    *,
    bin_width_deg: float = 30.0,
    theta_period: float = 360.0,
    min_pts_per_bin: int = 10,
    n_iter: int = 3,
) -> tuple[np.ndarray, dict[int, float], list[np.ndarray]]:
    """Estimate one representative measured radius for each ring group.

    A shared theta-dependent wave term is estimated iteratively so partially
    sampled ring fragments can be compared on a common radial scale.

    Parameters
    ----------
    points : numpy.ndarray
        Polar point coordinates with columns ``theta`` and ``r``.
    ring_groups : list[numpy.ndarray]
        Candidate ring fragments.
    bin_width_deg : float, optional
        Width of theta bins in degrees.
    theta_period : float, optional
        Period of the theta coordinate.
    min_pts_per_bin : int, optional
        Minimum number of points needed to keep a bin.
    n_iter : int, optional
        Number of wave-correction iterations.

    Returns
    -------
    tuple[numpy.ndarray, dict[int, float], list[numpy.ndarray]]
        Ring levels, wave correction by bin, and valid bins per group.
    """
    ngroups = len(ring_groups)
    nbins = int(round(theta_period / bin_width_deg))

    grp_bins: list[np.ndarray] = []
    grp_rmed: list[np.ndarray] = []
    levels = np.zeros(ngroups, dtype=float)

    for i, group in enumerate(ring_groups):
        bins_i, rmed_i = ring_group_theta_bins(
            points,
            group,
            bin_width_deg=bin_width_deg,
            theta_period=theta_period,
            min_pts_per_bin=min_pts_per_bin,
        )
        grp_bins.append(bins_i)
        grp_rmed.append(rmed_i)
        levels[i] = float(np.median(points[group, 1])) if group.size else 0.0

    wave = {bi: 0.0 for bi in range(nbins)}

    for _ in range(n_iter):
        resid_by_bin: list[list[float]] = [[] for _ in range(nbins)]

        for i in range(ngroups):
            for bi, rmed in zip(grp_bins[i], grp_rmed[i]):
                resid_by_bin[int(bi)].append(float(rmed - levels[i]))

        for bi in range(nbins):
            if resid_by_bin[bi]:
                wave[bi] = float(np.median(resid_by_bin[bi]))

        for i in range(ngroups):
            if grp_bins[i].size == 0:
                continue
            adjusted = np.array(
                [rmed - wave[int(bi)] for bi, rmed in zip(grp_bins[i], grp_rmed[i])],
                dtype=float,
            )
            levels[i] = float(np.median(adjusted))

    return levels, wave, grp_bins
