# grid_calibration/gui/workflow/product_io.py

from __future__ import annotations

from enum import Enum, auto
from pathlib import Path
from typing import Any, Iterable, Callable

from ...errors import MissingProductError, PipelineStepError
from .io_helpers import load_npz_dict, save_npz_dict


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


def discover_products(
    product_io_by_step: dict[str, ProductIO],
    input_files: Iterable[Path],
    output_dir: Path,
) -> dict[str, Any]:
    input_files = [Path(p) for p in input_files]

    if not input_files:
        raise PipelineStepError(
            "discover_products requires at least one input file."
        )

    output_dir = Path(output_dir)
    results: dict[str, Any] = {}

    for step_key, product in product_io_by_step.items():
        if product is None:
            continue

        if product.kind is ProductKind.SINGLETON:
            path = output_dir / product.relative_path(input_files[0])
            results[step_key] = path if path.exists() else None

        elif product.kind is ProductKind.PER_INPUT:
            paths = []

            for infile in input_files:
                path = output_dir / product.relative_path(infile)
                if path.exists():
                    paths.append(path)

            results[step_key] = paths

        else:
            raise PipelineStepError(
                f"Unsupported product kind for step {step_key!r}: {product.kind!r}"
            )

    return results