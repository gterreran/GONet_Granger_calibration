# Grid calibration tests

Run the fast suite from the parent folder of `grid_calibration/`:

```bash
python -m pytest grid_calibration/tests
```

## Optional real-data tests

Real-data tests are skipped unless you point them at input images:

```bash
export GRID_CALIBRATION_REALDATA_GLOB='../data/GONet/Grainger/new/202/after_focus_new_calibration/*.jpg'
python -m pytest grid_calibration/tests -m realdata
```

To check products that already exist in an output directory:

```bash
export GRID_CALIBRATION_REALDATA_OUTDIR='grid_calibration_output'
python -m pytest grid_calibration/tests -m realdata --realdata-report -s
```

The report lists each registered product step, how many products were discovered, and whether at least one product can be loaded.

To make missing products fail the test instead of merely appearing in the report:

```bash
python -m pytest grid_calibration/tests -m realdata \
  --realdata-report -s \
  --realdata-require-products=full-array,grid-points,averaged-grid
```

or require every registered product:

```bash
python -m pytest grid_calibration/tests -m realdata \
  --realdata-report -s \
  --realdata-require-products=all
```

You can also use the environment variable equivalent:

```bash
export GRID_CALIBRATION_REQUIRE_REALDATA_PRODUCTS='full-array,grid-points'
```

To run the slow real pipeline smoke test:

```bash
export GRID_CALIBRATION_RUN_REAL_PIPELINE=1
python -m pytest grid_calibration/tests -m 'realdata and slow'
```

### Optional real-data quality checks

Once `GRID_CALIBRATION_REALDATA_GLOB` and `GRID_CALIBRATION_REALDATA_OUTDIR` are set,
the `realdata` marker also runs lightweight quality assertions against existing
products. These checks are intentionally loose by default: they catch missing,
empty, malformed, or wildly poor products without acting as final science-grade
regression tests.

Useful options:

```bash
python -m pytest grid_calibration/tests -m realdata --realdata-report -s \
  --realdata-min-grid-points=100 \
  --realdata-min-averaged-points=100 \
  --realdata-min-nominal-records=100 \
  --realdata-max-model-rms=20
```

The same thresholds can be set with environment variables:

- `GRID_CALIBRATION_REALDATA_MIN_GRID_POINTS`
- `GRID_CALIBRATION_REALDATA_MIN_AVERAGED_POINTS`
- `GRID_CALIBRATION_REALDATA_MIN_NOMINAL_RECORDS`
- `GRID_CALIBRATION_REALDATA_MAX_MODEL_RMS`
