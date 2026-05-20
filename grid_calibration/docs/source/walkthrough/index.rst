Grid Calibration Walkthrough
============================

Welcome to the Grid Calibration walkthrough documentation.

This guide explains how to use the grid calibration pipeline from beginning to
end, including:

- preparing calibration images,
- launching the GUI,
- understanding each pipeline step,
- interpreting outputs,
- troubleshooting common problems,
- rebuilding products,
- and understanding the final distortion model.

This walkthrough is intended for *users* of the software. It focuses on
workflow, interpretation, and practical usage rather than implementation
internals.

For developer-oriented API documentation, see the main API reference.

Overview
--------

The grid calibration package calibrates fisheye camera systems using images of
known circular angular calibration grids.

The workflow progressively transforms raw calibration images into:

- detected grid intersections,
- nominal polar-grid assignments,
- dense bootstrapped calibration correspondences,
- and finally a fitted distortion model.

The package combines:

- automated processing stages,
- interactive validation steps,
- persistent intermediate products,
- and distortion-model fitting.

Installation
------------

The project uses a modern ``pyproject.toml``-based installation.

Installation
~~~~~~~~~~~~~~~~~~~~~

From the repository root:

.. code-block:: bash

    pip install .

This installs the standalone command-line launcher:

.. code-block:: bash

    grid-calibration

Requirements
~~~~~~~~~~~~

The package requires:

- Python 3.10+
- NumPy
- SciPy
- Plotly
- Dash
- scikit-image
- pywebview
- Matplotlib
- GONet_Wizard

Launching the Workflow
----------------------

After installation, the recommended launch method is:

.. code-block:: bash

    grid-calibration path/to/images/*.jpg --debug

Example:

.. code-block:: bash

    grid-calibration ../data/calibration/*.jpg \
        --outdir grid_calibration_output \
        --debug

The command-line interface automatically:

- expands glob patterns,
- filters supported image extensions,
- initializes the calibration session,
- discovers existing products,
- launches the Dash server,
- and opens the desktop GUI.

Legacy Module Launch
--------------------

The package can still be launched using:

.. code-block:: bash

    python -m grid_calibration path/to/images/*.jpg --debug

Internally, this delegates to the same CLI implementation used by the
``grid-calibration`` executable.

Quickstart
----------

1. Launch the GUI:

   .. code-block:: bash

       grid-calibration *.jpg --debug

2. Run the steps from top to bottom:

   - Build full arrays
   - Detect grid points
   - Average grids
   - Unwrap grid
   - Identify nominal grid
   - Bootstrap the grid
   - Fit the distortion model

3. Inspect the outputs at every stage.

4. Use the interactive steps to:

   - select the grid center,
   - validate nominal assignments,
   - adjust problematic structures if needed.

5. Run the modeling step to obtain the final distortion model.

6. Inspect the residual diagnostics.

Documentation Structure
-----------------------

.. toctree::
   :maxdepth: 2

   concepts
   gui_interface
   products
   troubleshooting
   advanced
   pipeline/index

Typical Workflow Duration
-------------------------

Typical runtimes depend on:

- image resolution,
- number of calibration images,
- CPU performance,
- fitting settings,
- and multiprocessing configuration.

A complete calibration session usually takes:

- a few seconds for early processing stages,
- and a few minutes for dense bootstrapping and modeling.

Interactive stages typically dominate user time.

What Makes a Good Calibration?
------------------------------

A successful calibration generally has:

- dense and uniform grid-point detections,
- correct nominal ring and spoke assignments,
- smooth residual maps,
- low RMS residuals,
- and no large coherent residual structures.

The later walkthrough sections explain how to recognize both good and bad
results.

Future Integration with GONet Wizard
------------------------------------

Although the project is distributed as an independent package with its own
repository, it is intentionally designed to integrate cleanly with
:mod:`GONet_Wizard`.

The package exposes a stable launcher API:

.. code-block:: python

    from grid_calibration import launch_grid_calibration

allowing external tools to launch the calibration workflow directly from Python
without spawning subprocesses.
