from app.llm import ModelProvider
from app.models import AgentState, PlanDraft, TaskState


class Planner:
    def __init__(self, model: ModelProvider):
        self.model = model

    @staticmethod
    def validate(draft: PlanDraft) -> None:
        if not 3 <= len(draft.tasks) <= 8:
            raise ValueError("Planner must return between 3 and 8 tasks")
        seen: set[str] = set()
        for task in draft.tasks:
            if task.id in seen:
                raise ValueError(f"Duplicate task id: {task.id}")
            unknown = set(task.depends_on) - seen
            if unknown:
                raise ValueError(f"Task {task.id} has missing or forward dependencies: {unknown}")
            seen.add(task.id)

    async def create(self, objective: str) -> PlanDraft:
        draft = await self.model.create_plan(objective)
        self.validate(draft)
        return draft

    async def revise(self, state: AgentState, failed: TaskState, error: str) -> PlanDraft:
        draft = await self.model.revise_plan(state, failed, error)
        self.validate(draft)
        return draft
