# grid_calibration/gui/workflow/product_io.py
"""
Product path, schema, loading, saving, and discovery helpers.

This module defines the product contract used by the grid-calibration workflow.
A product is an intermediate or final ``.npz`` artifact produced by a pipeline
step, such as a full-array image, detected grid points, an averaged grid, a
nominal-grid assignment, or modeling results.

The central abstraction is :class:`~grid_calibration.gui.workflow.product_io.ProductIO`.
Each step package declares one :class:`~grid_calibration.gui.workflow.product_io.ProductIO`
instance in its ``spec.py`` module. That object owns the rules for deriving
filenames, resolving paths, validating NPZ schemas, encoding and decoding
semantic payloads, registering products in session state, and discovering
existing products at GUI startup.

Keeping these responsibilities in this module prevents individual step modules
from duplicating path conventions, ``numpy`` loading logic, and schema checks.
The :class:`~grid_calibration.gui.session.CalibrationSession` stores runtime
state, while :class:`~grid_calibration.gui.workflow.product_io.ProductIO`
defines how each product behaves.
"""

from __future__ import annotations

from enum import Enum, auto
import logging
from pathlib import Path
from typing import Any, Iterable, Callable

from ...errors import MissingProductError, PipelineStepError
from .io_helpers import load_npz_dict, save_npz_dict


logger = logging.getLogger(__name__)

EncodeFunc = Callable[..., dict[str, Any]]
"""Callable used to convert semantic save arguments into NPZ arrays.

The callable receives the keyword arguments passed to
:meth:`~grid_calibration.gui.workflow.product_io.ProductIO.save` and must return
a dictionary whose keys match the product's required and optional NPZ schema.
"""

DecodeFunc = Callable[[dict[str, Any]], Any]
"""Callable used to convert loaded NPZ arrays into a semantic Python object.

The callable receives the validated dictionary returned by
:func:`~grid_calibration.gui.workflow.io_helpers.load_npz_dict` and may return
any object expected by downstream code.
"""


class ProductKind(Enum):
    """Enumeration describing how many files a step product owns.

    Attributes
    ----------
    PER_INPUT
        Product kind for steps that produce one artifact per raw input image.

    SINGLETON
        Product kind for steps that produce one artifact for the whole session.
    """

    PER_INPUT = auto()
    SINGLETON = auto()


class ProductIO:
    """Define the IO contract for one workflow product.

    A :class:`ProductIO` instance is the single source of truth for a step's
    product naming convention, product kind, NPZ schema, optional encode/decode
    hooks, session registration behavior, and load cache.

    Parameters
    ----------
    step_key : :class:`str`
        Workflow step key associated with this product. This key must match the
        corresponding
        :attr:`~grid_calibration.gui.workflow.specs.PipelineStepSpec.key`.

    suffix : :class:`str`
        Filename suffix appended to the derived product stem. For per-input
        products, the stem comes from the full raw-input stem. For singleton
        products, the stem is derived from the first three underscore-separated
        parts of the first raw-input stem.

    kind : :class:`~grid_calibration.gui.workflow.product_io.ProductKind`
        Product multiplicity. Use
        :attr:`~grid_calibration.gui.workflow.product_io.ProductKind.PER_INPUT`
        for one product per raw file and
        :attr:`~grid_calibration.gui.workflow.product_io.ProductKind.SINGLETON`
        for one product per session.

    required_keys : :class:`tuple` [:class:`str`, ...], optional
        Required NPZ keys. Missing required keys raise
        :class:`~grid_calibration.errors.ProductLoadError` during load and
        :class:`~grid_calibration.errors.ProductSaveError` during save.

    optional_keys : :class:`tuple` [:class:`str`, ...], optional
        Optional NPZ keys accepted by the product schema.

    allow_pickle : :class:`bool`, optional
        Whether loading this product may use pickle-backed object arrays. This
        should be enabled only for semantic products that intentionally store
        dictionaries or other object arrays.

    encode : :data:`~grid_calibration.gui.workflow.product_io.EncodeFunc`, optional
        Callable used before saving. It converts semantic keyword arguments into
        NPZ-compatible arrays.

    decode : :data:`~grid_calibration.gui.workflow.product_io.DecodeFunc`, optional
        Callable used after loading. It converts validated NPZ arrays into the
        object consumed by the rest of the pipeline.

    Notes
    -----
    :class:`ProductIO` does not own the session. Instead, methods such as
    :meth:`expected_path`, :meth:`get`, :meth:`register`, and :meth:`save`
    access the active :class:`~grid_calibration.gui.session.CalibrationSession`
    through :func:`~grid_calibration.gui.session.get_session`.
    """
    def __init__(
        self,
        *,
        step_key: str,
        suffix: str,
        kind: ProductKind,
        required_keys: tuple[str, ...] = (),
        optional_keys: tuple[str, ...] = (),
        allow_pickle: bool = False,
        encode: EncodeFunc | None = None,
        decode: DecodeFunc | None = None,
    ) -> None:
        self.step_key = step_key
        self.suffix = suffix
        self.kind = kind
        self.required_keys = required_keys
        self.optional_keys = optional_keys
        self.allow_pickle = allow_pickle
        self.encode = encode
        self.decode = decode
        self._cache: dict[str, Any] = {}

    @property
    def is_singleton(self) -> bool:
        """Return whether this product has one file per session.

        Returns
        -------
        :class:`bool`
            ``True`` when :attr:`kind` is
            :attr:`~grid_calibration.gui.workflow.product_io.ProductKind.SINGLETON`.
        """
        return self.kind is ProductKind.SINGLETON

    @property
    def is_per_input(self) -> bool:
        """Return whether this product has one file per raw input.

        Returns
        -------
        :class:`bool`
            ``True`` when :attr:`kind` is
            :attr:`~grid_calibration.gui.workflow.product_io.ProductKind.PER_INPUT`.
        """
        return self.kind is ProductKind.PER_INPUT

    def relative_path(self, input_file: Path) -> Path:
        """Return the product path relative to the output directory.

        Parameters
        ----------
        input_file : :class:`pathlib.Path`
            Raw input file used to derive the product filename.

        Returns
        -------
        :class:`pathlib.Path`
            Relative product path. Per-input products use the full input stem,
            while singleton products use the first three underscore-separated
            stem components.

        Notes
        -----
        This method performs filename construction only. It does not check
        whether the product exists and does not prepend the session output
        directory. Use :meth:`expected_path` when an absolute path is needed.
        """
        input_file = Path(input_file)

        if self.is_singleton:
            root = "_".join(input_file.stem.split("_")[:3])
            return Path(f"{root}{self.suffix}")

        return Path(f"{input_file.stem}{self.suffix}")

    def expected_path(self, input_file: Path | None = None) -> Path:
        """Return the expected absolute product path in the active session.

        Parameters
        ----------
        input_file : :class:`pathlib.Path` or :data:`None`, optional
            Raw input file used to derive the product filename. This argument is
            required for per-input products and optional for singleton products.

        Returns
        -------
        :class:`pathlib.Path`
            Absolute path under
            :attr:`~grid_calibration.gui.session.CalibrationSession.output_dir`.

        Raises
        ------
        :class:`~grid_calibration.errors.MissingProductError`
            Raised when this product is per-input and no ``input_file`` is
            provided.

        Notes
        -----
        Singleton products may omit ``input_file`` because their stem is derived
        from :attr:`~grid_calibration.gui.session.CalibrationSession.first_raw_file`.
        Per-input products must never silently use the first raw file, because
        doing so can save or load the wrong product.
        """
        from ..session import get_session

        session = get_session()

        if self.is_per_input and input_file is None:
            raise MissingProductError(
                f"Product {self.step_key!r} is per-input; provide input_file."
            )

        input_file = input_file or session.first_raw_file
        return session.output_dir / self.relative_path(input_file)

    def get(self) -> Path | list[Path] | None:
        """Return the product path or paths currently registered in the session.

        Returns
        -------
        :class:`pathlib.Path` or :class:`list` [:class:`pathlib.Path`] or :data:`None`
            For singleton products, returns a path or :data:`None`. For
            per-input products, returns a list of paths, which may be empty.

        Notes
        -----
        This method reads
        :attr:`~grid_calibration.gui.session.CalibrationSession.products`; it
        does not check whether the returned paths still exist on disk.
        """
        from ..session import get_session

        value = get_session().get(self.step_key)

        if self.is_singleton:
            return None if value is None else Path(value)

        return [Path(p) for p in (value or [])]

    def require(self) -> Path | list[Path]:
        """Return registered product paths, raising when none are available.

        Returns
        -------
        :class:`pathlib.Path` or :class:`list` [:class:`pathlib.Path`]
            Registered singleton path or registered per-input path list.

        Raises
        ------
        :class:`~grid_calibration.errors.MissingProductError`
            Raised when no path is registered for this product.
        """
        value = self.get()

        if self.is_singleton:
            if value is None:
                raise MissingProductError(
                    f"No product found for step {self.step_key!r}."
                )
            return value

        if not value:
            raise MissingProductError(
                f"No products found for step {self.step_key!r}."
            )

        return value

    def load(self, path: Path | None = None) -> dict[str, Any]:
        """Load and optionally decode an NPZ product.

        Parameters
        ----------
        path : :class:`pathlib.Path` or :data:`None`, optional
            Product path to load. Singleton products may omit this argument, in
            which case the registered path is loaded. Per-input products must
            provide an explicit path.

        Returns
        -------
        :class:`dict` [:class:`str`, :class:`typing.Any`]
            Loaded product data, or the object returned by ``decode`` when a
            decode hook is configured.

        Raises
        ------
        :class:`~grid_calibration.errors.MissingProductError`
            Raised when a per-input product is loaded without an explicit path,
            or when no registered singleton product exists.

        :class:`~grid_calibration.errors.ProductLoadError`
            Raised by :func:`~grid_calibration.gui.workflow.io_helpers.load_npz_dict`
            when the product is missing required schema keys or cannot be read.

        Notes
        -----
        Loaded products are cached by path string. Use :meth:`clear_cache` to
        force a subsequent load from disk.
        """
        if path is None:
            if self.is_per_input:
                raise MissingProductError(
                    f"Product {self.step_key!r} is per-input; provide a path."
                )

            path = self.require()

        path = Path(path)
        cache_key = str(path)

        if cache_key in self._cache:
            return self._cache[cache_key]

        loaded = load_npz_dict(
            path,
            required_keys=self.required_keys,
            optional_keys=self.optional_keys,
            allow_pickle=self.allow_pickle,
            label=f"{self.step_key} product",
        )

        if self.decode is not None:
            loaded = self.decode(loaded)

        self._cache[cache_key] = loaded
        return loaded

    def load_index(self, index: int) -> dict[str, Any]:
        """Load one registered per-input product by list index.

        Parameters
        ----------
        index : :class:`int`
            Index into the registered per-input product list.

        Returns
        -------
        :class:`dict` [:class:`str`, :class:`typing.Any`]
            Loaded product data for the selected input, or the object returned
            by the product's decode hook.

        Raises
        ------
        :class:`TypeError`
            Raised when this method is called for a singleton product.

        :class:`~grid_calibration.errors.MissingProductError`
            Raised when ``index`` is outside the registered product list.
        """
        paths = self.require()

        if not isinstance(paths, list):
            raise TypeError(
                f"{self.step_key!r} is a singleton product; use load()."
            )

        if index < 0 or index >= len(paths):
            raise MissingProductError(
                f"Product index {index} is out of range for step {self.step_key!r}."
            )

        return self.load(paths[index])

    def save(
        self,
        *,
        input_file: Path | None = None,
        path: Path | None = None,
        **arrays: Any,
    ) -> Path:
        """Save a product to disk and invalidate its cached load entry.

        Parameters
        ----------
        input_file : :class:`pathlib.Path` or :data:`None`, optional
            Raw input file used to derive the output path when ``path`` is not
            provided. Required for per-input products unless ``path`` is given.

        path : :class:`pathlib.Path` or :data:`None`, optional
            Explicit output path. When omitted, the path is computed with
            :meth:`expected_path`.

        **arrays : :class:`typing.Any`
            Product payload. If ``encode`` is configured, these keyword
            arguments are passed to the encode hook before schema validation and
            saving.

        Returns
        -------
        :class:`pathlib.Path`
            Path where the product was written.

        Raises
        ------
        :class:`~grid_calibration.errors.MissingProductError`
            Raised when saving a per-input product without either ``input_file``
            or an explicit ``path``.

        :class:`~grid_calibration.errors.ProductSaveError`
            Raised by :func:`~grid_calibration.gui.workflow.io_helpers.save_npz_dict`
            when required keys are missing or unexpected keys are provided.
        """
        if path is None:
            if self.is_per_input and input_file is None:
                raise MissingProductError(
                    f"Product {self.step_key!r} is per-input; provide input_file or path."
                )
            path = self.expected_path(input_file=input_file)

        arrays = self.encode(**arrays) if self.encode is not None else arrays

        save_npz_dict(
            path,
            required_keys=self.required_keys,
            optional_keys=self.optional_keys,
            label=f"{self.step_key} product",
            **arrays,
        )

        self._cache.pop(str(Path(path)), None)
        return Path(path)

    def register(
        self,
        value: Path | list[Path] | None = None,
        *,
        input_file: Path | None = None,
    ) -> Path | list[Path]:
        """Register product path information in the active session.

        Parameters
        ----------
        value : :class:`pathlib.Path` or :class:`list` [:class:`pathlib.Path`] or :data:`None`, optional
            Path or path list to register. Singleton products may omit this
            argument, in which case :meth:`expected_path` is used. Per-input
            products must provide a list of paths.

        input_file : :class:`pathlib.Path` or :data:`None`, optional
            Raw input used to derive the default singleton path when ``value`` is
            omitted.

        Returns
        -------
        :class:`pathlib.Path` or :class:`list` [:class:`pathlib.Path`]
            Registered path or list of registered paths.

        Raises
        ------
        :class:`~grid_calibration.errors.MissingProductError`
            Raised when attempting to register a per-input product without an
            explicit path list.

        :class:`TypeError`
            Raised when the provided value does not match the product kind.

        Notes
        -----
        Registration updates
        :attr:`~grid_calibration.gui.session.CalibrationSession.products`; it
        does not save data and does not validate file contents.
        """
        if value is None:
            if self.is_per_input:
                raise MissingProductError(
                    f"Product {self.step_key!r} is per-input; provide a list of paths."
                )
            value = self.expected_path(input_file=input_file)

        from ..session import get_session

        if self.is_singleton:
            if isinstance(value, list):
                raise TypeError(f"{self.step_key!r} is singleton; expected Path.")
            path = Path(value)
            get_session().set(self.step_key, path)
            return path

        if not isinstance(value, list):
            raise TypeError(f"{self.step_key!r} is per-input; expected list[Path].")

        paths = [Path(p) for p in value]
        get_session().set(self.step_key, paths)
        return paths

    def clear_cache(self) -> None:
        """Clear all cached loaded products for this IO object.

        Returns
        -------
        :data:`None`
            This method mutates the internal cache in place.
        """
        self._cache.clear()


def _existing_product_paths(
    product: ProductIO,
    input_files: list[Path],
    output_dir: Path,
) -> Path | list[Path] | None:
    """Return existing product paths without deciding availability.

    Parameters
    ----------
    product : :class:`~grid_calibration.gui.workflow.product_io.ProductIO`
        Product definition used to compute expected paths.

    input_files : :class:`list` [:class:`pathlib.Path`]
        Raw input files for the current session.

    output_dir : :class:`pathlib.Path`
        Directory where products are expected.

    Returns
    -------
    :class:`pathlib.Path` or :class:`list` [:class:`pathlib.Path`] or :data:`None`
        Existing singleton path, list of existing per-input paths, or
        :data:`None` when a singleton product is absent.

    Raises
    ------
    :class:`~grid_calibration.errors.PipelineStepError`
        Raised when ``product.kind`` is unsupported.
    """
    if product.kind is ProductKind.SINGLETON:
        path = output_dir / product.relative_path(input_files[0])
        return path if path.exists() else None

    if product.kind is ProductKind.PER_INPUT:
        return [
            output_dir / product.relative_path(infile)
            for infile in input_files
            if (output_dir / product.relative_path(infile)).exists()
        ]

    raise PipelineStepError(
        f"Unsupported product kind for step {product.step_key!r}: {product.kind!r}"
    )


def _product_is_complete(
    value: Path | list[Path] | None,
    product: ProductIO,
    *,
    n_inputs: int,
) -> bool:
    """Return whether a discovered product set is complete.

    Parameters
    ----------
    value : :class:`pathlib.Path` or :class:`list` [:class:`pathlib.Path`] or :data:`None`
        Candidate product path or path list returned by
        :func:`_existing_product_paths`.

    product : :class:`~grid_calibration.gui.workflow.product_io.ProductIO`
        Product definition used to interpret ``value``.

    n_inputs : :class:`int`
        Number of raw inputs expected for the session.

    Returns
    -------
    :class:`bool`
        ``True`` for existing singleton products and for per-input products with
        exactly one product per raw input.

    Raises
    ------
    :class:`~grid_calibration.errors.PipelineStepError`
        Raised when ``product.kind`` is unsupported.
    """
    if product.kind is ProductKind.SINGLETON:
        return value is not None

    if product.kind is ProductKind.PER_INPUT:
        return isinstance(value, list) and len(value) == n_inputs

    raise PipelineStepError(
        f"Unsupported product kind for step {product.step_key!r}: {product.kind!r}"
    )


def discover_products(
    product_io_by_step: dict[str, ProductIO],
    input_files: Iterable[Path],
    output_dir: Path,
    *,
    ordered_steps: Iterable[str] | None = None,
    stop_at_first_missing: bool = False,
    warn_stale: bool = False,
) -> dict[str, Any]:
    """Discover existing products for a calibration session.

    Parameters
    ----------
    product_io_by_step : :class:`dict` [:class:`str`, :class:`~grid_calibration.gui.workflow.product_io.ProductIO`]
        Mapping from workflow step key to product definition. Entries with
        :data:`None` values are ignored.

    input_files : :class:`collections.abc.Iterable` [:class:`pathlib.Path`]
        Raw files for the current session. At least one input is required
        because singleton product names are derived from the first raw input.

    output_dir : :class:`pathlib.Path`
        Directory where products are expected.

    ordered_steps : :class:`collections.abc.Iterable` [:class:`str`] or :data:`None`, optional
        Explicit pipeline order. When omitted, the insertion order of
        ``product_io_by_step`` is used.

    stop_at_first_missing : :class:`bool`, optional
        If ``True``, discovery stops registering products after the first
        missing or incomplete step. Products found downstream are treated as
        stale and are not returned. This is the safety-net mode used by
        :meth:`~grid_calibration.gui.session.CalibrationSession.from_inputs`
        and :meth:`~grid_calibration.gui.session.CalibrationSession.refresh_products`.

    warn_stale : :class:`bool`, optional
        If ``True``, log warnings when downstream products are found after an
        earlier step is missing or incomplete.

    Returns
    -------
    :class:`dict` [:class:`str`, :class:`typing.Any`]
        Mapping from step key to discovered product path information. Singleton
        products are represented as :class:`pathlib.Path` or :data:`None`.
        Per-input products are represented as a list of paths. Incomplete
        per-input product sets are returned as an empty list and are not treated
        as available.

    Raises
    ------
    :class:`~grid_calibration.errors.PipelineStepError`
        Raised when ``input_files`` is empty or when a product uses an
        unsupported :class:`ProductKind`.

    Notes
    -----
    The function separates two questions:

    * whether a product file exists on disk, and
    * whether that product should be registered as usable.

    A per-input step is usable only when all expected files exist. In
    dependency-aware mode, enabled with ``stop_at_first_missing=True``,
    discovery will also ignore downstream products once an earlier required
    step is unavailable. This prevents stale products from later workflow stages
    from making the GUI appear to be in a valid state when an upstream product
    has been deleted.
    """
    input_files = [Path(p) for p in input_files]

    if not input_files:
        raise PipelineStepError(
            "discover_products requires at least one input file."
        )

    output_dir = Path(output_dir)
    step_order = list(ordered_steps) if ordered_steps is not None else list(product_io_by_step)
    results: dict[str, Any] = {}
    blocked_by: str | None = None

    for step_key in step_order:
        product = product_io_by_step.get(step_key)

        if product is None:
            continue

        value = _existing_product_paths(product, input_files, output_dir)
        complete = _product_is_complete(value, product, n_inputs=len(input_files))

        if blocked_by is not None:
            if warn_stale and value:
                logger.warning(
                    "Ignoring stale product(s) for step %r because earlier step %r "
                    "is missing or incomplete.",
                    step_key,
                    blocked_by,
                )
            continue

        if complete:
            results[step_key] = value
            continue

        if product.kind is ProductKind.PER_INPUT and value:
            logger.warning(
                "Ignoring incomplete per-input product set for step %r: found %d/%d.",
                step_key,
                len(value),
                len(input_files),
            )

        results[step_key] = [] if product.kind is ProductKind.PER_INPUT else None

        if stop_at_first_missing:
            blocked_by = step_key

    return results
