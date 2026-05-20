Sessions and Products
=====================

The session/product split is the core runtime design of the GUI.  It prevents
product-specific behavior from leaking into the session object and keeps runtime
state small, explicit, and easy to inspect.

Responsibilities
----------------

:class:`~grid_calibration.gui.session.CalibrationSession` owns runtime state:

* raw input files;
* output directory;
* registered products, stored as ``step_key -> Path | list[Path] | None``.

:class:`~grid_calibration.gui.workflow.product_io.ProductIO` owns product behavior:

* relative file naming;
* expected output paths;
* singleton vs per-input semantics;
* required and optional NPZ keys;
* encode/decode functions;
* :meth:`~grid_calibration.gui.workflow.product_io.ProductIO.save`/:meth:`~grid_calibration.gui.workflow.product_io.ProductIO.load` helpers;
* :meth:`~grid_calibration.gui.workflow.product_io.ProductIO.register`;
* in-memory load cache.

:func:`~grid_calibration.gui.workflow.product_io.discover_products` owns startup discovery:

* checks the output directory for products matching each step contract;
* respects workflow order;
* avoids registering stale downstream products when an upstream dependency is
  missing or incomplete.

This division is intentional.  A session should be serializable in spirit: it is
just the current state of one calibration run.  It should not need to understand
how a nominal-grid product is encoded or how a per-input grid-points product is
named.

Product Kinds
-------------

There are two product kinds.

``ProductKind.PER_INPUT``
    One product file per raw input image.  Examples include full-array and
    grid-points products.  Per-input products require an ``input_file`` or an
    explicit ``path`` when saving.  They should not silently fall back to the
    first raw file, because that can overwrite or mis-register products.

``ProductKind.SINGLETON``
    One product file for the full calibration session.  Examples include
    averaged-grid, unwrapped-grid, nominal-grid, bootstrapping-grid, and
    modeling-results products.  Singleton product names are derived from the
    common prefix of the first raw file.

Schema Validation
-----------------

Each :class:`~grid_calibration.gui.workflow.product_io.ProductIO` declares ``required_keys`` and ``optional_keys``.  These keys
are enforced when saving and loading NPZ products.

On save:

* missing required keys raise a product-save error;
* unexpected keys raise a product-save error;
* optional keys may be omitted.

On load:

* missing required NPZ keys raise a product-load error;
* optional keys are loaded only if present.

This catches many refactor bugs at the product boundary rather than later in a
plotting or modeling function.

Encoding and Decoding
---------------------

Simple products can save arrays directly.  More semantic products use
``encode`` and ``decode`` functions.

A typical semantic product stores one or more Python-level structures under
stable NPZ keys, for example:

``data``
    The main record list or structured payload.

``params``
    Parameters used to produce the product.

The encode/decode functions make the file representation explicit while keeping
call sites readable.  Step processing code can work with natural Python objects,
while :class:`~grid_calibration.gui.workflow.product_io.ProductIO` handles conversion to and from NPZ-safe arrays.

Registration
------------

Saving a product and registering a product are related but separate operations.
A processing function usually saves a product and then registers the returned
path in the active session.

This separation is useful because tests, discovery, and manual recovery may need
to register existing products without re-running a step.

For singleton products, ``register()`` can infer the expected path.  For
per-input products, registration must receive an explicit list of paths.  This is
another safety mechanism that prevents accidental registration of only one file
from a multi-input run.

Dependency-Aware Discovery
--------------------------

Product discovery is deliberately conservative.  It walks the workflow in order
and stops trusting downstream products once an upstream step is missing or
incomplete.

The important rules are:

* raw images are always registered directly by the session;
* a singleton product is available only when its expected file exists;
* a per-input product is available only when the complete expected set exists;
* once a step is unavailable, later products are treated as stale;
* stale downstream products may be logged as warnings, but they are not
  registered in the session.

This behavior protects the GUI during debugging.  For example, if
``averaged-grid`` is deleted but ``nominal-grid`` still exists on disk, the GUI
should not behave as though the nominal product belongs to a valid current
workflow chain.  It should expose the pipeline only up to the last coherent step.

Refreshing Products
-------------------

``CalibrationSession.refresh_products()`` should replace discovered product
state, not blindly update it.  Blind updates can leave stale entries in memory
after files have been deleted from disk.

The safe refresh pattern is:

#. keep ``raw-image`` from the current session;
#. rediscover products from disk using dependency-aware discovery;
#. replace the session's product dictionary with the coherent result.

This guarantees that the in-memory GUI state mirrors the safe subset of products
that currently exists on disk.

Caching
-------

:class:`~grid_calibration.gui.workflow.product_io.ProductIO` caches loaded products by path string.  This avoids repeated NPZ
loads while the user explores products in the GUI.  Saving a product invalidates
that path's cache entry.  Tests can clear caches explicitly when needed.

The cache belongs to :class:`~grid_calibration.gui.workflow.product_io.ProductIO` rather than :class:`~grid_calibration.gui.session.CalibrationSession` because it
is an implementation detail of product loading, not user-visible runtime state.
