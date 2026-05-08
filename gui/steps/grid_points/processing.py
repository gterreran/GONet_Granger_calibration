from __future__ import annotations
from pathlib import Path
from typing import List

import numpy as np
from skimage.filters import gaussian
from skimage.feature import peak_local_max

import logging

logger = logging.getLogger(__name__)

def detect_grid_points_for_images(
    image_paths: List[Path],
) -> List[Path]:
    """
    Run detect_grid_points on each input full array `.npz` file and return the list of
    generated grid points `.npz` files.
    """

    grid_points_paths: List[Path] = []
    from ...session import get_session
    session = get_session()
    for img in image_paths:
        full_array = session.expected_path("full-array", input_file=img)
        out_path = session.expected_path("grid-points", input_file=img)
        logger.info(f"[pipeline] Detecting grid points for {full_array.name} -> {out_path}")
        detect_grid_points(
            full_gonet_array_file_path = full_array,
            outfile = out_path,
            sigma_bg = 20.0,
            threshold_rel = 0.1,
        )
        grid_points_paths.append(out_path)

    return grid_points_paths


def detect_grid_points(full_gonet_array_file_path: Path, outfile: Path, sigma_bg=20.0, threshold_rel=0.1):
    # Loading image component of .npz files
    logging.info(f"Loading {full_gonet_array_file_path}...")
    data = np.load(full_gonet_array_file_path, allow_pickle=True)
    image = data['image']

    background = gaussian(image, sigma=sigma_bg, preserve_range=True)
    residual = image - background

    # robust noise estimate from MAD
    med = np.median(residual)
    mad = np.median(np.abs(residual - med))
    noise_sigma = 1.4826 * mad

    # pick thresholds in terms of noise_sigma
    low_clip  = med + 3 * noise_sigma   # ~3σ above background
    high_clip = med + 8 * noise_sigma   # cap out extreme peaks

    clipped = residual.copy()
    clipped[clipped < low_clip] = 0
    clipped = np.clip(clipped, 0, high_clip)


    small  = gaussian(image, sigma=1.5, preserve_range=True)   # near intersection scale
    large  = gaussian(image, sigma=10.0, preserve_range=True)  # suppress grid-scale & larger
    dog    = small - large

    dog[dog < 0] = 0

    smoothed_peaks = gaussian(dog, sigma=1.0, preserve_range=True)

    peaks = peak_local_max(smoothed_peaks**2, threshold_rel=threshold_rel)
    logging.info(f"Detected {len(peaks)} grid points.")

    # Saving the grid points
    np.savez_compressed(outfile, grid = peaks)