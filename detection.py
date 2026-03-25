import numpy as np
from skimage.filters import gaussian
from skimage.feature import peak_local_max
from pathlib import Path
from scipy.spatial import cKDTree
import logging

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


def average_detected_grids(grid_npz_files, outfile, match_tolerance=5.0, min_matches=3):
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
        logging.warning("No grid files provided for averaging.")
        np.savez_compressed(outfile, grid=np.empty((0, 2)), counts=np.empty((0,), dtype=int))
        return np.empty((0, 2)), np.empty((0,), dtype=int)
    if min_matches > n_files:
        logging.warning(f"min_matches={min_matches} is greater than number of files={n_files}. Reducing min_matches to {n_files}.")
    min_matches = min(min_matches, n_files)


    # --- 1) Load all detections and keep track of which image they came from
    all_points = []
    image_ids = []

    for i, fname in enumerate(grid_npz_files):
        data = np.load(fname, allow_pickle=True)
        pts = np.asarray(data["grid"])
        all_points.append(pts)
        image_ids.append(np.full(len(pts), i, dtype=np.int16))

    all_points = np.vstack(all_points)   # shape (N_total, 2)
    image_ids = np.concatenate(image_ids)  # shape (N_total,)

    if all_points.size == 0:
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
        return np.empty((0, 2)), np.empty((0,), dtype=int)

    averaged_points = np.vstack(averaged_points)   # (M, 2)
    counts = np.asarray(counts)

    np.savez_compressed(outfile,
                        grid=averaged_points, counts=counts)

    return averaged_points, counts