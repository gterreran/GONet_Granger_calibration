# grid_calibration/gui/workflow/product_io.py

from __future__ import annotations

from enum import Enum, auto
import logging
from pathlib import Path
from typing import Any, Iterable, Callable

from ...errors import MissingProductError, PipelineStepError
from .io_helpers import load_npz_dict, save_npz_dict


logger = logging.getLogger(__name__)

EncodeFunc = Callable[..., dict[str, Any]]
DecodeFunc = Callable[[dict[str, Any]], Any]


class ProductKind(Enum):
    PER_INPUT = auto()
    SINGLETON = auto()


class ProductIO:
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
        return self.kind is ProductKind.SINGLETON

    @property
    def is_per_input(self) -> bool:
        return self.kind is ProductKind.PER_INPUT

    def relative_path(self, input_file: Path) -> Path:
        input_file = Path(input_file)

        if self.is_singleton:
            root = "_".join(input_file.stem.split("_")[:3])
            return Path(f"{root}{self.suffix}")

        return Path(f"{input_file.stem}{self.suffix}")

    def expected_path(self, input_file: Path | None = None) -> Path:
        from ..session import get_session

        session = get_session()

        if self.is_per_input and input_file is None:
            raise MissingProductError(
                f"Product {self.step_key!r} is per-input; provide input_file."
            )

        input_file = input_file or session.first_raw_file
        return session.output_dir / self.relative_path(input_file)

    def get(self) -> Path | list[Path] | None:
        """
        Return the currently registered product path(s).

        Returns
        -------
        Path | list[Path] | None
            For singleton products, returns ``Path`` or ``None``.
            For per-input products, returns ``list[Path]``.
        """
        from ..session import get_session

        value = get_session().get(self.step_key)

        if self.is_singleton:
            return None if value is None else Path(value)

        return [Path(p) for p in (value or [])]

    def require(self) -> Path | list[Path]:
        """
        Return the currently registered product path(s), raising if missing.
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
        """
        Load an NPZ product.

        For singleton products, ``path`` may be omitted.
        For per-input products, ``path`` should usually be provided.
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
        """
        Load one per-input product by index.
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
        self._cache.clear()


def _existing_product_paths(
    product: ProductIO,
    input_files: list[Path],
    output_dir: Path,
) -> Path | list[Path] | None:
    """
    Return existing product path(s), without deciding whether the step is usable.
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
    """
    Return whether a discovered product should be registered as available.
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
    """
    Discover existing products for a calibration session.

    Parameters
    ----------
    product_io_by_step : dict
        Mapping from step key to :class:`ProductIO`.
    input_files : iterable of :class:`pathlib.Path`
        Raw files for the current session.
    output_dir : :class:`pathlib.Path`
        Directory where products are expected.
    ordered_steps : iterable of str, optional
        Explicit pipeline order. When omitted, the mapping insertion order is
        used.
    stop_at_first_missing : bool, optional
        If ``True``, discovery stops registering products after the first
        missing or incomplete step. Products found downstream are treated as
        stale and are not returned.
    warn_stale : bool, optional
        If ``True``, log warnings for downstream products found after the first
        missing or incomplete step.

    Returns
    -------
    dict
        Mapping from step key to registered product path(s). For per-input
        products, a step is registered only when all expected per-input files
        exist.
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
