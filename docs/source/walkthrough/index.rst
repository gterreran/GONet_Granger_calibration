Grid Calibration Walkthrough
============================

Welcome to the Grid Calibration walkthrough documentation.

This guide explains how to use the grid calibration pipeline from beginning to
end, including:

- preparing calibration images,
- running the GUI,
- understanding each pipeline step,
- interpreting outputs,
- troubleshooting common problems,
- rebuilding products,
- and understanding the calibration model.

This walkthrough is intended for *users* of the software. It focuses on
workflow, concepts, interpretation, and practical usage rather than internal
implementation details.

For developer-oriented API documentation, see the main API reference.

Overview
--------

The grid calibration package calibrates fisheye camera systems using images of
a known circular angular calibration grid.

The workflow progressively transforms raw images into:

- detected grid intersections,
- nominal angular assignments,
- dense calibration correspondences,
- and finally a fitted distortion model.

The pipeline combines:

- automated batch-processing stages,
- interactive validation steps,
- cached intermediate products,
- and distortion-model fitting.

Installation
------------

The package is typically run directly as a Python module from the source tree.

Example:

.. code-block:: bash

    python -m grid_calibration *.jpg --debug

Requirements
~~~~~~~~~~~~

The package requires:

- Python 3.10+
- NumPy
- SciPy
- Plotly
- Dash
- scikit-image
- Matplotlib
- GONet_Wizard

Quickstart
----------

1. Launch the GUI:

   .. code-block:: bash

       python -m grid_calibration path/to/images/*.jpg --debug

2. Run the steps from top to bottom:

   - Build full arrays
   - Detect grid points
   - Average grids
   - Unwrap grid
   - Nominal assignment
   - Bootstrapping
   - Modeling

3. Inspect the outputs at every stage.

4. Use the interactive steps to:

   - select the grid center,
   - validate nominal assignments,
   - adjust problematic regions if needed.

5. Run the modeling step to obtain the final distortion model.

6. Inspect residuals and fit quality.

Documentation Structure
-----------------------

.. toctree::
   :maxdepth: 2

   concepts
   gui_interface
   pipeline/index
   products

Typical Workflow Duration
-------------------------

Typical runtimes depend on:

- image resolution,
- number of calibration images,
- CPU performance,
- fitting settings.

A complete calibration session usually takes:

- a few seconds for early processing steps,
- a few minutes for dense bootstrapping and modeling.

Interactive steps typically dominate user time.

What Makes a Good Calibration?
------------------------------

A successful calibration generally has:

- dense and uniform grid-point detections,
- correct nominal ring/spoke assignments,
- smooth residual maps,
- low RMS residuals,
- no large coherent residual structures.

The later walkthrough sections explain how to recognize both good and bad
results.