from .server import app
import threading, webview, logging
from GONet_Wizard.ui.api import WebviewAPI # type: ignore
from .logging_utils import configure_gui_logging 
from ..pipeline import make_output_dir
from ..products import discover_products
from .session import CalibrationSession

def run_app(debug=False):
    # Configure logging interception BEFORE importing code that logs
    configure_gui_logging()

    if not debug:
        # Suppress Flask/Werkzeug/Dash startup logging
        logging.getLogger("werkzeug").setLevel(logging.ERROR)
        logging.getLogger("dash.dash").setLevel(logging.ERROR)
        import flask.cli
        flask.cli.show_server_banner = lambda *args, **kwargs: None

    # Set up the app layout and callbacks
    from .layout import build_layout
    app.layout = build_layout()

    from . import callbacks  # noqa: F401

    app.run_server(port=8050, debug=debug, use_reloader=False)


def launch_extraction_gui(data_files, outdir=None, debug=False):
    if outdir is None or outdir == "":
        outdir = "grid_calibration_output"

    output_dir = make_output_dir(outdir)

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
