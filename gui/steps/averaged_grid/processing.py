# grid_calibration/gui/steps/averaged_grid/processing.py
from __future__ import annotations

from pathlib import Path
from typing import List

import logging

import numpy as np
from scipy.spatial import cKDTree

from ..grid_points import product_io as grid_points_io
from ..grid_points.keys import GRID_KEY
from .spec import product_io as averaged_grid_io


logger = logging.getLogger(__name__)


def average_detected_grids_images(
    image_paths: List[Path],
) -> Path:
    """
    Run average_detected_grids on the grid-point products for each input image.
    """
    
    detection_paths = [
        grid_points_io.expected_path(input_file=img)
        for img in image_paths
    ]

    logger.info("Averaging detected grid points.")

    average_detected_grids(
        grid_npz_files=detection_paths,
        match_tolerance=5.0,
        min_matches=3,
    )

    averaged_grid_io.register()
    out_path = averaged_grid_io.expected_path(input_file=image_paths[0])
    return out_path


def average_detected_grids(grid_npz_files, match_tolerance=5.0, min_matches=3):
    """
    Load multiple detection files and keep only grid points that appear
    in at least `min_matches` images, within `match_tolerance` pixels.

    Parameters
    ----------
    grid_npz_files : list or Path
        Paths to the .npz detection files. Each must contain 'grid'
        as an (N_i, 2) array of (y, x) coordinates.
    outfile : Path
        Path to save the averaged grid points .npz file.
    match_tolerance : float
        Maximum distance (in pixels) to consider two detections the same point.
    min_matches : int
        Minimum number of images that must contribute to a cluster.

    Returns
    -------
    averaged_points : (M, 2) ndarray
        Averaged (y, x) coordinates of the accepted grid intersections.
    counts : (M,) ndarray
        Number of *distinct images* contributing to each averaged point.
    """

    # --- Sanity checks
    # override min_matches to be at most the number of input files
    n_files = len(grid_npz_files)
    if n_files == 0:
        logger.warning("No grid files provided for averaging.")
        averaged_grid_io.save(
            grid=np.empty((0, 2)),
            counts=np.empty((0,), dtype=int),
        )
        return np.empty((0, 2)), np.empty((0,), dtype=int)
    if min_matches > n_files:
        logger.warning(f"min_matches={min_matches} is greater than number of files={n_files}. Reducing min_matches to {n_files}.")
    min_matches = min(min_matches, n_files)


    # --- 1) Load all detections and keep track of which image they came from
    all_points = []
    image_ids = []

    for i, fname in enumerate(grid_npz_files):
        data = grid_points_io.load(fname)
        pts = np.asarray(data[GRID_KEY])
        all_points.append(pts)
        image_ids.append(np.full(len(pts), i, dtype=np.int16))

    all_points = np.vstack(all_points)   # shape (N_total, 2)
    image_ids = np.concatenate(image_ids)  # shape (N_total,)

    if all_points.size == 0:
        logger.warning("No grid points found in the provided files.")
        averaged_grid_io.save(
            grid=np.empty((0, 2)),
            counts=np.empty((0,), dtype=int),
        )
        return np.empty((0, 2)), np.empty((0,), dtype=int)

    # --- 2) Build a KD-tree for fast neighbor queries
    tree = cKDTree(all_points)

    # --- 3) Cluster by "friends within match_tolerance"
    N = len(all_points)
    visited = np.zeros(N, dtype=bool)
    cluster_indices = []

    for i in range(N):
        if visited[i]:
            continue
        # all points within match_tolerance of point i
        neighbors = tree.query_ball_point(all_points[i], r=match_tolerance)
        neighbors = np.asarray(neighbors, dtype=int)
        visited[neighbors] = True
        cluster_indices.append(neighbors)

    # --- 4) For each cluster, count distinct images and average coordinates
    averaged_points = []
    counts = []

    for idx in cluster_indices:
        imgs = np.unique(image_ids[idx])
        n_imgs = len(imgs)
        if n_imgs >= min_matches:
            averaged_points.append(all_points[idx].mean(axis=0))
            counts.append(n_imgs)

    if len(averaged_points) == 0:
        logger.warning("No clusters met the minimum match requirement.")
        averaged_grid_io.save(
            grid=np.empty((0, 2)),
            counts=np.empty((0,), dtype=int),
        )
        return np.empty((0, 2)), np.empty((0,), dtype=int)

    averaged_points = np.vstack(averaged_points)   # (M, 2)
    counts = np.asarray(counts)

    averaged_grid_io.save(
        grid=averaged_points,
        counts=counts,
    )

    return averaged_points, counts