
# grid_calibration/__init__.py
"""
Top-level package for the :mod:`grid_calibration` project.

The package provides a workflow-driven system for detecting, grouping,
bootstrapping, and modeling the printed polar calibration grid used in GONet
fisheye images.

The project is organized around several major subsystems:

``grid_calibration.gui``
    Dash-based graphical user interface and workflow orchestration layer.

``grid_calibration.gui.workflow``
    Product discovery, step specifications, registry construction, and session
    management infrastructure.

``grid_calibration.gui.steps``
    Self-contained processing and visualization packages for each calibration
    step.

``grid_calibration.errors``
    Package-specific exception hierarchy.

The package can be launched directly from the command line with:

.. code-block:: bash

   python -m grid_calibration <images>

which invokes :func:`grid_calibration.__main__.main`.
"""
