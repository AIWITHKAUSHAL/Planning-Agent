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
    model = build_provider(settings.gemini_api_key, settings.gemini_model, settings.demo_mode)
    tools = ToolRegistry(model, settings.output_dir)
    return PlanningAgent(Planner(model), Executor(tools, settings.max_retries), model, store, settings.max_replans)


app = FastAPI(title="Gemini Planning Agent", version="1.0.0")
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(Path("app/static/index.html"))


@app.get("/api/health")
async def health() -> dict[str, str | bool]:
    return {"status": "ok", "mode": "demo" if settings.demo_mode else "gemini", "model": settings.gemini_model}


@app.post("/api/runs", response_model=AgentState, status_code=202)
async def create_run(request: RunRequest) -> AgentState:
    try:
        agent = create_agent()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    initial = AgentState(objective=request.objective)
    store.save(initial)

    async def execute() -> None:
        await agent.run(request.objective, initial)

    task = asyncio.create_task(execute())
    background_runs.add(task)
    task.add_done_callback(background_runs.discard)
    return initial


@app.get("/api/runs", response_model=list[AgentState])
async def list_runs() -> list[AgentState]:
    return store.list()


@app.get("/api/runs/{run_id}", response_model=AgentState)
async def get_run(run_id: str) -> AgentState:
    state = store.get(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return state
