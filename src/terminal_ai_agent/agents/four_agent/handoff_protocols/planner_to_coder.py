from __future__ import annotations

from terminal_ai_agent.agents.four_agent.shared_contracts.task_contracts import (
    TaskEnvelope,
    TaskStatus,
)


def handoff_planner_to_coder(envelope: TaskEnvelope) -> TaskEnvelope:
    if envelope.status != TaskStatus.PLANNED:
        raise ValueError("planner_to_coder handoff requires PLANNED status")
    if envelope.plan is None:
        raise ValueError("planner_to_coder handoff requires a plan")
    return envelope
