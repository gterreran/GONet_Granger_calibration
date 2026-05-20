Architecture Overview
=====================

The grid-calibration package is organized around a small number of explicit
contracts.  The goal is to keep each layer responsible for one kind of decision:
workflow structure, product storage, runtime state, GUI orchestration, or
step-local processing.

The main architectural pieces are:

:class:`~grid_calibration.gui.workflow.specs.PipelineStepSpec`
    Defines a step in the workflow.  A step specification is intentionally about
    workflow metadata only: key, label, order, mode, option style, and factories
    for lazily resolving processing/viewer/initializer callables.

:class:`~grid_calibration.gui.workflow.product_io.ProductIO`
    Owns the product contract for a step.  This includes file naming, expected
    paths, schema validation, saving, loading, encoding/decoding, cache handling,
    and session registration.  Product behavior is deliberately not stored on
    :class:`~grid_calibration.gui.workflow.specs.PipelineStepSpec`.

:class:`~grid_calibration.gui.session.CalibrationSession`
    Stores runtime state: input files, output directory, and currently registered
    products.  It does not know product schemas or naming rules.  It delegates
    discovery and IO to the workflow/product layer.

:mod:`~grid_calibration.gui.workflow.registry`
    Imports and validates all step packages, builds ordered workflow lists, and
    creates enable/clickability rules used by the GUI.

``Step`` packages
    Self-contained step packages.  Each step exposes a ``pipeline_step`` and a
    ``product_io`` object from ``spec.py``.  Larger steps may also expose a
    ``processing`` package instead of a single ``processing.py`` module.

:mod:`~grid_calibration.gui.callbacks` modules
    Dash callback orchestration.  The callbacks connect user actions to session
    updates, step execution, selected-step viewing, product refresh, logging, and
    interactive-step state.

Design Principles
-----------------

Single source of truth
~~~~~~~~~~~~~~~~~~~~~~

Product-related decisions live in :class:`~grid_calibration.gui.workflow.product_io.ProductIO`.  Workflow-order decisions live
in :mod:`~grid_calibration.gui.workflow.registry`.  Runtime state lives in :class:`~grid_calibration.gui.session.CalibrationSession`.  This
separation prevents subtle drift where multiple modules independently decide how
a product should be named, loaded, validated, or considered available.

Stable public step APIs
~~~~~~~~~~~~~~~~~~~~~~~

The GUI and registry should not care whether a step implements its processing
logic as ``processing.py`` or as ``processing/``.  The public import surface is
preserved by exporting the same functions from ``processing/__init__.py``.  This
lets large algorithm-heavy modules be split internally without forcing changes in
step specs, callbacks, or tests.

Lazy imports
~~~~~~~~~~~~

Step specs use factories for processing, plotting, and interactive
initialization callables.  This keeps registry import cheap and reduces circular
import pressure.  The registry can inspect step metadata without immediately
importing heavy plotting, Dash, scipy, or processing code.

Products, not transient objects, drive the GUI
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The GUI state is derived primarily from products registered in the session.
A completed step is represented by a product path or paths.  Viewers load from
registered products.  Buttons are enabled when prerequisites exist.  Rows are
clickable when their own product exists.

Dependency-aware startup
~~~~~~~~~~~~~~~~~~~~~~~~

At startup and refresh, product discovery follows the workflow order.  Once a
required upstream product is missing or incomplete, downstream products are not
registered even if their files exist on disk.  This protects the GUI from stale
or inconsistent output directories produced during debugging.

High-Level Flow
---------------

A typical run follows this pattern:

#. The CLI or server startup creates a :class:`CalibrationSession` from raw input
   files and an output directory.
#. The session asks the workflow/product layer to discover existing products.
#. The Dash layout is built from the session products and ordered step registry.
#. User actions trigger callbacks.
#. Batch callbacks run a step pipeline function, save/register products through
   :class:`~grid_calibration.gui.workflow.product_io.ProductIO`, refresh the session, and update the GUI.
#. Viewer callbacks use the selected step and dropdown value to load the
   appropriate product and render the right-hand panel.
#. Interactive steps initialize temporary UI state and later save a product once
   the user confirms the result.

The result is a workflow where the file system, the session state, and the GUI
controls all follow the same product contract.
