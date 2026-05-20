.. _grid-calibration-test-suite:

Grid Calibration Test Suite
===========================

This page documents the test suite for the grid calibration package after the
workflow, product IO, session, registry, logging, and real-data test refactors.
The goal of the suite is to protect the package architecture while keeping the
normal development cycle fast. Expensive or machine-specific checks are kept
behind explicit pytest markers and environment variables.

The tests are organized into two broad groups:

* **fast tests**, which should run on every development pass and require no real
  calibration images;
* **optional real-data tests**, which validate discovery, loading, and loose
  scientific plausibility against a user-provided dataset and existing product
  directory.

Running the Test Suite
----------------------

Run the normal fast suite from the parent directory that contains the
``grid_calibration`` package directory:

.. code-block:: bash

   cd /path/to/project-parent
   python -m pytest grid_calibration/tests

Using ``python -m pytest`` is recommended because it mirrors the import behavior
used by the package entry point:

.. code-block:: bash

   python -m grid_calibration ...

A successful fast run should execute the unit, architecture, callback,
synthetic-fixture, and CLI smoke tests. Real-data tests are skipped unless a
real dataset is configured.

Pytest Configuration
--------------------

The test suite includes a ``pytest.ini`` file with the following markers:

.. list-table:: Pytest markers
   :header-rows: 1
   :widths: 20 80

   * - Marker
     - Meaning
   * - ``dash``
     - Tests that require Dash components or callback modules.
   * - ``realdata``
     - Optional tests that require user-provided calibration images.
   * - ``slow``
     - Tests that may run expensive processing on real data.

The markers make it possible to keep day-to-day tests lightweight while still
supporting stronger validation when local data are available.

Test Layers
-----------

The current suite is intentionally layered. Lower layers protect small,
centralized contracts. Higher layers verify that the package still behaves like
a coherent calibration application.

.. list-table:: Test modules
   :header-rows: 1
   :widths: 35 65

   * - Module
     - Purpose
   * - ``tests/test_product_io.py``
     - Unit tests for :class:`~grid_calibration.gui.workflow.product_io.ProductIO` path generation, save/load behavior,
       schema validation, caching, registration, and encode/decode round trips.
   * - ``tests/test_session.py``
     - Unit tests for :class:`~grid_calibration.gui.session.CalibrationSession` product state, first raw file
       handling, and product rediscovery.
   * - ``tests/test_registry.py``
     - Architecture tests for registered step ordering, product keys, runnable
       steps, and factory availability.
   * - ``tests/test_step_smoke.py``
     - Lightweight smoke tests for registered step packages, factories, and
       minimal product IO compatibility.
   * - ``tests/test_callback_orchestration.py``
     - Tests for GUI callback orchestration without launching a Dash server.
   * - ``tests/synthetic_products.py``
     - Small helper module for generating fake but structurally valid products.
   * - ``tests/test_synthetic_discovery_and_viewers.py``
     - Synthetic product discovery and viewer regression tests.
   * - ``tests/test_cli_smoke.py``
     - Lightweight command-line import/help/initialization smoke tests.
   * - ``tests/realdata_helpers.py``
     - Shared helpers for optional real-data configuration, product reporting,
       product loading, and quality threshold extraction.
   * - ``tests/test_realdata_optional.py``
     - Optional real-data session, product discovery, product loadability, and
       slow pipeline smoke tests.
   * - ``tests/test_realdata_quality.py``
     - Optional loose quality checks for existing real-data products.

ProductIO Tests
---------------

``tests/test_product_io.py`` protects the product system, which is the single
source of truth for file naming, schema validation, encoding, decoding, loading,
saving, caching, and session registration.

These tests cover:

* relative paths for per-input products;
* relative paths for singleton products;
* expected paths for singleton products using the session's first raw file;
* rejection of implicit paths for per-input products;
* rejection of per-input saves without ``input_file`` or explicit ``path``;
* save/load round trips for simple ``.npz`` products;
* in-memory load caching;
* missing required-key validation on save;
* unexpected-key validation on save;
* missing required-key validation on load;
* semantic encode/decode round trips for object-like products;
* singleton registration into the session;
* per-input registration requirements;
* product discovery for both singleton and per-input products.

A particularly important regression check is that per-input products must not
silently choose the first raw file. This protects batch products such as grid
point detections, where an implicit input file would be ambiguous and dangerous.

CalibrationSession Tests
------------------------

``tests/test_session.py`` verifies that :class:`~grid_calibration.gui.session.CalibrationSession` remains a runtime
state container rather than a second source of product logic.

These tests cover:

* returning the first raw file for non-empty sessions;
* raising a clear error for empty sessions;
* basic ``get`` and ``set`` product state behavior;
* rediscovery of existing products through the registered :class:`~grid_calibration.gui.workflow.product_io.ProductIO` objects.

The session tests deliberately avoid schema and file-naming logic. Those belong
to :class:`~grid_calibration.gui.workflow.product_io.ProductIO`.

Registry Tests
---------------

``tests/test_registry.py`` protects the central workflow registry. The registry
is what turns self-contained step packages into an ordered GUI/pipeline
workflow.

These tests assert that:

* registered step keys are unique;
* ``ORDERED_STEPS`` matches ``ORDERED_STEP_SPECS``;
* step specs are sorted by ``order``;
* every registered step has a matching product key, or explicitly has no
  product;
* each ``ProductIO.step_key`` matches the corresponding registry key;
* runnable steps exclude only the initial raw-image step;
* batch steps have pipeline factories;
* non-raw steps have viewer factories.

These checks catch common refactor mistakes, such as forgetting to expose
``pipeline_step`` or ``product_io`` from a step package, mismatching step keys,
or registering steps out of order.

Step Smoke Tests
----------------

``tests/test_step_smoke.py`` checks that registered steps are importable and
that their factories resolve without requiring real images. This layer is not
intended to validate algorithmic correctness. Instead, it catches architectural
breakages early.

Typical failures caught here include:

* missing imports after moving modules;
* a step package failing to expose its expected spec/product objects;
* broken lazy factories;
* product definitions that cannot save/load minimal valid payloads;
* interactive initializers that crash before real user interaction begins.

Callback Orchestration Tests
----------------------------

``tests/test_callback_orchestration.py`` verifies GUI callback behavior without
starting a Dash development server. This gives useful coverage for the Dash
orchestration layer while keeping the suite fast.

These tests cover behavior such as:

* starting a batch step;
* initializing an interactive step;
* rebuilding options after step finalization;
* selecting viewer content;
* safely handling unknown or unavailable selected steps.

This layer is especially useful because GUI regressions often happen at the
boundary between session state, product discovery, and callback return values.
The tests focus on those boundaries rather than on browser-level behavior.

Synthetic Product and Viewer Tests
----------------------------------

``tests/synthetic_products.py`` provides generated, minimal products that mimic
the structure of real pipeline outputs without requiring image processing or
large binary fixtures. The corresponding tests live in
``tests/test_synthetic_discovery_and_viewers.py``.

This layer checks that:

* fake products can be written using the same :class:`~grid_calibration.gui.workflow.product_io.ProductIO` objects as real
  products;
* a fresh session can rediscover those products from disk;
* :func:`viewer_factory` viewer functions can load expected products;
* missing products fail gracefully or produce controlled placeholder behavior;
* nominal-grid-style object records survive encode/decode boundaries.

Synthetic products are intentionally small and deterministic. They are not a
substitute for real calibration data, but they are ideal for continuous
architecture regression testing.

CLI Smoke Tests
---------------

``tests/test_cli_smoke.py`` gives a minimal safety net around the command-line
entry point and import path assumptions.

The tests are designed for the source-tree workflow where the package is often
run as:

.. code-block:: bash

   python -m grid_calibration <inputs> --debug

rather than from an installed wheel. This helps ensure that ``python -m pytest``
and ``python -m grid_calibration`` see the package in a consistent way.

Optional Real-Data Tests
------------------------

The optional real-data tests are marked with ``realdata`` and are skipped unless
a dataset is explicitly configured. They are meant to validate real products and
loose scientific plausibility without slowing down the normal suite.

Configuring Real Input Images
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provide real input images with either a glob:

.. code-block:: bash

   export GRID_CALIBRATION_REALDATA_GLOB='../data/GONet/Grainger/new/202/after_focus_new_calibration/*.jpg'

or a directory:

.. code-block:: bash

   export GRID_CALIBRATION_REALDATA_DIR='../data/GONet/Grainger/new/202/after_focus_new_calibration'

Then run:

.. code-block:: bash

   python -m pytest grid_calibration/tests -m realdata

By default, the helper uses at most five input files. This can be changed with:

.. code-block:: bash

   export GRID_CALIBRATION_REALDATA_MAX_FILES=10

Checking Existing Products
~~~~~~~~~~~~~~~~~~~~~~~~~~

To validate products that already exist in an output directory, set:

.. code-block:: bash

   export GRID_CALIBRATION_REALDATA_OUTDIR='grid_calibration_output'

Then run with reporting enabled:

.. code-block:: bash

   python -m pytest grid_calibration/tests -m realdata --realdata-report -s

The report lists every registered product step, whether it is singleton or
per-input, how many products were discovered, and whether at least one product
was loadable.

Example output looks like:

.. code-block:: text

   Real-data product status:
     - full-array           per_input 5/5   loadable
     - grid-points          per_input 5/5   loadable
     - averaged-grid        singleton 1/1   loadable
     - unwrapped-grid       singleton 1/1   loadable
     - nominal-grid         singleton 1/1   loadable
     - bootstrapping-grid   singleton 1/1   loadable
     - modeling-results     singleton 1/1   loadable

Requiring Products
~~~~~~~~~~~~~~~~~~

By default, product reporting is informational. To make missing or incomplete
products fail the test, require specific products:

.. code-block:: bash

   python -m pytest grid_calibration/tests -m realdata \
     --realdata-report -s \
     --realdata-require-products=full-array,grid-points,averaged-grid

To require every registered product:

.. code-block:: bash

   python -m pytest grid_calibration/tests -m realdata \
     --realdata-report -s \
     --realdata-require-products=all

The equivalent environment variable is:

.. code-block:: bash

   export GRID_CALIBRATION_REQUIRE_REALDATA_PRODUCTS='full-array,grid-points'

Running the Slow Real Pipeline Smoke Test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The slow real pipeline smoke test is marked with both ``realdata`` and ``slow``.
It is skipped unless explicitly enabled:

.. code-block:: bash

   export GRID_CALIBRATION_RUN_REAL_PIPELINE=1
   python -m pytest grid_calibration/tests -m 'realdata and slow'

This test creates a temporary output directory and attempts to run registered
batch steps. It is intended as a smoke test, not a full numerical regression
benchmark.

Real-Data Quality Tests
-----------------------

``tests/test_realdata_quality.py`` adds loose quality assertions for existing
real-data products. These tests run only when both the input images and output
directory are configured.

They check that:

* every grid-points product contains a finite ``(N, 2)`` coordinate array;
* each grid-points product has at least a configurable minimum number of points;
* the averaged-grid product contains finite ``(N, 2)`` points;
* averaged-grid counts are one-dimensional, positive, and aligned with the grid;
* the unwrapped-grid product contains aligned point, index, theta, and radius
  arrays;
* unwrapped theta values lie in the expected ``0`` to ``360`` degree range;
* nominal-grid records contain fields such as ``idx``, ``pixel_x``,
  ``pixel_y``, ``nominal_r``, and ``nominal_theta``;
* bootstrapped-grid records retain finite nominal coordinates;
* modeling-results expose a representative final RMS value;
* the extracted model RMS is below a configurable loose threshold.

The default thresholds are intentionally permissive. They are designed to catch
missing, empty, malformed, or wildly poor products rather than to certify the
final calibration quality.

Quality Threshold Options
~~~~~~~~~~~~~~~~~~~~~~~~~

The real-data quality tests support pytest command-line options:

.. code-block:: bash

   python -m pytest grid_calibration/tests -m realdata --realdata-report -s \
     --realdata-min-grid-points=100 \
     --realdata-min-averaged-points=100 \
     --realdata-min-nominal-records=100 \
     --realdata-max-model-rms=20

The same thresholds can be set using environment variables:

.. list-table:: Real-data quality thresholds
   :header-rows: 1
   :widths: 45 20 35

   * - Environment variable
     - Default
     - Meaning
   * - ``GRID_CALIBRATION_REALDATA_MIN_GRID_POINTS``
     - ``10``
     - Minimum detected points in each grid-points product.
   * - ``GRID_CALIBRATION_REALDATA_MIN_AVERAGED_POINTS``
     - ``10``
     - Minimum points in averaged-grid and unwrapped-grid products.
   * - ``GRID_CALIBRATION_REALDATA_MIN_NOMINAL_RECORDS``
     - ``10``
     - Minimum records in nominal-grid and bootstrapped-grid products.
   * - ``GRID_CALIBRATION_REALDATA_MAX_MODEL_RMS``
     - ``50.0``
     - Maximum acceptable final model RMS in pixels.

Real-Data Configuration Reference
---------------------------------

.. list-table:: Environment variables
   :header-rows: 1
   :widths: 42 58

   * - Variable
     - Description
   * - ``GRID_CALIBRATION_REALDATA_GLOB``
     - One or more image glob patterns. Multiple patterns may be separated by
       ``os.pathsep``.
   * - ``GRID_CALIBRATION_REALDATA_DIR``
     - Directory containing real input images. Used when no glob is supplied.
   * - ``GRID_CALIBRATION_REALDATA_OUTDIR``
     - Existing output directory containing pipeline products to discover and
       validate.
   * - ``GRID_CALIBRATION_REALDATA_MAX_FILES``
     - Maximum number of raw files used by optional tests. Defaults to ``5``.
   * - ``GRID_CALIBRATION_RUN_REAL_PIPELINE``
     - Set to ``1``, ``true``, ``yes``, ``y``, or ``on`` to enable slow real
       pipeline execution.
   * - ``GRID_CALIBRATION_REQUIRE_REALDATA_PRODUCTS``
     - Comma-separated product step keys, or ``all``, that must exist and load.
   * - ``GRID_CALIBRATION_REALDATA_MIN_GRID_POINTS``
     - Minimum points required in each real grid-points product.
   * - ``GRID_CALIBRATION_REALDATA_MIN_AVERAGED_POINTS``
     - Minimum points required in averaged and unwrapped grid products.
   * - ``GRID_CALIBRATION_REALDATA_MIN_NOMINAL_RECORDS``
     - Minimum records required in nominal and bootstrapped products.
   * - ``GRID_CALIBRATION_REALDATA_MAX_MODEL_RMS``
     - Maximum allowed modeling RMS for loose quality validation.

Suggested Development Workflow
------------------------------

During normal development, run the fast suite frequently:

.. code-block:: bash

   python -m pytest grid_calibration/tests

After changing product definitions, session behavior, or step registration, also
run the product and registry tests directly:

.. code-block:: bash

   python -m pytest grid_calibration/tests/test_product_io.py \
                   grid_calibration/tests/test_session.py \
                   grid_calibration/tests/test_registry.py

After changing GUI callback orchestration or viewer behavior, run:

.. code-block:: bash

   python -m pytest grid_calibration/tests/test_callback_orchestration.py \
                   grid_calibration/tests/test_synthetic_discovery_and_viewers.py

When real products are available, run the optional real-data suite:

.. code-block:: bash

   export GRID_CALIBRATION_REALDATA_GLOB='../data/GONet/Grainger/new/202/after_focus_new_calibration/*.jpg'
   export GRID_CALIBRATION_REALDATA_OUTDIR='grid_calibration_output'
   python -m pytest grid_calibration/tests -m realdata --realdata-report -s

For a stricter local validation pass, require all products and tighten the
quality thresholds:

.. code-block:: bash

   python -m pytest grid_calibration/tests -m realdata --realdata-report -s \
     --realdata-require-products=all \
     --realdata-min-grid-points=100 \
     --realdata-min-averaged-points=100 \
     --realdata-min-nominal-records=100 \
     --realdata-max-model-rms=20

What the Suite Guarantees
-------------------------

The suite is designed to provide confidence that:

* product contracts remain stable;
* file naming and session registration do not drift;
* the workflow registry remains internally consistent;
* step packages remain importable and discoverable;
* callbacks can move the GUI through batch and interactive states;
* synthetic products can be discovered and visualized;
* the command-line entry point remains importable;
* real products can be discovered and loaded when configured;
* real outputs satisfy basic structural and plausibility checks.

What the Suite Does Not Yet Guarantee
-------------------------------------

The current suite is not a full scientific validation framework. In particular,
it does not yet provide:

* pixel-perfect visual regression testing for figures;
* benchmark tracking for runtime or memory usage;
* strict numerical regression baselines for calibration parameters;
* uncertainty validation;
* browser-level end-to-end Dash interaction tests;
* large multi-dataset robustness testing.

Those are good future additions, but the current suite already provides a strong
foundation for safe refactoring and day-to-day development.

Adding a New Step
-----------------

When a new step package is added under ``gui/steps/<step_name>/``, it should
expose at least:

.. code-block:: python

   from .spec import pipeline_step, product_io

The registry and smoke tests will then check that:

* the step key is unique;
* the step appears in the expected order;
* the step has a matching product key if it produces a product;
* batch steps expose a pipeline factory;
* non-raw steps expose a viewer factory;
* the product definition can save/load a minimal valid payload if applicable.

If the new product has semantic encoding or object arrays, add a targeted
round-trip test or extend the synthetic product helpers so future refactors
cannot silently break the encoded format.

Adding Real-Data Assertions
---------------------------

When adding new real-data assertions, prefer loose structural checks first:

* Does the product exist?
* Does it load through :class:`~grid_calibration.gui.workflow.product_io.ProductIO`?
* Are required keys present?
* Are array shapes correct?
* Are values finite?
* Are counts or record numbers non-trivially large?

Only add strict numerical thresholds when the dataset, algorithm, and expected
outputs are stable enough to justify them. Strict thresholds are best reserved
for dedicated regression datasets or manually triggered benchmark jobs.
