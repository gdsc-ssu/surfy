"""Scout adapter의 history 변환 로직 단위 테스트."""

from surfy.adapters.browser.agent_adapter import _history_to_route_map


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


def test_history_to_route_map_sets_scout_completed_true_when_successful() -> None:
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


def test_history_to_route_map_sets_scout_completed_false_when_failed() -> None:
    history = MockAgentHistoryList(
        urls=["https://example.com", "https://example.com/fail"],
        action_names=["go_to_url", "click_element"],
        final_result="실패",
        is_successful=False,
    )

    route_map = _history_to_route_map(history)  # type: ignore[arg-type]

    assert route_map.scout_completed is False
