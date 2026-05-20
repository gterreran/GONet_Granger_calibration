# grid_calibration/gui/server.py
"""
Global Flask and Dash application objects for the calibration GUI.

The GUI uses a single :class:`flask.Flask` server and a single
:class:`dash.Dash` application object.  Other modules import
:data:`app` to attach a layout, register callbacks, or access the underlying
Flask configuration dictionary where the active
:class:`~grid_calibration.gui.session.CalibrationSession` is stored.
"""

from __future__ import annotations

from pathlib import Path

from dash import Dash
from flask import Flask

# Flask + Dash app
server = Flask("Grainger Grid Calibration Server")
""":class:`flask.Flask`: Flask server backing the Dash application."""

ASSETS = Path(__file__).resolve().parent / "assets"
""":class:`pathlib.Path`: Directory containing Dash CSS/static assets."""

app = Dash(server=server, assets_folder=str(ASSETS), suppress_callback_exceptions=True)
""":class:`dash.Dash`: Global Dash application used by the GUI."""
