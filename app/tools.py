"""Allow-listed tools for research, analysis, and Markdown output generation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Awaitable, Callable

from app.llm import ModelProvider
from app.models import TaskState

ToolFunction = Callable[[TaskState, dict[str, str]], Awaitable[str]]


class ToolRegistry:
    """Dispatch planned tasks to a fixed set of safe application tools."""

    def __init__(self, model: ModelProvider, output_dir: Path):
        """Initialize tool handlers and ensure the output directory exists.

        Args:
            model: Provider used for research, analysis, and document text.
            output_dir: Directory in which generated Markdown files are stored.
        """
        self.model = model
        self.output_dir = output_dir.resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._tools: dict[str, ToolFunction] = {
            "research": self.research,
            "analyze": self.analyze,
            "write_document": self.write_document,
        }

    async def execute(self, task: TaskState, dependency_results: dict[str, str]) -> str:
        """Dispatch a task to its selected registered tool.

        Raises:
            ValueError: If the task names a tool outside the allow-list.
        """
        function = self._tools.get(task.tool.value)
        if function is None:
            raise ValueError(f"Unknown tool: {task.tool}")
        return await function(task, dependency_results)

    async def research(self, task: TaskState, dependency_results: dict[str, str]) -> str:
        """Research a query with search-grounded model generation."""
        query = str(task.inputs.get("query") or task.description)
        return await self.model.generate_text(
            "Research this query. Return concise facts, source names, and source URLs. "
            f"Clearly label uncertainty. Query: {query}",
            grounded=True,
        )

    async def analyze(self, task: TaskState, dependency_results: dict[str, str]) -> str:
        """Analyze dependency results according to the task instruction."""
        instruction = str(task.inputs.get("instruction") or task.description)
        context = "\n\n".join(f"[{key}]\n{value}" for key, value in dependency_results.items())
        return await self.model.generate_text(
            f"Follow this analysis instruction: {instruction}\n\nEvidence:\n{context}"
        )

    async def write_document(self, task: TaskState, dependency_results: dict[str, str]) -> str:
        """Generate and safely save a Markdown document inside the output directory.

        Raises:
            ValueError: If the resolved output path escapes the configured directory.
        """
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
