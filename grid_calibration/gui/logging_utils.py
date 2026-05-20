# grid_calibration/gui/logging_utils.py
"""
Logging helpers for the grid calibration GUI.

This module provides a small logging layer shared by the Dash callbacks,
processing steps, and GUI log window.  The key design goal is that application
logs are collected in one predictable place without globally hijacking every
third-party logger.

The GUI log window reads from :data:`global_log_handler`, while
:func:`log_step` uses a :class:`contextvars.ContextVar` to attach the current
workflow step key to log records emitted during step execution.
"""

from __future__ import annotations

import logging
from collections import deque
from contextlib import contextmanager
from contextvars import ContextVar
from threading import Lock
from typing import Iterator


# External logger used by GONet's full-array builder.  Keep it explicit so the
# GUI captures useful progress messages without opening the floodgates to all
# third-party logging.
FULL_ARRAY_LOGGER = "GONet_Wizard.GONet_utils.src.gonet.analysis_utils.full_array"
""":class:`str`: External logger name captured for full-array progress output."""

DEFAULT_EXTERNAL_LOGGERS = (FULL_ARRAY_LOGGER,)
"""tuple[str, ...]: External loggers routed into the GUI log window by default."""

_APP_LOGGER_NAME = __name__.split(".gui.", 1)[0]
_step_context: ContextVar[str] = ContextVar("grid_calibration_step", default="-")


class StepContextFilter(logging.Filter):
    """
    Add the active pipeline step to each log record.

    The formatter can safely use ``%(step_key)s`` even for records emitted by
    third-party libraries or by modules that do not know about the pipeline.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Ensure that ``record.step_key`` is available to the formatter.

        Parameters
        ----------
        record : :class:`logging.LogRecord`
            Record being processed by the logging system.

        Returns
        -------
        :class:`bool`
            Always ``True`` so the record remains eligible for emission.
        """
        if not hasattr(record, "step_key"):
            record.step_key = _step_context.get()
        return True


class DashLogHandler(logging.Handler):
    """
    In-memory log handler consumed by the Dash log window.

    Parameters
    ----------
    max_entries : :class:`int`, optional
        Maximum number of formatted log lines retained in the rolling buffer.
    """

    def __init__(self, max_entries: int = 5000) -> None:
        super().__init__()
        self.buffer: deque[str] = deque(maxlen=max_entries)
        self._lock = Lock()

    def emit(self, record: logging.LogRecord) -> None:
        """
        Format and append one log record to the in-memory buffer.

        Parameters
        ----------
        record : :class:`logging.LogRecord`
            Record emitted by a configured logger.

        Returns
        -------
        :class:`None`
            The internal buffer is modified in place.
        """
        try:
            message = self.format(record)
        except Exception:
            self.handleError(record)
            return

        with self._lock:
            self.buffer.append(message)

    def get_logs(self) -> str:
        """
        Return the complete buffered log text.

        Returns
        -------
        :class:`str`
            Buffered log messages joined by newline characters.
        """
        with self._lock:
            return "\n".join(self.buffer)

    def clear(self) -> None:
        """
        Clear the in-memory log buffer.

        Returns
        -------
        :class:`None`
            The internal buffer is emptied in place.
        """
        with self._lock:
            self.buffer.clear()


global_log_handler = DashLogHandler()
""":class:`DashLogHandler`: Shared handler read by the GUI log-window callback."""

_step_context_filter = StepContextFilter()


def _make_formatter() -> logging.Formatter:
    """
    Build the formatter used by the GUI log window.

    Returns
    -------
    :class:`logging.Formatter`
        Formatter that includes time, level, step key, and message.
    """
    return logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(step_key)s | %(message)s",
        datefmt="%H:%M:%S",
    )


def _attach_handler(logger: logging.Logger, *, level: int, propagate: bool) -> None:
    """
    Attach the shared GUI handler to one logger.

    Parameters
    ----------
    logger : :class:`logging.Logger`
        Logger to configure.
    level : :class:`int`
        Minimum log level for the logger.
    propagate : :class:`bool`
        Whether records should continue propagating to ancestor loggers.

    Returns
    -------
    :class:`None`
        The logger is modified in place.
    """
    logger.setLevel(level)

    if global_log_handler not in logger.handlers:
        logger.addHandler(global_log_handler)

    logger.propagate = propagate


def configure_gui_logging(
    level: int = logging.INFO,
    *,
    external_loggers: tuple[str, ...] = DEFAULT_EXTERNAL_LOGGERS,
    clear_existing: bool = False,
) -> None:
    """
    Configure logging for the GUI and Dash log window.

    Parameters
    ----------
    level : :class:`int`
        Minimum logging level captured by the GUI.
    external_loggers : tuple[str, ...]
        Non-package logger names that should also be routed to the GUI log
        window.  This is intentionally opt-in to avoid noisy dependency logs.
    clear_existing : :class:`bool`
        If ``True``, clear the GUI log buffer before attaching handlers.

    Returns
    -------
    :class:`None`
        Logging configuration is updated in place.
    """

    if clear_existing:
        global_log_handler.clear()

    global_log_handler.setLevel(level)
    global_log_handler.setFormatter(_make_formatter())

    if _step_context_filter not in global_log_handler.filters:
        global_log_handler.addFilter(_step_context_filter)

    # Capture all logs from this package through one package-level handler.
    app_logger = logging.getLogger(_APP_LOGGER_NAME)
    _attach_handler(app_logger, level=level, propagate=False)

    # Capture selected external loggers without routing all root logs into the UI.
    for logger_name in external_loggers:
        ext_logger = logging.getLogger(logger_name)
        ext_logger.handlers.clear()
        _attach_handler(ext_logger, level=level, propagate=False)

    # Keep root configured enough that warnings/errors are not dropped in debug
    # contexts, but do not attach the Dash handler to root.
    logging.getLogger().setLevel(min(level, logging.WARNING))


def silence_server_loggers() -> None:
    """
    Reduce routine Flask/Werkzeug/Dash startup chatter.

    Returns
    -------
    :class:`None`
        Known server loggers are set to :data:`logging.ERROR`.
    """

    for logger_name in ("werkzeug", "dash", "dash.dash", "flask.app"):
        logging.getLogger(logger_name).setLevel(logging.ERROR)


@contextmanager
def log_step(step_key: str) -> Iterator[None]:
    """
    Temporarily attach a pipeline step label to emitted log records.

    Parameters
    ----------
    step_key : :class:`str`
        Workflow step key to expose as ``record.step_key`` while the context is
        active.

    Returns
    -------
    collections.abc.Iterator[None]
        Context manager iterator used by :code:`with` statements.
    """

    token = _step_context.set(step_key)
    try:
        yield
    finally:
        _step_context.reset(token)
