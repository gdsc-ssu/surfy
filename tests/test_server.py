import asyncio
import json
from dataclasses import dataclass
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
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

    async def astream(self, payload: dict[str, Any] | Command, config: dict[str, Any]):
        _ = config
        if isinstance(payload, Command):
            self.interrupted = False
            yield {"plan_approval": {"plan_approved": True, "done": False}}
            yield {"planner": {"done": True, "current_task_idx": 0, "completed_tasks": [], "error": None}}
            return

        self.interrupted = True
        yield {
            "planner": {
                "plan": {"anchor": "테스트", "tasks": []},
                "current_task_idx": 0,
                "completed_tasks": [],
                "done": False,
                "error": None,
            }
        }

    async def aget_state(self, config: dict[str, Any]) -> _FakeSnapshot:
        _ = config
        if self.interrupted:
            payload = {"type": "plan_approval", "plan": {"anchor": "테스트", "tasks": []}}
            return _FakeSnapshot(
                next=("plan_approval",),
                tasks=[_FakeTask(interrupts=[_FakeInterrupt(value=payload)])],
                values={},
            )
        return _FakeSnapshot(next=(), tasks=[], values={"done": True, "error": None})


class _SlowGraph:
    async def astream(self, payload: dict[str, Any] | Command, config: dict[str, Any]):
        _ = payload
        _ = config
        await asyncio.sleep(1)
        yield {"planner": {"done": False, "current_task_idx": 0, "completed_tasks": [], "error": None}}

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


@pytest.mark.asyncio
async def test_health_endpoint(reset_server_state):
    _ = reset_server_state
    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_websocket_connected_message(reset_server_state):
    _ = reset_server_state
    with TestClient(server.app) as client:
        with client.websocket_connect("/ws") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "connected"
            assert msg["data"]["state"] is None


def test_websocket_heartbeat_bidirectional(reset_server_state):
    _ = reset_server_state
    with TestClient(server.app) as client:
        with client.websocket_connect("/ws") as ws:
            _ = ws.receive_json()

            server_ping = ws.receive_json()
            assert server_ping["type"] == "heartbeat"

            ws.send_text(json.dumps({"type": "heartbeat", "data": {}}))
            server_pong = ws.receive_json()
            assert server_pong["type"] == "heartbeat"


def test_websocket_cancel_message(reset_server_state, monkeypatch: pytest.MonkeyPatch):
    _ = reset_server_state

    async def fake_runtime() -> server.ServerRuntime:
        return server.ServerRuntime(graph=_SlowGraph(), browser=_DummyCloser(), agent_session=_DummyStopper())

    monkeypatch.setattr(server, "_get_or_create_runtime", fake_runtime)

    with TestClient(server.app) as client:
        with client.websocket_connect("/ws") as ws:
            _ = ws.receive_json()

            ws.send_text(json.dumps({"type": "run", "data": {"command": "run cancel test", "thread_id": "x"}}))
            ws.send_text(json.dumps({"type": "cancel", "data": {}}))

            cancelled = ws.receive_json()
            assert cancelled["type"] == "cancelled"
            assert "Cancelled" in cancelled["data"]["reason"]


def test_websocket_invalid_message_returns_error(reset_server_state):
    _ = reset_server_state
    with TestClient(server.app) as client:
        with client.websocket_connect("/ws") as ws:
            _ = ws.receive_json()
            ws.send_text("this is not json")
            error = ws.receive_json()

            assert error["type"] == "error"
            assert "Invalid JSON" in error["data"]["message"]


def test_websocket_run_interrupt_and_resume(reset_server_state, monkeypatch: pytest.MonkeyPatch):
    _ = reset_server_state

    async def fake_runtime() -> server.ServerRuntime:
        return server.ServerRuntime(graph=_FakeGraph(), browser=_DummyCloser(), agent_session=_DummyStopper())

    monkeypatch.setattr(server, "_get_or_create_runtime", fake_runtime)

    with TestClient(server.app) as client:
        with client.websocket_connect("/ws") as ws:
            _ = ws.receive_json()

            ws.send_text(json.dumps({"type": "run", "data": {"command": "do work", "thread_id": "x"}}))

            first_types = [ws.receive_json()["type"] for _ in range(4)]
            assert first_types == ["node_start", "node_end", "state_update", "interrupt"]

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

            resume_types = [ws.receive_json()["type"] for _ in range(6)]
            assert resume_types.count("node_start") == 2
            assert resume_types.count("node_end") == 2
            assert resume_types.count("state_update") == 2


def test_websocket_chat_is_queued_and_included_in_next_interrupt(
    reset_server_state,
    monkeypatch: pytest.MonkeyPatch,
):
    _ = reset_server_state

    async def fake_runtime() -> server.ServerRuntime:
        return server.ServerRuntime(graph=_FakeGraph(), browser=_DummyCloser(), agent_session=_DummyStopper())

    monkeypatch.setattr(server, "_get_or_create_runtime", fake_runtime)

    with TestClient(server.app) as client:
        with client.websocket_connect("/ws") as ws:
            _ = ws.receive_json()

            ws.send_text(json.dumps({"type": "run", "data": {"command": "do work", "thread_id": "x"}}))
            ws.send_text(json.dumps({"type": "chat", "data": {"message": "계획을 더 짧게 바꿔줘"}}))

            interrupt = None
            for _ in range(10):
                msg = ws.receive_json()
                if msg["type"] == "interrupt":
                    interrupt = msg
                    break

            assert interrupt is not None
            assert interrupt["data"]["payload"]["queued_messages"] == ["계획을 더 짧게 바꿔줘"]
