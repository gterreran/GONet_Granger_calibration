from flask import Flask
from dash import Dash
from pathlib import Path

# Flask + Dash app
server = Flask("Grainger Grid Calibration Server")

ASSETS = Path(__file__).resolve().parent / "assets"
app = Dash(server=server, assets_folder=str(ASSETS))
