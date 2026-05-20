# grid_calibration/gui/steps/full_array/processing.py
"""
Batch processing function for building full-array products.

This module contains the pipeline callable used by the full-array
:class:`~grid_calibration.gui.workflow.specs.PipelineStepSpec`. It delegates the
actual full-array construction to :mod:`GONet_Wizard`, then registers the
generated per-input products through the step's
:class:`~grid_calibration.gui.workflow.product_io.ProductIO`.
"""

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
    Build one full-array product for each input image.

    Parameters
    ----------
    image_paths : :class:`list` [:class:`~pathlib.Path`]
        Raw image paths to process. The returned product list preserves this
        order.

    Returns
    -------
    :class:`list` [:class:`~pathlib.Path`]
        Paths to the generated ``*_full_array.npz`` products.

    Notes
    -----
    Product paths are resolved using
    :meth:`~grid_calibration.gui.workflow.product_io.ProductIO.expected_path`.
    After all products are written, the resulting list is registered in the
    active :class:`~grid_calibration.gui.session.CalibrationSession` with
    :meth:`~grid_calibration.gui.workflow.product_io.ProductIO.register`.
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
