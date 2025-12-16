from flask import Flask
from dash import Dash

# Flask + Dash app
server = Flask("Grainger Grid Calibration Server")
app = Dash(server=server)
