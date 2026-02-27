from terminal_ai_agent.agents.four_agent.shared_contracts.task_contracts import (
    TaskEnvelope,
    TaskStatus,
)
from terminal_ai_agent.orchestration.director.director import Director


def test_director_happy_path_marks_task_done() -> None:
    envelope = TaskEnvelope(task_id="t-1", objective="create sample module")
    result = Director().run(envelope)

    assert result.status == TaskStatus.DONE
    assert result.plan is not None
    assert result.draft is not None
    assert result.execution is not None
    assert result.execution.success is True
