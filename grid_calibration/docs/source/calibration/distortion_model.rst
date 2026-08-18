Distortion Model for Fisheye Polar Grid Calibration
===================================================

Overview
--------

This module implements a distortion model for fisheye camera calibration
using a polar calibration grid composed of concentric circles and radial spokes.

The goal of this model is to:

- Recover the **distortion center** (≈ optical center / FoV center)
- Map pixel coordinates → angular coordinates
- Accurately describe **anisotropic distortions** across the field

The calibration is performed using a set of grid intersection points with known
nominal polar coordinates.

.. note::

   The model is intentionally **non-physical** (i.e., not tied to a specific lens model),
   and instead uses a flexible orthogonal basis to capture real-world distortions.

---

Data Model
----------

Each calibration point contains:

- Measured pixel coordinates:
  - ``pixel_x``, ``pixel_y``

- Measured polar coordinates (from approximate center):
  - ``r`` (pixels)
  - ``theta`` (degrees)

- Nominal grid coordinates:
  - ``nominal_r`` (degrees)
  - ``nominal_theta`` (degrees)

These are stored in a ``.npz`` file under the ``data`` key.

---

Motivation and Design Choices
-----------------------------

Why not a simple model?
~~~~~~~~~~~~~~~~~~~~~~~

Initial attempts using:

- symmetric radial distortion
- ellipse / decentering models

failed because:

- distortions are **anisotropic**
- distortions vary with **radius and angle**
- residuals showed clear **harmonic structure**

Conclusion:

→ A more flexible, orthogonal basis is required.

---

Why a Polar Harmonic Model?
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The distortion field naturally decomposes into:

- **radial component** (along rays)
- **tangential component** (perpendicular to rays)

This motivates modeling:

.. math::

   d_r(s, \phi), \quad d_{\mathrm{tan}}(s, \phi)

using a Fourier-polynomial basis.

Advantages:

- Matches physical intuition of distortions
- Separates radial and angular effects
- Orthogonal basis → stable fitting

---

Model Definition
----------------

Coordinates
~~~~~~~~~~~

Let:

- :math:`u = r_{\mathrm{nom}}` in radians
- :math:`s = r_{\mathrm{nom}} / r_{\max}`
- :math:`\phi = \theta_{\mathrm{nom}} + \theta_0`

where:

- :math:`\theta_0` is a global rotation offset

---

1. Symmetric Radial Model
~~~~~~~~~~~~~~~~~~~~~~~~~

We first model an ideal radial mapping:

.. math::

   \rho(u) = k_1 u + k_2 u^2 + \dots + k_N u^N

This captures the dominant fisheye behavior:

- approximately equidistant: :math:`r \propto \theta`
- with higher-order corrections

---

2. Harmonic Distortion Field
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

We introduce corrections:

.. math::

   d_r(s, \phi) = \sum_{m,n} a_{m,n} \, s^m \cos(n\phi), \sin(n\phi)

.. math::

   d_{\mathrm{tan}}(s, \phi) = \sum_{m,n} b_{m,n} \, s^m \cos(n\phi), \sin(n\phi)

where:

- :math:`m` controls radial variation
- :math:`n` controls angular harmonics

---

3. Final Mapping
~~~~~~~~~~~~~~~~

The predicted pixel coordinates are:

.. math::

   x = c_x + (\rho + d_r)\cos\phi - d_{\mathrm{tan}}\sin\phi

.. math::

   y = c_y + (\rho + d_r)\sin\phi + d_{\mathrm{tan}}\cos\phi

where:

- :math:`(c_x, c_y)` is the distortion center

---

Fitting Procedure
-----------------

The model is fit in **three stages**.

Stage 1 — Symmetric Fit
~~~~~~~~~~~~~~~~~~~~~~~

- Fit only :math:`\rho(u)`
- Ignore harmonic terms

Purpose:

- establish stable radial baseline
- estimate center and rotation

---

Stage 2 — Full Harmonic Fit
~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Fit full model including:

  - radial distortion
  - tangential distortion

- Uses robust loss:

  - ``soft_l1``

Purpose:

- capture anisotropic structure

---

Stage 3 — Outlier Rejection
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Outliers are identified using:

.. math::

   \text{threshold} = \mathrm{median} + \sigma \cdot \mathrm{MAD}

Then:

- remove outliers
- refit model on inliers only

Purpose:

- remove contaminated grid detections
- stabilize final solution

---

Key Implementation Details
--------------------------

Parameterization
~~~~~~~~~~~~~~~~

The parameter vector includes:

- Center: ``cx, cy``
- Rotation: ``theta0``
- Radial coefficients: ``k1, k2, ...``
- Harmonic coefficients:

  - ``dr_mn_cos``, ``dr_mn_sin``
  - ``dtan_mn_cos``, ``dtan_mn_sin``

---

Regularization
~~~~~~~~~~~~~~

A ridge penalty is applied:

.. math::

   \lambda \sum p_i^2

Purpose:

- prevent overfitting
- stabilize high-order terms

---

Diagnostics
-----------

The script generates a multi-page PDF including:

- Residual maps
- Vector fields
- Radial / tangential decomposition
- Residual vs radius
- Histograms
- Outlier visualization

These are essential to validate:

- model correctness
- absence of structure in residuals
- absence of overfitting

---

Key Challenges Encountered
--------------------------

1. Incorrect Nominal Grid Assignment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Early fits were degraded by:

- systematic offset in nominal circle indexing

Lesson:

→ Calibration depends critically on **correct labeling**

---

2. Center Singularity
~~~~~~~~~~~~~~~~~~~~~

Using polar coordinates introduces:

- instability near :math:`r = 0`

Mitigation:

- rely on pixel-space fitting
- bootstrap inner regions carefully

---

3. Anisotropic Distortions
~~~~~~~~~~~~~~~~~~~~~~~~~~

Simple models failed because:

- distortions vary with angle
- not well-described by ellipses

Solution:

→ harmonic basis

---

4. Outliers at Outer Radii
~~~~~~~~~~~~~~~~~~~~~~~~~~

Outer grid regions contain:

- contamination
- misidentified points

Solution:

→ robust loss + explicit outlier rejection

---

Why This Model Was Chosen
-------------------------

We tested:

- symmetric radial models
- ellipse + decentering
- direct cartesian polynomial fits

Final choice:

**polar harmonic model**, because:

- best residuals
- physically interpretable
- stable across full field
- flexible but controlled

---

Outputs
-------

The final modeling stage produces:

- ``*_modeling_results.npz`` for workflow recovery and rich Python diagnostics,
- ``*_calibration.npz`` as the stable plain-data calibration artifact,
- and optionally ``*_modeling_report.pdf`` for visual diagnostics.

The portable calibration artifact can be consumed through
:class:`grid_calibration.GridCalibration`,
:func:`grid_calibration.angle_to_pixel`, and
:func:`grid_calibration.pixel_to_angle`.
  - fitted parameters
  - predicted coordinates
  - residuals

- ``*_distortion_report_polar.pdf``
  - diagnostic plots

- ``*_summary.json``
  - compact fit summary

---

Fit Summary
-----------

.. image:: figures/01_summary.png
   :width: 80%
   :align: center

The model achieves sub-pixel accuracy after outlier rejection:

- RMS ≈ 0.7 px (inliers)
- Median ≈ 0.58 px
- Only a handful of outliers removed

---

Pixel-Space Residuals
---------------------

.. image:: figures/02_residual_map_pixel_space.png
   :width: 80%
   :align: center

Residuals are spatially uniform, with slightly larger errors near the outer edge,
where contamination and detection errors are more likely.

---

Residuals in Nominal Space
--------------------------

.. image:: figures/03_residuals_nominal_space.png
   :width: 90%
   :align: center

Before correction (left), strong structured residuals are present.

After applying the full model (right), residuals are nearly eliminated,
confirming that the distortion is well captured.

---

Residual Vector Fields
----------------------

.. image:: figures/04_residual_vector_fields.png
   :width: 90%
   :align: center

The symmetric model leaves large coherent distortions.
The full model removes these patterns almost entirely.

---

Radial and Tangential Components
--------------------------------

.. image:: figures/05_radial_tangential_components.png
   :width: 90%
   :align: center

Residuals decompose naturally into:

- radial component (dominant)
- tangential component (smaller but structured)

The fitted correction fields (bottom panels) match these patterns closely.

---

Residuals vs Radius
-------------------

.. image:: figures/06_residuals_vs_radius.png
   :width: 90%
   :align: center

Key observations:

- Residuals are small across most of the field
- Outliers appear primarily at large radii
- Threshold-based rejection is effective

---

Residual Distributions
----------------------

.. image:: figures/07_residual_histograms.png
   :width: 90%
   :align: center

The full model significantly reduces the residual spread.

---

Residuals vs Angle
------------------

.. image:: figures/08_residuals_vs_theta.png
   :width: 90%
   :align: center

Residuals show minimal angular dependence after correction,
indicating that azimuthal distortions are properly modeled.

---

Distortion Magnitude
--------------------

.. image:: figures/09_distortion_magnitude_pixel_space.png
   :width: 80%
   :align: center

The distortion magnitude increases smoothly with radius,
as expected for a fisheye system.

---

Model-Predicted Grid Overlay
----------------------------

.. image:: figures/10_predicted_grid_overlay_pixel_space.png
   :width: 80%
   :align: center

The predicted grid aligns extremely well with measured points,
validating the forward model.

---

Undistorted Grid Check
----------------------

.. image:: figures/11_undistorted_nominal_grid_check.png
   :width: 80%
   :align: center

When mapped back to nominal coordinates, the grid becomes nearly perfect,
confirming the correctness of the inversion.

---

