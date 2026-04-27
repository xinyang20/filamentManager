from __future__ import annotations

from dataclasses import dataclass


ACTIVE_STATES = {"RUNNING", "PAUSE"}


@dataclass(frozen=True)
class StateTransition:
    event_type: str
    severity: str
    message: str


def classify_transition(
    previous_state: str | None,
    current_state: str | None,
    *,
    recent_stop_success: bool = False,
) -> StateTransition | None:
    if current_state is None or previous_state == current_state:
        return None

    if current_state == "RUNNING" and previous_state not in {"RUNNING", "PAUSE"}:
        return StateTransition("print.started", "info", "Print started")

    if previous_state == "RUNNING" and current_state == "PAUSE":
        return StateTransition("print.paused", "info", "Print paused")

    if previous_state == "PAUSE" and current_state == "RUNNING":
        return StateTransition("print.resumed", "info", "Print resumed")

    if previous_state in ACTIVE_STATES and current_state == "FINISH":
        return StateTransition("print.finished", "info", "Print finished")

    if current_state == "FAILED" and (previous_state in ACTIVE_STATES or recent_stop_success):
        if recent_stop_success:
            return StateTransition("print.cancelled", "warning", "Print cancelled by user")
        return StateTransition("print.failed", "error", "Print failed")

    return None
