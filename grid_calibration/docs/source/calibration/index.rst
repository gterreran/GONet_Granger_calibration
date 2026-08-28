Calibration Model
=================

This section documents the final geometric calibration model produced by Grid
Calibration.

The modeling details are not required to operate the GUI, but they are central
to understanding what the exported calibration represents, why the current
model is comparatively high dimensional, and how its accuracy should be
interpreted.

For the operational workflow that produces the model, see
:doc:`../walkthrough/pipeline/modeling_results`.

Model documentation
-------------------

.. toctree::
   :maxdepth: 2

   distortion_model
   model_components

A useful reading order is:

#. :doc:`model_components` for a visual, geometric explanation of each model
   component and why the current default contains 159 fitted parameters.
#. :doc:`distortion_model` for the mathematical parameterization, fitting
   procedure, regularization, validation strategy, and exported products.

What the calibration is referenced to
--------------------------------------

Grid Calibration is currently anchored to a polar grid projected onto the dome
of the **Grainger Sky Theater at the Adler Planetarium**.  The nominal rings and
spokes of that projected pattern are treated as the angular reference used by
the fit.

That reference is extremely useful because it provides dense, repeatable
sampling across most of the camera field, but it should not be confused with a
perfect metrological standard.  Small projector alignment errors, projection
geometry, local dome imperfections, or other departures from the ideal nominal
pattern can all become part of the measured mapping.

This matters especially for the current flexible model: if a repeatable feature
belongs to the projected grid rather than to the camera optics, the calibration
has no way to distinguish the two.  It can faithfully absorb that feature and
then propagate it into downstream pixel-to-angle coordinates.

Star-tracking validation has already provided evidence that the projected grid
is not a perfectly ideal absolute reference.  At present, however, there is no
comparably dense and practical independent reference that samples the entire
fisheye field.  A direct stellar calibration would be attractive because the
sky supplies an external angular standard, but obtaining sufficiently dense,
unobstructed star coverage across the full field---especially toward the
horizon---is operationally difficult.

A likely long-term direction is therefore a **hybrid calibration**:

* use the projected grid for dense and repeatable full-field constraints;
* use stars as an independent absolute check and, where practical, an
  additional geometric constraint;
* separate camera distortion from reference-grid systematics as far as the two
  datasets allow.

The detailed model pages return to this limitation when discussing the meaning
of the fitted coefficients and the interpretation of residuals.
