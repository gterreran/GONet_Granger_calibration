import argparse
from GONet_Wizard.commands.cli_core import ExpandFilenames, filter_by_ext # type: ignore
from .gui.app import launch_extraction_gui

def main():
    parser = argparse.ArgumentParser(description="GONet Grid Calibration GUI Launcher")
    parser.add_argument(
        "file_list", nargs="*", action=ExpandFilenames, help="List of data files to process"
    )
    parser.add_argument(
        "--outdir", type=str, default=None, help="Output directory for processed files"
    )
    args = parser.parse_args()

    files = filter_by_ext(args.file_list, [".jpg", ".tiff"])

    launch_extraction_gui(files, outdir=args.outdir)

if __name__ == "__main__":
    main()