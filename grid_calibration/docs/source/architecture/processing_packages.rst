Processing Modules and Packages
===============================

Processing code may be implemented either as a single ``processing.py`` module or
as a ``processing/`` package.  The choice should be based on complexity, not on a
strict rule that every step must use the same internal layout.

Public API Preservation
-----------------------

The external import surface should remain stable.  A step spec or callback should
be able to import the same public function regardless of whether the
implementation is a module or a package.

For a package implementation, expose the public functions from
``processing/__init__.py``:

.. code-block:: python

   from .pipeline import detect_nominal
   from .grouping import chain_groups_closest_neighbor_with_axis_gate

   __all__ = [
       "detect_nominal",
       "chain_groups_closest_neighbor_with_axis_gate",
   ]

This lets refactors improve maintainability without changing the workflow layer.

When to Split
-------------

A single ``processing.py`` is appropriate when the step is small and readable.
A ``processing/`` package is preferred when the module:

* grows beyond a few hundred lines;
* contains multiple separable algorithmic domains;
* mixes orchestration, containers, geometry, fitting, and output construction;
* has helper functions that deserve independent tests;
* is difficult to navigate as one file.

The project currently uses processing packages for the largest algorithm-heavy
steps, such as nominal-grid assignment, bootstrapping, and modeling results.
Smaller processing modules can remain as single files until there is a clear
benefit to splitting them.

Recommended Package Layout
--------------------------

A large processing package should usually have one orchestration module and
several domain modules.  For example:

.. code-block:: text

   processing/
   ├── __init__.py
   ├── containers.py
   ├── geometry.py
   ├── grouping.py
   ├── fitting.py
   ├── records.py
   └── pipeline.py

``pipeline.py``
    Contains the public high-level function called by the step spec.  It should
    read like the algorithm outline.

``containers.py``
    Dataclasses and structured payloads.

``geometry.py``
    Coordinate transforms and small geometric helpers.

``grouping.py`` / ``rings.py`` / ``spokes.py``
    Domain-specific algorithm pieces.

``records.py``
    Conversion from internal arrays/containers to product records.

``reporting.py``
    Plotting/report generation used by processing, separate from Dash viewers.

This structure is flexible.  The goal is that file names reflect algorithmic
responsibilities.

Orchestration vs Algorithms
---------------------------

The high-level processing function should orchestrate steps in a readable order,
while detailed numerical logic lives in helper modules.  This makes the pipeline
easier to audit and easier to document.

For example, a good orchestration function reads like:

.. code-block:: text

   load inputs
   group spokes
   group circles
   assign nominal labels
   reject outliers
   build output records

The mathematical details of grouping, fitting, or outlier rejection can then be
documented and tested in their own modules.

Relative Imports
----------------

When converting ``processing.py`` to ``processing/``, relative import depth
changes.  Imports that previously went from a step module to package-level errors
or workflow helpers may need one additional leading dot from inside the new
subpackage.

This is a common source of small bugs during refactors.  The test suite should be
run after each split, and package-level imports should be checked explicitly.

Dataclasses and Public Containers
---------------------------------

Dataclasses used across multiple processing modules should live in a containers
module and should be decorated explicitly with ``@dataclass``.  These containers
are part of the internal algorithm API, even if they are not part of the public
step API.

Document the meaning and shape of array fields.  For numerical code, this is
often more valuable than documenting the Python type alone.

Testing Processing Packages
---------------------------

Large processing packages should have tests at several levels:

* import smoke tests for the public API;
* small helper tests for pure functions;
* synthetic product tests for input/output contracts;
* optional real-data regression tests for full algorithm behavior.

The goal is not to freeze every numerical detail, but to catch broken imports,
broken product shapes, missing fields, and obviously implausible outputs.
