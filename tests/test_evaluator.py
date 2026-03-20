"""EvaluatorService 단위 테스트.

mock BrowserPort로 3가지 평가 경로 테스트:
1. URL 불일치 → 즉시 실패
2. 텍스트 불일치 → 즉시 실패
3. 구조 체크 통과 (또는 기준 없음) → 성공
"""

import pytest

from surfy.domain.models import (
    BrowserAction,
    PageState,
    StepResult,
    SuccessCriteria,
    Task,
)
from surfy.domain.ports import BrowserPort
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


@pytest.mark.asyncio
async def test_url_mismatch_fails_immediately():
    """URL 불일치 시 즉시 실패."""
    evaluator = EvaluatorService(MockBrowser())

    task = Task(
        description="테스트",
        success_criteria=SuccessCriteria(url_contains="naver.com"),
    )
    page_state = PageState(url="https://google.com", title="Google", dom_text="")

    result = await evaluator.evaluate(task, page_state)

    assert result.success is False
    assert "naver.com" in result.reason


@pytest.mark.asyncio
async def test_text_not_visible_fails_immediately():
    """텍스트 불일치 시 즉시 실패."""
    evaluator = EvaluatorService(MockBrowser(text_visible=False))

    task = Task(
        description="테스트",
        success_criteria=SuccessCriteria(text_visible="검색 결과"),
    )
    page_state = PageState(url="https://example.com", title="Test", dom_text="")

    result = await evaluator.evaluate(task, page_state)

    assert result.success is False
    assert "검색 결과" in result.reason


@pytest.mark.asyncio
async def test_structure_check_passes():
    """구조 체크 통과 → 성공 (description은 평가에 사용하지 않음)."""
    evaluator = EvaluatorService(MockBrowser(text_visible=True))

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


@pytest.mark.asyncio
async def test_no_criteria_passes_immediately():
    """아무 기준도 없으면 즉시 성공."""
    evaluator = EvaluatorService(MockBrowser())

    task = Task(description="테스트", success_criteria=SuccessCriteria())
    page_state = PageState(url="https://example.com", title="Test", dom_text="")

    result = await evaluator.evaluate(task, page_state)

    assert result.success is True
    assert "구조 체크 통과" in result.reason


@pytest.mark.asyncio
async def test_url_matches_passes():
    """URL 매칭 → 성공."""
    evaluator = EvaluatorService(MockBrowser())

    task = Task(
        description="테스트",
        success_criteria=SuccessCriteria(url_contains="example"),
    )
    page_state = PageState(url="https://example.com", title="Test", dom_text="")

    result = await evaluator.evaluate(task, page_state)

    assert result.success is True


@pytest.mark.asyncio
async def test_url_mismatch_with_description_fails():
    """URL 불일치 + description 있어도 실패 (description은 평가에 사용 안 함)."""
    evaluator = EvaluatorService(MockBrowser())

    task = Task(
        description="테스트",
        success_criteria=SuccessCriteria(
            url_contains="soongsil",
            description="숭실대학교 소프트웨어학부 공지사항 페이지가 로드되어야 함",
        ),
    )
    page_state = PageState(url="https://sw.ssu.ac.kr/bbs/board.php?bo_table=notice", title="학사 공지사항", dom_text="")

    result = await evaluator.evaluate(task, page_state)

    assert result.success is False
    assert "soongsil" in result.reason


@pytest.mark.asyncio
async def test_text_not_visible_with_description_fails():
    """텍스트 불일치 + description 있어도 실패 (description은 평가에 사용 안 함)."""
    evaluator = EvaluatorService(MockBrowser(text_visible=False))

    task = Task(
        description="테스트",
        success_criteria=SuccessCriteria(
            text_visible="검색 결과",
            description="검색 결과가 표시되어야 함",
        ),
    )
    page_state = PageState(url="https://example.com", title="Test", dom_text="")

    result = await evaluator.evaluate(task, page_state)

    assert result.success is False
    assert "검색 결과" in result.reason
