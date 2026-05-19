# grid_calibration/__main__.py

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
        Lightweight fallback used when GONet_Wizard is not installed.

        The full project normally reuses GONet_Wizard's CLI helpers.  Keeping a
        small local fallback makes ``python -m grid_calibration --help`` and the
        unit tests importable in minimal development environments.
        """

        def __call__(self, parser, namespace, values, option_string=None):
            expanded: list[Path] = []
            for value in values:
                matches = glob.glob(value)
                if matches:
                    expanded.extend(Path(match) for match in matches)
                else:
                    expanded.append(Path(value))
            setattr(namespace, self.dest, expanded)

    def filter_by_ext(files: Sequence[Path | str], extensions: Sequence[str]) -> list[Path]:
        allowed = {ext.lower() for ext in extensions}
        return [Path(file) for file in files if Path(file).suffix.lower() in allowed]


def build_parser() -> argparse.ArgumentParser:
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
    parser = build_parser()
    args = parser.parse_args(argv)

    files = filter_by_ext(args.file_list, [".jpg", ".jpeg", ".tiff", ".tif"])

    if launch_gui is None:
        from .gui.app import launch_extraction_gui

        launch_gui = launch_extraction_gui

    launch_gui(files, output_dir=args.outdir, debug=args.debug)


if __name__ == "__main__":
    main()
