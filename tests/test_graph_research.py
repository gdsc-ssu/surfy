from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver

from surfy.domain.models import RouteMap, RouteStep, SuccessCriteria, Task
from surfy.domain.models.plan import Plan
from surfy.domain.models.research import ResearchResult
from surfy.graph import _is_simple_navigation_command, compile_graph


def _initial_state(command: str) -> dict:
    return {
        "command": command,
        "plan": None,
        "route_map": None,
        "current_task_idx": 0,
        "eval_result": None,
        "retry_count": 0,
        "max_retries": 1,
        "history": [],
        "completed_tasks": [],
        "last_page_state": None,
        "plan_approved": False,
        "research_result": None,
        "done": False,
        "error": None,
    }


def _build_graph(researcher):
    scout = MagicMock()
    scout.scout = AsyncMock(return_value=MagicMock())

    planner = MagicMock()
    planner.create_plan = AsyncMock(return_value=Plan(anchor="a", tasks=[], anchor_rationale="r"))
    planner.next_tasks = AsyncMock()
    planner.replan = AsyncMock()

    actor = MagicMock()
    evaluator = MagicMock()

    return compile_graph(scout=scout, planner=planner, actor=actor, evaluator=evaluator, researcher=researcher)


def test_is_simple_navigation_command_with_url():
    assert _is_simple_navigation_command("https://example.com") is True


def test_is_simple_navigation_command_with_short_text():
    assert _is_simple_navigation_command("네이버") is True


def test_is_simple_navigation_command_with_normal_command():
    assert _is_simple_navigation_command("네이버에서 오늘 날씨 검색") is False


@pytest.mark.asyncio
async def test_research_node_skips_simple_navigation_command():
    researcher = MagicMock()
    researcher.research = AsyncMock()
    graph = _build_graph(researcher=researcher)

    result = await graph.ainvoke(_initial_state("https://example.com"))

    assert result["research_result"] is None
    researcher.research.assert_not_awaited()


@pytest.mark.asyncio
async def test_research_node_runs_and_stores_result_for_complex_command():
    researcher = MagicMock()
    research_result = ResearchResult(summary="요약", sources=["https://a.com"], raw_results=[])
    researcher.research = AsyncMock(return_value=research_result)
    graph = _build_graph(researcher=researcher)

    result = await graph.ainvoke(_initial_state("파이썬 비동기 처리 방법 조사"))

    assert result["research_result"] == research_result
    researcher.research.assert_awaited_once_with("파이썬 비동기 처리 방법 조사")


@pytest.mark.asyncio
async def test_research_node_handles_researcher_failure():
    researcher = MagicMock()
    researcher.research = AsyncMock(side_effect=RuntimeError("timeout"))
    graph = _build_graph(researcher=researcher)

    result = await graph.ainvoke(_initial_state("LLM 벤치마크 비교 분석"))

    assert result["research_result"] is None


@pytest.mark.asyncio
async def test_plan_approval_interrupt_payload_contains_plan_and_route_map():
    researcher = MagicMock()
    researcher.research = AsyncMock(
        return_value=ResearchResult(summary="요약", sources=["https://a.com"], raw_results=[])
    )

    scout = MagicMock()
    route_map = RouteMap(
        steps=[
            RouteStep(
                url="https://example.com/search",
                title="검색",
                action_taken="검색어 입력",
                observed_elements=["검색창"],
                notes="정상",
            )
        ],
        final_url="https://example.com/result",
        scout_summary="검색 결과 페이지로 이동 가능",
    )
    scout.scout = AsyncMock(return_value=route_map)

    planner = MagicMock()
    plan = Plan(
        anchor="결과 확인",
        anchor_rationale="핵심 결과 페이지 진입이 목표",
        tasks=[
            Task(
                description="결과 링크 클릭",
                target_url="https://example.com/result",
                success_criteria=SuccessCriteria(text_visible="결과"),
            )
        ],
    )
    planner.create_plan = AsyncMock(return_value=plan)
    planner.next_tasks = AsyncMock()
    planner.replan = AsyncMock()

    actor = MagicMock()
    evaluator = MagicMock()
    graph = compile_graph(
        scout=scout,
        planner=planner,
        actor=actor,
        evaluator=evaluator,
        researcher=researcher,
        checkpointer=MemorySaver(),
    )

    config = cast(RunnableConfig, {"configurable": {"thread_id": "research_interrupt_payload"}})
    async for _ in graph.astream(_initial_state("복잡한 검색 요청"), config):
        pass

    state = await graph.aget_state(config)
    assert state.next == ("plan_approval",)
    interrupt_payload = state.tasks[0].interrupts[0].value
    assert interrupt_payload["type"] == "plan_approval"
    assert interrupt_payload["plan"] == plan.model_dump()
    assert interrupt_payload["route_map"] == route_map.model_dump()
