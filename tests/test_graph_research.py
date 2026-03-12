from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

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
        "user_feedback": None,
        "research_result": None,
        "done": False,
        "error": None,
    }


def _build_graph(researcher):
    scout = MagicMock()
    scout.scout = AsyncMock(return_value=RouteMap(steps=[], final_url="https://example.com", scout_summary="요약"))

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
async def test_scout_completed_skips_planner():
    researcher = MagicMock()
    researcher.research = AsyncMock(return_value=None)

    scout = MagicMock()
    scout.scout = AsyncMock(
        return_value=RouteMap(
            steps=[], final_url="https://example.com", scout_summary="완료", scout_completed=True
        )
    )

    planner = MagicMock()
    planner.create_plan = AsyncMock()
    planner.next_tasks = AsyncMock()
    planner.replan = AsyncMock()

    actor = MagicMock()
    evaluator = MagicMock()
    graph = compile_graph(scout=scout, planner=planner, actor=actor, evaluator=evaluator, researcher=researcher)

    result = await graph.ainvoke(_initial_state("네이버 열어"))

    assert result["done"] is True
    assert result["route_map"].scout_completed is True
    planner.create_plan.assert_not_awaited()


@pytest.mark.asyncio
async def test_scout_not_completed_routes_to_planner():
    researcher = MagicMock()
    researcher.research = AsyncMock(return_value=None)
    graph = _build_graph(researcher=researcher)

    result = await graph.ainvoke(_initial_state("네이버에서 날씨 검색"))

    assert result["done"] is True
    assert result["plan"] is not None


@pytest.mark.asyncio
async def test_scout_exception_falls_through_to_planner():
    researcher = MagicMock()
    researcher.research = AsyncMock(return_value=None)

    scout = MagicMock()
    scout.scout = AsyncMock(side_effect=RuntimeError("browser crash"))

    planner = MagicMock()
    planner.create_plan = AsyncMock(return_value=Plan(anchor="a", tasks=[], anchor_rationale="r"))
    planner.next_tasks = AsyncMock()
    planner.replan = AsyncMock()

    actor = MagicMock()
    evaluator = MagicMock()
    graph = compile_graph(scout=scout, planner=planner, actor=actor, evaluator=evaluator, researcher=researcher)

    result = await graph.ainvoke(_initial_state("네이버 열어"))

    assert result["route_map"] is None
    planner.create_plan.assert_awaited_once()


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


@pytest.mark.asyncio
async def test_plan_modification_resume_triggers_replan_and_new_approval_interrupt():
    researcher = MagicMock()
    researcher.research = AsyncMock(
        return_value=ResearchResult(summary="요약", sources=["https://a.com"], raw_results=[])
    )

    scout = MagicMock()
    scout.scout = AsyncMock(return_value=RouteMap(steps=[], final_url="https://example.com", scout_summary="요약"))

    planner = MagicMock()
    initial_plan = Plan(
        anchor="결과 확인",
        anchor_rationale="초기 계획",
        tasks=[Task(description="초기 태스크", success_criteria=SuccessCriteria(text_visible="초기"))],
    )
    replanned = Plan(
        anchor="결과 확인",
        anchor_rationale="수정 반영",
        tasks=[Task(description="수정된 태스크", success_criteria=SuccessCriteria(text_visible="수정"))],
    )
    planner.create_plan = AsyncMock(return_value=initial_plan)
    planner.next_tasks = AsyncMock()
    planner.replan = AsyncMock(return_value=replanned)

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

    config = cast(RunnableConfig, {"configurable": {"thread_id": "plan_modification_replan"}})
    async for _ in graph.astream(_initial_state("복잡한 검색 요청"), config):
        pass

    before_resume = await graph.aget_state(config)
    assert before_resume.next == ("plan_approval",)

    modification = "검색 대신 뉴스 탭으로 바로 가도록 바꿔줘"
    resume_events: list[dict] = []
    async for event in graph.astream(Command(resume={"approved": False, "modification": modification}), config):
        resume_events.append(event)

    plan_approval_updates = [
        updates for event in resume_events for node_name, updates in event.items() if node_name == "plan_approval"
    ]
    assert any(update.get("user_feedback") == modification for update in plan_approval_updates)

    planner.replan.assert_awaited_once()
    assert planner.replan.await_args.args[2] == modification

    after_resume = await graph.aget_state(config)
    assert after_resume.next == ("plan_approval",)
