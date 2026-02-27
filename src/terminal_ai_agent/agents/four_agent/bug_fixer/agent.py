from __future__ import annotations

from terminal_ai_agent.agents.four_agent.shared_contracts.task_contracts import (
    FixPatch,
    TaskEnvelope,
    TaskStatus,
)


class BugFixerAgent:
    """Provides a minimal corrective patch when executor reports failures."""

    def fix(self, envelope: TaskEnvelope) -> TaskEnvelope:
        if envelope.execution is None:
            raise ValueError("execution report required before fixing")

        if envelope.execution.success:
            envelope.status = TaskStatus.DONE
            return envelope

        envelope.fix = FixPatch(
            files={"src/generated/example.py": "# patched by bug fixer\n"},
            rationale="executor found failing checks, applying stabilization patch",
        )
        envelope.status = TaskStatus.FIXED
        return envelope
