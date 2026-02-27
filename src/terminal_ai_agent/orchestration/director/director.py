from __future__ import annotations

from terminal_ai_agent.agents.four_agent.bug_fixer.agent import BugFixerAgent
from terminal_ai_agent.agents.four_agent.executor.agent import ExecutorAgent
from terminal_ai_agent.agents.four_agent.handoff_protocols.coder_to_executor import (
    handoff_coder_to_executor,
)
from terminal_ai_agent.agents.four_agent.handoff_protocols.executor_to_bugfixer import (
    handoff_executor_to_bugfixer,
)
from terminal_ai_agent.agents.four_agent.handoff_protocols.planner_to_coder import (
    handoff_planner_to_coder,
)
from terminal_ai_agent.agents.four_agent.main_coder.agent import MainCoderAgent
from terminal_ai_agent.agents.four_agent.planner.agent import PlannerAgent
from terminal_ai_agent.agents.four_agent.shared_contracts.task_contracts import (
    TaskEnvelope,
    TaskStatus,
)


class Director:
    """Coordinates the phase-1 4-agent pipeline end-to-end."""

    def __init__(self) -> None:
        self.planner = PlannerAgent()
        self.main_coder = MainCoderAgent()
        self.executor = ExecutorAgent()
        self.bug_fixer = BugFixerAgent()

    def run(self, envelope: TaskEnvelope) -> TaskEnvelope:
        envelope = self.planner.plan(envelope)
        envelope = handoff_planner_to_coder(envelope)

        envelope = self.main_coder.generate(envelope)
        envelope = handoff_coder_to_executor(envelope)

        envelope = self.executor.execute(envelope)
        envelope = handoff_executor_to_bugfixer(envelope)

        envelope = self.bug_fixer.fix(envelope)

        if envelope.status == TaskStatus.EXECUTED and envelope.execution and envelope.execution.success:
            envelope.status = TaskStatus.DONE
        return envelope
