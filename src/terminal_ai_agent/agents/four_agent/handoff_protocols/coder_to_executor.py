from __future__ import annotations

from terminal_ai_agent.agents.four_agent.shared_contracts.task_contracts import (
    TaskEnvelope,
    TaskStatus,
)


def handoff_coder_to_executor(envelope: TaskEnvelope) -> TaskEnvelope:
    if envelope.status != TaskStatus.CODED:
        raise ValueError("coder_to_executor handoff requires CODED status")
    if envelope.draft is None:
        raise ValueError("coder_to_executor handoff requires a code draft")
    return envelope
