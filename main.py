import argparse
import asyncio
import inspect
import logging
import os
from typing import cast

from browser_use.llm import ChatAnthropic as BrowserUseChatAnthropic
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from surfy.adapters.browser import BrowserUseAdapter
from surfy.adapters.browser.agent_adapter import BrowserUseAgentAdapter
from surfy.adapters.llm import LangChainLLMAdapter
from surfy.adapters.research import DdgsSearchAdapter
from surfy.config import Settings
from surfy.domain.services import ActorService, EvaluatorService, PlannerService, ResearcherService, ScoutService
from surfy.graph import compile_graph
from surfy.state import AgentState


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


async def run(command: str) -> AgentState:
    _ensure_asyncio_create_task_compat()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    settings = Settings()
    browser = await BrowserUseAdapter.create(use_system_chrome=True)
    shared_session = browser.get_session()

    google_api_key = settings.google_api_key or os.environ.get("GOOGLE_API_KEY")
    anthropic_api_key = settings.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")

    if google_api_key:
        from browser_use.llm import ChatGoogle as BrowserUseChatGoogle
        from langchain_google_genai import ChatGoogleGenerativeAI

        chat_model = ChatGoogleGenerativeAI(model=settings.llm.model_name, google_api_key=google_api_key)
        agent_llm = BrowserUseChatGoogle(model=settings.scout.model_name, api_key=google_api_key, thinking_budget=0)
    elif anthropic_api_key:
        from langchain_anthropic import ChatAnthropic

        chat_model = ChatAnthropic(model_name=settings.llm.model_name, timeout=None, stop=None)
        agent_llm = BrowserUseChatAnthropic(model=settings.llm.model_name)
    else:
        raise RuntimeError("Either GOOGLE_API_KEY or ANTHROPIC_API_KEY must be set")

    llm = LangChainLLMAdapter(
        model=chat_model, use_vision=settings.llm.use_vision, handoff_on_auth=settings.handoff_on_auth
    )

    agent_adapter = BrowserUseAgentAdapter(session=shared_session, llm=agent_llm)
    researcher = ResearcherService(research_port=DdgsSearchAdapter())

    planner = PlannerService(llm=llm)
    actor = ActorService(browser=browser, llm=llm)
    scout = ScoutService(scout=agent_adapter)
    evaluator = EvaluatorService(browser=browser, llm=llm)

    checkpointer = MemorySaver()
    graph = compile_graph(
        scout=scout,
        planner=planner,
        actor=actor,
        evaluator=evaluator,
        researcher=researcher,
        checkpointer=checkpointer,
        handoff_on_auth=settings.handoff_on_auth,
    )

    initial_state: AgentState = {
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

    logger = logging.getLogger("surfy.run")
    final_state = initial_state
    config = {"configurable": {"thread_id": "surfy-cli"}}

    try:
        input_payload: AgentState | Command = initial_state
        while True:
            async for event in graph.astream(input_payload, config=config):  # type: ignore
                for node_name, updates in event.items():
                    _log_node_result(logger, node_name, updates)
                    final_state = {**final_state, **updates}

            state = await graph.aget_state(config=config)  # type: ignore
            if not state.next:
                break

            if state.tasks and state.tasks[0].interrupts:
                interrupt = state.tasks[0].interrupts[0]
                payload = interrupt.value
                interrupt_type = payload.get("type")

                if interrupt_type == "plan_approval":
                    plan = payload.get("plan")
                    logger.info("\n" + "=" * 20 + " [PLAN APPROVAL] " + "=" * 20)
                    logger.info("Anchor: %s", plan.get("anchor"))
                    for i, task in enumerate(plan.get("tasks", [])):
                        logger.info("  %d. %s", i + 1, task.get("description"))
                    logger.info("=" * 57 + "\n")

                    ans = input("승인하시겠습니까? (y/n): ").strip().lower()
                    input_payload = Command(resume={"approved": ans == "y"})

                elif interrupt_type == "auth_required":
                    failed_task = payload.get("failed_task")
                    reason = payload.get("reason")
                    logger.info("\n" + "=" * 20 + " [AUTH REQUIRED] " + "=" * 20)
                    logger.info("Task: %s", failed_task)
                    logger.info("Reason: %s", reason)
                    logger.info("=" * 57 + "\n")

                    ans = input("인증을 완료했습니까? (y/n): ").strip().lower()
                    input_payload = Command(resume={"approved": ans == "y"})

                elif interrupt_type == "human_gateway":
                    failed_task = payload.get("failed_task")
                    reason = payload.get("reason")
                    logger.info("\n" + "!" * 20 + " [TASK FAILED] " + "!" * 20)
                    logger.info("Task: %s", failed_task)
                    logger.info("Reason: %s", reason)
                    logger.info("!" * 55 + "\n")

                    ans = input("재시도하시겠습니까? (y/n): ").strip().lower()
                    action = "retry" if ans == "y" else "exit"
                    input_payload = Command(resume={"action": action})

                elif interrupt_type == "completion_check":
                    anchor = payload.get("anchor")
                    completed_count = payload.get("completed_count")
                    logger.info("\n" + "?" * 20 + " [COMPLETION CHECK] " + "?" * 20)
                    logger.info("Anchor: %s", anchor)
                    logger.info("Completed Tasks: %d", completed_count)
                    logger.info("?" * 55 + "\n")

                    ans = input("계속 진행하시겠습니까? (y/n): ").strip().lower()
                    action = "continue" if ans == "y" else "exit"
                    input_payload = Command(resume={"action": action})
                else:
                    logger.warning("Unknown interrupt type: %s", interrupt_type)
                    break
            else:
                break

        logger.info("=" * 60)
        logger.info("작업 완료. done=%s, error=%s", final_state.get("done"), final_state.get("error"))
        return cast(AgentState, final_state)
    finally:
        await browser.close()


def _log_node_result(logger: logging.Logger, node_name: str, updates: dict) -> None:
    """각 노드 실행 결과를 사람이 읽기 좋게 로깅."""
    tag = f"[{node_name.upper()}]"

    if node_name == "research":
        research_result = updates.get("research_result")
        if research_result is not None:
            logger.info(
                "%s Research 완료: %s (%d sources)",
                tag,
                research_result.summary[:80],
                len(research_result.sources),
            )
        else:
            logger.info("%s Research 건너뜀", tag)

    elif node_name == "scout":
        route_map = updates.get("route_map")
        if route_map is not None:
            logger.info(
                "%s RouteMap 생성: %d steps, final_url=%s, summary=%s",
                tag,
                len(route_map.steps),
                route_map.final_url,
                route_map.scout_summary,
            )
        else:
            logger.info("%s Scout 실패 — blind planning으로 진행", tag)

    elif node_name == "planner":
        plan = updates.get("plan")
        if plan is not None:
            task_names = [t.description[:50] for t in plan.tasks]
            logger.info("%s Plan anchor=%s", tag, plan.anchor[:80])
            logger.info("%s   tasks=%s", tag, task_names)
        done = updates.get("done")
        if done:
            logger.info("%s 완료 처리됨 (error=%s)", tag, updates.get("error"))

    elif node_name == "actor":
        history = updates.get("history", [])
        if history:
            entry = history[-1]
            logger.info(
                "%s %s → %s",
                tag,
                entry.action.action_type.value,
                entry.result.message[:80] if entry.result.message else "",
            )

    elif node_name == "plan_approval":
        if updates.get("plan_approved"):
            logger.info("%s 사용자 승인 완료", tag)
        elif updates.get("done"):
            logger.info("%s 사용자가 실행을 취소했습니다", tag)

    elif node_name == "evaluator":
        eval_result = updates.get("eval_result")
        if eval_result is not None:
            logger.info(
                "%s %s — %s",
                tag,
                "✅ 성공" if eval_result.success else "❌ 실패",
                eval_result.reason[:80],
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Surfy: Hierarchical Browser Automation Agent")
    parser.add_argument("command", nargs="?", help="Command to execute in CLI mode")
    parser.add_argument("--serve", action="store_true", help="Start as a FastAPI server")
    parser.add_argument("--port", type=int, default=8765, help="Port for the server (default: 8765)")

    args = parser.parse_args()

    if args.serve:
        import uvicorn
        uvicorn.run("surfy.server:app", host="0.0.0.0", port=args.port)
    else:
        cmd = args.command or input("명령을 입력하세요: ")
        asyncio.run(run(cmd))


if __name__ == "__main__":
    main()
