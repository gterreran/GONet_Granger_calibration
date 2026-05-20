
# grid_calibration/__main__.py
"""
Command-line entry point for :mod:`grid_calibration`.

This module provides a lightweight command-line interface for launching the
grid-calibration GUI directly from a terminal using:

.. code-block:: bash

   python -m grid_calibration <images>

The CLI is intentionally minimal. Its responsibilities are:

- expanding filename patterns and glob expressions;
- filtering supported image extensions;
- parsing output-directory and debug options; and
- delegating execution to
  :func:`~grid_calibration.gui.app.launch_extraction_gui`.

The implementation attempts to reuse helper utilities from
:mod:`GONet_Wizard.commands.cli_core` when available. A small fallback
implementation is provided so the package remains importable and testable in
standalone development environments where :mod:`GONet_Wizard` is not installed.
"""

from __future__ import annotations

import argparse
import glob
from pathlib import Path
from typing import Callable, Sequence

try:
    from GONet_Wizard.commands.cli_core import ExpandFilenames, filter_by_ext  # type: ignore
except ModuleNotFoundError:
    class ExpandFilenames(argparse.Action):
        """
        Expand positional filename arguments into :class:`~pathlib.Path` objects.

        This lightweight fallback is used when
        :mod:`GONet_Wizard.commands.cli_core` is unavailable. It preserves the
        behavior needed by unit tests and local development environments without
        requiring the full :mod:`GONet_Wizard` package.
        """

        def __call__(self, parser, namespace, values, option_string=None):
            """
            Expand glob patterns into lists of :class:`~pathlib.Path` objects.

            Parameters
            ----------
            parser : :class:`argparse.ArgumentParser`
                Active argument parser.
            namespace : :class:`argparse.Namespace`
                Namespace object receiving parsed values.
            values : :class:`list`
                Raw filename or glob-pattern arguments.
            option_string : :class:`str`, optional
                Triggering option string supplied by :mod:`argparse`.

            Returns
            -------
            :data:`None`
                Expanded paths are written directly into ``namespace``.
            """
            expanded: list[Path] = []
            for value in values:
                matches = glob.glob(value)
                if matches:
                    expanded.extend(Path(match) for match in matches)
                else:
                    expanded.append(Path(value))
            setattr(namespace, self.dest, expanded)

    def filter_by_ext(files: Sequence[Path | str], extensions: Sequence[str]) -> list[Path]:
        """
        Filter files by extension.

        Parameters
        ----------
        files : sequence of :class:`~pathlib.Path` or :class:`str`
            Candidate file paths.
        extensions : sequence of :class:`str`
            Allowed filename extensions.

        Returns
        -------
        :class:`list`
            Filtered list of :class:`~pathlib.Path` objects whose suffix matches
            one of the allowed extensions.
        """
        allowed = {ext.lower() for ext in extensions}
        return [Path(file) for file in files if Path(file).suffix.lower() in allowed]


def build_parser() -> argparse.ArgumentParser:
    """
    Build the command-line argument parser.

    Returns
    -------
    :class:`argparse.ArgumentParser`
        Configured parser for the grid-calibration CLI.
    """
    parser = argparse.ArgumentParser(description="GONet Grid Calibration GUI Launcher")
    parser.add_argument(
        "file_list",
        nargs="*",
        action=ExpandFilenames,
        help="List of data files to process",
    )
    parser.add_argument(
        "--outdir",
        type=str,
        default=None,
        help="Output directory for processed files",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode with verbose logging",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    launch_gui: Callable[..., None] | None = None,
) -> None:
    """
    Launch the grid-calibration GUI from the command line.

    Parameters
    ----------
    argv : sequence of :class:`str`, optional
        Explicit command-line arguments. When omitted, arguments are read from
        :data:`sys.argv`.
    launch_gui : callable, optional
        Optional override for the GUI launcher function. This is primarily used
        by unit tests to avoid starting the real GUI runtime.

    Returns
    -------
    :data:`None`
        This function launches the GUI and does not return a value.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    files = filter_by_ext(args.file_list, [".jpg", ".jpeg", ".tiff", ".tif"])

    if launch_gui is None:
        from .gui.app import launch_extraction_gui

        launch_gui = launch_extraction_gui

    launch_gui(files, output_dir=args.outdir, debug=args.debug)


if __name__ == "__main__":
    main()
