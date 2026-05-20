# grid_calibration/gui/session.py
"""
Runtime session state for the grid-calibration GUI.

This module defines the small state container used by the Dash application while
one calibration run is open.  The central object is
:class:`~grid_calibration.gui.session.CalibrationSession`, which stores the raw
input files, the output directory, and the currently registered products for
all workflow steps.

The session deliberately does not know how products are named, encoded, decoded,
or validated.  Those responsibilities belong to
:class:`~grid_calibration.gui.workflow.product_io.ProductIO`.  At startup and
when products are refreshed, the session delegates product discovery to
:func:`~grid_calibration.gui.workflow.product_io.discover_products` using the
ordered workflow defined by :mod:`~grid_calibration.gui.workflow.registry`.

A session is attached to the Dash/Flask server configuration by the GUI startup
code and retrieved through :func:`~grid_calibration.gui.session.get_session`.
This keeps step code and plotting code independent of the app-construction path
while still giving them access to the active runtime state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .workflow.registry import ORDERED_STEPS, PRODUCT_IO_BY_STEP
from .workflow.product_io import discover_products
from ..errors import PipelineStepError, GridCalibrationError


def get_session() -> "CalibrationSession":
    """
    Return the active GUI calibration session.

    The active :class:`~grid_calibration.gui.session.CalibrationSession` is
    stored on the Dash server configuration under the ``"session"`` key.  The
    import of :mod:`~grid_calibration.gui.server` is intentionally local so this
    helper can be imported by workflow, plotting, and step modules without
    creating circular imports during application startup.

    Returns
    -------
    :class:`~grid_calibration.gui.session.CalibrationSession`
        Active session attached to the Dash/Flask server.

    Raises
    ------
    :class:`~grid_calibration.errors.GridCalibrationError`
        If no session has been attached to the Dash app.
    """
    from .server import app  # local import avoids circular import issues

    try:
        return app.server.config["session"]
    except KeyError as exc:
        raise GridCalibrationError(
            "No CalibrationSession is attached to the Dash app."
        ) from exc


@dataclass
class CalibrationSession:
    """
    Runtime state for one grid-calibration GUI session.

    The session tracks the raw inputs, output directory, and currently available
    products.  It is intentionally a state container only: product schemas,
    product paths, load/save behavior, and encode/decode hooks are owned by
    :class:`~grid_calibration.gui.workflow.product_io.ProductIO`.

    Product availability is represented by the :attr:`products` mapping.  The
    mapping keys are workflow step keys, such as ``"raw-image"`` or
    ``"grid-points"``.  Values follow the corresponding product kind:

    - raw images are stored as ``list[pathlib.Path]``;
    - per-input products are stored as ``list[pathlib.Path]``;
    - singleton products are stored as ``pathlib.Path``;
    - unavailable products may be absent, ``None``, or an empty list depending
      on the product kind and discovery context.

    Parameters
    ----------
    raw_files : list[pathlib.Path]
        Raw image files associated with the calibration run.
    output_dir : pathlib.Path
        Directory where step products are saved and discovered.
    products : dict[str, Any], optional
        Existing product registry.  This is usually created by
        :meth:`from_inputs` rather than supplied directly.
    """

    raw_files: list[Path]
    output_dir: Path
    products: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_inputs(
        cls,
        raw_files: list[Path],
        output_dir: Path,
    ) -> "CalibrationSession":
        """
        Create a session from raw input files and an output directory.

        This constructor initializes the ``"raw-image"`` product entry and then
        performs ordered, dependency-aware product discovery for all registered
        workflow steps.  Discovery uses
        :func:`~grid_calibration.gui.workflow.product_io.discover_products` with
        :data:`~grid_calibration.gui.workflow.registry.ORDERED_STEPS`, so
        products downstream of a missing or incomplete upstream step are treated
        as stale and are not registered.

        Parameters
        ----------
        raw_files : list[pathlib.Path]
            Raw image files selected for the session.  Values are normalized to
            :class:`pathlib.Path` instances.
        output_dir : pathlib.Path
            Directory where existing products are searched for and new products
            will be written.

        Returns
        -------
        :class:`~grid_calibration.gui.session.CalibrationSession`
            New session with raw files and any valid existing products
            registered.

        Raises
        ------
        :class:`~grid_calibration.errors.PipelineStepError`
            Propagated from
            :func:`~grid_calibration.gui.workflow.product_io.discover_products`
            if no raw input files are provided.
        """
        raw_files = [Path(p) for p in raw_files]
        output_dir = Path(output_dir)

        products = {
            "raw-image": raw_files,
        }
        products.update(
            discover_products(
                PRODUCT_IO_BY_STEP,
                raw_files,
                output_dir,
                ordered_steps=ORDERED_STEPS,
                stop_at_first_missing=True,
                warn_stale=True,
            )
        )

        return cls(
            raw_files=raw_files,
            output_dir=output_dir,
            products=products,
        )

    @property
    def first_raw_file(self) -> Path:
        """
        Return the first raw input file for singleton product naming.

        Singleton product paths are derived from the first raw input file by
        :meth:`~grid_calibration.gui.workflow.product_io.ProductIO.relative_path`.
        This property centralizes that convention and provides a clear error if
        the session was constructed without raw files.

        Returns
        -------
        pathlib.Path
            First raw image file in :attr:`raw_files`.

        Raises
        ------
        :class:`~grid_calibration.errors.PipelineStepError`
            If the session has no raw files.
        """
        if not self.raw_files:
            raise PipelineStepError("CalibrationSession has no raw files.")
        return self.raw_files[0]

    def get(self, step: str) -> Any:
        """
        Return the registered product value for a workflow step.

        This is the low-level session accessor used by
        :class:`~grid_calibration.gui.workflow.product_io.ProductIO`.  It does
        not validate that a product exists or has a particular type; callers
        that require a product should usually use
        :meth:`~grid_calibration.gui.workflow.product_io.ProductIO.require`.

        Parameters
        ----------
        step : str
            Workflow step key.

        Returns
        -------
        Any
            Registered product value for ``step``, or ``None`` if the step is
            not present in :attr:`products`.
        """
        return self.products.get(step)

    def set(self, step: str, value: Any) -> None:
        """
        Register or replace a product value for a workflow step.

        This method is intentionally permissive because product-specific type
        checks are handled by
        :meth:`~grid_calibration.gui.workflow.product_io.ProductIO.register`.
        Direct callers should follow the same product-value conventions used by
        :class:`~grid_calibration.gui.workflow.product_io.ProductIO`.

        Parameters
        ----------
        step : str
            Workflow step key.
        value : Any
            Product value to store.  Typical values are ``pathlib.Path`` for
            singleton products and ``list[pathlib.Path]`` for per-input
            products.

        Returns
        -------
        None
            The session is modified in place.
        """
        self.products[step] = value

    def refresh_products(self) -> None:
        """
        Rediscover products from disk using ordered dependency checks.

        The current product registry is rebuilt from scratch rather than updated
        in place.  This prevents stale downstream products from remaining
        registered after an upstream product has been deleted during debugging or
        manual cleanup.

        Discovery uses
        :func:`~grid_calibration.gui.workflow.product_io.discover_products` with
        ``stop_at_first_missing=True`` and ``warn_stale=True``.  As a result,
        products are registered only up to the first missing or incomplete step;
        products found after that point are ignored and logged as stale.

        Returns
        -------
        None
            The :attr:`products` mapping is replaced in place.

        Raises
        ------
        :class:`~grid_calibration.errors.PipelineStepError`
            Propagated from
            :func:`~grid_calibration.gui.workflow.product_io.discover_products`
            if the session has no raw input files.
        """
        products = {
            "raw-image": self.raw_files,
        }
        products.update(
            discover_products(
                PRODUCT_IO_BY_STEP,
                self.raw_files,
                self.output_dir,
                ordered_steps=ORDERED_STEPS,
                stop_at_first_missing=True,
                warn_stale=True,
            )
        )
        self.products = products
