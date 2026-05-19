# grid_calibration/gui/steps/full_array/processing.py

from __future__ import annotations

from pathlib import Path
from typing import List
import logging

from GONet_Wizard.GONet_utils.src.gonet.analysis_utils.full_array import build_full_array  # type: ignore

from .spec import product_io as full_array_product_io


logger = logging.getLogger(__name__)


def build_full_arrays_for_images(
    image_paths: List[Path],
) -> List[Path]:
    """
    Run build_full_array on each input JPEG and return the generated NPZ paths.
    """
    full_paths: List[Path] = []

    for img in image_paths:
        out_path = full_array_product_io.expected_path(img)

        logger.info("Building full array for %s -> %s", img.name, out_path)

        build_full_array(
            gonet_file=img,
            show=False,
            outfile=out_path,
            verbose=logger.isEnabledFor(logging.DEBUG),
            save_diagnostics=True,
        )

        full_paths.append(out_path)

    full_array_product_io.register(full_paths)

    return full_paths