from __future__ import annotations

from terminal_ai_agent.agents.four_agent.shared_contracts.task_contracts import (
    ExecutionReport,
    TaskEnvelope,
    TaskStatus,
)


class ExecutorAgent:
    """Simulates execution for phase-1 until real tool runners are connected."""

    def execute(self, envelope: TaskEnvelope) -> TaskEnvelope:
        if envelope.draft is None:
            raise ValueError("draft must exist before execution")

        logs = [
            "executor: staged generated files",
            "executor: ran simulated checks",
            "executor: no failing tests detected",
        ]
        envelope.execution = ExecutionReport(success=True, logs=logs, failing_tests=[])
        envelope.status = TaskStatus.EXECUTED
        return envelope
