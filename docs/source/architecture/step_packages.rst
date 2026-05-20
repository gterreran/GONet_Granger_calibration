Step Packages
=============

Each workflow step is implemented as a self-contained package under
``grid_calibration/gui/steps``.  A step package should contain everything needed
to define, run, visualize, and optionally interact with one stage of the
calibration workflow.

Typical Layout
--------------

A typical step package looks like this:

.. code-block:: text

   gui/steps/<step_name>/
   ├── __init__.py
   ├── spec.py
   ├── processing.py      # or processing/
   ├── plotting.py
   ├── params.py          # optional
   ├── callbacks.py       # optional
   └── keys.py            # optional

``spec.py``
    Defines ``pipeline_step`` and ``product_io``.  This is the public contract
    consumed by the registry.

``processing.py`` or ``processing/``
    Implements the step's computational logic.  Small steps may remain as a
    single module.  Large algorithm-heavy steps may be split into a package.

``plotting.py``
    Provides :func:`viewer_factory` viewer functions used by the right-hand GUI panel.

``params.py``
    Holds default parameters and parameter helper functions.  Keeping defaults
    here avoids scattering magic numbers across callbacks and processing code.

``callbacks.py``
    Optional Dash callbacks for step-specific interactive behavior.

``keys.py``
    Optional shared string constants for product keys or payload fields.

Public Exports
--------------

Every step package should expose at least the following from ``__init__.py``:

.. code-block:: python

   from .spec import pipeline_step, product_io

The registry depends on this convention.  Internal modules can be reorganized as
needed as long as these two objects remain available.

Spec Files
----------

The spec file is the contract between a step and the generic workflow system.  It
should define:

* a :class:`~grid_calibration.gui.workflow.product_io.ProductIO` object;
* lazy factories for viewer, pipeline, and optional interactive initializer;
* a :class:`~grid_calibration.gui.workflow.specs.PipelineStepSpec` object.

The spec file should avoid importing heavy implementation modules directly at top
level.  Prefer local imports inside factories.  This keeps registry import cheap
and avoids circular imports.

Example pattern:

.. code-block:: python

   def viewer_factory():
       from .plotting import plot_product
       return plot_product

   def pipeline_factory():
       from .processing import run_step
       return run_step

   product_io = ProductIO(...)

   pipeline_step = PipelineStepSpec.from_dict(
       {
           "key": "example-step",
           "label": "Example step",
           "order": 3,
           "mode": "batch",
           "product_kind": product_io.kind,
       }
   )

Batch and Interactive Steps
---------------------------

A batch step runs from inputs to a product with no required user intervention.
Its processing function should save/register products through :class:`~grid_calibration.gui.workflow.product_io.ProductIO` and
return enough information for the orchestration callbacks to refresh the GUI.

An interactive step has an initialization function that prepares temporary UI
state.  The user then modifies or confirms that state through step-specific
callbacks.  The final confirmation saves/registers the product.

The important distinction is that both step types still produce products through
the same product system.  Interactive state is temporary; products are the stable
workflow outputs.

Parameter Defaults
------------------

Step-specific defaults should live in ``params.py``.  This keeps callbacks,
layouts, and processing functions from each defining their own defaults.  It also
makes future documentation and GUI parameter panels much easier to maintain.

When possible, parameter dictionaries should be treated as explicit inputs to
processing functions rather than read from global mutable state.

Step Locality
-------------

A step package should prefer local ownership of details that are not shared by
other steps.  For example, nominal-grid grouping heuristics belong in the
nominal-grid processing package.  Product keys used only by unwrapped-grid should
live in that step's ``keys.py``.

Shared abstractions should move upward only when multiple steps genuinely depend
on them.  This keeps the project DRY without creating premature generic code.

Adding Tests for a Step
-----------------------

New steps should usually add tests for:

* registry registration;
* product save/load round trip;
* viewer behavior for present and missing products;
* processing smoke behavior;
* interactive initialization, if applicable.

The existing smoke tests are intentionally generic and should catch many basic
registration/import failures automatically once the step is listed in
``STEP_MODULES``.
