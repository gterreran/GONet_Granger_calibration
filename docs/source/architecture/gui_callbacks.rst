GUI Callback Architecture
=========================

The Dash GUI is intentionally driven by a small number of stores and generic
callbacks.  Step-specific callbacks are used only where a step needs custom
interactive behavior.

Core Stores
-----------

The most important stores are:

``STORE_ACTIVE_STEP``
    The latest/current completed or initialized workflow step.  This represents
    workflow progress.

``STORE_SELECTED_STEP``
    The step currently being viewed in the right-hand panel.  This represents
    user navigation.

``STORE_RUN_STEP``
    The step requested for execution by a button click.

``STORE_STEP_REQUEST`` and ``STORE_STEP_RESULT``
    Intermediate stores used by orchestration callbacks to separate user intent,
    execution, and final GUI updates.

``STORE_CONTROL_STEPS``
    Ordered list of step keys used by clientside callbacks for row styles and
    row-click behavior.

The distinction between active and selected step is important.  The active step
tracks pipeline progress; the selected step tracks what the user is inspecting.
A user should be able to click and view previous products without changing the
workflow's latest completed step.

Left Menu Behavior
------------------

Rows in the left control panel have two separate behaviors:

* the action button runs a step;
* the surrounding row selects a viewable step.

A row should be clickable if that step's product exists.  The visual highlight
should follow ``STORE_SELECTED_STEP`` when it is set, falling back to
``STORE_ACTIVE_STEP`` during initial load.  This allows the GUI to open at the
latest coherent product while still letting the user browse earlier steps.

A previous bug came from highlighting ``STORE_ACTIVE_STEP`` only.  In that state,
clicking an older step changed the right-hand viewer but left the blue highlight
on the latest processed step.  The correct model is:

.. code-block:: text

   active step   = workflow progress
   selected step = current viewer/highlight

The row-click callback should allow clicking the active/latest step, even if it
is already the active step, because the user may be returning to it after viewing
another step.

Batch Step Orchestration
------------------------

A batch step generally follows this callback flow:

#. A step button is clicked.
#. The requested step key is stored.
#. The corresponding ``pipeline_func`` is resolved from the step spec.
#. The pipeline function runs and writes products through :class:`~grid_calibration.gui.workflow.product_io.ProductIO`.
#. The session refreshes products from disk.
#. The active and selected step stores are updated.
#. The control panel options and right-hand viewer are rebuilt.

The callback layer should not know details such as NPZ keys or expected product
paths.  Those belong to the step's :class:`~grid_calibration.gui.workflow.product_io.ProductIO`.

Interactive Step Orchestration
------------------------------

Interactive steps add a preparation phase:

#. User clicks the step button.
#. The step's ``initialize_interactive_state`` function is resolved and called.
#. The GUI renders step-specific controls and temporary state.
#. User interactions update temporary stores or figures.
#. A confirm action saves/registers the product.
#. The generic finalization path refreshes products and updates the viewer.

The final saved product should still use :class:`~grid_calibration.gui.workflow.product_io.ProductIO`.  Interactive callbacks
should not bypass the product system.

Viewer Callback
---------------

The viewer callback chooses the right plotting function based on
``STORE_SELECTED_STEP`` and the selected dropdown/label value.  If the selected
step is missing, unknown, or has no viewable product, the callback should return a
graceful placeholder or ``no_update`` rather than raising.

This is especially important during debugging, product deletion, and stale-output
recovery.

Product Refresh and Finalization
--------------------------------

After running or confirming a step, callbacks should refresh the session product
state from disk.  Refresh uses dependency-aware discovery, so deleted upstream
products will remove downstream products from the registered GUI state even if
those downstream files still exist on disk.

This keeps the left menu, dropdown options, and viewer callbacks aligned with the
coherent workflow state.

Logging
-------

The GUI logging system should capture package-scoped logs and selected external
logs, not indiscriminately capture every root logger.  Step execution should log
through module-level loggers.  Per-step context can be added by orchestration
callbacks so the log window remains readable during multi-step workflows.

Design Guidance
---------------

When adding or modifying callbacks:

* keep product IO out of callback code where possible;
* use stores to make state transitions explicit;
* separate workflow progress from viewer selection;
* fail gracefully when products are missing;
* prefer generic callbacks for common behavior;
* keep step-specific callbacks inside the step package.
