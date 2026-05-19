# grid_calibration/gui/app.py
# grid_calibration_extraction/gui/app.py

from .server import app
import threading, webview, logging
from GONet_Wizard.ui.api import WebviewAPI # type: ignore
from .logging_utils import configure_gui_logging, silence_server_loggers 
from .session import CalibrationSession
from pathlib import Path

def run_app(debug=False):
    # Configure logging interception BEFORE importing code that logs.
    level = logging.DEBUG if debug else logging.INFO
    configure_gui_logging(level=level, clear_existing=True)

    if not debug:
        silence_server_loggers()
        import flask.cli
        flask.cli.show_server_banner = lambda *args, **kwargs: None

    # Set up the app layout and callbacks
    from .layout import build_layout
    app.layout = build_layout()

    from . import callbacks  # noqa: F401

    app.run_server(port=8050, debug=debug, use_reloader=False)


def launch_extraction_gui(data_files, output_dir=None, debug=False):
    if output_dir is None or output_dir == "":
        output_dir = "grid_calibration_output"

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    app.server.config["session"] = CalibrationSession.from_inputs(
        raw_files=data_files,
        output_dir=output_dir,
    )

    # Start Dash server in a background thread
    dash_thread = threading.Thread(
        target=run_app,
        kwargs={"debug": debug}
    )
    dash_thread.daemon = True
    dash_thread.start()

    # Give Dash a moment to initialize
    import time
    time.sleep(1)

    # Create and run the PyWebview window
    webview.create_window(
        "Grid Calibration Extraction GUI",
        "http://127.0.0.1:8050",
        width=2000,
        height=1500,
        js_api=WebviewAPI()
    )

    webview.start()
