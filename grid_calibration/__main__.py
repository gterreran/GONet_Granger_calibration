# grid_calibration/__main__.py
"""
Module execution entry point for :mod:`grid_calibration`.

This module keeps ``python -m grid_calibration`` working while delegating the
real command-line implementation to :mod:`grid_calibration.cli`.
"""

from __future__ import annotations

from .cli import main


if __name__ == "__main__":
    main()
