import logging
from collections import deque

FULL_ARRAY_LOGGER = "GONet_Wizard.GONet_utils.src.gonet.analysis_utils.full_array"


class DashLogHandler(logging.Handler):
    def __init__(self, max_entries: int = 5000) -> None:
        super().__init__()
        self.buffer = deque(maxlen=max_entries)

    def emit(self, record: logging.LogRecord) -> None:
        self.buffer.append(self.format(record))

    def get_logs(self) -> str:
        return "\n".join(self.buffer)

    def clear(self) -> None:
        self.buffer.clear()


global_log_handler = DashLogHandler()


def configure_gui_logging(level=logging.INFO) -> None:
    """
    Attach DashLogHandler to the full_array module logger (and optionally its parents),
    without modifying full_array.py.
    """
    global_log_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

    # 1) Intercept the exact logger used by full_array.py
    fa_logger = logging.getLogger(FULL_ARRAY_LOGGER)
    fa_logger.setLevel(level)

    # IMPORTANT: remove any handlers attached to that logger
    fa_logger.handlers.clear()

    # Route ONLY to our handler
    fa_logger.addHandler(global_log_handler)

    # IMPORTANT: stop propagation to root (prevents terminal duplication)
    fa_logger.propagate = False
