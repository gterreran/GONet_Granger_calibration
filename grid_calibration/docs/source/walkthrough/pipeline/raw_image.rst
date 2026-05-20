Raw Images
===========

The raw-image stage represents the starting point of the calibration workflow.

Unlike the later pipeline stages, this step does not generate a product. It
simply exposes the original calibration images through the GUI so they can be
inspected before processing begins.

Overview
--------

The raw-image step allows users to:

- inspect the calibration images,
- verify image quality,
- confirm proper grid visibility,
- check exposure and focus,
- and select which image will be used as the initial workflow reference.

This step acts as the visual entry point for the entire calibration session.

GUI Example
-----------

.. image:: figures/Step_0.png
   :width: 100%
   :align: center

The raw images are displayed directly in the main visualization panel.

If multiple images are provided, the dropdown menu on the left allows switching
between them.

Inputs
------

The raw-image step consumes the input image files provided when launching the
pipeline.

Example:

.. code-block:: bash

    python -m grid_calibration *.jpg --debug

Outputs
-------

This step does not produce a product.

The raw images remain external input files throughout the workflow.

Purpose
-------

Although simple, this stage is extremely important.

It allows users to quickly identify problems before running the pipeline.

Typical issues include:

- out-of-focus images,
- missing grid regions,
- motion blur,
- saturation,
- insufficient illumination,
- partial field-of-view coverage.

The earlier these issues are detected, the easier the calibration workflow
becomes.

Image Channels
--------------

The visualization panel displays the individual Bayer channels separately.

Typical channels include:

- red,
- green1,
- green2,
- blue.

Inspecting the individual channels is useful because the calibration target may
appear differently across the sensor channels.

This is particularly important when:

- illumination is uneven,
- one channel saturates earlier,
- or the grid contrast differs significantly by wavelength.

What a Good Input Image Looks Like
----------------------------------

A good calibration image generally has:

- sharp grid intersections,
- uniform illumination,
- minimal saturation,
- strong contrast,
- visible grid coverage across most of the field,
- and limited motion blur.

The calibration target should remain visible over the majority of the fisheye
projection.


Next Step
---------

Once the raw images have been inspected, the next workflow stage is:

:doc:`full_array`

which converts the raw Bayer data into calibrated full-array image products.