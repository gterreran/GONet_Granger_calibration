# grid_calibration/gui/steps/grid_points/processing.py
"""
Batch-processing functions for the grid-points step.

This module contains the processing callable used by the
:grid-points :class:`~grid_calibration.gui.workflow.specs.PipelineStepSpec`.
The implementation loads full-array products, applies image filtering and local
peak detection, and saves the resulting grid-point coordinates through the
step's :class:`~grid_calibration.gui.workflow.product_io.ProductIO`.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import logging
import numpy as np
from skimage.feature import peak_local_max
from skimage.filters import gaussian

from ..full_array import product_io as full_array_io
from ..full_array.keys import IMAGE_KEY
from .spec import product_io as grid_points_io

logger = logging.getLogger(__name__)


def detect_grid_points_for_images(
    image_paths: List[Path],
) -> List[Path]:
    """
    Detect grid points for each input image.

    Parameters
    ----------
    image_paths : :class:`list` [:class:`~pathlib.Path`]
        Raw input image paths. Their corresponding full-array products are
        resolved using the full-array
        :class:`~grid_calibration.gui.workflow.product_io.ProductIO`.

    Returns
    -------
    :class:`list` [:class:`~pathlib.Path`]
        Paths to the generated ``*_grid_points.npz`` products.

    Notes
    -----
    Product paths are resolved with
    :meth:`~grid_calibration.gui.workflow.product_io.ProductIO.expected_path`
    and registered in the active
    :class:`~grid_calibration.gui.session.CalibrationSession` after processing
    completes.
    """
    grid_points_paths: List[Path] = []

    for img in image_paths:
        full_array_path = full_array_io.expected_path(img)
        out_path = grid_points_io.expected_path(img)

        logger.info(
            "Detecting grid points for %s -> %s",
            full_array_path.name,
            out_path,
        )

        detect_grid_points(
            full_gonet_array_file_path=full_array_path,
            outfile=out_path,
            threshold_rel=0.1,
        )

        grid_points_paths.append(out_path)

    grid_points_io.register(grid_points_paths)
    return grid_points_paths


def detect_grid_points(
    full_gonet_array_file_path: Path,
    outfile: Path,
    threshold_rel: float = 0.1,
) -> None:
    """
    Detect candidate grid intersections from one full-array image.

    Parameters
    ----------
    full_gonet_array_file_path : :class:`~pathlib.Path`
        Path to the input ``*_full_array.npz`` product.
    outfile : :class:`~pathlib.Path`
        Output path for the generated ``*_grid_points.npz`` product.
    threshold_rel : :class:`float`, optional
        Relative threshold passed to
        :func:`skimage.feature.peak_local_max`.

    Returns
    -------
    :data:`None`
        The detected grid points are written directly to ``outfile``.

    Notes
    -----
    The implementation uses a difference-of-Gaussians enhancement followed by a
    second smoothing pass and local-maxima detection.
    """
    logger.info("Loading %s...", full_gonet_array_file_path)

    data = full_array_io.load(full_gonet_array_file_path)
    image = data[IMAGE_KEY]

    small = gaussian(image, sigma=1.5, preserve_range=True)
    large = gaussian(image, sigma=10.0, preserve_range=True)
    dog = small - large
    dog[dog < 0] = 0

    smoothed_peaks = gaussian(dog, sigma=1.0, preserve_range=True)
    peaks = peak_local_max(smoothed_peaks**2, threshold_rel=threshold_rel)

    logger.info("Detected %d grid points.", len(peaks))

    grid_points_io.save(path=outfile, grid=peaks)
