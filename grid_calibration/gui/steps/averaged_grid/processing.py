# grid_calibration/gui/steps/averaged_grid/processing.py
"""
Batch-processing functions for the averaged-grid step.

This module combines multiple per-input grid-point products into one singleton
averaged-grid product. Clustering is performed in image space using a KD-tree
neighbor search and a configurable matching tolerance.
"""

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
    Build the singleton averaged-grid product from per-input detections.

    Parameters
    ----------
    image_paths : :class:`list` [:class:`~pathlib.Path`]
        Raw input image paths. Their corresponding grid-point products are
        resolved through the grid-points
        :class:`~grid_calibration.gui.workflow.product_io.ProductIO`.

    Returns
    -------
    :class:`~pathlib.Path`
        Path to the generated ``*_averaged_grid.npz`` singleton product.

    Notes
    -----
    The generated singleton product is registered in the active
    :class:`~grid_calibration.gui.session.CalibrationSession` using
    :meth:`~grid_calibration.gui.workflow.product_io.ProductIO.register`.
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


def average_detected_grids(
    grid_npz_files,
    match_tolerance=5.0,
    min_matches=3,
):
    """
    Average matching grid detections across multiple images.

    Parameters
    ----------
    grid_npz_files : sequence
        Paths to the per-input ``*_grid_points.npz`` products.
    match_tolerance : :class:`float`, optional
        Maximum Euclidean distance, in pixels, for detections to be considered
        part of the same cluster.
    min_matches : :class:`int`, optional
        Minimum number of distinct images contributing to a cluster for that
        cluster to be retained in the averaged result.

    Returns
    -------
    :class:`tuple`
        ``(averaged_points, counts)`` where:

        - ``averaged_points`` is an ``(N, 2)`` array of averaged coordinates;
        - ``counts`` is an ``(N,)`` array containing the number of contributing
          images for each point.

    Notes
    -----
    The resulting arrays are saved through the singleton
    :class:`~grid_calibration.gui.workflow.product_io.ProductIO`
    descriptor for the averaged-grid step.
    """

    # --- Sanity checks
    n_files = len(grid_npz_files)
    if n_files == 0:
        logger.warning("No grid files provided for averaging.")
        averaged_grid_io.save(
            grid=np.empty((0, 2)),
            counts=np.empty((0,), dtype=int),
        )
        return np.empty((0, 2)), np.empty((0,), dtype=int)

    if min_matches > n_files:
        logger.warning(
            "min_matches=%d is greater than number of files=%d. "
            "Reducing min_matches to %d.",
            min_matches,
            n_files,
            n_files,
        )

    min_matches = min(min_matches, n_files)

    # --- 1) Load all detections and keep track of source image
    all_points = []
    image_ids = []

    for i, fname in enumerate(grid_npz_files):
        data = grid_points_io.load(fname)
        pts = np.asarray(data[GRID_KEY])

        all_points.append(pts)
        image_ids.append(np.full(len(pts), i, dtype=np.int16))

    all_points = np.vstack(all_points)
    image_ids = np.concatenate(image_ids)

    if all_points.size == 0:
        logger.warning("No grid points found in the provided files.")

        averaged_grid_io.save(
            grid=np.empty((0, 2)),
            counts=np.empty((0,), dtype=int),
        )

        return np.empty((0, 2)), np.empty((0,), dtype=int)

    # --- 2) Build KD-tree for neighbor clustering
    tree = cKDTree(all_points)

    # --- 3) Cluster nearby detections
    N = len(all_points)
    visited = np.zeros(N, dtype=bool)
    cluster_indices = []

    for i in range(N):
        if visited[i]:
            continue

        neighbors = tree.query_ball_point(
            all_points[i],
            r=match_tolerance,
        )

        neighbors = np.asarray(neighbors, dtype=int)

        visited[neighbors] = True
        cluster_indices.append(neighbors)

    # --- 4) Average clusters with enough distinct-image support
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

    averaged_points = np.vstack(averaged_points)
    counts = np.asarray(counts)

    averaged_grid_io.save(
        grid=averaged_points,
        counts=counts,
    )

    return averaged_points, counts
