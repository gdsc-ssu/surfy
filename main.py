import asyncio
import inspect
import logging
import sys
from typing import cast

from browser_use import BrowserSession
from browser_use.llm import ChatAnthropic as BrowserUseChatAnthropic
from langgraph.checkpoint.memory import MemorySaver

from surfy.adapters.browser import BrowserUseAdapter
from surfy.adapters.browser.agent_adapter import BrowserUseAgentAdapter
from surfy.adapters.llm import AnthropicAdapter
from surfy.adapters.research import DdgsSearchAdapter
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

    browser = await BrowserUseAdapter.create()
    llm = AnthropicAdapter(use_vision=True, model_name="claude-sonnet-4-20250514")
    agent_llm = BrowserUseChatAnthropic(model="claude-sonnet-4-20250514")

    agent_session = BrowserSession(headless=False, disable_security=True)
    await agent_session.start()

    agent_adapter = BrowserUseAgentAdapter(session=agent_session, llm=agent_llm)
    researcher = ResearcherService(research_port=DdgsSearchAdapter())

    planner = PlannerService(llm=llm)
    actor = ActorService(browser=browser, llm=llm)
    scout = ScoutService(agent_adapter=agent_adapter)
    evaluator = EvaluatorService(browser=browser, llm=llm)

    checkpointer = MemorySaver()
    graph = compile_graph(
        scout=scout,
        planner=planner,
        actor=actor,
        evaluator=evaluator,
        researcher=researcher,
        checkpointer=checkpointer,
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
        "done": False,
        "error": None,
    }

    logger = logging.getLogger("surfy.run")
    final_state = initial_state

    try:
        async for event in graph.astream(
            initial_state,
            config={"configurable": {"thread_id": "surfy-default"}},
        ):
            for node_name, updates in event.items():
                _log_node_result(logger, node_name, updates)
                final_state = {**final_state, **updates}

        logger.info("=" * 60)
        logger.info("작업 완료. done=%s, error=%s", final_state.get("done"), final_state.get("error"))
        return cast(AgentState, final_state)
    finally:
        await agent_session.stop()
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


def main(command: str) -> None:
    asyncio.run(run(command))


if __name__ == "__main__":
    user_command = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else input("명령을 입력하세요: ")
    main(user_command)
