import sqlite3
from pathlib import Path
from threading import Lock

from app.models import AgentState, utc_now


class StateStore:
    """Small durable state store. Every agent transition is written immediately."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )"""
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10)

    def save(self, state: AgentState) -> AgentState:
        state.updated_at = utc_now()
        payload = state.model_dump_json()
        with self._lock, self._connect() as connection:
            connection.execute(
                """INSERT INTO runs(run_id, state_json, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    state_json=excluded.state_json, updated_at=excluded.updated_at""",
                (state.run_id, payload, state.updated_at.isoformat()),
            )
        return state

    def get(self, run_id: str) -> AgentState | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT state_json FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        return AgentState.model_validate_json(row[0]) if row else None

    def list(self, limit: int = 20) -> list[AgentState]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT state_json FROM runs ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [AgentState.model_validate_json(row[0]) for row in rows]

