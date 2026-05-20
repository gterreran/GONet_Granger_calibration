Modeling Results
================

The modeling-results step fits the final fisheye distortion model using the
dense bootstrapped calibration grid.

This is the final stage of the calibration workflow.

Overview
--------

The previous stages progressively transformed the raw calibration images into a
dense set of correspondences between:

- measured image coordinates,
- measured polar coordinates,
- and ideal nominal grid coordinates.

The goal of the modeling stage is to fit a smooth parametric distortion model
that maps between the ideal grid geometry and the observed fisheye projection.

Interactive Initialization
--------------------------

When the step begins, the GUI displays the bootstrapped grid together with the
modeling controls.

.. image:: figures/Step_7_1.png
   :width: 100%
   :align: center

The side panel exposes the main fitting parameters.

Unlike earlier stages, this step focuses primarily on numerical optimization and
diagnostic analysis rather than geometric editing.

Inputs
------

This step consumes the singleton bootstrapped-grid product.

Typical input product:

.. code-block:: text

    *_bootstrapped_grid.npz

Outputs
-------

This step generates one singleton modeling-results product.

Typical output product:

.. code-block:: text

    *_modeling_results.npz

Optionally, a PDF diagnostic report may also be generated:

.. code-block:: text

    *_modeling_report.pdf

The output product stores:

- the fitted model parameters,
- residual diagnostics,
- inlier masks,
- predicted model coordinates,
- optimization summaries,
- and the fitting configuration used.

Goal of the Modeling Stage
--------------------------

The calibration target provides known nominal geometry.

The measured fisheye image introduces distortions caused by:

- lens projection,
- optical misalignment,
- detector offsets,
- asymmetric distortions,
- and higher-order optical effects.

The modeling stage estimates a smooth transformation capable of reproducing the
observed projection geometry.

High-Level Strategy
-------------------

The fitting procedure models the distortion as a combination of:

- a radial distortion model,
- harmonic azimuthal perturbations,
- and global geometric alignment terms.

The workflow then optimizes the model parameters to minimize the residual
distance between:

- measured calibration points,
- and model-predicted positions.

The fitting routines are implemented in the modeling processing package:

``model.py``
    Core parametric distortion model definitions.

``fitting.py``
    Numerical optimization and iterative fitting logic.

``data.py``
    Construction of fitting datasets and residual structures.

``results.py``
    Containers for optimization outputs and diagnostics.

``reporting.py``
    PDF report generation and summary visualization.

``pipeline.py``
    High-level orchestration of the full fitting workflow.

Radial Distortion Model
-----------------------

The dominant fisheye behavior is modeled through a radial distortion expansion.

The parameter:

``Radial degree``

controls the polynomial complexity of the radial distortion model.

Higher degrees allow the model to capture more complex radial behavior but may
increase the risk of overfitting.

Harmonic Distortion Terms
-------------------------

Real optical systems are rarely perfectly radially symmetric.

To capture asymmetric distortions, the workflow includes harmonic perturbation
terms.

Two parameters control this behavior:

``Harmonic radial degree``
    Controls the radial complexity of the harmonic corrections.

``Harmonic order``
    Controls the angular harmonic order included in the model.

These terms allow the fit to model effects such as:

- asymmetric lens distortions,
- decentering,
- optical tilt,
- mechanical misalignment.

Outlier Rejection
-----------------

The fitting pipeline includes iterative sigma clipping to reject problematic
points.

The parameter:

``Sigma rejection``

controls the clipping threshold.

Points with residuals exceeding the threshold are excluded from later fitting
iterations.

This improves robustness against:

- incorrect propagated assignments,
- residual false detections,
- local image artifacts,
- unstable outer-edge points.

Optimization Procedure
----------------------

The fitting proceeds iteratively:

1. construct the fitting dataset,
2. evaluate the current distortion model,
3. compute residuals,
4. reject outliers,
5. update the model parameters,
6. repeat until convergence.

The numerical optimization minimizes the residual separation between measured
and predicted point locations.

The fitting system stores both:

- the symmetric radial-only solution,
- and the full harmonic solution.

Generating the Model
--------------------

Once the parameters are configured, the user clicks:

.. code-block:: text

    Model grid

The optimization may require noticeable processing time depending on:

- model complexity,
- number of calibration points,
- harmonic order,
- outlier rejection settings.

The log window reports the fitting progress and parameter evolution. 

Optional PDF Report
-------------------

The GUI optionally generates a PDF diagnostic report.

This behavior is controlled through the:

.. code-block:: text

    Generate PDF report

checkbox.

The report includes:

- residual statistics,
- parameter summaries,
- inlier diagnostics,
- distortion visualizations,
- and fit-quality metrics.

The callbacks explicitly invoke the reporting pipeline only when the PDF option
is enabled. 

Final Diagnostic Visualization
------------------------------

Once the fitting completes, the GUI displays the residual diagnostics.

.. image:: figures/Step_7_2.png
   :width: 100%
   :align: center

The visualization shows:

- the fitted calibration grid,
- residual magnitudes,
- spatial residual distribution,
- outlier locations.

Residuals are color-coded by magnitude.

Outliers rejected during fitting are highlighted explicitly.

Interpreting the Residual Map
-----------------------------

The residual plot is one of the most important validation tools in the entire
workflow.

A good fit generally shows:

- small residuals across most of the field,
- smooth spatial behavior,
- no large coherent structures,
- limited edge instability,
- few extreme outliers.

Large coherent residual patterns may indicate:

- insufficient model complexity,
- incorrect nominal assignments,
- poor center selection,
- incomplete bootstrapping,
- or physical optical asymmetries not captured by the model.

What a Good Result Looks Like
-----------------------------

A good final solution generally has:

- low median residuals,
- low maximum residuals,
- smooth residual distribution,
- stable harmonic structure,
- and only a small number of rejected outliers.

Residuals should remain visually small compared to the grid spacing.

Final Calibration Product
-------------------------

Once the fit completes successfully, the modeling-results product is written to
disk and registered automatically in the calibration session. 

Additional Documentation
------------------------

A more detailed mathematical description of the distortion model is available
in:

.. toctree::
   :maxdepth: 1

   ../../calibration/distortion_model

This supplemental document focuses specifically on the mathematical formulation
of the fisheye distortion parameterization and fitting methodology.

End of the Pipeline
-------------------

This is the final workflow stage.

The resulting distortion model can now be used for:

- fisheye calibration,
- coordinate reconstruction,
- astrometric projection,
- image reprojection,
- and downstream scientific analysis.