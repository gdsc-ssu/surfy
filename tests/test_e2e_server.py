import asyncio
import json
from dataclasses import dataclass
from typing import Any

import pytest
from langgraph.types import Command
from starlette.testclient import TestClient

import surfy.server as server


@dataclass
class _FakeInterrupt:
    value: dict[str, Any]


@dataclass
class _FakeTask:
    interrupts: list[_FakeInterrupt]


@dataclass
class _FakeSnapshot:
    next: tuple[str, ...]
    tasks: list[_FakeTask]
    values: dict[str, Any]


class _FakeGraph:
    def __init__(self) -> None:
        self.interrupted = False
        self.replan_requested = False
        self.completed = False

    async def astream(self, payload: dict[str, Any] | Command, config: dict[str, Any]):
        _ = config
        if isinstance(payload, Command):
            resume_val = payload.resume
            if isinstance(resume_val, dict):
                if resume_val.get("approved"):
                    # Resume with approval -> continue to completion
                    self.interrupted = False
                    yield {"actor": {"last_page_state": {"url": "http://test", "title": "test", "dom_text": "test"}}}
                    yield {"evaluator": {"eval_result": {"success": True, "reason": "ok"}, "done": True}}
                    self.completed = True
                elif resume_val.get("modification"):
                    # Resume with modification -> replan
                    self.replan_requested = True
                    yield {"planner": {"plan": {"anchor": "modified", "tasks": []}, "user_feedback": None}}
                    self.interrupted = True  # Re-interrupt after replan
            return

        # Initial run
        await asyncio.sleep(0.05)
        self.interrupted = True
        yield {"research": {"research_result": None}}
        yield {"scout": {"route_map": None}}
        yield {
            "planner": {
                "plan": {"anchor": "initial", "tasks": [{"description": "task 1"}]},
                "current_task_idx": 0,
                "completed_tasks": [],
                "done": False,
                "error": None,
            }
        }

    async def aget_state(self, config: dict[str, Any]) -> _FakeSnapshot:
        _ = config
        if self.interrupted:
            payload = {
                "type": "plan_approval",
                "plan": {"anchor": "modified" if self.replan_requested else "initial", "tasks": []},
            }
            return _FakeSnapshot(
                next=("plan_approval",),
                tasks=[_FakeTask(interrupts=[_FakeInterrupt(value=payload)])],
                values={},
            )
        if self.completed:
            return _FakeSnapshot(next=(), tasks=[], values={"done": True, "error": None})
        return _FakeSnapshot(next=("planner",), tasks=[], values={})


class _SlowGraph:
    def __init__(self) -> None:
        self.cancelled = False

    async def astream(self, payload: dict[str, Any] | Command, config: dict[str, Any]):
        _ = payload
        _ = config
        try:
            await asyncio.sleep(10)  # Long sleep to allow cancellation
            yield {"planner": {"done": False}}
        except asyncio.CancelledError:
            self.cancelled = True
            raise

    async def aget_state(self, config: dict[str, Any]) -> _FakeSnapshot:
        _ = config
        return _FakeSnapshot(next=(), tasks=[], values={})


class _DummyCloser:
    async def close(self) -> None:
        return


class _DummyStopper:
    async def stop(self) -> None:
        return


@pytest.fixture
def reset_server_state(monkeypatch: pytest.MonkeyPatch):
    server._SESSION = server.SessionStore()
    monkeypatch.setattr(server, "HEARTBEAT_INTERVAL_SECONDS", 0.05)
    yield


def test_full_run_interrupt_resume_completion(reset_server_state, monkeypatch: pytest.MonkeyPatch):
    """run -> node_start/node_end events -> plan_approval interrupt -> resume -> completion"""
    _ = reset_server_state

    async def fake_runtime() -> server.ServerRuntime:
        return server.ServerRuntime(graph=_FakeGraph(), browser=_DummyCloser(), agent_session=_DummyStopper())

    monkeypatch.setattr(server, "_get_or_create_runtime", fake_runtime)

    with TestClient(server.app) as client:
        with client.websocket_connect("/ws") as ws:
            _ = ws.receive_json()  # connected

            ws.send_text(json.dumps({"type": "run", "data": {"command": "test full flow"}}))

            # Collect events until interrupt
            events = []
            while True:
                msg = ws.receive_json()
                events.append(msg["type"])
                if msg["type"] == "interrupt":
                    break

            assert "node_start" in events
            assert "node_end" in events
            assert "state_update" in events
            assert "interrupt" in events

            # Resume with approval
            ws.send_text(
                json.dumps(
                    {
                        "type": "resume",
                        "data": {
                            "interrupt_type": "plan_approval",
                            "value": {"approved": True, "modification": None},
                        },
                    }
                )
            )

            # Collect events until completion
            final_events = []
            done = False
            while not done:
                msg = ws.receive_json()
                final_events.append(msg["type"])
                if msg["type"] == "state_update" and msg["data"]["done"]:
                    done = True

            assert "node_start" in final_events
            assert "node_end" in final_events
            assert "dom_highlight" in final_events


def test_cancel_scenario(reset_server_state, monkeypatch: pytest.MonkeyPatch):
    """run -> cancel -> cancelled"""
    _ = reset_server_state

    slow_graph = _SlowGraph()

    async def fake_runtime() -> server.ServerRuntime:
        return server.ServerRuntime(graph=slow_graph, browser=_DummyCloser(), agent_session=_DummyStopper())

    monkeypatch.setattr(server, "_get_or_create_runtime", fake_runtime)

    with TestClient(server.app) as client:
        with client.websocket_connect("/ws") as ws:
            _ = ws.receive_json()  # connected

            ws.send_text(json.dumps({"type": "run", "data": {"command": "test cancel"}}))
            # Wait a bit for the task to start
            import time

            time.sleep(0.1)

            ws.send_text(json.dumps({"type": "cancel", "data": {}}))

            cancelled_msg = ws.receive_json()
            while cancelled_msg["type"] == "heartbeat":
                cancelled_msg = ws.receive_json()

            assert cancelled_msg["type"] == "cancelled"
            assert "Cancelled" in cancelled_msg["data"]["reason"]
            assert slow_graph.cancelled


def test_chat_replan_scenario(reset_server_state, monkeypatch: pytest.MonkeyPatch):
    """run -> chat -> interrupt with queued_messages -> resume with modification -> replan -> new interrupt"""
    _ = reset_server_state

    async def fake_runtime() -> server.ServerRuntime:
        return server.ServerRuntime(graph=_FakeGraph(), browser=_DummyCloser(), agent_session=_DummyStopper())

    monkeypatch.setattr(server, "_get_or_create_runtime", fake_runtime)

    with TestClient(server.app) as client:
        with client.websocket_connect("/ws") as ws:
            _ = ws.receive_json()  # connected

            ws.send_text(json.dumps({"type": "run", "data": {"command": "test chat replan"}}))
            ws.send_text(json.dumps({"type": "chat", "data": {"message": "change plan please"}}))

            # Wait for interrupt
            interrupt = None
            while True:
                msg = ws.receive_json()
                if msg["type"] == "interrupt":
                    interrupt = msg
                    break

            assert interrupt["data"]["payload"]["queued_messages"] == ["change plan please"]

            # Resume with modification
            ws.send_text(
                json.dumps(
                    {
                        "type": "resume",
                        "data": {
                            "interrupt_type": "plan_approval",
                            "value": {"approved": False, "modification": "change plan please"},
                        },
                    }
                )
            )

            # Should get another interrupt after replan
            second_interrupt = None
            while True:
                msg = ws.receive_json()
                if msg["type"] == "interrupt":
                    second_interrupt = msg
                    break

            assert second_interrupt["data"]["payload"]["plan"]["anchor"] == "modified"


def test_reconnection_scenario(reset_server_state, monkeypatch: pytest.MonkeyPatch):
    """connect -> run -> disconnect -> reconnect -> connected with state"""
    _ = reset_server_state

    async def fake_runtime() -> server.ServerRuntime:
        return server.ServerRuntime(graph=_FakeGraph(), browser=_DummyCloser(), agent_session=_DummyStopper())

    monkeypatch.setattr(server, "_get_or_create_runtime", fake_runtime)

    with TestClient(server.app) as client:
        # First connection
        with client.websocket_connect("/ws") as ws:
            _ = ws.receive_json()  # connected
            ws.send_text(json.dumps({"type": "run", "data": {"command": "test reconnect"}}))

            # Wait for some state updates
            while True:
                msg = ws.receive_json()
                if msg["type"] == "state_update":
                    break

        # Disconnected here. Now reconnect.
        with client.websocket_connect("/ws") as ws:
            connected_msg = ws.receive_json()
            assert connected_msg["type"] == "connected"
            assert connected_msg["data"]["state"] is not None
            assert connected_msg["data"]["state"]["command"] == "test reconnect"
