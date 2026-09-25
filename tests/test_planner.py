"""Tests for plan validation and the deterministic demo workflow."""

import pytest

from app.llm import DemoProvider, EuriProvider, build_provider
from app.models import PlanDraft, PlannedTask
from app.planner import Planner


def task(task_id: str, depends_on: list[str] | None = None) -> PlannedTask:
    """Build a minimal planned task for validation tests."""
    return PlannedTask(
        id=task_id,
        title=task_id,
        description="test task",
        tool="analyze",
        depends_on=depends_on or [],
        success_criteria="done",
    )


def test_accepts_ordered_dependencies():
    """Accept dependencies that reference tasks appearing earlier in the plan."""
    Planner.validate(PlanDraft(goal_summary="goal", reasoning="reason", tasks=[task("a"), task("b", ["a"]), task("c", ["b"])]))


def test_rejects_forward_dependency():
    """Reject a task that depends on a later task."""
    draft = PlanDraft(goal_summary="goal", reasoning="reason", tasks=[task("a", ["b"]), task("b"), task("c")])
    with pytest.raises(ValueError, match="forward dependencies"):
        Planner.validate(draft)


def test_rejects_duplicate_ids():
    """Reject repeated task identifiers within a plan."""
    draft = PlanDraft(goal_summary="goal", reasoning="reason", tasks=[task("a"), task("a"), task("c")])
    with pytest.raises(ValueError, match="Duplicate"):
        Planner.validate(draft)


@pytest.mark.asyncio
async def test_demo_planner_creates_complete_workflow():
    """Verify that demo mode produces research, analysis, and writing stages."""
    draft = await Planner(DemoProvider()).create("Research several tools and write a report")
    assert [item.tool.value for item in draft.tasks] == ["research", "analyze", "write_document"]


@pytest.mark.asyncio
async def test_euri_provider_extracts_and_validates_json_plan():
    """Validate JSON returned through the EURI-compatible chat interface."""
    expected = PlanDraft(
        goal_summary="goal",
        reasoning="reason",
        tasks=[task("a"), task("b", ["a"]), task("c", ["b"])],
    )
    provider = object.__new__(EuriProvider)

    async def fake_complete(prompt: str, system: str) -> str:
        """Return a valid plan surrounded by incidental model text."""
        return f"Plan follows:\n{expected.model_dump_json()}\nDone"

    provider._complete = fake_complete
    actual = await provider._structured("Create a plan")

    assert actual == expected


def test_live_provider_requires_euri_key():
    """Reject live mode when no EURI credential is configured."""
    with pytest.raises(RuntimeError, match="EURI_API_KEY"):
        build_provider("", "gemini-3.5-flash-lite", demo_mode=False)
