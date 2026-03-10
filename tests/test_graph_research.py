from unittest.mock import AsyncMock, MagicMock

import pytest

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
