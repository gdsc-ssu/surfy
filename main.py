import asyncio
import inspect
import logging
import sys
from typing import cast

from langgraph.checkpoint.memory import MemorySaver

from surfy.adapters.browser import BrowserUseAdapter
from surfy.adapters.llm import AnthropicAdapter
from surfy.domain.services import ActorService, EvaluatorService, PlannerService
from surfy.graph import compile_graph
from surfy.state import AgentState


def _ensure_asyncio_create_task_compat() -> None:
    params = inspect.signature(asyncio.create_task).parameters
    if "context" in params:
        return

    original_create_task = asyncio.create_task

    def create_task_compat(coro, *, name=None, context=None):
        if name is not None:
            return original_create_task(coro, name=name)
        return original_create_task(coro)

    asyncio.create_task = create_task_compat


async def run(command: str) -> AgentState:
    _ensure_asyncio_create_task_compat()
    browser = await BrowserUseAdapter.create()
    llm = AnthropicAdapter(use_vision=True, model_name="claude-sonnet-4-20250514")

    planner = PlannerService(llm=llm)
    actor = ActorService(browser=browser, llm=llm)
    evaluator = EvaluatorService(browser=browser, llm=llm)

    checkpointer = MemorySaver()
    graph = compile_graph(planner=planner, actor=actor, evaluator=evaluator, checkpointer=checkpointer)

    initial_state: AgentState = {
        "command": command,
        "plan": None,
        "current_task_idx": 0,
        "eval_result": None,
        "retry_count": 0,
        "max_retries": 3,
        "history": [],
        "completed_tasks": [],
        "last_page_state": None,
        "done": False,
        "error": None,
    }

    try:
        result = await graph.ainvoke(initial_state, config={"configurable": {"thread_id": "surfy-phase4-default"}})
        typed_result = cast(AgentState, result)
        logging.info("작업이 완료되었습니다.")
        return typed_result
    finally:
        await browser.close()


def main(command: str) -> None:
    asyncio.run(run(command))


if __name__ == "__main__":
    user_command = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else input("명령을 입력하세요: ")
    main(user_command)
