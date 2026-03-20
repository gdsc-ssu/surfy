"""PlannerService 단위 테스트.

mock LLMPort로 3가지 메서드 테스트:
1. create_plan: anchor 설정 검증
2. next_tasks: anchor 불변 검증
3. replan: 실패 정보 전달 검증
"""

import pytest

from surfy.domain.models import (
    ActionType,
    ActorOutput,
    EvalResult,
    HistoryEntry,
    PageState,
    Plan,
    SuccessCriteria,
    Task,
)
from surfy.domain.ports import LLMPort
from surfy.domain.services import PlannerService


class MockLLM(LLMPort):
    """Mock LLMPort for testing PlannerService."""

    def __init__(self):
        self.plan_calls: list[tuple[str, str, str, str]] = []

    async def decide_action(
        self, task: Task, page_state: PageState, history: list[HistoryEntry], **kwargs
    ) -> ActorOutput:
        return ActorOutput(thinking="test", action_type=ActionType.DONE)

    async def scout(self, task: Task, page_state: PageState, history: list[HistoryEntry]) -> ActorOutput:
        return ActorOutput(thinking="test", action_type=ActionType.DONE)

    async def plan(self, command: str, progress: str, route_observations: str = "", research_result: str = "") -> Plan:
        self.plan_calls.append((command, progress, route_observations, research_result))
        return Plan(
            anchor=f"anchor_for_{command[:10]}",
            tasks=[
                Task(
                    description=f"Task for {command}",
                    success_criteria=SuccessCriteria(description="test"),
                )
            ],
            anchor_rationale=f"Rationale for {command}",
        )

    async def evaluate(self, criteria: SuccessCriteria, page_state: PageState) -> EvalResult:
        return EvalResult(success=True, reason="OK")

    async def extract_intent(self, command: str):
        from surfy.domain.models.cache import CommandIntent

        return CommandIntent(service="unknown", action="navigate")

    async def generate_report(self, command: str, task_results: list[dict[str, str]]) -> str:
        return f"Report for {command}"


@pytest.mark.asyncio
async def test_create_plan_sets_anchor():
    """create_plan이 anchor를 설정하는지 검증."""
    llm = MockLLM()
    planner = PlannerService(llm)

    plan = await planner.create_plan("네이버에서 날씨 검색")

    assert plan.anchor.startswith("anchor_for_")
    assert len(plan.tasks) == 1
    assert "네이버" in plan.tasks[0].description
    # LLM.plan이 빈 progress로 호출됨
    assert llm.plan_calls[-1] == ("네이버에서 날씨 검색", "", "", "")


@pytest.mark.asyncio
async def test_next_tasks_preserves_anchor():
    """next_tasks가 원본 anchor를 유지하는지 검증."""
    llm = MockLLM()
    planner = PlannerService(llm)

    # 초기 계획 생성
    original_plan = Plan(
        anchor="원본 앵커 — 절대 변경 안 됨",
        tasks=[Task(description="완료된 태스크")],
        anchor_rationale="초기 이유",
    )
    completed = [Task(description="완료된 태스크")]

    # next_tasks 호출
    new_plan = await planner.next_tasks(original_plan, completed)

    # anchor가 원본 그대로 유지되는지 확인
    assert new_plan.anchor == "원본 앵커 — 절대 변경 안 됨"
    # LLM.plan이 anchor로 호출됨
    assert llm.plan_calls[-1][0] == "원본 앵커 — 절대 변경 안 됨"
    # progress에 완료된 태스크 정보가 포함됨
    assert "완료된 태스크" in llm.plan_calls[-1][1]


@pytest.mark.asyncio
async def test_replan_preserves_anchor():
    """replan이 원본 anchor를 유지하는지 검증."""
    llm = MockLLM()
    planner = PlannerService(llm)

    original_plan = Plan(
        anchor="원본 앵커",
        tasks=[Task(description="실패한 태스크")],
        anchor_rationale="초기 이유",
    )
    failed_task = Task(description="실패한 태스크")

    new_plan = await planner.replan(original_plan, failed_task, "요소를 찾을 수 없음")

    # anchor가 원본 그대로 유지
    assert new_plan.anchor == "원본 앵커"
    # progress에 실패 정보가 포함됨
    assert "실패한 태스크" in llm.plan_calls[-1][1]
    assert "요소를 찾을 수 없음" in llm.plan_calls[-1][1]


@pytest.mark.asyncio
async def test_replan_includes_completed_tasks_context():
    """#62 재현: replan 시 completed_tasks가 progress에 포함되어 중복 방지."""
    llm = MockLLM()
    planner = PlannerService(llm)

    original_plan = Plan(
        anchor="SRT 예약",
        tasks=[Task(description="출발역 선택")],
        anchor_rationale="예약 흐름",
    )
    completed = [Task(description="SRT 홈페이지 접속"), Task(description="예매 탭 클릭")]

    await planner.replan(
        original_plan, Task(description="출발역 선택"), "요소를 찾을 수 없음", completed_tasks=completed
    )

    progress_sent = llm.plan_calls[-1][1]
    assert "SRT 홈페이지 접속" in progress_sent
    assert "예매 탭 클릭" in progress_sent
    assert "출발역 선택" in progress_sent
    assert "요소를 찾을 수 없음" in progress_sent


@pytest.mark.asyncio
async def test_replan_without_completed_tasks_still_works():
    """completed_tasks=None 시 기존 동작과 동일."""
    llm = MockLLM()
    planner = PlannerService(llm)

    original_plan = Plan(
        anchor="검색",
        tasks=[Task(description="실패 태스크")],
        anchor_rationale="이유",
    )

    await planner.replan(original_plan, Task(description="실패 태스크"), "타임아웃")

    progress_sent = llm.plan_calls[-1][1]
    assert "실패 태스크" in progress_sent
    assert "타임아웃" in progress_sent
    assert "완료된 태스크" not in progress_sent


@pytest.mark.asyncio
async def test_summarize_progress_empty():
    """완료된 태스크가 없으면 빈 문자열."""
    llm = MockLLM()
    planner = PlannerService(llm)

    progress = planner._summarize_progress([])
    assert progress == ""


@pytest.mark.asyncio
async def test_summarize_progress_with_tasks():
    """완료된 태스크가 있으면 요약 생성."""
    llm = MockLLM()
    planner = PlannerService(llm)

    completed = [
        Task(description="태스크 1"),
        Task(description="태스크 2"),
    ]
    progress = planner._summarize_progress(completed)

    assert "완료된 태스크" in progress
    assert "태스크 1" in progress
    assert "태스크 2" in progress
