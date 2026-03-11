"""PlannerService RouteMap 지원 단위 테스트."""

import pytest

from surfy.domain.models import (
    ActionType,
    ActorOutput,
    EvalResult,
    HistoryEntry,
    PageState,
    Plan,
    RouteMap,
    RouteStep,
    SuccessCriteria,
    Task,
)
from surfy.domain.models.research import ResearchResult, SearchResult
from surfy.domain.ports import LLMPort
from surfy.domain.services import PlannerService


class MockLLM(LLMPort):
    def __init__(self):
        self.plan_calls: list[tuple[str, str, str, str]] = []

    async def decide_action(
        self, task: Task, page_state: PageState, history: list[HistoryEntry]
    ) -> ActorOutput:
        return ActorOutput(thinking="test", action_type=ActionType.DONE)

    async def scout(
        self, task: Task, page_state: PageState, history: list[HistoryEntry]
    ) -> ActorOutput:
        return ActorOutput(thinking="test", action_type=ActionType.DONE)

    async def plan(self, command: str, progress: str, route_observations: str = "", research_result: str = "") -> Plan:
        self.plan_calls.append((command, progress, route_observations, research_result))
        return Plan(
            anchor=command,
            tasks=[Task(description="Task 1")],
            anchor_rationale="Rationale",
        )

    async def evaluate(self, criteria: SuccessCriteria, page_state: PageState) -> EvalResult:
        return EvalResult(success=True, reason="OK")


@pytest.mark.asyncio
async def test_create_plan_without_route_map():
    """route_map 없이 create_plan 호출 시 route_observations가 비어있는지 확인."""
    llm = MockLLM()
    planner = PlannerService(llm)

    await planner.create_plan("Test command")

    assert llm.plan_calls[0][2] == ""


@pytest.mark.asyncio
async def test_create_plan_with_route_map():
    """route_map과 함께 create_plan 호출 시 route_observations가 채워지는지 확인."""
    llm = MockLLM()
    planner = PlannerService(llm)
    
    route_map = RouteMap(
        steps=[
            RouteStep(
                url="https://example.com",
                title="Example",
                action_taken="GOTO",
                observed_elements=["link1"],
                notes="Start",
            )
        ],
        final_url="https://example.com",
        scout_summary="Found it",
    )

    await planner.create_plan("Test command", route_map=route_map)

    route_obs = llm.plan_calls[0][2]
    assert "Scout 탐색 요약: Found it" in route_obs
    assert "Step 1: GOTO → https://example.com" in route_obs
    assert "발견한 요소: link1" in route_obs
    assert "최종 URL: https://example.com" in route_obs


def test_format_route_observations_empty():
    """빈 steps를 가진 RouteMap 포맷팅 확인."""
    llm = MockLLM()
    planner = PlannerService(llm)
    
    route_map = RouteMap(steps=[], final_url="", scout_summary="")
    obs = planner._format_route_observations(route_map)
    
    assert obs == ""


def test_format_route_observations_content():
    """RouteMap 포맷팅 내용 검증."""
    llm = MockLLM()
    planner = PlannerService(llm)
    
    route_map = RouteMap(
        steps=[
            RouteStep(
                url="https://a.com",
                title="A",
                action_taken="CLICK",
                observed_elements=["e1", "e2"],
                notes="n1",
            ),
            RouteStep(
                url="https://b.com",
                title="B",
                action_taken="TYPE",
                observed_elements=["e3"],
                notes="",
            ),
        ],
        final_url="https://b.com",
        scout_summary="Summary",
    )
    
    obs = planner._format_route_observations(route_map)
    
    assert "Scout 탐색 요약: Summary" in obs
    assert "Step 1: CLICK → https://a.com" in obs
    assert "발견한 요소: e1, e2" in obs
    assert "메모: n1" in obs
    assert "Step 2: TYPE → https://b.com" in obs
    assert "발견한 요소: e3" in obs
    assert "최종 URL: https://b.com" in obs


def test_format_research_result_with_full_result():
    llm = MockLLM()
    planner = PlannerService(llm)

    research_result = ResearchResult(
        summary="파이썬 비동기 처리 방식 비교",
        sources=["https://a.com", "https://b.com"],
        raw_results=[
            SearchResult(title="문서 A", url="https://a.com", snippet="A 설명"),
            SearchResult(title="문서 B", url="https://b.com", snippet=""),
        ],
    )

    formatted = planner._format_research_result(research_result)

    assert "Research 요약: 파이썬 비동기 처리 방식 비교" in formatted
    assert "참고 출처:" in formatted
    assert "- https://a.com" in formatted
    assert "검색 결과:" in formatted
    assert "1. 문서 A (https://a.com)" in formatted
    assert "- A 설명" in formatted
    assert "2. 문서 B (https://b.com)" in formatted


def test_format_research_result_with_empty_sources():
    llm = MockLLM()
    planner = PlannerService(llm)

    research_result = ResearchResult(summary="요약만 있음", sources=[], raw_results=[])

    formatted = planner._format_research_result(research_result)

    assert formatted == "Research 요약: 요약만 있음"


@pytest.mark.asyncio
async def test_create_plan_with_research_result():
    llm = MockLLM()
    planner = PlannerService(llm)
    research_result = ResearchResult(
        summary="핵심 정보",
        sources=["https://research.example.com"],
        raw_results=[],
    )

    await planner.create_plan("Test command", research_result=research_result)

    research_obs = llm.plan_calls[0][3]
    assert "Research 요약: 핵심 정보" in research_obs
    assert "참고 출처:" in research_obs
    assert "- https://research.example.com" in research_obs
