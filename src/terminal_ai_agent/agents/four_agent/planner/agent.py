from __future__ import annotations

from typing import List

from terminal_ai_agent.agents.four_agent.shared_contracts.task_contracts import (
    Plan,
    TaskEnvelope,
    TaskStatus,
)


class PlannerAgent:
    """Creates a deterministic first-pass plan for a coding task."""

    def plan(self, envelope: TaskEnvelope) -> TaskEnvelope:
        steps: List[str] = [
            "Analyze objective and constraints",
            "Generate implementation changes",
            "Execute validation commands",
            "Apply bug-fix loop if execution fails",
        ]
        envelope.plan = Plan(
            objective=envelope.objective,
            steps=steps,
            assumptions=["Workspace is writable", "Python runtime is available"],
            risks=["Missing external dependencies", "Incomplete task context"],
        )
        envelope.status = TaskStatus.PLANNED
        return envelope
