from __future__ import annotations

from terminal_ai_agent.agents.four_agent.shared_contracts.task_contracts import (
    CodeDraft,
    TaskEnvelope,
    TaskStatus,
)


class MainCoderAgent:
    """Builds a draft implementation from a validated plan."""

    def generate(self, envelope: TaskEnvelope) -> TaskEnvelope:
        if envelope.plan is None:
            raise ValueError("plan must exist before code generation")

        synthesized = {
            "src/generated/example.py": (
                "def run_task() -> str:\n"
                "    return 'phase-1 generated artifact from main coder'\n"
            )
        }
        envelope.draft = CodeDraft(
            files=synthesized,
            summary=f"Generated {len(synthesized)} file(s) from planner steps",
        )
        envelope.status = TaskStatus.CODED
        return envelope
