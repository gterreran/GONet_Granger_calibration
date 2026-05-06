from __future__ import annotations

# Stores / globals
STORE_ACTIVE_STEP = "active-step-store"
STORE_CONTROL_STEPS = "control-row-steps-store"
STORE_RUN_STEP = "run-step-store"
STORE_STEP_REQUEST = "step-request-store"
STORE_STEP_RESULT = "step-result-store"

# Controls
BTN_EXIT = "btn-exit"

# Step run buttons (keep existing names to avoid breaking callbacks)
def step_button_id(step: str) -> str:
    return {"type": "button", "step": step}

# Step right-side widgets
def step_dropdown_id(step: str) -> str:
    return {"type": "options", "step": step}

# Viewer + status
PLOTTING_AREA = "plotting-area"
FIGURE_CONTAINER_ID = "figure-container"
STATUS_TEXT = "status-text"
STORE_SELECTED_STEP = "selected-step-store"

# Logging
LOG_WINDOW = "log-window"
LOG_POLL_INTERVAL = "log-poll-interval"
LOG_AUTOSCROLL_DUMMY = "log-autoscroll-dummy"

# Unwrapping
GRID_GRAPH_ID = "full-array-image-graph"
UNWRAPPING_INTERACTIVE_CONTROLS_ID = "unwrapping-interactive-controls"
PENDING_STORE_ID = "unwrapping-pending-point-store"
CENTER_STORE_ID = "unwrapping-center-store"
UNWRAPPING_STATUS_ID = "unwrapping-status"
MODE_RADIO_ID = "unwrapping-mode-radio"
CONFIRM_BTN_ID = "unwrapping-confirm-center-btn"
RESET_BTN_ID = "unwrapping-reset-center-btn"

# Nominal grid
NOMINAL_INTERACTIVE_CONTROLS_ID = "nominal-interactive-controls"
RING_MAX_DIST_ID = "nominal-ring-max-dist"
RING_GATE_TOL_R_ID = "nominal-ring-gate-tol-r"
MIN_RING_GROUP_ID = "nominal-min-ring-group"
SPOKE_MAX_DIST_ID = "nominal-spoke-max-dist"
SPOKE_MIN_DIST_ID = "nominal-spoke-min-dist"
SPOKE_GATE_TOL_THETA_ID = "nominal-spoke-gate-tol-theta"
MIN_SPOKE_GROUP_ID = "nominal-min-spoke-group"
FIND_NOMINAL_BTN_ID = "find-nominal-btn"
RESET_NOMINAL_BTN_ID = "reset-nominal-btn"
CONFIRM_NOMINAL_BTN_ID = "confirm-nominal-btn"
NOMINAL_STATUS_ID = "nominal-status"
NOMINAL_ASSIGNMENT_ID = "nominal-assignment"
SELECTED_GRID_POINT_ID = "selected-grid-point"
SELECTION_CONTROL_DIV_ID = "selection-control-div"
EDIT_NOMINAL_RING_ID = "edit-nominal-ring-btn"
EDIT_NOMINAL_SPOKE_ID = "edit-nominal-spoke-btn"
VALID_NOMINAL_RING_ID = "valid-nominal-ring-store"
VALID_NOMINAL_SPOKE_ID = "valid-nominal-spoke-store"
RIGID_SHIFT_CONTROL_DIV_ID = "rigid-shift-control-div"
SHIFT_SPOKES_DEC_ID = "shift-spokes-dec-btn"
SHIFT_SPOKES_INC_ID = "shift-spokes-inc-btn"
SHIFT_RINGS_DEC_ID = "shift-rings-dec-btn"
SHIFT_RINGS_INC_ID = "shift-rings-inc-btn"

# Bootstrapping controls
BOOTSTRAPPING_INTERACTIVE_CONTROLS_ID = "bootstrapping-interactive-controls"
BOOTSTRAPPING_SPOKE_TOL_ID = "bootstrapping-spoke-tol"
BOOTSTRAPPING_CIRCLE_TOL_ID = "bootstrapping-circle-tol"
BOOTSTRAPPING_CIRCLE_POLY_DEGREE_ID = "bootstrapping-circle-poly-degree"
BOOTSTRAPPING_PARALLEL_WORKERS_ID = "bootstrapping-parallel-workers"
BOOTSTRAPPING_BTN_ID = "run-bootstrapping-btn"
RESET_BOOTSTRAPPING_BTN_ID = "reset-bootstrapping-btn"
BOOTSTRAPPING_STATUS_ID = "bootstrapping-status"