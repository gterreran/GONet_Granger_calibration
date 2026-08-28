GONet Calibration Documentation
===============================

Grid Calibration provides an interactive workflow for deriving a fisheye
camera calibration from the projected polar grid used in the Grainger Sky
Theater at the Adler Planetarium.

Most users should begin with the :doc:`walkthrough/index`.  Readers who want to
understand the final calibration mathematically can go directly to the
:doc:`calibration/index`.  The architecture and API sections are intended
primarily for developers.

Where to go next
----------------

* **Run a calibration:** :doc:`walkthrough/index`
* **Understand the final distortion model:** :doc:`calibration/index`
* **Understand the codebase:** :doc:`architecture/index`
* **Look up Python interfaces:** :doc:`api/index`

.. toctree::
   :maxdepth: 2
   :caption: User guide

   walkthrough/index

.. toctree::
   :maxdepth: 2
   :caption: Calibration model

   calibration/index

.. toctree::
   :maxdepth: 2
   :caption: Developer documentation

   architecture/index
   api/index
