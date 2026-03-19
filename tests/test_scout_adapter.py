"""Scout adapter의 history 변환 로직 단위 테스트."""

import pytest

from surfy.adapters.browser import agent_adapter
from surfy.adapters.browser.agent_adapter import BrowserUseAgentAdapter, _history_to_route_map, _is_login_wall


class MockAgentHistoryList:
    def __init__(
        self,
        urls: list[str | None],
        action_names: list[str],
        final_result: str | None,
        is_successful: bool | None,
    ) -> None:
        self._urls = urls
        self._action_names = action_names
        self._final_result = final_result
        self._is_successful = is_successful

    def urls(self) -> list[str | None]:
        return self._urls

    def action_names(self) -> list[str]:
        return self._action_names

    def final_result(self) -> str | None:
        return self._final_result

    def is_successful(self) -> bool | None:
        return self._is_successful


def test_history_to_route_map_sets_scout_completed_true_on_success() -> None:
    history = MockAgentHistoryList(
        urls=["https://example.com", "https://example.com/done"],
        action_names=["go_to_url", "click_element"],
        final_result="탐색 성공",
        is_successful=True,
    )

    route_map = _history_to_route_map(history)  # type: ignore[arg-type]

    assert route_map.scout_completed is True


def test_history_to_route_map_sets_scout_completed_false_when_not_done() -> None:
    history = MockAgentHistoryList(
        urls=["https://example.com"],
        action_names=["go_to_url"],
        final_result=None,
        is_successful=None,
    )

    route_map = _history_to_route_map(history)  # type: ignore[arg-type]

    assert route_map.scout_completed is False


def test_history_to_route_map_sets_scout_completed_true_when_final_result_exists() -> None:
    history = MockAgentHistoryList(
        urls=["https://example.com", "https://example.com/fail"],
        action_names=["go_to_url", "click_element"],
        final_result="실패",
        is_successful=False,
    )

    route_map = _history_to_route_map(history)  # type: ignore[arg-type]

    assert route_map.scout_completed is True


def test_login_wall_detected_on_login_url() -> None:
    assert _is_login_wall([None, "https://maru.org/login?redirect=/eventhall/reserve"]) is True
    assert _is_login_wall(["https://example.com/signin"]) is True
    assert _is_login_wall(["https://example.com/auth/callback"]) is True
    assert _is_login_wall(["https://example.com/sign-in"]) is True
    assert _is_login_wall(["https://example.com/sso/login"]) is True


def test_login_wall_not_detected_on_normal_url() -> None:
    assert _is_login_wall(["https://example.com/dashboard"]) is False
    assert _is_login_wall(["https://example.com/eventhall/calendar"]) is False
    assert _is_login_wall([]) is False
    assert _is_login_wall([None]) is False


def test_history_to_route_map_overrides_scout_completed_on_login_wall() -> None:
    history = MockAgentHistoryList(
        urls=["https://example.com", "https://example.com/login?redirect=/reserve"],
        action_names=["go_to_url", "click_element"],
        final_result="로그인 페이지 도달",
        is_successful=True,
    )

    route_map = _history_to_route_map(history)  # type: ignore[arg-type]

    assert route_map.scout_completed is False
    assert "로그인 필요" in route_map.scout_summary


def test_history_to_route_map_non_login_success_is_true() -> None:
    history = MockAgentHistoryList(
        urls=["https://example.com", "https://example.com/dashboard"],
        action_names=["go_to_url", "click_element"],
        final_result="탐색 완료",
        is_successful=True,
    )

    route_map = _history_to_route_map(history)  # type: ignore[arg-type]

    assert route_map.scout_completed is True


@pytest.mark.asyncio
async def test_explore_passes_scout_prompt_via_extend_system_message(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeAgent:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

        async def run(self, max_steps: int):
            captured["max_steps"] = max_steps
            return MockAgentHistoryList(
                urls=["https://example.com"],
                action_names=["go_to_url"],
                final_result="탐색 완료",
                is_successful=True,
            )

    monkeypatch.setattr(agent_adapter, "Agent", FakeAgent)

    adapter = BrowserUseAgentAdapter(session=object(), llm=object())  # type: ignore[arg-type]

    route_map = await adapter.explore("정찰: 테스트", max_steps=3)

    assert captured["task"] == "정찰: 테스트"
    assert captured["browser_session"] is adapter._session
    assert captured["llm"] is adapter._llm
    assert captured["extend_system_message"] == adapter._scout_prompt
    assert "정찰은 경로 수집이다" in str(captured["extend_system_message"])
    assert captured["max_steps"] == 3
    assert route_map.scout_completed is True
