from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class TaskStatus(str, Enum):
    """Lifecycle states for a task moving through the 4-agent pipeline."""

    NEW = "new"
    PLANNED = "planned"
    CODED = "coded"
    EXECUTED = "executed"
    NEEDS_FIX = "needs_fix"
    FIXED = "fixed"
    DONE = "done"


@dataclass
class Plan:
    """A lightweight implementation plan created by the planner agent."""

    objective: str
    steps: List[str]
    assumptions: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)


@dataclass
class CodeDraft:
    """Represents generated code changes before execution."""

    files: Dict[str, str]
    summary: str


@dataclass
class ExecutionReport:
    """Execution output produced by executor agent."""

    success: bool
    logs: List[str]
    failing_tests: List[str] = field(default_factory=list)


@dataclass
class FixPatch:
    """Patch proposal from bug fixer agent."""

    files: Dict[str, str]
    rationale: str


@dataclass
class TaskEnvelope:
    """Shared transport object across planner, coder, executor, and bug fixer."""

    task_id: str
    objective: str
    constraints: List[str] = field(default_factory=list)
    context: Dict[str, str] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.NEW
    plan: Optional[Plan] = None
    draft: Optional[CodeDraft] = None
    execution: Optional[ExecutionReport] = None
    fix: Optional[FixPatch] = None
