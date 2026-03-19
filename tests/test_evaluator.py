"""EvaluatorService 단위 테스트.

mock BrowserPort/LLMPort로 3가지 평가 경로 테스트:
1. URL 불일치 → 즉시 실패
2. 텍스트 불일치 → 즉시 실패
3. 구조 체크 통과 → LLM 호출
"""

import pytest

from surfy.domain.models import (
    ActionType,
    ActorOutput,
    BrowserAction,
    EvalResult,
    HistoryEntry,
    PageState,
    Plan,
    StepResult,
    SuccessCriteria,
    Task,
)
from surfy.domain.ports import BrowserPort, LLMPort
from surfy.domain.services import EvaluatorService


class MockBrowser(BrowserPort):
    """Mock BrowserPort for testing."""

    def __init__(self, *, text_visible: bool = True):
        self._text_visible = text_visible

    async def get_page_state(self) -> PageState:
        return PageState(url="https://example.com", title="Test", dom_text="test content")

    async def execute_action(self, action: BrowserAction) -> StepResult:
        return StepResult(success=True, message="OK")

    async def check_text_visible(self, text: str) -> bool:
        return self._text_visible

    async def close(self) -> None:
        pass


class MockLLM(LLMPort):
    """Mock LLMPort for testing."""

    def __init__(self, *, eval_result: EvalResult | None = None):
        self._eval_result = eval_result or EvalResult(success=True, reason="LLM says OK")
        self.evaluate_called = False

    async def decide_action(
        self, task: Task, page_state: PageState, history: list[HistoryEntry], **kwargs
    ) -> ActorOutput:
        return ActorOutput(thinking="test", action_type=ActionType.DONE)

    async def scout(self, task: Task, page_state: PageState, history: list[HistoryEntry]) -> ActorOutput:
        return ActorOutput(thinking="test", action_type=ActionType.DONE)

    async def plan(self, command: str, progress: str, route_observations: str = "") -> Plan:
        return Plan(anchor=command, tasks=[], anchor_rationale="test")

    async def evaluate(self, criteria: SuccessCriteria, page_state: PageState) -> EvalResult:
        self.evaluate_called = True
        return self._eval_result

    async def extract_intent(self, command: str):
        from surfy.domain.models.cache import CommandIntent
        return CommandIntent(service="unknown", action="navigate")
    async def generate_report(self, command: str, task_results: list[dict[str, str]]) -> str:
        return f"Report for {command}"


@pytest.mark.asyncio
async def test_url_mismatch_fails_immediately():
    """URL 불일치 시 즉시 실패 (LLM 호출 없음)."""
    browser = MockBrowser()
    llm = MockLLM()
    evaluator = EvaluatorService(browser, llm)

    task = Task(
        description="테스트",
        success_criteria=SuccessCriteria(url_contains="naver.com"),
    )
    page_state = PageState(url="https://google.com", title="Google", dom_text="")

    result = await evaluator.evaluate(task, page_state)

    assert result.success is False
    assert "naver.com" in result.reason
    assert llm.evaluate_called is False  # LLM 호출 안 함


@pytest.mark.asyncio
async def test_text_not_visible_fails_immediately():
    """텍스트 불일치 시 즉시 실패 (LLM 호출 없음)."""
    browser = MockBrowser(text_visible=False)
    llm = MockLLM()
    evaluator = EvaluatorService(browser, llm)

    task = Task(
        description="테스트",
        success_criteria=SuccessCriteria(text_visible="검색 결과"),
    )
    page_state = PageState(url="https://example.com", title="Test", dom_text="")

    result = await evaluator.evaluate(task, page_state)

    assert result.success is False
    assert "검색 결과" in result.reason
    assert llm.evaluate_called is False  # LLM 호출 안 함


@pytest.mark.asyncio
async def test_structure_check_passes_calls_llm():
    """구조 체크 통과 + description 있으면 LLM 호출."""
    browser = MockBrowser(text_visible=True)
    llm = MockLLM(eval_result=EvalResult(success=True, reason="LLM 판정: 성공"))
    evaluator = EvaluatorService(browser, llm)

    task = Task(
        description="테스트",
        success_criteria=SuccessCriteria(
            url_contains="example.com",
            text_visible="content",
            description="페이지에 컨텐츠가 표시되어야 함",
        ),
    )
    page_state = PageState(url="https://example.com/page", title="Test", dom_text="content")

    result = await evaluator.evaluate(task, page_state)

    assert result.success is True
    assert llm.evaluate_called is True  # LLM 호출됨
    assert "LLM 판정" in result.reason


@pytest.mark.asyncio
async def test_no_criteria_passes_immediately():
    """아무 기준도 없으면 즉시 성공."""
    browser = MockBrowser()
    llm = MockLLM()
    evaluator = EvaluatorService(browser, llm)

    task = Task(description="테스트", success_criteria=SuccessCriteria())
    page_state = PageState(url="https://example.com", title="Test", dom_text="")

    result = await evaluator.evaluate(task, page_state)

    assert result.success is True
    assert "구조 체크 통과" in result.reason
    assert llm.evaluate_called is False  # LLM 호출 안 함


@pytest.mark.asyncio
async def test_url_matches_but_no_description_passes():
    """URL 매칭 + description 없음 → LLM 호출 없이 성공."""
    browser = MockBrowser()
    llm = MockLLM()
    evaluator = EvaluatorService(browser, llm)

    task = Task(
        description="테스트",
        success_criteria=SuccessCriteria(url_contains="example"),
    )
    page_state = PageState(url="https://example.com", title="Test", dom_text="")

    result = await evaluator.evaluate(task, page_state)

    assert result.success is True
    assert llm.evaluate_called is False  # description 없으므로 LLM 호출 안 함


@pytest.mark.asyncio
async def test_url_mismatch_with_description_falls_through_to_llm():
    """URL 불일치 + description 있으면 LLM 판정으로 넘어감."""
    browser = MockBrowser()
    llm = MockLLM(eval_result=EvalResult(success=True, reason="LLM: 올바른 페이지"))
    evaluator = EvaluatorService(browser, llm)

    task = Task(
        description="테스트",
        success_criteria=SuccessCriteria(
            url_contains="soongsil",
            description="숭실대학교 소프트웨어학부 공지사항 페이지가 로드되어야 함",
        ),
    )
    page_state = PageState(url="https://sw.ssu.ac.kr/bbs/board.php?bo_table=notice", title="학사 공지사항", dom_text="")

    result = await evaluator.evaluate(task, page_state)

    assert result.success is True
    assert llm.evaluate_called is True


@pytest.mark.asyncio
async def test_text_not_visible_with_description_falls_through_to_llm():
    """텍스트 불일치 + description 있으면 LLM 판정으로 넘어감."""
    browser = MockBrowser(text_visible=False)
    llm = MockLLM(eval_result=EvalResult(success=True, reason="LLM: OK"))
    evaluator = EvaluatorService(browser, llm)

    task = Task(
        description="테스트",
        success_criteria=SuccessCriteria(
            text_visible="검색 결과",
            description="검색 결과가 표시되어야 함",
        ),
    )
    page_state = PageState(url="https://example.com", title="Test", dom_text="")

    result = await evaluator.evaluate(task, page_state)

    assert result.success is True
    assert llm.evaluate_called is True
