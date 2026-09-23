# Planning Agent — Project Requirements

## 1. Project brief

Build a Gemini-powered agent that accepts a complex natural-language objective and turns it into smaller executable tasks. It must expose planning and tool decisions, persist current execution state, recover from individual failures, and return a consolidated final response.

Due: **25 September 2026, 17:57 IST**  
Marks: **25** — code (15), video explanation (10)

## 2. Functional requirements

| ID | Requirement | Acceptance evidence |
|---|---|---|
| FR-01 | Accept a non-trivial objective from a web UI and API. | Submitting 10–4,000 characters returns a run ID. |
| FR-02 | Use Gemini to convert the objective into 3–8 tasks. | Stored state contains ordered typed tasks. |
| FR-03 | Give every task a description, tool, inputs, dependencies, and success criterion. | Inspect `GET /api/runs/{id}`. |
| FR-04 | Validate unique IDs and prevent missing/forward dependencies. | Planner unit tests reject invalid plans. |
| FR-05 | Support at least three tools. | Research, analysis, and Markdown output tools execute through a registry. |
| FR-06 | Execute tasks in valid dependency order. | A dependent task receives completed dependency results. |
| FR-07 | Persist current plan and execution status. | Restarting the API retains runs in SQLite. |
| FR-08 | Record attempts, timestamps, outputs, errors, and lifecycle events. | Run JSON exposes the complete trace. |
| FR-09 | Retry a failed task automatically. | Failure test shows multiple attempts and retry events. |
| FR-10 | Modify the plan if retries are exhausted. | State changes to `replanning`; successful work is retained. |
| FR-11 | Synthesize task results into a final response. | A successful run ends in `completed` with `final_response`. |
| FR-12 | Show live status to the user. | UI progresses through pending/running/completed/failed states. |

## 3. Non-functional requirements

- **Maintainability:** planner, execution, tools, model access, data models, and persistence remain separate modules.
- **Reliability:** state is checkpointed after each transition; retry/replan counts are bounded.
- **Security:** no secret in source control, no arbitrary code/shell tool, and file output is sandboxed.
- **Testability:** the model is behind an interface and a deterministic fake can replace Gemini.
- **Usability:** the main workflow can be demonstrated from one screen with visible task progress.
- **Explainability:** the plan, chosen tool, attempts, task result/error, and event history are inspectable.

## 4. State contract

A run stores:

- run ID, objective, overall status, plan reasoning;
- every task's ID, description, selected tool, inputs, dependencies, success criterion;
- task status, attempt count, result, error, start and finish time;
- replan count, chronological events, final response, and terminal error;
- creation and last-update timestamps.

Allowed run states: `planning`, `running`, `replanning`, `completed`, `failed`.  
Allowed task states: `pending`, `running`, `completed`, `failed`, `skipped`.

## 5. Failure policy

1. Catch a tool exception and persist the error.
2. Retry up to `MAX_RETRIES` with capped exponential backoff.
3. Mark the task failed when attempts are exhausted.
4. If below `MAX_REPLANS`, ask Gemini for a different unfinished plan using prior results and the error.
5. If replanning is exhausted, mark the run failed and expose a useful message.

## 6. Suggested code marking rubric (15 marks)

| Area | Marks |
|---|---:|
| Goal decomposition and valid structured plan | 3 |
| Task/tool selection and dependency execution | 3 |
| Persistent state and visible status transitions | 3 |
| Retry, replanning, and bounded failure handling | 3 |
| Code quality, tests, setup, and documentation | 3 |

## 7. Suggested video marking rubric (10 marks)

| Area | Marks |
|---|---:|
| Clearly explains objective and architecture | 2 |
| Shows planning and explicit tool selection in code/state | 2 |
| Demonstrates persistent state and live execution | 2 |
| Explains and demonstrates retry/replanning | 2 |
| Shows final result and gives a clear code walkthrough | 2 |

## 8. Definition of done

- Fresh installation works from the README.
- Tests pass without a Gemini key.
- Real mode completes the example objective with a valid key.
- The UI visibly displays the tasks and terminal response.
- A deliberate test failure proves retry/replanning behavior.
- GitHub repository, README, and video link are submitted by the deadline.

