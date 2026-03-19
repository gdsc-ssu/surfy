import asyncio
import json
from dataclasses import dataclass
from typing import Any, cast

import pytest
from httpx import ASGITransport, AsyncClient
from langgraph.types import Command
from starlette.testclient import TestClient

import surfy.server as server
from surfy.domain.models.messages import StepProgressMessageData


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

        await asyncio.sleep(0.05)
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


class _ScoutGraph:
    async def astream(self, payload: dict[str, Any] | Command, config: dict[str, Any]):
        _ = payload
        _ = config
        yield {
            "scout": {
                "route_map": {"steps": [], "final_url": "", "scout_summary": "ok"},
                "current_task_idx": 0,
                "completed_tasks": [],
                "done": False,
                "error": None,
            }
        }

    async def aget_state(self, config: dict[str, Any]) -> _FakeSnapshot:
        _ = config
        return _FakeSnapshot(next=(), tasks=[], values={})


class _FakeScoutAdapter:
    def __init__(self) -> None:
        self.step_progress_queue: asyncio.Queue[StepProgressMessageData] = asyncio.Queue()


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


@pytest.mark.asyncio
async def test_handle_graph_stream_scout_step_progress(reset_server_state, monkeypatch: pytest.MonkeyPatch):
    _ = reset_server_state

    scout_adapter = _FakeScoutAdapter()
    await scout_adapter.step_progress_queue.put(
        StepProgressMessageData(
            node="scout",
            step_number=1,
            description="Navigating to google.com",
            action_type="go_to_url",
        )
    )

    async def fake_runtime() -> server.ServerRuntime:
        return server.ServerRuntime(
            graph=_ScoutGraph(),
            browser=_DummyCloser(),
            agent_session=_DummyStopper(),
            scout_adapter=cast(Any, scout_adapter),
        )

    sent_messages: list[Any] = []

    async def capture_send(message: Any) -> None:
        sent_messages.append(message)

    monkeypatch.setattr(server, "_get_or_create_runtime", fake_runtime)
    monkeypatch.setattr(server, "_send_message", capture_send)

    await server._handle_graph_stream(server._initial_state("do scout"))

    sent_types = [msg.type for msg in sent_messages]
    assert "step_progress" in sent_types

    scout_start_idx = sent_types.index("node_start")
    scout_step_idx = sent_types.index("step_progress")
    scout_end_idx = sent_types.index("node_end")
    assert scout_start_idx < scout_step_idx < scout_end_idx


def test_websocket_connected_message(reset_server_state):
    _ = reset_server_state
    with TestClient(server.app) as client:
        with client.websocket_connect("/ws") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "connected"
            assert msg["data"]["state"] is None


def test_websocket_get_status_message(reset_server_state):
    _ = reset_server_state
    server._SESSION.current_state = {"test": "state"}
    with TestClient(server.app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.receive_json()  # Initial connected message

            ws.send_text(json.dumps({"type": "get_status", "data": {}}))
            msg = ws.receive_json()
            assert msg["type"] == "connected"
            assert msg["data"]["state"] == {"test": "state"}


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

            first_types = []
            while len(first_types) < 4:
                msg = ws.receive_json()
                if msg["type"] == "heartbeat":
                    continue
                first_types.append(msg["type"])
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

            resume_types = []
            while len(resume_types) < 6:
                msg = ws.receive_json()
                if msg["type"] == "heartbeat":
                    continue
                resume_types.append(msg["type"])
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


@pytest.mark.asyncio
async def test_watchdog_does_not_kill_on_single_failure(reset_server_state, monkeypatch):
    _ = reset_server_state
    monkeypatch.setattr(server, "BROWSER_WATCHDOG_INTERVAL", 0.01)
    monkeypatch.setattr(server, "BROWSER_WATCHDOG_MAX_FAILURES", 3)

    call_count = 0

    def fake_alive():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return False
        return True

    monkeypatch.setattr(server, "_is_browser_alive", fake_alive)

    async def noop_send(msg):
        _ = msg

    monkeypatch.setattr(server, "_send_message", noop_send)

    runtime = server.ServerRuntime(graph=None, browser=_DummyCloser(), agent_session=_DummyStopper())
    server._SESSION.runtime = runtime

    task = asyncio.create_task(server._browser_watchdog())
    await asyncio.sleep(0.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert server._SESSION.runtime is not None


@pytest.mark.asyncio
async def test_watchdog_kills_after_consecutive_failures(reset_server_state, monkeypatch):
    _ = reset_server_state
    monkeypatch.setattr(server, "BROWSER_WATCHDOG_INTERVAL", 0.01)
    monkeypatch.setattr(server, "BROWSER_WATCHDOG_MAX_FAILURES", 3)
    monkeypatch.setattr(server, "_is_browser_alive", lambda: False)

    async def noop_send(msg):
        _ = msg

    monkeypatch.setattr(server, "_send_message", noop_send)

    runtime = server.ServerRuntime(graph=None, browser=_DummyCloser(), agent_session=_DummyStopper())
    server._SESSION.runtime = runtime
    server._SESSION.lock = asyncio.Lock()

    task = asyncio.create_task(server._browser_watchdog())
    await asyncio.sleep(0.15)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert server._SESSION.runtime is None


@pytest.mark.asyncio
async def test_watchdog_resets_counter_on_alive(reset_server_state, monkeypatch):
    _ = reset_server_state
    monkeypatch.setattr(server, "BROWSER_WATCHDOG_INTERVAL", 0.01)
    monkeypatch.setattr(server, "BROWSER_WATCHDOG_MAX_FAILURES", 3)

    sequence = [False, False, True, False, False]
    idx = 0

    def fake_alive():
        nonlocal idx
        if idx < len(sequence):
            result = sequence[idx]
            idx += 1
            return result
        return True

    monkeypatch.setattr(server, "_is_browser_alive", fake_alive)

    async def noop_send(msg):
        _ = msg

    monkeypatch.setattr(server, "_send_message", noop_send)

    runtime = server.ServerRuntime(graph=None, browser=_DummyCloser(), agent_session=_DummyStopper())
    server._SESSION.runtime = runtime

    task = asyncio.create_task(server._browser_watchdog())
    await asyncio.sleep(0.15)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert server._SESSION.runtime is not None


@pytest.mark.asyncio
async def test_watchdog_cleanup_does_not_cancel_itself(reset_server_state, monkeypatch):
    _ = reset_server_state

    stop_called = False
    original_stop = server._stop_browser_watchdog

    async def tracking_stop():
        nonlocal stop_called
        stop_called = True
        await original_stop()

    monkeypatch.setattr(server, "_stop_browser_watchdog", tracking_stop)

    runtime = server.ServerRuntime(graph=None, browser=_DummyCloser(), agent_session=_DummyStopper())
    server._SESSION.runtime = runtime

    await server._cleanup_runtime_from_watchdog()

    assert not stop_called
    assert server._SESSION.runtime is None


@pytest.mark.asyncio
async def test_runtime_creation_failure_no_runtime_stored(reset_server_state, monkeypatch):
    _ = reset_server_state

    async def failing_create(*args, **kwargs):
        _ = args
        _ = kwargs
        raise ConnectionError("Chrome not running")

    monkeypatch.setattr("surfy.server.BrowserUseAdapter.create", failing_create)
    monkeypatch.setattr(
        "surfy.server.Settings",
        lambda **kwargs: type(
            "S",
            (),
            {
                "browser": type("B", (), {"cdp_url": None, "use_system_chrome": False, "chrome_profile": "Default"})(),
                "llm": type("L", (), {"model_name": "test", "use_vision": True})(),
                "scout": type("SC", (), {"model_name": "test", "max_steps": 20})(),
                "google_api_key": None,
                "anthropic_api_key": "test-key",
            },
        )(),
    )

    with pytest.raises(ConnectionError, match="Chrome not running"):
        await server._get_or_create_runtime()

    assert server._SESSION.runtime is None


@pytest.mark.asyncio
async def test_runtime_partial_creation_cleans_up_browser(reset_server_state, monkeypatch):
    _ = reset_server_state

    close_called = False

    class FakeBrowser:
        def get_session(self):
            return _DummyStopper()

        async def close(self):
            nonlocal close_called
            close_called = True

    async def fake_create(*args, **kwargs):
        _ = args
        _ = kwargs
        return FakeBrowser()

    monkeypatch.setattr("surfy.server.BrowserUseAdapter.create", fake_create)
    monkeypatch.setattr(
        "surfy.server.Settings",
        lambda **kwargs: type(
            "S",
            (),
            {
                "browser": type("B", (), {"cdp_url": None, "use_system_chrome": False, "chrome_profile": "Default"})(),
                "llm": type("L", (), {"model_name": "test", "use_vision": True})(),
                "scout": type("SC", (), {"model_name": "test", "max_steps": 20})(),
                "google_api_key": None,
                "anthropic_api_key": "test-key",
                "handoff_on_auth": True,
            },
        )(),
    )

    def failing_adapter(*args, **kwargs):
        _ = args
        _ = kwargs
        raise RuntimeError("LLM init failed")

    monkeypatch.setattr("surfy.server.LangChainLLMAdapter", failing_adapter)

    with pytest.raises(RuntimeError, match="LLM init failed"):
        await server._get_or_create_runtime()

    assert close_called
    assert server._SESSION.runtime is None


def test_websocket_run_runtime_creation_failure_sends_error(reset_server_state, monkeypatch: pytest.MonkeyPatch):
    _ = reset_server_state

    async def failing_runtime() -> server.ServerRuntime:
        raise RuntimeError("CDP connection failed")

    monkeypatch.setattr(server, "_get_or_create_runtime", failing_runtime)

    with TestClient(server.app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.receive_json()

            ws.send_text(json.dumps({"type": "run", "data": {"command": "fail test", "thread_id": "x"}}))

            error = ws.receive_json()
            assert error["type"] == "error"
            assert "CDP connection failed" in error["data"]["message"]
