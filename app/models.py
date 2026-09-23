from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TaskStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"


class RunStatus(str, Enum):
    planning = "planning"
    running = "running"
    replanning = "replanning"
    completed = "completed"
    failed = "failed"


class ToolName(str, Enum):
    research = "research"
    analyze = "analyze"
    write_document = "write_document"


class PlannedTask(BaseModel):
    id: str = Field(description="Short stable id such as task_1")
    title: str
    description: str
    tool: ToolName
    inputs: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    success_criteria: str


class PlanDraft(BaseModel):
    goal_summary: str
    reasoning: str = Field(description="Brief explanation of the decomposition")
    tasks: list[PlannedTask]


class TaskState(PlannedTask):
    status: TaskStatus = TaskStatus.pending
    attempts: int = 0
    result: str | None = None
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class Event(BaseModel):
    at: datetime = Field(default_factory=utc_now)
    kind: str
    message: str
    task_id: str | None = None


class AgentState(BaseModel):
    run_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    objective: str
    status: RunStatus = RunStatus.planning
    plan_reasoning: str = ""
    tasks: list[TaskState] = Field(default_factory=list)
    replan_count: int = 0
    final_response: str | None = None
    error: str | None = None
    events: list[Event] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class RunRequest(BaseModel):
    objective: str = Field(min_length=10, max_length=4000)

