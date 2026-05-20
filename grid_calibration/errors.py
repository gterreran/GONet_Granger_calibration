# grid_calibration/errors.py
"""
Exception hierarchy for :mod:`grid_calibration`.

All package-specific exceptions inherit from :class:`GridCalibrationError`.
Catching this base class allows callers to handle expected calibration,
workflow, product-IO, and modeling failures without accidentally suppressing
unrelated Python exceptions.

The subclasses are intentionally grouped by failure domain:

``MissingProductError``
    A required product path is not registered or does not exist.

``ProductLoadError`` and ``ProductSaveError``
    Product serialization or deserialization failed.

``PipelineStepError``
    A workflow step could not be configured or executed correctly.

``DetectionError``
    Grid-point, ring, spoke, or nominal-assignment detection failed.

``ModelingError``
    Distortion-model fitting or evaluation failed.

``InvalidCalibrationError``
    A completed calibration result is internally inconsistent or otherwise
    unusable.
"""


class GridCalibrationError(Exception):
    """
    Base exception for the :mod:`grid_calibration` package.

    This class is the common ancestor for all expected, package-specific
    exceptions. It is useful at API boundaries where callers want to catch
    errors raised by the calibration workflow while allowing unrelated
    exceptions to propagate.

    Parameters
    ----------
    *args : :class:`object`
        Positional arguments passed to :class:`Exception`.

    Returns
    -------
    :class:`GridCalibrationError`
        Exception instance.
    """


class MissingProductError(GridCalibrationError):
    """
    Raised when a required pipeline product is missing.

    Typical sources include missing files on disk, unavailable session
    registrations, or attempts to load a per-input product without specifying
    which input product should be used.

    Parameters
    ----------
    *args : :class:`object`
        Positional arguments passed to :class:`GridCalibrationError`.

    Returns
    -------
    :class:`MissingProductError`
        Exception instance.
    """


class ProductLoadError(GridCalibrationError):
    """
    Raised when a pipeline product cannot be loaded or parsed.

    This error is used when a product file exists but cannot be read, does not
    contain the schema expected by
    :class:`~grid_calibration.gui.workflow.product_io.ProductIO`, or cannot be
    decoded into the semantic object expected by the caller.

    Parameters
    ----------
    *args : :class:`object`
        Positional arguments passed to :class:`GridCalibrationError`.

    Returns
    -------
    :class:`ProductLoadError`
        Exception instance.
    """


class ProductSaveError(GridCalibrationError):
    """
    Raised when a pipeline product cannot be saved.

    This error is used for schema validation failures before writing, filesystem
    errors during writing, or failures in product encoding before data are passed
    to the low-level NPZ writer.

    Parameters
    ----------
    *args : :class:`object`
        Positional arguments passed to :class:`GridCalibrationError`.

    Returns
    -------
    :class:`ProductSaveError`
        Exception instance.
    """


class InvalidCalibrationError(GridCalibrationError):
    """
    Raised when calibration results are invalid or inconsistent.

    This exception is intended for products or results that were produced
    successfully but fail later consistency checks, such as incompatible
    dimensions, missing required calibration fields, or physically implausible
    fitted values.

    Parameters
    ----------
    *args : :class:`object`
        Positional arguments passed to :class:`GridCalibrationError`.

    Returns
    -------
    :class:`InvalidCalibrationError`
        Exception instance.
    """


class PipelineStepError(GridCalibrationError):
    """
    Raised when a pipeline step cannot be configured or executed.

    This exception covers workflow-level failures, such as missing raw inputs,
    invalid step specifications, unsupported product kinds, or other errors that
    prevent a step from being run as part of the GUI pipeline.

    Parameters
    ----------
    *args : :class:`object`
        Positional arguments passed to :class:`GridCalibrationError`.

    Returns
    -------
    :class:`PipelineStepError`
        Exception instance.
    """


class DetectionError(GridCalibrationError):
    """
    Raised when grid detection or assignment fails.

    This exception is used by detection-oriented steps when they cannot identify
    enough reliable grid points, ring fragments, spoke fragments, nominal labels,
    or bootstrapped assignments to continue safely.

    Parameters
    ----------
    *args : :class:`object`
        Positional arguments passed to :class:`GridCalibrationError`.

    Returns
    -------
    :class:`DetectionError`
        Exception instance.
    """


class ModelingError(GridCalibrationError):
    """
    Raised when model fitting or model evaluation fails.

    This exception is intended for errors in the distortion-modeling stage, such
    as invalid model parameters, failed optimization, malformed fit inputs, or
    impossible prediction/evaluation states.

    Parameters
    ----------
    *args : :class:`object`
        Positional arguments passed to :class:`GridCalibrationError`.

    Returns
    -------
    :class:`ModelingError`
        Exception instance.
    """
