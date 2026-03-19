import asyncio
import inspect
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Literal

from browser_use.llm import ChatAnthropic as BrowserUseChatAnthropic
from browser_use.llm import ChatGoogle as BrowserUseChatGoogle
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
from pydantic import BaseModel

from surfy.adapters.browser import BrowserUseAdapter
from surfy.adapters.browser.agent_adapter import BrowserUseAgentAdapter
from surfy.adapters.llm import LangChainLLMAdapter
from surfy.adapters.research import DdgsSearchAdapter
from surfy.config import Settings
from surfy.domain.models import (
    CancelledMessage,
    CancelMessage,
    ChatMessage,
    ClearMessage,
    ConnectedMessage,
    DomHighlightMessage,
    ErrorMessage,
    GetStatusMessage,
    HeartbeatMessage,
    InterruptMessage,
    NodeEndMessage,
    NodeStartMessage,
    ResumeMessage,
    RunMessage,
    StateUpdateMessage,
    StepProgressMessage,
)
from surfy.domain.models.messages import (
    CancelledMessageData,
    ChatMessageData,
    ConnectedMessageData,
    DomHighlightMessageData,
    ErrorMessageData,
    InterruptMessageData,
    NodeEndMessageData,
    NodeStartMessageData,
    StateUpdateMessageData,
    parse_client_message,
)
from surfy.domain.services import (
    ActorService,
    EvaluatorService,
    PlannerService,
    ReporterService,
    ResearcherService,
    ScoutService,
)
from surfy.graph import compile_graph
from surfy.observability import create_langfuse_handler
from surfy.state import AgentState

HEARTBEAT_INTERVAL_SECONDS = 30.0
logger = logging.getLogger(__name__)


def _ensure_asyncio_create_task_compat() -> None:
    params = inspect.signature(asyncio.create_task).parameters
    if "context" in params:
        return

    original_create_task = asyncio.create_task

    def create_task_compat(coro, *, name=None, context=None):
        _ = context
        if name is not None:
            return original_create_task(coro, name=name)
        return original_create_task(coro)

    asyncio.create_task = create_task_compat


@dataclass
class ServerRuntime:
    graph: Any
    browser: Any
    agent_session: Any
    scout_adapter: BrowserUseAgentAdapter | None = None


BROWSER_WATCHDOG_INTERVAL = 5.0
BROWSER_WATCHDOG_MAX_FAILURES = 3


def _new_thread_id() -> str:
    return f"surfy-{uuid.uuid4().hex[:8]}"


@dataclass
class SessionStore:
    websocket: WebSocket | None = None
    runtime: ServerRuntime | None = None
    graph_task: asyncio.Task[None] | None = None
    browser_watchdog_task: asyncio.Task[None] | None = None
    current_state: dict[str, Any] | None = None
    chat_queue: list[str] = field(default_factory=list)
    last_activity_at: float = 0.0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    thread_id: str = field(default_factory=_new_thread_id)


_SESSION = SessionStore()


def _is_browser_alive() -> bool:
    if _SESSION.runtime is None:
        return False
    try:
        session = _SESSION.runtime.agent_session
        return getattr(session, "_cdp_client_root", None) is not None
    except Exception:
        return False


async def _cancel_graph_task() -> None:
    task = _SESSION.graph_task
    if task is not None and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    _SESSION.graph_task = None


async def _stop_browser_watchdog() -> None:
    task = _SESSION.browser_watchdog_task
    if task is not None and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    _SESSION.browser_watchdog_task = None


async def _cleanup_runtime() -> None:
    await _stop_browser_watchdog()
    await _cancel_graph_task()

    if _SESSION.runtime is not None:
        try:
            await _SESSION.runtime.agent_session.stop()
        except Exception:
            logger.warning("Failed to stop agent session during cleanup")
        try:
            await _SESSION.runtime.browser.close()
        except Exception:
            logger.warning("Failed to close browser during cleanup")
        _SESSION.runtime = None

    _SESSION.current_state = None
    _SESSION.chat_queue.clear()


async def _cleanup_runtime_from_watchdog() -> None:
    """Watchdog 전용 cleanup — watchdog 자신은 cancel하지 않음."""
    await _cancel_graph_task()
    if _SESSION.runtime is not None:
        try:
            await _SESSION.runtime.agent_session.stop()
        except Exception:
            logger.warning("Failed to stop agent session during watchdog cleanup")
        try:
            await _SESSION.runtime.browser.close()
        except Exception:
            logger.warning("Failed to close browser during watchdog cleanup")
        _SESSION.runtime = None

    _SESSION.current_state = None
    _SESSION.chat_queue.clear()


async def _browser_watchdog() -> None:
    consecutive_failures = 0
    while True:
        await asyncio.sleep(BROWSER_WATCHDOG_INTERVAL)
        if _SESSION.runtime is None:
            consecutive_failures = 0
            continue
        if _is_browser_alive():
            consecutive_failures = 0
            continue

        consecutive_failures += 1
        if consecutive_failures < BROWSER_WATCHDOG_MAX_FAILURES:
            logger.warning(
                "Browser health check failed (%d/%d)",
                consecutive_failures,
                BROWSER_WATCHDOG_MAX_FAILURES,
            )
            continue

        logger.warning("Browser disconnected — cancelling graph task and cleaning up runtime")
        await _send_message(ErrorMessage(data=ErrorMessageData(message="Browser disconnected", node=None)))

        async with _SESSION.lock:
            await _cleanup_runtime_from_watchdog()
            await _send_message(CancelledMessage(data=CancelledMessageData(reason="Browser disconnected")))
        consecutive_failures = 0


@asynccontextmanager
async def _lifespan(_: FastAPI):
    yield
    await _cleanup_runtime()


app = FastAPI(lifespan=_lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


def _initial_state(command: str) -> AgentState:
    return {
        "command": command,
        "research_result": None,
        "plan": None,
        "route_map": None,
        "current_task_idx": 0,
        "eval_result": None,
        "retry_count": 0,
        "max_retries": 3,
        "history": [],
        "completed_tasks": [],
        "last_page_state": None,
        "plan_approved": False,
        "user_feedback": None,
        "auth_required": False,
        "done": False,
        "error": None,
    }


def _to_plain(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return {key: _to_plain(item) for key, item in value.model_dump().items()}
    if isinstance(value, dict):
        return {key: _to_plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_plain(item) for item in value]
    if isinstance(value, tuple):
        return [_to_plain(item) for item in value]
    return value


def _state_update_from(state: dict[str, Any]) -> StateUpdateMessage:
    plan = state.get("plan")
    plan_payload = _to_plain(plan) if plan is not None else None
    completed = state.get("completed_tasks") or []
    data = StateUpdateMessageData(
        plan=plan_payload,
        current_task_idx=int(state.get("current_task_idx", 0)),
        completed_count=len(completed),
        done=bool(state.get("done", False)),
        error=state.get("error"),
    )
    return StateUpdateMessage(data=data)


def _interrupt_type_from(payload: dict[str, Any]) -> Literal["plan_approval", "human_gateway", "completion_check"]:
    raw = payload.get("type")
    if raw in {"plan_approval", "human_gateway", "completion_check"}:
        return raw
    return "human_gateway"


async def _send_message(message: BaseModel) -> None:
    websocket = _SESSION.websocket
    if websocket is None:
        return
    try:
        await websocket.send_text(message.model_dump_json())
        _SESSION.last_activity_at = time.monotonic()
    except Exception:
        _SESSION.websocket = None


async def _stream_scout_step_progress(adapter: BrowserUseAgentAdapter, stop_event: asyncio.Event) -> None:
    while True:
        if stop_event.is_set() and adapter.step_progress_queue.empty():
            return

        try:
            step_data = await asyncio.wait_for(adapter.step_progress_queue.get(), timeout=0.05)
        except TimeoutError:
            continue

        await _send_message(StepProgressMessage(data=step_data))


async def _get_or_create_runtime() -> ServerRuntime:
    if _SESSION.runtime is not None:
        return _SESSION.runtime

    _ensure_asyncio_create_task_compat()

    settings = Settings()
    browser_cfg = settings.browser

    browser: BrowserUseAdapter | None = None
    try:
        browser = await BrowserUseAdapter.create(
            cdp_url=browser_cfg.cdp_url,
            use_system_chrome=browser_cfg.use_system_chrome,
            chrome_profile=browser_cfg.chrome_profile,
        )
        shared_session = browser.get_session()

        google_api_key = settings.google_api_key or os.environ.get("GOOGLE_API_KEY")
        anthropic_api_key = settings.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")

        if google_api_key:
            from langchain_google_genai import ChatGoogleGenerativeAI

            chat_model = ChatGoogleGenerativeAI(model=settings.llm.model_name, google_api_key=google_api_key)
            scout_llm = BrowserUseChatGoogle(
                model=settings.scout.model_name,
                api_key=google_api_key,
                thinking_budget=0,
            )
            logger.info("LLM using Gemini: %s", settings.llm.model_name)
            logger.info("Scout using Gemini: %s", settings.scout.model_name)
        elif anthropic_api_key:
            from langchain_anthropic import ChatAnthropic

            chat_model = ChatAnthropic(model_name=settings.llm.model_name, timeout=None, stop=None)
            agent_llm = BrowserUseChatAnthropic(model=settings.llm.model_name)
            scout_llm = agent_llm
            logger.info("LLM using Anthropic: %s", settings.llm.model_name)
            logger.warning("Scout falling back to Claude (no GOOGLE_API_KEY)")
        else:
            raise RuntimeError("Either GOOGLE_API_KEY or ANTHROPIC_API_KEY must be set")

        llm = LangChainLLMAdapter(
            model=chat_model, use_vision=settings.llm.use_vision, handoff_on_auth=settings.handoff_on_auth
        )

        agent_adapter = BrowserUseAgentAdapter(session=shared_session, llm=scout_llm)
        researcher = ResearcherService(research_port=DdgsSearchAdapter())
        planner = PlannerService(llm=llm)
        actor = ActorService(browser=browser, llm=llm)
        scout = ScoutService(scout=agent_adapter)
        evaluator = EvaluatorService(browser=browser, llm=llm)
        reporter = ReporterService(llm=llm)

        compiled_graph = compile_graph(
            scout=scout,
            planner=planner,
            actor=actor,
            evaluator=evaluator,
            reporter=reporter,
            researcher=researcher,
            checkpointer=MemorySaver(),
            scout_max_steps=settings.scout.max_steps,
            handoff_on_auth=settings.handoff_on_auth,
        )

        langfuse_handler = create_langfuse_handler()
        if langfuse_handler is not None:
            graph = compiled_graph.with_config({"callbacks": [langfuse_handler]})
        else:
            graph = compiled_graph

        _SESSION.runtime = ServerRuntime(
            graph=graph,
            browser=browser,
            agent_session=shared_session,
            scout_adapter=agent_adapter,
        )

        if _SESSION.browser_watchdog_task is None or _SESSION.browser_watchdog_task.done():
            _SESSION.browser_watchdog_task = asyncio.create_task(_browser_watchdog())

        return _SESSION.runtime
    except Exception:
        if browser is not None:
            try:
                await browser.close()
            except Exception:
                logger.warning("Failed to close browser during runtime creation cleanup")
        raise


async def _handle_graph_stream(input_payload: AgentState | Command) -> None:
    try:
        runtime = await _get_or_create_runtime()
        config = {"configurable": {"thread_id": _SESSION.thread_id}}

        async for event in runtime.graph.astream(input_payload, config):
            for node_name, updates in event.items():
                if node_name == "__interrupt__":
                    continue

                plain_updates = _to_plain(updates)
                if not isinstance(plain_updates, dict):
                    continue

                scout_stop_event: asyncio.Event | None = None
                scout_stream_task: asyncio.Task[None] | None = None

                try:
                    await _send_message(NodeStartMessage(data=NodeStartMessageData(node=node_name)))

                    if node_name == "scout" and runtime.scout_adapter is not None:
                        scout_stop_event = asyncio.Event()
                        scout_stream_task = asyncio.create_task(
                            _stream_scout_step_progress(runtime.scout_adapter, scout_stop_event)
                        )

                    if node_name == "actor":
                        state = _SESSION.current_state or {}
                        plan = state.get("plan")
                        current_idx = state.get("current_task_idx", 0)
                        task_desc = None
                        if plan and isinstance(plan, dict):
                            tasks = plan.get("tasks", [])
                            if 0 <= current_idx < len(tasks):
                                task_desc = tasks[current_idx].get("description")

                        await _send_message(
                            DomHighlightMessage(
                                data=DomHighlightMessageData(
                                    action_type="task_start",
                                    description=task_desc,
                                )
                            )
                        )

                    if node_name == "scout" and runtime.scout_adapter is not None:
                        for _ in range(10):
                            if runtime.scout_adapter.step_progress_queue.empty():
                                break
                            await asyncio.sleep(0.01)

                    await _send_message(NodeEndMessage(data=NodeEndMessageData(node=node_name, updates=plain_updates)))

                    if node_name == "report" and plain_updates.get("report_result"):
                        await _send_message(ChatMessage(data=ChatMessageData(message=plain_updates["report_result"])))

                    if node_name == "actor":
                        await _send_message(DomHighlightMessage(data=DomHighlightMessageData(action_type="task_end")))

                    state = _SESSION.current_state or {}
                    state.update(plain_updates)
                    _SESSION.current_state = state
                    await _send_message(_state_update_from(state))
                finally:
                    if scout_stop_event is not None and scout_stream_task is not None:
                        scout_stop_event.set()
                        await scout_stream_task

        snapshot = await runtime.graph.aget_state(config)
        snapshot_values = _to_plain(getattr(snapshot, "values", {}))
        if snapshot_values:
            state = _SESSION.current_state or {}
            state.update(snapshot_values)
            _SESSION.current_state = state

        if getattr(snapshot, "next", ()):
            tasks = getattr(snapshot, "tasks", [])
            if tasks and getattr(tasks[0], "interrupts", []):
                payload = _to_plain(tasks[0].interrupts[0].value)
                if _SESSION.chat_queue:
                    payload["queued_messages"] = list(_SESSION.chat_queue)
                    _SESSION.chat_queue.clear()
                await _send_message(
                    InterruptMessage(
                        data=InterruptMessageData(
                            interrupt_type=_interrupt_type_from(payload),
                            payload=payload,
                        )
                    )
                )
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.exception("Graph execution failed")
        await _send_message(ErrorMessage(data=ErrorMessageData(message=str(e), node=None)))
    finally:
        _SESSION.graph_task = None


async def _clear_session() -> None:
    await _cancel_graph_task()
    _SESSION.current_state = None
    _SESSION.chat_queue.clear()
    _SESSION.thread_id = _new_thread_id()
    logger.info("Session cleared — new thread_id: %s", _SESSION.thread_id)
    await _send_message(ConnectedMessage(data=ConnectedMessageData(state=None, running=False)))


async def _start_run(command: str) -> None:
    if _SESSION.graph_task is not None and not _SESSION.graph_task.done():
        if not _is_browser_alive():
            logger.warning("Graph task running but browser dead — force cancelling")
            await _cancel_graph_task()
            await _cleanup_runtime()
        else:
            await _send_message(ErrorMessage(data=ErrorMessageData(message="Graph is already running", node=None)))
            return

    _SESSION.thread_id = _new_thread_id()
    _SESSION.current_state = _to_plain(_initial_state(command))
    _SESSION.chat_queue.clear()
    _ensure_asyncio_create_task_compat()
    _SESSION.graph_task = asyncio.create_task(_handle_graph_stream(_initial_state(command)))


async def _start_resume(value: dict[str, Any]) -> None:
    if _SESSION.graph_task is not None and not _SESSION.graph_task.done():
        await _send_message(ErrorMessage(data=ErrorMessageData(message="Graph is already running", node=None)))
        return

    _ensure_asyncio_create_task_compat()
    _SESSION.graph_task = asyncio.create_task(_handle_graph_stream(Command(resume=value)))


async def _cancel_run() -> None:
    task = _SESSION.graph_task
    if task is None or task.done():
        await _send_message(CancelledMessage(data=CancelledMessageData(reason="No running task")))
        _SESSION.graph_task = None
        return

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    await _send_message(CancelledMessage(data=CancelledMessageData(reason="Cancelled by client")))


async def _heartbeat_loop(websocket: WebSocket) -> None:
    while _SESSION.websocket is websocket:
        await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
        if _SESSION.websocket is not websocket:
            return
        now = time.monotonic()
        if now - _SESSION.last_activity_at >= HEARTBEAT_INTERVAL_SECONDS:
            await _send_message(HeartbeatMessage())


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    _SESSION.websocket = websocket
    _SESSION.last_activity_at = time.monotonic()

    if _SESSION.runtime is not None and not _is_browser_alive():
        logger.warning("Stale runtime detected on reconnect — cleaning up")
        async with _SESSION.lock:
            await _cleanup_runtime()

    is_running = _SESSION.graph_task is not None and not _SESSION.graph_task.done()
    await _send_message(ConnectedMessage(data=ConnectedMessageData(state=_SESSION.current_state, running=is_running)))

    heartbeat_task = asyncio.create_task(_heartbeat_loop(websocket))

    try:
        while True:
            raw = await websocket.receive_text()
            _SESSION.last_activity_at = time.monotonic()

            try:
                message = parse_client_message(raw)
            except ValueError as e:
                await _send_message(ErrorMessage(data=ErrorMessageData(message=str(e), node=None)))
                continue

            if isinstance(message, RunMessage):
                async with _SESSION.lock:
                    await _start_run(message.data.command)
            elif isinstance(message, ResumeMessage):
                async with _SESSION.lock:
                    await _start_resume(message.data.value.model_dump())
            elif isinstance(message, CancelMessage):
                async with _SESSION.lock:
                    await _cancel_run()
            elif isinstance(message, HeartbeatMessage):
                await _send_message(HeartbeatMessage())
            elif isinstance(message, GetStatusMessage):
                task_running = _SESSION.graph_task is not None and not _SESSION.graph_task.done()
                await _send_message(
                    ConnectedMessage(data=ConnectedMessageData(state=_SESSION.current_state, running=task_running))
                )
            elif isinstance(message, ClearMessage):
                async with _SESSION.lock:
                    await _clear_session()
            elif isinstance(message, ChatMessage):
                _SESSION.chat_queue.append(message.data.message)
    except WebSocketDisconnect:
        pass
    finally:
        if _SESSION.websocket is websocket:
            _SESSION.websocket = None
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
