"""Language-model provider interfaces and EURI/demo implementations."""

from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod

from app.models import AgentState, PlanDraft, PlannedTask

TOOLS = """
Available tools:
- research: Find factual information and identify useful sources. Inputs: query.
- analyze: Compare, reason over, or summarize prior results. Inputs: instruction.
- write_document: Save a Markdown deliverable. Inputs: filename, title.
Choose exactly one tool for every task. Use dependencies to order tasks.
"""


class ModelProvider(ABC):
    """Define the model operations required by the planning agent."""

    @abstractmethod
    async def create_plan(self, objective: str) -> PlanDraft:
        """Create a structured task plan for an objective."""
        ...

    @abstractmethod
    async def revise_plan(
        self, state: AgentState, failed_task: PlannedTask, error: str
    ) -> PlanDraft:
        """Create a replacement plan after a task failure."""
        ...

    @abstractmethod
    async def generate_text(self, prompt: str, grounded: bool = False) -> str:
        """Generate text, optionally applying research-oriented source guidance."""
        ...


class EuriProvider(ModelProvider):
    """Use EURI's OpenAI-compatible API for plans and text generation."""

    def __init__(self, api_key: str, model: str, base_url: str):
        """Create an asynchronous EURI client.

        Args:
            api_key: EURI API credential.
            model: Model identifier exposed by EURI.
            base_url: OpenAI-compatible EURI API base URL.
        """
        from openai import AsyncOpenAI

        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    async def _complete(self, prompt: str, system: str) -> str:
        """Send a chat-completion request and return its text content."""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("EURI returned an empty response")
        return content

    async def _structured(self, prompt: str) -> PlanDraft:
        """Generate a JSON plan and validate it against ``PlanDraft``."""
        schema = json.dumps(PlanDraft.model_json_schema(), separators=(",", ":"))
        response_text = await self._complete(
            f"{prompt}\n\nReturn only valid JSON matching this schema:\n{schema}",
            "You are a precise planning agent. Return JSON only, without Markdown fences.",
        )
        start = response_text.find("{")
        end = response_text.rfind("}")
        if start == -1 or end < start:
            raise ValueError("EURI did not return a JSON object for the plan")
        return PlanDraft.model_validate_json(response_text[start : end + 1])

    async def create_plan(self, objective: str) -> PlanDraft:
        """Ask EURI to decompose an objective into ordered executable tasks."""
        return await self._structured(
            "You are a planning agent. Break the objective into 3-8 small, executable tasks. "
            "Every dependency must refer to an earlier task id. Finish with write_document when "
            f"the objective asks for a deliverable.\n{TOOLS}\nObjective: {objective}"
        )

    async def revise_plan(
        self, state: AgentState, failed_task: PlannedTask, error: str
    ) -> PlanDraft:
        """Ask EURI to replace unfinished work while retaining completed results."""
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
        """Generate text, requesting careful source attribution for research."""
        system = (
            "You are a careful research assistant. Cite source names and URLs when known, "
            "label uncertainty, and never invent a source."
            if grounded
            else "You are a helpful assistant. Follow the user's instructions precisely."
        )
        return await self._complete(prompt, system)


class DemoProvider(ModelProvider):
    """Deterministic provider for classrooms and automated tests; makes no API calls."""

    async def create_plan(self, objective: str) -> PlanDraft:
        """Return a deterministic three-stage plan without making API calls."""
        await asyncio.sleep(0)
        return PlanDraft(
            goal_summary=objective,
            reasoning="Research the parts, compare evidence, then create the requested deliverable.",
            tasks=[
                PlannedTask(
                    id="task_1",
                    title="Research the objective",
                    description="Collect key facts",
                    tool="research",
                    inputs={"query": objective},
                    success_criteria="Relevant facts are collected",
                ),
                PlannedTask(
                    id="task_2",
                    title="Analyze findings",
                    description="Organize and compare the evidence",
                    tool="analyze",
                    inputs={"instruction": "Extract themes, comparisons, and conclusions"},
                    depends_on=["task_1"],
                    success_criteria="Findings answer the objective",
                ),
                PlannedTask(
                    id="task_3",
                    title="Prepare final report",
                    description="Write a clear Markdown report",
                    tool="write_document",
                    inputs={
                        "filename": "planning-agent-report.md",
                        "title": "Planning Agent Report",
                    },
                    depends_on=["task_2"],
                    success_criteria="A readable report is saved",
                ),
            ],
        )

    async def revise_plan(
        self, state: AgentState, failed_task: PlannedTask, error: str
    ) -> PlanDraft:
        """Return a fresh deterministic plan for the original objective."""
        return await self.create_plan(state.objective)

    async def generate_text(self, prompt: str, grounded: bool = False) -> str:
        """Return predictable placeholder text derived from the prompt."""
        await asyncio.sleep(0)
        return "DEMO RESULT\n\n" + prompt[-900:]


def build_provider(
    api_key: str,
    model: str,
    demo_mode: bool,
    base_url: str = "https://api.euron.one/api/v1/euri",
) -> ModelProvider:
    """Construct the configured model provider.

    Args:
        api_key: EURI credential used in live mode.
        model: Model identifier exposed by EURI.
        demo_mode: Whether to use the offline deterministic provider.
        base_url: OpenAI-compatible EURI API endpoint.

    Returns:
        A demo provider or live EURI provider.

    Raises:
        RuntimeError: If live mode is requested without an API key.
    """
    if demo_mode:
        return DemoProvider()
    if not api_key:
        raise RuntimeError("EURI_API_KEY is missing. Add it to .env or set DEMO_MODE=true.")
    return EuriProvider(api_key, model, base_url)
