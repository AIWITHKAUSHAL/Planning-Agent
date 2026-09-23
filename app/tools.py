from __future__ import annotations

import re
from pathlib import Path
from typing import Awaitable, Callable

from app.llm import ModelProvider
from app.models import TaskState


ToolFunction = Callable[[TaskState, dict[str, str]], Awaitable[str]]


class ToolRegistry:
    def __init__(self, model: ModelProvider, output_dir: Path):
        self.model = model
        self.output_dir = output_dir.resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._tools: dict[str, ToolFunction] = {
            "research": self.research,
            "analyze": self.analyze,
            "write_document": self.write_document,
        }

    async def execute(self, task: TaskState, dependency_results: dict[str, str]) -> str:
        function = self._tools.get(task.tool.value)
        if function is None:
            raise ValueError(f"Unknown tool: {task.tool}")
        return await function(task, dependency_results)

    async def research(self, task: TaskState, dependency_results: dict[str, str]) -> str:
        query = str(task.inputs.get("query") or task.description)
        return await self.model.generate_text(
            "Research this query. Return concise facts, source names, and source URLs. "
            f"Clearly label uncertainty. Query: {query}",
            grounded=True,
        )

    async def analyze(self, task: TaskState, dependency_results: dict[str, str]) -> str:
        instruction = str(task.inputs.get("instruction") or task.description)
        context = "\n\n".join(f"[{key}]\n{value}" for key, value in dependency_results.items())
        return await self.model.generate_text(
            f"Follow this analysis instruction: {instruction}\n\nEvidence:\n{context}"
        )

    async def write_document(self, task: TaskState, dependency_results: dict[str, str]) -> str:
        raw_name = str(task.inputs.get("filename") or "result.md")
        filename = re.sub(r"[^a-zA-Z0-9._-]", "-", Path(raw_name).name)
        if not filename.endswith(".md"):
            filename += ".md"
        target = (self.output_dir / filename).resolve()
        if self.output_dir not in target.parents:
            raise ValueError("Output path must stay inside the output directory")
        title = str(task.inputs.get("title") or task.title)
        context = "\n\n".join(dependency_results.values())
        content = await self.model.generate_text(
            f"Write a polished Markdown document titled '{title}' from these results. "
            f"Keep useful source links.\n\n{context}"
        )
        target.write_text(content, encoding="utf-8")
        return f"Saved {target.name}\n\n{content}"

