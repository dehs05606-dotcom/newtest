from __future__ import annotations

import argparse
import json

from terminal_ai_agent.agents.four_agent.shared_contracts.task_contracts import TaskEnvelope
from terminal_ai_agent.orchestration.director.director import Director


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="terminal-ai-agent")
    parser.add_argument("objective", help="Task objective for the 4-agent pipeline")
    parser.add_argument(
        "--constraint",
        action="append",
        default=[],
        help="Optional constraints; can be provided multiple times",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    envelope = TaskEnvelope(
        task_id="task-001",
        objective=args.objective,
        constraints=list(args.constraint),
    )
    result = Director().run(envelope)

    output = {
        "task_id": result.task_id,
        "status": result.status.value,
        "plan_steps": result.plan.steps if result.plan else [],
        "draft_files": list(result.draft.files.keys()) if result.draft else [],
        "execution_success": result.execution.success if result.execution else None,
        "fix_applied": result.fix is not None,
    }
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
