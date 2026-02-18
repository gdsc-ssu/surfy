import pytest

from surfy.domain.models import ActionType, BrowserAction, PageState, StepResult


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
    assert result.page_state.url == "https://example.com"


def test_invalid_action_type():
    with pytest.raises(ValueError):
        BrowserAction(action_type="INVALID")