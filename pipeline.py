from pathlib import Path
from typing import List, Dict, Iterable
import logging
from GONet_Wizard.GONet_utils.src.gonet.analysis_utils.full_array import build_full_array # type: ignore
from .products import ALL_PRODUCTS, ProductKind

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
        stem = img.stem
        out_path = out_dir / f"{stem}_full_array.npz"
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