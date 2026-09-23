# Atlas — Gemini Planning Agent

Atlas converts a complex objective into a validated sequence of executable tasks, selects a tool for each task, runs them in dependency order, stores progress, and recovers from failure.

![Planning agent architecture](docs/diagrams/architecture.svg)

## What the project demonstrates

The visible workflow is:

`Goal → Plan → Tasks → Tool Selection → Execution → Results → Final Response`

- **Planning:** Gemini returns a typed `PlanDraft` using structured output.
- **State management:** the goal, plan, task status, attempts, results, errors, and event log are saved in SQLite after every transition.
- **Tool selection:** each planned task explicitly selects `research`, `analyze`, or `write_document`.
- **Execution:** tasks run only after their dependencies have completed.
- **Failure handling:** a failed tool call is retried with exponential backoff. After retries are exhausted, Gemini revises the unfinished plan while completed results are preserved.
- **Demo mode:** the full workflow runs without an API key, which is useful during a classroom presentation and in tests.

## Quick start

Prerequisites: Python 3.11+ and, for real model execution, a Gemini API key.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env
```

Add your key to `.env`:

```dotenv
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash
DEMO_MODE=false
```

Start the application:

```bash
uvicorn app.api:app --reload
```

Open <http://127.0.0.1:8000>. API documentation is available at <http://127.0.0.1:8000/docs>.

To run without a key:

```bash
DEMO_MODE=true uvicorn app.api:app --reload
```

Try this objective:

> Research three AI companies, compare their products, and prepare a summary.

## Application flow

1. The browser sends the objective to `POST /api/runs`.
2. The API immediately returns a run ID and starts the agent in the background.
3. The planner asks Gemini for schema-constrained tasks and validates task IDs and dependencies.
4. The executor resolves dependencies and sends each task to its selected tool.
5. The state store checkpoints status and results after every step.
6. The browser polls `GET /api/runs/{run_id}` and renders live progress.
7. Gemini synthesizes the successful task results into the final response.

![File responsibility map](docs/diagrams/file-map.svg)

## File guide

| File | Responsibility | Receives → Produces |
|---|---|---|
| `app/api.py` | FastAPI routes and background runs | HTTP objective → run ID/state |
| `app/agent.py` | Orchestrates the complete lifecycle | objective → completed agent state |
| `app/planner.py` | Creates/revises and validates plans | objective/failure → valid plan |
| `app/llm.py` | Gemini adapter and deterministic demo adapter | prompts → plan/text |
| `app/executor.py` | Runs dependencies, retries, and raises failures | tasks → task results |
| `app/tools.py` | Tool registry for research, analysis, and writing | selected tool + context → result |
| `app/models.py` | Pydantic schemas and status enums | raw values → typed state |
| `app/state_store.py` | Durable SQLite checkpoints | `AgentState` ↔ JSON row |
| `app/static/*` | Student-facing interface and polling | browser events ↔ API |
| `tests/*` | Unit and integration verification | controlled inputs → assertions |

## Failure recovery

![Retry and replanning flow](docs/diagrams/failure-flow.svg)

A task gets `MAX_RETRIES + 1` total attempts. Each error is recorded in the event timeline. When all attempts fail, the top-level agent changes to `replanning` and sends Gemini the objective, successful results, failed task, and error. The revised tasks then execute. `MAX_REPLANS` prevents an infinite loop.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/health` | Show model and current mode |
| `POST` | `/api/runs` | Start an agent run |
| `GET` | `/api/runs/{run_id}` | Read current plan and execution state |
| `GET` | `/api/runs` | List recent runs |

Example:

```bash
curl -X POST http://127.0.0.1:8000/api/runs \
  -H 'Content-Type: application/json' \
  -d '{"objective":"Research three AI companies, compare their products and prepare a summary."}'
```

## Run tests

```bash
pytest -q
```

The tests cover plan validation, state persistence, successful execution, retries, and replanning. No Gemini key is needed.

## Security and limits

- Secrets come from environment variables and `.env` is ignored by Git.
- Output filenames are sanitized and restricted to `outputs/`.
- The model can choose only registered tools; it cannot execute arbitrary shell commands.
- Search-grounded output can still contain mistakes. Check important claims and source links.
- This is a single-process teaching project. A production deployment should use a job queue and a managed database.

## Submission checklist

- Push this repository to GitHub without `.env` or `data/*.db`.
- Record the walkthrough using [docs/VIDEO_SCRIPT.md](docs/VIDEO_SCRIPT.md).
- Show one Gemini run and one failure/retry test.
- Put the GitHub and unlisted YouTube links in the submission form.

Detailed acceptance criteria are in [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md).

## Gemini implementation reference

This project uses the current `google-genai` Python SDK, Pydantic structured output for plans, and Google Search grounding for the research tool. See the official [Google Gen AI SDK documentation](https://googleapis.github.io/python-genai/) and [Gemini structured output guide](https://ai.google.dev/gemini-api/docs/structured-output).

