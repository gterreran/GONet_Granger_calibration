Architecture
============

This section documents the internal architecture of the grid-calibration GUI and
processing pipeline.  It is meant for developers who need to extend the package,
add a new workflow step, debug product discovery, or understand how the Dash GUI
is connected to the processing code.

The API reference generated from docstrings should describe individual modules,
classes, and functions.  These pages explain the higher-level contracts between
those pieces: what owns what, which modules are intentionally lightweight, which
objects are runtime state, and where hidden mechanisms such as lazy imports,
product discovery, callback orchestration, and stale-product protection live.

.. toctree::
   :maxdepth: 2
   :caption: Architecture topics

   overview
   workflow_registry
   sessions_and_products
   step_packages
   gui_callbacks
   processing_packages
   testing
