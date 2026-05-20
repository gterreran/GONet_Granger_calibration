from __future__ import annotations


def pytest_addoption(parser):
    parser.addoption(
        "--realdata-report",
        action="store_true",
        default=False,
        help="Print a summary of real-data product discovery/loading checks.",
    )
    parser.addoption(
        "--realdata-require-products",
        action="store",
        default=None,
        metavar="STEPS",
        help=(
            "Require real-data products to exist and load. Use 'all' or a comma-separated "
            "list of step keys, e.g. full-array,grid-points,averaged-grid."
        ),
    )
    parser.addoption(
        "--realdata-min-grid-points",
        action="store",
        default=None,
        metavar="N",
        help="Minimum detected points required in each real-data grid-points product.",
    )
    parser.addoption(
        "--realdata-min-averaged-points",
        action="store",
        default=None,
        metavar="N",
        help="Minimum points required in the real-data averaged/unwrapped grid products.",
    )
    parser.addoption(
        "--realdata-min-nominal-records",
        action="store",
        default=None,
        metavar="N",
        help="Minimum records required in real-data nominal/bootstrapped products.",
    )
    parser.addoption(
        "--realdata-max-model-rms",
        action="store",
        default=None,
        metavar="PX",
        help="Maximum acceptable modeling RMS in pixels for real-data quality checks.",
    )
