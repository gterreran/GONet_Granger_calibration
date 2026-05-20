# grid_calibration/cli.py
"""
Command-line interface for :mod:`grid_calibration`.

This module implements the standalone ``grid-calibration`` command.  It is kept
separate from :mod:`grid_calibration.__main__` so the same parser and execution
logic can be used by both:

.. code-block:: bash

   grid-calibration path/to/images/*.jpg --outdir grid_calibration_output --debug

and:

.. code-block:: bash

   python -m grid_calibration path/to/images/*.jpg --outdir grid_calibration_output --debug

The CLI intentionally launches the main calibration workflow directly rather
than introducing subcommands.  The package currently has one primary user-facing
operation: opening the extraction/calibration GUI for a set of input images.
"""

from __future__ import annotations

import argparse
import glob
from pathlib import Path
from typing import Callable, Sequence


SUPPORTED_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".tif", ".tiff")
"""
Image extensions accepted by the command-line launcher.
"""


try:
    from GONet_Wizard.commands.cli_core import ExpandFilenames, filter_by_ext  # type: ignore
except ModuleNotFoundError:
    class ExpandFilenames(argparse.Action):
        """
        Expand positional filename and glob arguments into paths.

        This fallback keeps :mod:`grid_calibration` runnable in standalone
        environments where :mod:`GONet_Wizard.commands.cli_core` is not
        importable.

        Parameters
        ----------
        parser : :class:`argparse.ArgumentParser`
            Active parser.
        namespace : :class:`argparse.Namespace`
            Namespace receiving parsed values.
        values : sequence of :class:`str`
            Raw filenames or glob patterns.
        option_string : :class:`str`, optional
            Triggering option string supplied by :mod:`argparse`.

        Returns
        -------
        :data:`None`
            Expanded paths are written into ``namespace``.
        """

        def __call__(
            self,
            parser: argparse.ArgumentParser,
            namespace: argparse.Namespace,
            values: Sequence[str],
            option_string: str | None = None,
        ) -> None:
            """
            Expand input filenames and glob patterns.

            Parameters
            ----------
            parser : :class:`argparse.ArgumentParser`
                Active parser.
            namespace : :class:`argparse.Namespace`
                Namespace receiving parsed values.
            values : sequence of :class:`str`
                Raw filenames or glob patterns.
            option_string : :class:`str`, optional
                Triggering option string supplied by :mod:`argparse`.

            Returns
            -------
            :data:`None`
                Expanded paths are written into ``namespace``.
            """
            expanded: list[Path] = []

            for value in values:
                matches = glob.glob(value)

                if matches:
                    expanded.extend(Path(match) for match in matches)
                else:
                    expanded.append(Path(value))

            setattr(namespace, self.dest, expanded)

    def filter_by_ext(
        files: Sequence[Path | str],
        extensions: Sequence[str],
    ) -> list[Path]:
        """
        Filter candidate paths by filename extension.

        Parameters
        ----------
        files : sequence of :class:`~pathlib.Path` or :class:`str`
            Candidate input paths.
        extensions : sequence of :class:`str`
            Accepted filename extensions.

        Returns
        -------
        :class:`list` [:class:`~pathlib.Path`]
            Paths whose suffix matches one of ``extensions``.
        """
        allowed = {ext.lower() for ext in extensions}
        return [
            Path(file)
            for file in files
            if Path(file).suffix.lower() in allowed
        ]


def build_parser() -> argparse.ArgumentParser:
    """
    Build the command-line argument parser.

    Returns
    -------
    :class:`argparse.ArgumentParser`
        Configured parser for the standalone grid-calibration launcher.
    """
    parser = argparse.ArgumentParser(
        prog="grid-calibration",
        description="Launch the GONet grid-calibration GUI.",
    )

    parser.add_argument(
        "file_list",
        nargs="*",
        action=ExpandFilenames,
        help="Input calibration image files or glob patterns.",
    )

    parser.add_argument(
        "--outdir",
        type=str,
        default=None,
        help=(
            "Output directory for generated calibration products. "
            "Defaults to 'grid_calibration_output'."
        ),
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable verbose debug logging and Dash debug mode.",
    )

    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    launch_gui: Callable[..., None] | None = None,
) -> None:
    """
    Parse command-line arguments and launch the calibration GUI.

    Parameters
    ----------
    argv : sequence of :class:`str`, optional
        Explicit command-line arguments.  When omitted, arguments are read from
        :data:`sys.argv`.
    launch_gui : callable, optional
        Optional launcher override.  This is useful for tests and for callers
        that want to verify argument parsing without starting the GUI runtime.

    Returns
    -------
    :data:`None`
        The function launches the GUI and does not return a value.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    files = filter_by_ext(args.file_list, SUPPORTED_IMAGE_EXTENSIONS)

    if not files:
        parser.error(
            "No supported image files were provided. "
            f"Supported extensions: {', '.join(SUPPORTED_IMAGE_EXTENSIONS)}"
        )

    if launch_gui is None:
        from . import launch_grid_calibration

        launch_gui = launch_grid_calibration

    launch_gui(
        files=files,
        output_dir=args.outdir,
        debug=args.debug,
    )
