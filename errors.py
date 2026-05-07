# grid_calibration/errors.py

class GridCalibrationError(Exception):
    """
    Base exception for the grid_calibration package.
    """


class MissingProductError(GridCalibrationError):
    """
    Raised when a required pipeline product is missing.
    """


class ProductLoadError(GridCalibrationError):
    """
    Raised when a pipeline product cannot be loaded or parsed.
    """


class InvalidCalibrationError(GridCalibrationError):
    """
    Raised when calibration results are invalid or inconsistent.
    """


class PipelineStepError(GridCalibrationError):
    """
    Raised when a pipeline step fails.
    """


class DetectionError(GridCalibrationError):
    """
    Raised when grid detection fails.
    """


class ModelingError(GridCalibrationError):
    """
    Raised when model fitting or evaluation fails.
    """