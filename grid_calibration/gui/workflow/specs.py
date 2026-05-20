# grid_calibration/gui/workflow/specs.py
"""
Workflow step specifications for the grid-calibration GUI.

This module defines the small metadata object used to describe each pipeline
step in the Dash interface. A step specification intentionally contains only
workflow information: identity, display label, ordering, execution mode, option
widget type, and lazy factories for runtime callables. It does not own product
paths, product schemas, file IO, or session state; those responsibilities belong
to :class:`~grid_calibration.gui.workflow.product_io.ProductIO` and
:class:`~grid_calibration.gui.session.CalibrationSession`.

The central class is :class:`~grid_calibration.gui.workflow.specs.PipelineStepSpec`.
Step packages usually construct one instance in their ``spec.py`` module and
export it as ``pipeline_step``. The workflow registry then imports these objects
and builds derived lookup tables such as ``STEP_BY_ID`` and ``ORDERED_STEPS``.

Factory discovery
-----------------

The constructor itself accepts explicit factory callables, but most step
packages use :meth:`~grid_calibration.gui.workflow.specs.PipelineStepSpec.from_dict`.
That helper inspects the caller module's global namespace using
:func:`inspect.currentframe` and captures any variables named
``viewer_factory``, ``pipeline_factory``, and ``initialize_factory``. This keeps
step ``spec.py`` files compact while preserving lazy imports and avoiding heavy
processing or plotting imports during registry construction.

The tradeoff is that factory variables must be defined in the step module scope
before :meth:`~grid_calibration.gui.workflow.specs.PipelineStepSpec.from_dict`
is called.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from .product_io import ProductKind
from typing import Any, Callable, Literal, Optional


StepMode = Literal["batch", "interactive"]
"""Execution mode for a pipeline step.

``"batch"`` steps run a processing function and produce a product immediately.
``"interactive"`` steps initialize GUI state and let callbacks drive additional
user interaction before a product is finalized.
"""

OptionKind = Literal["dropdown", "label"]
"""Kind of option widget displayed next to a step in the control panel.

``"dropdown"`` is used for per-input products where the user can choose among
multiple product files. ``"label"`` is used for singleton products where the
widget behaves as a read-only product indicator.
"""

StepCallable = Callable[..., Any]
"""Runtime callable used by a workflow step."""

StepCallableFactory = Callable[[], StepCallable]
"""Zero-argument callable that lazily returns a workflow callable."""


@dataclass(frozen=True)
class PipelineStepSpec:
    """
    Immutable workflow metadata for one GUI pipeline step.

    A :class:`PipelineStepSpec` describes how a step participates in the GUI
    workflow. It is deliberately limited to workflow-level concerns: the step's
    key, display label, order, execution mode, control-panel option type, and
    lazy factories for viewer, processing, and interactive-initialization
    callables.

    The specification does not know how products are named, saved, loaded, or
    validated. Product behavior is described separately by
    :class:`~grid_calibration.gui.workflow.product_io.ProductIO`, and runtime
    state is stored in :class:`~grid_calibration.gui.session.CalibrationSession`.

    Parameters
    ----------
    key : :class:`str`
        Stable string identifier for the step. This key is used throughout the
        workflow registry, session product dictionary, Dash component IDs, and
        product IO map.
    label : :class:`str`
        Human-readable label displayed in the GUI control panel.
    order : :class:`int`
        Numeric position of the step in the pipeline. Lower values appear
        earlier in the workflow.
    mode : :class:`StepMode`
        Execution mode for the step. ``"batch"`` steps run directly, while
        ``"interactive"`` steps initialize GUI state and rely on callbacks to
        complete user-guided work.
    option_kind : :class:`OptionKind`
        Kind of option widget displayed next to the step. Per-input products
        generally use ``"dropdown"``; singleton products generally use
        ``"label"``.
    viewer_factory : :class:`StepCallableFactory` or :data:`None`, optional
        Lazy factory returning the function that renders the step's viewer.
    pipeline_factory : :class:`StepCallableFactory` or :data:`None`, optional
        Lazy factory returning the step's batch processing function.
    initialize_factory : :class:`StepCallableFactory` or :data:`None`, optional
        Lazy factory returning the function used to initialize an interactive
        step.
    """

    key: str
    label: str
    order: int
    mode: StepMode

    option_kind: OptionKind

    viewer_factory: Optional[StepCallableFactory] = None
    pipeline_factory: Optional[StepCallableFactory] = None
    initialize_factory: Optional[StepCallableFactory] = None

    @property
    def button_label(self) -> str:
        """
        Return the GUI button label for this step.

        The button label combines the numeric workflow order with the
        human-readable step label. It is used for the action button displayed in
        the left-hand control panel.

        Returns
        -------
        :class:`str`
            Formatted label of the form ``"<order>. <label>"``.
        """
        return f"{self.order}. {self.label}"

    @property
    def viewer_func(self) -> Optional[StepCallable]:
        """
        Resolve and return the step viewer callable.

        The viewer callable is resolved lazily by calling ``viewer_factory``.
        This avoids importing plotting modules while the registry is being
        constructed, which keeps application startup lighter and reduces circular
        import pressure between step packages and GUI callbacks.

        Returns
        -------
        :class:`StepCallable` or :data:`None`
            Viewer callable returned by ``viewer_factory``, or :data:`None` if
            the step has no viewer factory.
        """
        if self.viewer_factory is None:
            return None

        return self.viewer_factory()

    @property
    def pipeline_func(self) -> Optional[StepCallable]:
        """
        Resolve and return the batch processing callable.

        Batch steps use this callable when the user presses the step's action
        button. Interactive steps may leave this unset if their work is driven
        entirely by callback state and finalization logic.

        Returns
        -------
        :class:`StepCallable` or :data:`None`
            Processing callable returned by ``pipeline_factory``, or
            :data:`None` if the step has no pipeline factory.
        """
        if self.pipeline_factory is None:
            return None

        return self.pipeline_factory()

    @property
    def initialize_interactive_state(self) -> Optional[StepCallable]:
        """
        Resolve and return the interactive-state initializer.

        Interactive steps use this callable to prepare temporary GUI state before
        user-guided callbacks take over. Batch-only steps generally leave the
        initializer unset.

        Returns
        -------
        :class:`StepCallable` or :data:`None`
            Initializer callable returned by ``initialize_factory``, or
            :data:`None` if the step has no initializer factory.
        """
        if self.initialize_factory is None:
            return None

        return self.initialize_factory()
    
    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PipelineStepSpec":
        """
        Create a step specification from a compact dictionary.

        This helper is the preferred construction mechanism inside step
        ``spec.py`` modules. The dictionary supplies the stable metadata, while
        the option-widget type is derived from the product kind. Factory
        callables are discovered from the caller module's global namespace using
        :func:`inspect.currentframe`.

        The input dictionary is expected to contain ``"key"``, ``"label"``,
        ``"order"``, ``"mode"``, and optionally ``"product_kind"``. The
        ``"product_kind"`` value should be a
        :class:`~grid_calibration.gui.workflow.product_io.ProductKind`. If the
        product kind is :attr:`~grid_calibration.gui.workflow.product_io.ProductKind.PER_INPUT`,
        or if no product kind is supplied, the resulting ``option_kind`` is
        ``"dropdown"``. Other product kinds use ``"label"``.

        Parameters
        ----------
        d : :class:`dict`
            Compact step specification dictionary. Required keys are ``"key"``,
            ``"label"``, ``"order"``, and ``"mode"``. The optional
            ``"product_kind"`` key controls the derived option-widget type.

        Returns
        -------
        :class:`~grid_calibration.gui.workflow.specs.PipelineStepSpec`
            Immutable step specification with lazy factories captured from the
            caller module, when present.
        """
        caller_globals = inspect.currentframe().f_back.f_globals
        
        product_kind = d.get("product_kind")
        if product_kind is None or product_kind is ProductKind.PER_INPUT:
            option_kind = "dropdown"
        else:
            option_kind = "label"

        return cls(
            key=d["key"],
            label=d["label"],
            order=d["order"],
            mode=d["mode"],
            option_kind=option_kind,
            viewer_factory=caller_globals.get("viewer_factory"),
            pipeline_factory=caller_globals.get("pipeline_factory"),
            initialize_factory=caller_globals.get("initialize_factory"),
        )

    def __str__(self) -> str:
        """
        Return the stable step key.

        Returns
        -------
        :class:`str`
            The value of :attr:`key`.
        """
        return self.key
