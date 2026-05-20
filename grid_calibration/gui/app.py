# grid_calibration/gui/app.py
"""
Dash and pywebview launch helpers for the grid-calibration GUI.

This module is the runtime entry point for the interactive extraction GUI.  It
connects three pieces that are intentionally kept separate elsewhere in the
package:

* the global Dash application object from :mod:`~grid_calibration.gui.server`,
* the runtime :class:`~grid_calibration.gui.session.CalibrationSession`, and
* the pywebview desktop window used to display the Dash application.

The module does not define layout components or callbacks directly.  Instead,
:func:`run_app` builds the layout and imports the callback package after logging
has been configured, while :func:`launch_extraction_gui` prepares the session and
starts the desktop window.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

import webview
from GONet_Wizard.ui.api import WebviewAPI  # type: ignore

from .logging_utils import configure_gui_logging, silence_server_loggers
from .server import app
from .session import CalibrationSession


def run_app(debug: bool = False) -> None:
    """
    Configure and run the Dash server for the calibration GUI.

    Logging is configured before the layout and callbacks are imported so that
    import-time and callback-time messages are captured by the GUI log window.
    Callback modules are imported for their registration side effects after the
    layout has been attached to the global Dash app.

    Parameters
    ----------
    debug : :class:`bool`, optional
        If ``True``, run Dash in debug mode and capture debug-level log records.
        If ``False``, reduce Flask/Werkzeug/Dash startup chatter and capture
        info-level application messages.

    Returns
    -------
    :class:`None`
        The function blocks while the Dash development server is running.
    """
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


def launch_extraction_gui(
    data_files: list[Path] | list[str],
    output_dir: str | Path | None = None,
    debug: bool = False,
) -> None:
    """
    Launch the desktop extraction GUI for a set of raw calibration images.

    The function creates the output directory, initializes a
    :class:`~grid_calibration.gui.session.CalibrationSession`, stores it in the
    Flask configuration attached to :data:`~grid_calibration.gui.server.app`,
    starts the Dash server in a daemon thread, and opens a pywebview window
    pointed at the local Dash URL.

    Parameters
    ----------
    data_files : list[path-like]
        Raw image files for the calibration session.  These are passed to
        :meth:`~grid_calibration.gui.session.CalibrationSession.from_inputs`,
        which also performs dependency-aware product discovery.
    output_dir : path-like or :class:`None`, optional
        Directory where products are read and written.  When omitted or empty,
        ``"grid_calibration_output"`` is used.
    debug : :class:`bool`, optional
        If ``True``, run Dash with debug logging and debug server behavior.

    Returns
    -------
    :class:`None`
        The function blocks once :func:`webview.start` enters the desktop event
        loop.
    """
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
