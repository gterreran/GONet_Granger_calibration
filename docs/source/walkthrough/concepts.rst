Core Concepts
=============

This page introduces the core ideas behind the calibration pipeline.

Pipeline Philosophy
-------------------

The calibration workflow is intentionally divided into multiple stages.

Each stage:

- consumes one or more products,
- produces a new product,
- and isolates one conceptual task.

This design improves:

- debuggability,
- reproducibility,
- recovery from failures,
- and interactive validation.

Workflow Overview
-----------------

The full workflow is:

.. code-block:: text

    raw image
        ↓
    full array
        ↓
    grid points
        ↓
    averaged grid
        ↓
    unwrapped grid
        ↓
    nominal grid
        ↓
    bootstrapping
        ↓
    modeling results

Each stage is documented individually in the pipeline walkthrough.

Coordinate Systems
------------------

The pipeline operates in several coordinate systems.

Image Coordinates
~~~~~~~~~~~~~~~~~

Standard image-space pixel coordinates:

.. code-block:: text

    (x, y)

These are used directly in the raw images.

Polar Coordinates
~~~~~~~~~~~~~~~~~

The circular calibration grid is naturally represented in polar coordinates:

.. code-block:: text

    (theta, r)

where:

- ``theta`` is the angular position,
- ``r`` is the radial distance from the selected center.

Unwrapped Coordinates
~~~~~~~~~~~~~~~~~~~~~

The unwrapped representation converts the circular grid into a rectangular
representation in:

.. code-block:: text

    theta vs radius

This greatly simplifies ring and spoke assignment.

Nominal Coordinates
~~~~~~~~~~~~~~~~~~~

Nominal coordinates describe the *ideal* angular calibration grid.

These are the target values assigned during the nominal-grid step.

Products
--------

Every pipeline step produces a *product*.

Products are cached intermediate files stored on disk.

Examples:

.. code-block:: text

    *_grid_points.npz
    *_nominal_grid.npz
    *_modeling_results.npz

Products allow:

- resuming workflows,
- skipping completed steps,
- debugging intermediate results,
- rebuilding only part of the pipeline.

Singleton vs Per-Input Products
-------------------------------

The workflow uses two product types.

Per-Input Products
~~~~~~~~~~~~~~~~~~

One product per input image.

Examples:

- full-array
- grid-points

Singleton Products
~~~~~~~~~~~~~~~~~~

One shared product for the entire session.

Examples:

- averaged-grid
- nominal-grid
- modeling-results

Interactive vs Batch Steps
--------------------------

Batch Steps
~~~~~~~~~~~

Fully automated processing stages.

Examples:

- full-array generation,
- grid-point detection,
- averaging.

Interactive Steps
~~~~~~~~~~~~~~~~~

Require user validation or interaction.

Examples:

- center selection,
- nominal assignment validation,
- modeling parameter adjustment.

Session Recovery
----------------

The session system automatically discovers existing products at startup.

This allows workflows to resume automatically without recomputing all steps.

The workflow also detects stale downstream products and prevents inconsistent
states from being loaded.

Why the Workflow is Staged
--------------------------

The staged architecture is extremely important.

It allows users to:

- inspect intermediate results,
- diagnose problems early,
- rerun only problematic stages,
- adjust parameters incrementally,
- and understand where failures occur.

This is especially important for scientific calibration workflows where
validation and interpretability are critical.