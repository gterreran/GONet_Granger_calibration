# grid_calibration/docs/source/conf.py
import os
import sys
sys.path.insert(0, os.path.abspath(".."))

project = "GONet Calibration"
author = "Giacomo Terreran"
release = "0.1"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.mathjax",
]

templates_path = ["_templates"]
exclude_patterns = []

html_theme = "sphinx_rtd_theme"

html_static_path = ["_static"]

# Make math look nice
mathjax3_config = {
    "tex": {
        "inlineMath": [["\\(", "\\)"]],
        "displayMath": [["\\[", "\\]"]],
    }
}