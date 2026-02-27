from __future__ import annotations

from terminal_ai_agent.agents.four_agent.shared_contracts.task_contracts import (
    TaskEnvelope,
    TaskStatus,
)


def handoff_executor_to_bugfixer(envelope: TaskEnvelope) -> TaskEnvelope:
    if envelope.status != TaskStatus.EXECUTED:
        raise ValueError("executor_to_bugfixer handoff requires EXECUTED status")
    if envelope.execution is None:
        raise ValueError("executor_to_bugfixer handoff requires execution report")
    return envelope
