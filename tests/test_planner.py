import pytest

from app.llm import DemoProvider
from app.models import PlanDraft, PlannedTask
from app.planner import Planner


def task(task_id: str, depends_on: list[str] | None = None) -> PlannedTask:
    return PlannedTask(
        id=task_id,
        title=task_id,
        description="test task",
        tool="analyze",
        depends_on=depends_on or [],
        success_criteria="done",
    )


def test_accepts_ordered_dependencies():
    Planner.validate(PlanDraft(goal_summary="goal", reasoning="reason", tasks=[task("a"), task("b", ["a"]), task("c", ["b"])]))


def test_rejects_forward_dependency():
    draft = PlanDraft(goal_summary="goal", reasoning="reason", tasks=[task("a", ["b"]), task("b"), task("c")])
    with pytest.raises(ValueError, match="forward dependencies"):
        Planner.validate(draft)


def test_rejects_duplicate_ids():
    draft = PlanDraft(goal_summary="goal", reasoning="reason", tasks=[task("a"), task("a"), task("c")])
    with pytest.raises(ValueError, match="Duplicate"):
        Planner.validate(draft)


@pytest.mark.asyncio
async def test_demo_planner_creates_complete_workflow():
    draft = await Planner(DemoProvider()).create("Research several tools and write a report")
    assert [item.tool.value for item in draft.tasks] == ["research", "analyze", "write_document"]
