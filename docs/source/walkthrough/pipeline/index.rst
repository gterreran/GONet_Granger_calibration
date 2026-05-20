Pipeline Walkthrough
====================

The calibration workflow is organized as a sequential pipeline of processing
steps.

Each step:

- consumes one or more upstream products,
- performs one conceptual task,
- produces a new product,
- and exposes its output through the GUI.

Pipeline Overview
-----------------

The complete workflow is:

.. code-block:: text

    Raw image
        ↓
    Full array
        ↓
    Grid points
        ↓
    Averaged grid
        ↓
    Unwrapped grid
        ↓
    Nominal grid
        ↓
    Bootstrapping grid
        ↓
    Modeling results

The workflow gradually transforms raw calibration images into a fully fitted
fisheye distortion model.

Design Philosophy
-----------------

The workflow is intentionally divided into multiple stages instead of performing
a single monolithic calibration pass.

This design provides several important advantages:

- intermediate validation,
- easier debugging,
- incremental recomputation,
- cached reusable products,
- interactive correction steps,
- and improved interpretability.

At every stage, users can inspect the generated products before proceeding to
the next step.

Interactive vs Batch Steps
--------------------------

Some steps are fully automated.

Examples include:

- full-array generation,
- grid-point detection,
- averaging.

Other steps require user interaction.

Examples include:

- center selection,
- nominal assignment validation,
- fit inspection.

The GUI dynamically exposes the required controls for each interactive stage.

Pipeline Products
-----------------

Each step produces a persistent product stored on disk.

Products allow:

- restarting sessions,
- revisiting previous results,
- recomputing only selected stages,
- and protecting against accidental data loss.

The :doc:`../products` page describes the product system in detail.

Pipeline Pages
--------------

.. toctree::
   :maxdepth: 1

   raw_image
   full_array
   grid_points
   averaged_grid
   unwrapped_grid
   nominal_grid
   bootstrapping_grid
   modeling_results