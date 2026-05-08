# grid_calibration/gui/steps/full_array/processing.py

from __future__ import annotations
from typing import List
from pathlib import Path
import logging
from GONet_Wizard.GONet_utils.src.gonet.analysis_utils.full_array import build_full_array # type: ignore


logger = logging.getLogger(__name__)

def build_full_arrays_for_images(
    image_paths: List[Path],
) -> List[Path]:
    """
    Run build_full_array on each input JPEG and return the list of
    generated `.npz` files.
    """
    from ...session import get_session
    session = get_session()

    full_paths: List[Path] = []

    for img in image_paths:
        out_path = session.expected_path("full-array", input_file=img)
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