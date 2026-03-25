from pathlib import Path
from typing import List
import logging
from GONet_Wizard.GONet_utils.src.gonet.analysis_utils.full_array import build_full_array # type: ignore
from .products import ALL_PRODUCTS
from .detection import detect_grid_points, average_detected_grids

logger = logging.getLogger(__name__)


def make_output_dir(dir_name: str) -> Path:
    """
    Create and return a subdirectory within the base directory.

    Parameters
    ----------
    base_dir : :class:`Path`
        The base directory where the subdirectory will be created.
    subdir_name : :class:`str`
        The name of the subdirectory to create.

    Returns
    -------
    :class:`Path`
        The path to the created subdirectory.
    """
    out_dir = Path(dir_name)
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def build_full_arrays_for_images(
    image_paths: List[Path],
    out_dir: Path,
) -> List[Path]:
    """
    Run build_full_array on each input JPEG and return the list of
    generated `.npz` files.
    """

    full_paths: List[Path] = []

    for img in image_paths:
        out_path = out_dir / ALL_PRODUCTS["full-array"].path(input_file=img)
        logger.info(f"[pipeline] Building full array for {img.name} -> {out_path}")
        build_full_array(
            gonet_file = img,
            show = False,
            outfile = out_path,
            verbose = True,
            save_diagnostics = True,
        )
        full_paths.append(out_path)

    return full_paths

def detect_grid_points_for_images(
    image_paths: List[Path],
    out_dir: Path,
) -> List[Path]:
    """
    Run detect_grid_points on each input full array `.npz` file and return the list of
    generated grid points `.npz` files.
    """

    grid_points_paths: List[Path] = []

    for img in image_paths:
        full_array = out_dir / ALL_PRODUCTS["full-array"].path(input_file=img)
        out_path = out_dir / ALL_PRODUCTS["grid-points"].path(input_file=img)
        logger.info(f"[pipeline] Detecting grid points for {full_array.name} -> {out_path}")
        detect_grid_points(
            full_gonet_array_file_path = full_array,
            outfile = out_path,
            sigma_bg = 20.0,
            threshold_rel = 0.1,
        )
        grid_points_paths.append(out_path)

    return grid_points_paths

def average_detected_grids_images(
    image_paths: List[Path],
    out_dir: Path,
) -> Path:
    """
    Run average_detected_grids on the list of detection `.npz` files and return the path of
    the generated averaged grid points `.npz` file.
    """

    out_path = out_dir / ALL_PRODUCTS["averaged-grid"].path(input_file=image_paths[0])
    detection_paths = [
        out_dir / ALL_PRODUCTS["grid-points"].path(input_file=img)
        for img in image_paths
    ]
    logger.info(f"[pipeline] Averaging detected grid points -> {out_path}")
    average_detected_grids(
        grid_npz_files = detection_paths,
        outfile = out_path,
        match_tolerance = 5.0,
        min_matches = 3,
    )

    return out_path