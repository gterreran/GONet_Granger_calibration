# grid_calibration/docs/source/conf.py
import sys
from pathlib import Path

PACKAGE_PARENT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PACKAGE_PARENT))

project = "GONet Calibration"
author = "Giacomo Terreran"
release = "0.9"

master_doc = 'index'

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
]

autodoc_typehints = "description"
autosummary_generate = True

templates_path = ["_templates"]
exclude_patterns = []

html_theme = "sphinx_rtd_theme"

# html_static_path = ["_static"]

# Make math look nice
mathjax3_config = {
    "tex": {
        "inlineMath": [["\\(", "\\)"]],
        "displayMath": [["\\[", "\\]"]],
    }
}