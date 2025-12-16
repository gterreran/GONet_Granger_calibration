from .server import app
import threading, webview, logging
from GONet_Wizard.gui_launcher.api import WebviewAPI # type: ignore
from .logging_utils import configure_gui_logging 
from ..pipeline import make_output_dir
from ..products import discover_products

def run_app():
    # Configure logging interception BEFORE importing code that logs
    configure_gui_logging()

    # Suppress Flask/Werkzeug/Dash startup logging
    # logging.getLogger("werkzeug").setLevel(logging.ERROR)
    # logging.getLogger("dash.dash").setLevel(logging.ERROR)
    # import flask.cli
    # flask.cli.show_server_banner = lambda *args, **kwargs: None

    # Set up the app layout and callbacks
    from .layout import layout
    app.layout = layout

    from . import callbacks  # noqa: F401

    app.run_server(port=8050, debug=True, use_reloader=False)


def launch_extraction_gui(data_files, outdir=None):
    
    # Prepare output directory
    if outdir is None or outdir == "":
        outdir = "grid_calibration_output"
    app.server.config["output_dir"] = make_output_dir(outdir)

    # Make data_files available to the Dash server
    app.server.config["data_files"] = {"raw": data_files}
    app.server.config["data_files"].update(discover_products(data_files, outdir))

    # Start Dash server in a background thread
    dash_thread = threading.Thread(target=run_app)
    dash_thread.daemon = True
    dash_thread.start()

    # Give Dash a moment to initialize
    import time
    time.sleep(1)

    # Create and run the PyWebview window
    webview.create_window(
        "Grid Calibration Extraction GUI",
        "http://127.0.0.1:8050",
        width=1250,
        height=700,
        js_api=WebviewAPI()
    )

    webview.start()
