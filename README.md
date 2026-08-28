# Grid Calibration

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![Tests](https://github.com/gterreran/GONet_Granger_calibration/actions/workflows/tests.yml/badge.svg?branch=dev)](https://github.com/gterreran/GONet_Granger_calibration/actions/workflows/tests.yml)
[![Docs](https://github.com/gterreran/GONet_Granger_calibration/actions/workflows/docs.yml/badge.svg?branch=master)](https://github.com/gterreran/GONet_Granger_calibration/actions/workflows/docs.yml)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://gterreran.github.io/GONet_Granger_calibration/)

Grid Calibration is an interactive calibration pipeline for GONet fisheye images of circular polar calibration grids.

The package provides:

- a Dash/pywebview GUI for guided calibration,
- staged processing products for restartable workflows,
- interactive center selection and nominal-grid validation,
- bootstrapped dense calibration correspondences,
- final distortion-model fitting diagnostics,
- a public pixel ↔ angular-coordinate transform API,
- and a portable no-pickle ``*_calibration.npz`` artifact for downstream tools.

## Documentation

The main documentation is hosted on GitHub Pages:

[Documentation](https://gterreran.github.io/GONet_Granger_calibration/)

Recommended starting points:

- **User walkthrough**: end-to-end usage guide
- **Pipeline walkthrough**: step-by-step explanation of each calibration stage
- **API reference**: developer-facing module and function documentation

## Installation

From the repository root:

```bash
pip install -e .
```

For development and documentation work:

```bash
pip install -e ".[dev]"
```

## Launching the GUI

After installation:

```bash
grid-calibration path/to/images/*.jpg --outdir grid_calibration_output --debug
```

The legacy module entry point is also supported:

```bash
python -m grid_calibration path/to/images/*.jpg --outdir grid_calibration_output --debug
```

## Using a Finished Calibration

The final modeling step keeps the existing ``*_modeling_results.npz`` workflow
product and also writes a smaller ``*_calibration.npz`` interchange artifact.
The latter contains only plain NumPy-compatible data and can be loaded with
``allow_pickle=False``. Artifact format version 2 records the independent radial
and tangential harmonic configuration plus the fitted axisymmetric tanh twist;
version-1 artifacts remain readable through ``load_calibration()``.

```python
from grid_calibration import load_calibration

calibration = load_calibration("grid_calibration_output/camera_calibration.npz")

# Nominal angular polar coordinates -> image pixels
x, y = calibration.angle_to_pixel(45.0, 120.0)

# Image pixels -> nominal angular polar coordinates
r_deg, theta_deg = calibration.pixel_to_angle(x, y)
```

The module-level ``angle_to_pixel()`` and ``pixel_to_angle()`` functions are
also available for callers that prefer a functional API.

## Development

Run the test suite with:

```bash
python -m pytest grid_calibration/tests
```

Optional real-data tests are skipped unless the required environment variables are set.

## GitHub Actions

This repository uses two main CI workflows:

- `tests.yml`: runs tests on pushes to `dev` and pull requests targeting `dev` or `master`
- `docs.yml`: builds and deploys documentation to GitHub Pages on pushes to `master`

Before the first documentation deployment, enable GitHub Pages in the repository settings and set the Pages source to **GitHub Actions**.
