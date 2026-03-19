from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from surfy.domain.models import (
    ActionType,
    ActorOutput,
    CommandIntent,
    EvalResult,
    HistoryEntry,
    PageState,
    RouteMap,
    StepResult,
    Task,
)
from surfy.domain.models.criteria import SuccessCriteria
from surfy.domain.models.plan import Plan
from surfy.domain.ports import LLMPort
from surfy.domain.services import ReporterService
from surfy.graph import compile_graph


class MockLLM(LLMPort):
    def __init__(self, *, report_text: str = "테스트 리포트", raise_on_report: bool = False):
        self._report_text = report_text
        self._raise_on_report = raise_on_report
        self.generate_report_calls: list[tuple[str, list[dict[str, str]]]] = []

    async def decide_action(self, task: Task, page_state: PageState, history: list[HistoryEntry]) -> ActorOutput:
        return ActorOutput(thinking="test", action_type=ActionType.DONE)

    async def plan(self, command: str, progress: str, route_observations: str = "", research_result: str = "") -> Plan:
        return Plan(anchor=command, tasks=[], anchor_rationale="test")

    async def evaluate(self, criteria: SuccessCriteria, page_state: PageState) -> EvalResult:
        return EvalResult(success=True, reason="OK")

    async def extract_intent(self, command: str) -> CommandIntent:
        return CommandIntent(service="unknown")

    async def generate_report(self, command: str, task_results: list[dict[str, str]]) -> str:
        self.generate_report_calls.append((command, task_results))
        if self._raise_on_report:
            raise RuntimeError("llm failed")
        return self._report_text


@pytest.mark.asyncio
async def test_report_returns_llm_generated_text_when_success():
    llm = MockLLM(report_text="LLM 생성 보고서")
    reporter = ReporterService(llm)

    completed = [Task(description="첫 작업", result="완료")]
    result = await reporter.report("테스트 명령", completed)

    assert result == "LLM 생성 보고서"
    assert len(llm.generate_report_calls) == 1
    assert llm.generate_report_calls[0][0] == "테스트 명령"
    assert llm.generate_report_calls[0][1] == [{"description": "첫 작업", "result": "완료"}]


@pytest.mark.asyncio
async def test_report_returns_fallback_text_when_llm_fails():
    llm = MockLLM(raise_on_report=True)
    reporter = ReporterService(llm)

    completed = [Task(description="작업 A", result="실패 후 수동 완료")]
    result = await reporter.report("테스트 명령", completed)

    assert result == "완료된 작업:\n- 작업 A: 실패 후 수동 완료"


@pytest.mark.asyncio
async def test_report_uses_default_text_for_none_task_result():
    llm = MockLLM(report_text="unused")
    reporter = ReporterService(llm)

    completed = [Task(description="결과 없는 작업", result=None)]
    await reporter.report("테스트 명령", completed)

    assert llm.generate_report_calls[0][1] == [{"description": "결과 없는 작업", "result": "결과 없음"}]


@pytest.mark.asyncio
async def test_report_node_stores_report_result_after_completion():
    scout = MagicMock()
    scout.scout = AsyncMock(return_value=RouteMap(steps=[], final_url="https://example.com", scout_summary="요약"))

    task = Task(description="단일 태스크")
    planner = MagicMock()
    planner.create_plan = AsyncMock(return_value=Plan(anchor="목표", anchor_rationale="이유", tasks=[task]))
    planner.next_tasks = AsyncMock(return_value=Plan(anchor="목표", anchor_rationale="끝", tasks=[]))
    planner.replan = AsyncMock()

    actor = MagicMock()
    actor.execute_task = AsyncMock(
        return_value=StepResult(
            success=True,
            message="완료",
            page_state=PageState(url="https://example.com", title="Example", dom_text="ok"),
        )
    )

    evaluator = MagicMock()
    evaluator.evaluate = AsyncMock(return_value=EvalResult(success=True, reason="성공"))

    reporter = MagicMock()
    reporter.report = AsyncMock(return_value="최종 리포트")

    graph = compile_graph(
        scout=scout,
        planner=planner,
        actor=actor,
        evaluator=evaluator,
        reporter=reporter,
        researcher=None,
        checkpointer=MemorySaver(),
    )

    initial_state = {
        "command": "리포트 테스트",
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
        "auth_required": False,
        "done": False,
        "error": None,
    }
    config = RunnableConfig(configurable={"thread_id": "report_node_test"})

    async for _ in graph.astream(initial_state, config):
        pass
    async for _ in graph.astream(Command(resume={"approved": True}), config):
        pass
    async for _ in graph.astream(Command(resume={"approved": False}), config):
        pass

    final_state = await graph.aget_state(config)
    assert final_state.values.get("report_result") == "최종 리포트"
    reporter.report.assert_awaited_once()
    assert reporter.report.await_args.args[0] == "리포트 테스트"
    assert len(reporter.report.await_args.args[1]) == 1
