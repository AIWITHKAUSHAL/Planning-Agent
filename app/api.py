"""FastAPI application exposing planning-agent runs and the browser interface."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.agent import PlanningAgent
from app.config import get_settings
from app.executor import Executor
from app.llm import build_provider
from app.models import AgentState, RunRequest
from app.planner import Planner
from app.state_store import StateStore
from app.tools import ToolRegistry

settings = get_settings()
store = StateStore(settings.database_path)
background_runs: set[asyncio.Task] = set()


def create_agent() -> PlanningAgent:
    """Build a planning agent from the current application settings.

    Returns:
        A fully wired agent with model, planner, executor, tools, and state store.

    Raises:
        RuntimeError: If live EURI mode is selected without an API key.
    """
    model = build_provider(
        settings.euri_api_key,
        settings.euri_model,
        settings.demo_mode,
        settings.euri_base_url,
    )
    tools = ToolRegistry(model, settings.output_dir)
    return PlanningAgent(
        Planner(model), Executor(tools, settings.max_retries), model, store, settings.max_replans
    )


app = FastAPI(title="EURI Planning Agent", version="1.0.0")
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    """Serve the single-page browser interface."""
    return FileResponse(Path("app/static/index.html"))


@app.get("/api/health")
async def health() -> dict[str, str | bool]:
    """Return service availability and the configured provider mode."""
    configured = settings.demo_mode or bool(settings.euri_api_key)
    return {
        "status": "ok" if configured else "configuration_required",
        "mode": "demo" if settings.demo_mode else "euri",
        "model": settings.euri_model,
        "configured": configured,
    }


@app.post("/api/runs", response_model=AgentState, status_code=202)
async def create_run(request: RunRequest) -> AgentState:
    """Create a run, schedule its execution, and return its initial state.

    Args:
        request: Validated request containing the user's objective.

    Returns:
        The initial state with a run ID that clients can poll.

    Raises:
        HTTPException: If the configured model provider cannot be initialized.
    """
    try:
        agent = create_agent()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    initial = AgentState(objective=request.objective)
    store.save(initial)

    async def execute() -> None:
        """Execute the newly created run in the event-loop background."""
        await agent.run(request.objective, initial)

    task = asyncio.create_task(execute())
    background_runs.add(task)
    task.add_done_callback(background_runs.discard)
    return initial


@app.get("/api/runs", response_model=list[AgentState])
async def list_runs() -> list[AgentState]:
    """Return the most recently updated agent runs."""
    return store.list()


@app.get("/api/runs/{run_id}", response_model=AgentState)
async def get_run(run_id: str) -> AgentState:
    """Return one run by ID.

    Args:
        run_id: Public identifier assigned when the run was created.

    Raises:
        HTTPException: If no stored run has the supplied identifier.
    """
    state = store.get(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return state
