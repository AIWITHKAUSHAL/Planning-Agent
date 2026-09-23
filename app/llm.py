from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod

from app.models import AgentState, PlanDraft, PlannedTask


TOOLS = """
Available tools:
- research: Find factual information using Gemini with Google Search grounding. Inputs: query.
- analyze: Compare, reason over, or summarize prior results. Inputs: instruction.
- write_document: Save a Markdown deliverable. Inputs: filename, title.
Choose exactly one tool for every task. Use dependencies to order tasks.
"""


class ModelProvider(ABC):
    @abstractmethod
    async def create_plan(self, objective: str) -> PlanDraft: ...

    @abstractmethod
    async def revise_plan(self, state: AgentState, failed_task: PlannedTask, error: str) -> PlanDraft: ...

    @abstractmethod
    async def generate_text(self, prompt: str, grounded: bool = False) -> str: ...


class GeminiProvider(ModelProvider):
    def __init__(self, api_key: str, model: str):
        from google import genai

        self.client = genai.Client(api_key=api_key)
        self.model = model

    async def _structured(self, prompt: str) -> PlanDraft:
        from google.genai import types

        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=PlanDraft,
                temperature=0.2,
            ),
        )
        return PlanDraft.model_validate_json(response.text)

    async def create_plan(self, objective: str) -> PlanDraft:
        return await self._structured(
            "You are a planning agent. Break the objective into 3-8 small, executable tasks. "
            "Every dependency must refer to an earlier task id. Finish with write_document when "
            f"the objective asks for a deliverable.\n{TOOLS}\nObjective: {objective}"
        )

    async def revise_plan(self, state: AgentState, failed_task: PlannedTask, error: str) -> PlanDraft:
        completed = [
            {"id": task.id, "title": task.title, "result": task.result}
            for task in state.tasks
            if task.status.value == "completed"
        ]
        return await self._structured(
            "Revise only the unfinished portion of this plan after a failure. Preserve useful completed "
            "work by creating new tasks whose inputs mention it. Do not repeat the same failing action. "
            f"\n{TOOLS}\nObjective: {state.objective}\nCompleted: {completed}"
            f"\nFailed task: {failed_task.model_dump()}\nError: {error}"
        )

    async def generate_text(self, prompt: str, grounded: bool = False) -> str:
        from google.genai import types

        config = types.GenerateContentConfig(temperature=0.2)
        if grounded:
            config.tools = [types.Tool(google_search=types.GoogleSearch())]
        response = await self.client.aio.models.generate_content(
            model=self.model, contents=prompt, config=config
        )
        return response.text or "No text returned by Gemini."


class DemoProvider(ModelProvider):
    """Deterministic provider for classrooms and automated tests; makes no API calls."""

    async def create_plan(self, objective: str) -> PlanDraft:
        await asyncio.sleep(0)
        return PlanDraft(
            goal_summary=objective,
            reasoning="Research the parts, compare evidence, then create the requested deliverable.",
            tasks=[
                PlannedTask(id="task_1", title="Research the objective", description="Collect key facts", tool="research", inputs={"query": objective}, success_criteria="Relevant facts are collected"),
                PlannedTask(id="task_2", title="Analyze findings", description="Organize and compare the evidence", tool="analyze", inputs={"instruction": "Extract themes, comparisons, and conclusions"}, depends_on=["task_1"], success_criteria="Findings answer the objective"),
                PlannedTask(id="task_3", title="Prepare final report", description="Write a clear Markdown report", tool="write_document", inputs={"filename": "planning-agent-report.md", "title": "Planning Agent Report"}, depends_on=["task_2"], success_criteria="A readable report is saved"),
            ],
        )

    async def revise_plan(self, state: AgentState, failed_task: PlannedTask, error: str) -> PlanDraft:
        return await self.create_plan(state.objective)

    async def generate_text(self, prompt: str, grounded: bool = False) -> str:
        await asyncio.sleep(0)
        return "DEMO RESULT\n\n" + prompt[-900:]


def build_provider(api_key: str, model: str, demo_mode: bool) -> ModelProvider:
    if demo_mode:
        return DemoProvider()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing. Add it to .env or set DEMO_MODE=true.")
    return GeminiProvider(api_key, model)
