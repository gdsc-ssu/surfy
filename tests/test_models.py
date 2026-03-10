import pytest

from surfy.domain.models import (
    ActionType,
    BrowserAction,
    EvalResult,
    PageState,
    Plan,
    StepResult,
    SuccessCriteria,
    Task,
)


def test_browser_action_defaults():
    action = BrowserAction(action_type=ActionType.SCROLL_DOWN)
    assert action.target_id is None
    assert action.value is None


def test_browser_action_click():
    action = BrowserAction(action_type=ActionType.CLICK, target_id=5)
    assert action.target_id == 5


def test_page_state_required_fields():
    state = PageState(url="https://example.com", title="Example", dom_text="<body>hi</body>")
    assert state.screenshot is None


def test_step_result_success():
    result = StepResult(success=True, message="OK")
    assert result.page_state is None


def test_step_result_with_page_state():
    state = PageState(url="https://example.com", title="Example", dom_text="dom")
    result = StepResult(success=True, message="OK", page_state=state)
    assert result.page_state is not None
    assert result.page_state.url == "https://example.com"


def test_invalid_action_type():
    with pytest.raises(ValueError):
        BrowserAction(action_type="INVALID")  # type: ignore[arg-type]


# ============================================================
# Phase 3 모델 테스트 — SuccessCriteria, Task, Plan, EvalResult
# ============================================================


def test_success_criteria_defaults():
    """SuccessCriteria 기본값 테스트."""
    criteria = SuccessCriteria()
    assert criteria.url_contains is None
    assert criteria.text_visible is None
    assert criteria.description == ""


def test_success_criteria_with_values():
    """SuccessCriteria 값 설정 테스트."""
    criteria = SuccessCriteria(
        url_contains="search",
        text_visible="결과",
        description="검색 결과가 표시되어야 함",
    )
    assert criteria.url_contains == "search"
    assert criteria.text_visible == "결과"
    assert criteria.description == "검색 결과가 표시되어야 함"


def test_task_with_default_criteria():
    """Task가 기본 success_criteria를 가지는지 테스트 (Phase 2 호환성)."""
    task = Task(description="테스트 태스크")
    assert task.description == "테스트 태스크"
    assert task.success_criteria.url_contains is None
    assert task.success_criteria.description == ""


def test_task_with_custom_criteria():
    """Task에 커스텀 success_criteria 설정 테스트."""
    criteria = SuccessCriteria(url_contains="naver.com", description="네이버 접속 확인")
    task = Task(description="네이버 접속", success_criteria=criteria)
    assert task.success_criteria.url_contains == "naver.com"


def test_task_with_target_url():
    task_default = Task(description="test")
    assert task_default.target_url is None

    task_with_url = Task(description="test", target_url="https://naver.com")
    assert task_with_url.target_url == "https://naver.com"


def test_plan_creation():
    """Plan 생성 테스트."""
    task1 = Task(description="태스크 1")
    task2 = Task(description="태스크 2")
    plan = Plan(
        anchor="최종 목표",
        tasks=[task1, task2],
        anchor_rationale="이렇게 분해하면 효율적",
    )
    assert plan.anchor == "최종 목표"
    assert len(plan.tasks) == 2
    assert plan.tasks[0].description == "태스크 1"
    assert plan.anchor_rationale == "이렇게 분해하면 효율적"


def test_plan_anchor_immutability_pattern():
    """Plan의 anchor는 재할당으로만 변경 가능 (Pydantic frozen 아님)."""
    plan = Plan(anchor="원래 목표", tasks=[], anchor_rationale="이유")
    # anchor 변경 테스트 (PlannerService.next_tasks에서 사용하는 패턴)
    plan.anchor = "새 목표"
    assert plan.anchor == "새 목표"


def test_eval_result_success():
    """EvalResult 성공 케이스 테스트."""
    result = EvalResult(success=True, reason="구조 체크 통과")
    assert result.success is True
    assert result.reason == "구조 체크 통과"


def test_eval_result_failure():
    """EvalResult 실패 케이스 테스트."""
    result = EvalResult(success=False, reason="URL에 'search' 없음")
    assert result.success is False
    assert "search" in result.reason


def test_search_result_creation():
    from surfy.domain.models.research import SearchResult

    sr = SearchResult(title="Test", url="https://example.com", snippet="A snippet")
    assert sr.title == "Test"
    assert sr.url == "https://example.com"
    assert sr.snippet == "A snippet"


def test_research_result_creation():
    from surfy.domain.models.research import ResearchResult

    rr = ResearchResult(summary="Test summary", sources=["https://a.com"], raw_results=[])
    assert rr.summary == "Test summary"
    assert len(rr.sources) == 1


def test_research_result_defaults():
    from surfy.domain.models.research import ResearchResult

    rr = ResearchResult(summary="Test")
    assert rr.sources == []
    assert rr.raw_results == []
