"""Top-level orchestration for planning, execution, recovery, and synthesis."""

from __future__ import annotations

from app.executor import Executor, TaskFailed
from app.llm import ModelProvider
from app.models import AgentState, Event, RunStatus, TaskState, TaskStatus
from app.planner import Planner
from app.state_store import StateStore


class PlanningAgent:
    """Coordinate a planning-agent run from objective intake to final response."""

    def __init__(
        self,
        planner: Planner,
        executor: Executor,
        model: ModelProvider,
        store: StateStore,
        max_replans: int,
    ):
        """Initialize the agent and its collaborating services.

        Args:
            planner: Service that creates and revises validated plans.
            executor: Service that executes planned tasks and handles retries.
            model: Language-model provider used to synthesize the final response.
            store: Durable store used to checkpoint each state transition.
            max_replans: Maximum number of replacement plans allowed after failures.
        """
        self.planner = planner
        self.executor = executor
        self.model = model
        self.store = store
        self.max_replans = max_replans

    async def run(self, objective: str, state: AgentState | None = None) -> AgentState:
        """Run an objective through planning, execution, recovery, and synthesis.

        Args:
            objective: User goal that the agent must complete.
            state: Optional pre-created state, such as one returned by the API.

        Returns:
            The final persisted state. Unexpected failures are represented by a
            ``failed`` status and error message instead of being propagated.
        """
        state = state or AgentState(objective=objective)
        state.events.append(Event(kind="goal_received", message=objective))
        self.store.save(state)
        try:
            draft = await self.planner.create(objective)
            state.plan_reasoning = draft.reasoning
            state.tasks = [TaskState(**task.model_dump()) for task in draft.tasks]
            state.status = RunStatus.running
            state.events.append(
                Event(kind="plan_created", message=f"Created {len(state.tasks)} tasks")
            )
            self.store.save(state)

            while True:
                try:
                    await self.executor.run(state, self.store.save)
                    break
                except TaskFailed as failure:
                    if state.replan_count >= self.max_replans:
                        raise
                    state.status = RunStatus.replanning
                    state.replan_count += 1
                    state.events.append(
                        Event(kind="replanning", task_id=failure.task.id, message=failure.error)
                    )
                    self.store.save(state)
                    revised = await self.planner.revise(state, failure.task, failure.error)
                    completed = [
                        task for task in state.tasks if task.status == TaskStatus.completed
                    ]
                    id_map = {task.id: f"r{state.replan_count}_{task.id}" for task in revised.tasks}
                    new_tasks = []
                    for task in revised.tasks:
                        task.id = id_map[task.id]
                        task.depends_on = [id_map[dep] for dep in task.depends_on]
                        new_tasks.append(TaskState(**task.model_dump()))
                    state.tasks = completed + new_tasks
                    state.plan_reasoning = revised.reasoning
                    state.status = RunStatus.running
                    self.store.save(state)

            results = "\n\n".join(
                f"## {task.title}\n{task.result}" for task in state.tasks if task.result
            )
            state.final_response = await self.model.generate_text(
                f"Give the user a concise final response for this objective: {objective}\n\nResults:\n{results}"
            )
            state.status = RunStatus.completed
            state.events.append(Event(kind="run_completed", message="Final response generated"))
        except Exception as exc:
            state.status = RunStatus.failed
            state.error = f"{type(exc).__name__}: {exc}"
            state.events.append(Event(kind="run_failed", message=state.error))
        return self.store.save(state)
