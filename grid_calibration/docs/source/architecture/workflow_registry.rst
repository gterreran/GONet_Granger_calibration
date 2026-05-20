Workflow Registry
=================

The workflow registry centralizes the structure of the calibration pipeline.  It
answers questions such as:

* Which steps exist?
* What order do they run in?
* Which steps are runnable?
* Which product object belongs to each step?
* When should a step be enabled or clickable in the GUI?

The registry is intentionally small, but it is one of the most important modules
in the package because it is the bridge between self-contained step packages and
the generic GUI orchestration code.

Step Registration Contract
--------------------------

Each step package listed in ``gui.steps.STEP_MODULES`` must expose two public
objects:

``pipeline_step``
    A :class:`~grid_calibration.gui.workflow.specs.PipelineStepSpec` describing
    the workflow role of the step.

``product_io``
    A :class:`~grid_calibration.gui.workflow.product_io.ProductIO` object
    describing the product produced by the step.  Steps that do not produce a
    product may expose ``None`` when appropriate, but most processing steps
    should have a product object.

At import time, ``workflow.registry`` validates that every listed step exposes
these objects.  It also checks that ``product_io.step_key`` matches
``pipeline_step.key``.  This catches copy/paste mistakes early, before the GUI
can build an inconsistent workflow.

Ordered Step Lists
------------------

The registry derives several useful collections:

``STEP_BY_ID``
    Mapping from step key to :class:`PipelineStepSpec`.

``PRODUCT_IO_BY_STEP``
    Mapping from step key to :class:`ProductIO`.

``ORDERED_STEP_SPECS``
    Step specs sorted by their integer order.

``ORDERED_STEPS``
    Ordered list of step keys.

``RUNNABLE_STEPS``
    Ordered list of steps that can be executed by the pipeline.  The raw-image
    step is usually excluded because it is an input/viewer step rather than a
    generated product step.

These derived collections let callbacks and layout code remain generic.  The GUI
should not need hard-coded knowledge of specific step names except where a step
has genuinely custom interactive behavior.

Enable and Clickability Rules
-----------------------------

The registry provides two related but distinct concepts:

``enabled``
    A step's action button should be enabled when its prerequisite step product
    exists.  This answers: *Can this step be run now?*

``clickable``
    A step row should be clickable when that step's own product exists.  This
    answers: *Can this step be viewed now?*

This distinction matters because a step can be enabled before its own product
exists.  For example, once ``grid-points`` exists, the ``averaged-grid`` button
can become enabled, but the ``averaged-grid`` row should not become viewable
until the averaged-grid product has actually been created.

Callback Module Importing
-------------------------

Some steps need their own Dash callbacks, especially interactive steps.  The
registry provides a helper that attempts to import ``<step_package>.callbacks``
for each registered step.  Missing callback modules are allowed; import failures
inside an existing callback module are not silently swallowed.

This pattern lets simple steps avoid callback files entirely while keeping custom
interactive callback registration discoverable and centralized.

Why Factories Are Stored on Step Specs
--------------------------------------

:class:`~grid_calibration.gui.workflow.specs.PipelineStepSpec` stores factories rather than direct function objects for
viewer, pipeline, and initializer callables.  This is deliberate:

* it avoids importing heavy plotting/processing modules during registry import;
* it reduces circular imports between steps, callbacks, and session helpers;
* it keeps metadata import lightweight for tests and documentation;
* it allows step packages to preserve a stable public interface while refactoring
  internals.

The typical pattern inside a step ``spec.py`` is:

.. code-block:: python

   def viewer_factory():
       from .plotting import plot_some_product
       return plot_some_product

   def pipeline_factory():
       from .processing import run_some_step
       return run_some_step

   pipeline_step = PipelineStepSpec.from_dict({...})

The factory is resolved only when the callable is actually needed.

.. note::

   Step factories are discovered from the step module's global namespace when
   the :class:`~grid_calibration.gui.workflow.specs.PipelineStepSpec` is
   created. Internally, this uses :func:`inspect.currentframe` to
   inspect the caller's module globals and capture known factory names such as
   ``viewer_factory``, ``pipeline_factory``, and ``initialize_factory``.

   This is intentional. It keeps individual step ``spec.py`` files compact while
   still allowing missing factories to fail early during import/registry
   construction. The tradeoff is that these factory variables must exist in the
   step module scope before :class:`~grid_calibration.gui.workflow.specs.PipelineStepSpec` is instantiated.

Adding a New Step
-----------------

To add a new workflow step:

#. Create ``gui/steps/<new_step>/``.
#. Add ``spec.py`` defining ``pipeline_step`` and ``product_io``.
#. Expose both from ``gui/steps/<new_step>/__init__.py``.
#. Add the step package to ``gui.steps.STEP_MODULES``.
#. Provide a processing function, viewer function, and optional callbacks as
   needed.
#. Add tests verifying registry registration and product behavior.

Once the step is listed in ``STEP_MODULES``, the registry will include it in the
ordered workflow and the generic GUI machinery can discover it.
