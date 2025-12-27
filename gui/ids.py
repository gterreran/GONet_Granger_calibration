from __future__ import annotations

# Stores / globals
STORE_ACTIVE_STEP = "active-step-store"
STORE_CONTROL_STEPS = "control-row-steps-store"
STORE_RUN_STEP = "run-step-store"

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
STATUS_TEXT = "status-text"

# Logging
LOG_WINDOW = "log-window"
LOG_POLL_INTERVAL = "log-poll-interval"
LOG_AUTOSCROLL_DUMMY = "log-autoscroll-dummy"

# Special trigger
RUN_FULL_PIPELINE_TRIGGER = "run_full_pipeline_trigger"
