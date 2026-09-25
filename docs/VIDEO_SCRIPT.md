# 6–8 Minute Video Walkthrough

## 0:00–0:40 — Problem and result

“The requirement is to convert a complex objective into executable tasks and show the full path from goal to final response. My project is Atlas, an EURI-powered planning agent.” Show the home screen and the architecture diagram.

## 0:40–1:40 — Architecture

Open `docs/diagrams/architecture.svg`. Explain that EURI plans, the executor runs one selected tool per task, and SQLite receives checkpoints throughout. Emphasize that this is a workflow, not one large prompt.

## 1:40–2:45 — Planning and tool selection

Open `app/models.py`, `app/llm.py`, and `app/planner.py`.

- Show `PlanDraft` and `PlannedTask`.
- Point out `tool`, `inputs`, `depends_on`, and `success_criteria`.
- Show how EURI JSON responses are validated with the Pydantic plan schema.
- Show validation of unique IDs and earlier dependencies.

## 2:45–3:45 — State management

Open `app/state_store.py` and `app/agent.py`.

- Show `save()` and the SQLite upsert.
- Explain that the entire typed `AgentState` is saved after planning and each task transition.
- In the browser/API JSON, show task status, attempts, results, and the event list.

## 3:45–4:50 — Execution

Open `app/executor.py` and `app/tools.py`.

- Show dependency result collection.
- Show the tool registry, which limits the model to approved capabilities.
- Explain cited research generation, analysis over prior results, and sandboxed Markdown writing.

## 4:50–5:50 — Failure handling

Show `docs/diagrams/failure-flow.svg`, then the retry loop in `executor.py` and replanning loop in `agent.py`. Run:

```bash
pytest -q tests/test_failure_recovery.py -s
```

Explain that every failed attempt is stored, completed work survives replanning, and limits prevent infinite loops.

## 5:50–7:10 — Live demo

Enter:

> Research three AI companies, compare their products, and prepare a summary.

While it runs, point out the plan, chosen tool/status pills, attempt count, and polling. Show the final response and the generated file inside `outputs/`.

## 7:10–7:40 — Close

Briefly show the tests and README setup. State the limitations: generated research needs verification; production would move background jobs and storage to managed infrastructure. End on the completed run.

## Recording checklist

- Use a readable editor font and 125–150% browser zoom.
- Do not display the `.env` file or API key.
- Record voice clearly; keep the terminal visible during tests.
- Put both GitHub and YouTube links in the final submission.
