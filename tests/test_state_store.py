"""Tests for SQLite state persistence and recent-run retrieval."""

from app.models import AgentState, Event, RunStatus
from app.state_store import StateStore


def test_state_round_trip(tmp_path):
    """Persist and restore a run without losing its status or event history."""
    store = StateStore(tmp_path / "state.db")
    state = AgentState(objective="Prepare a detailed comparison")
    state.status = RunStatus.running
    state.events.append(Event(kind="test", message="checkpoint"))
    store.save(state)

    restored = store.get(state.run_id)
    assert restored is not None
    assert restored.objective == state.objective
    assert restored.status == RunStatus.running
    assert restored.events[0].message == "checkpoint"


def test_list_orders_recent_runs(tmp_path):
    """Return all recently saved runs from the listing operation."""
    store = StateStore(tmp_path / "state.db")
    first = store.save(AgentState(objective="First detailed objective"))
    second = store.save(AgentState(objective="Second detailed objective"))
    assert {item.run_id for item in store.list()} == {first.run_id, second.run_id}
