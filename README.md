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
- and final distortion-model fitting diagnostics.

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
