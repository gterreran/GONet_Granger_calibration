# grid_calibration/gui/steps/grid_points/processing.py
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
    Run detect_grid_points on each input full-array product and return the generated
    grid-points product paths.
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