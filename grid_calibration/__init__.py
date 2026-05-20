# grid_calibration/__init__.py
"""
Top-level package for :mod:`grid_calibration`.

The package provides a workflow-driven system for detecting, grouping,
bootstrapping, and modeling the printed polar calibration grid used in GONet
fisheye images.

The primary public launch API is :func:`launch_grid_calibration`.  This function
is intentionally small and stable so external tools, such as GONet Wizard, can
launch the calibration GUI without shelling out to the command-line interface.

The package can also be launched from the command line with either:

.. code-block:: bash

   grid-calibration <images>

or:

.. code-block:: bash

   python -m grid_calibration <images>
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence


def launch_grid_calibration(
    files: Sequence[str | Path],
    output_dir: str | Path | None = None,
    debug: bool = False,
) -> None:
    """
    Launch the grid-calibration GUI.

    This is the stable package-level API intended for external callers.  It is
    especially useful for optional integration from GONet Wizard, where the
    Wizard can import this function and provide the selected image files and
    output directory directly.

    Parameters
    ----------
    files : sequence of :class:`str` or :class:`~pathlib.Path`
        Input calibration image files.
    output_dir : :class:`str` or :class:`~pathlib.Path`, optional
        Directory where generated products are read and written.  When omitted,
        the GUI launcher uses ``"grid_calibration_output"``.
    debug : :class:`bool`, optional
        If ``True``, enable verbose GUI logging and Dash debug behavior.

    Returns
    -------
    :data:`None`
        The function launches the GUI and does not return a value.
    """
    from .gui.app import launch_extraction_gui

    launch_extraction_gui(
        data_files=[Path(file) for file in files],
        output_dir=output_dir,
        debug=debug,
    )


__all__ = [
    "launch_grid_calibration",
]
