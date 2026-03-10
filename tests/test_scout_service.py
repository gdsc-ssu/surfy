"""ScoutService 단위 테스트."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from surfy.adapters.browser.agent_adapter import BrowserUseAgentAdapter, history_to_route_map
from surfy.domain.models.research import ResearchResult
from surfy.domain.services import ScoutService


@pytest.fixture
def mock_agent_adapter():
    return MagicMock(spec=BrowserUseAgentAdapter)


@pytest.fixture
def scout_service(mock_agent_adapter):
    return ScoutService(agent_adapter=mock_agent_adapter)


@pytest.mark.asyncio
async def test_scout_completes_successfully(scout_service, mock_agent_adapter):
    """정찰이 성공적으로 완료되고 RouteMap을 반환하는지 확인."""
    # Mock AgentHistoryList
    mock_history = MagicMock()
    mock_history.urls.return_value = ["https://example.com/1", "https://example.com/2"]
    mock_history.action_names.return_value = ["go_to_url", "click_element"]
    mock_history.final_result.return_value = "Found target page"

    mock_agent_adapter.explore = AsyncMock(return_value=mock_history)

    route_map = await scout_service.scout("Find something", max_steps=10)

    assert len(route_map.steps) == 2
    assert route_map.steps[0].url == "https://example.com/1"
    assert route_map.steps[1].url == "https://example.com/2"
    assert route_map.final_url == "https://example.com/2"
    assert route_map.scout_summary == "Found target page"
    mock_agent_adapter.explore.assert_called_once_with(
        task="정찰: Find something", max_steps=10
    )


@pytest.mark.asyncio
async def test_scout_handles_exception(scout_service, mock_agent_adapter):
    """탐색 중 예외 발생 시 빈 RouteMap을 반환하는지 확인."""
    mock_agent_adapter.explore = AsyncMock(side_effect=Exception("Agent failed"))

    route_map = await scout_service.scout("Find something")

    assert len(route_map.steps) == 0
    assert route_map.final_url == ""
    assert "Scout failed: Agent failed" in route_map.scout_summary


@pytest.mark.asyncio
async def test_scout_with_research_result_includes_urls_in_task(scout_service, mock_agent_adapter):
    """리서치 결과가 있을 때 태스크 프롬프트에 URL이 포함되는지 확인."""
    mock_history = MagicMock()
    mock_history.urls.return_value = ["https://example.com/1"]
    mock_history.action_names.return_value = ["go_to_url"]
    mock_history.final_result.return_value = "Done"
    mock_agent_adapter.explore = AsyncMock(return_value=mock_history)

    research_result = ResearchResult(
        summary="Research summary",
        sources=["https://a.com", "https://b.com"],
        raw_results=[]
    )

    await scout_service.scout("Find something", research_result=research_result)

    # explore 호출 시 task 인자에 URL들이 포함되어 있는지 확인
    args, kwargs = mock_agent_adapter.explore.call_args
    task_prompt = kwargs.get("task", "")
    assert "https://a.com" in task_prompt
    assert "https://b.com" in task_prompt
    assert "참고 URL:" in task_prompt


def test_history_to_route_map_conversion():
    """AgentHistoryList가 RouteMap으로 올바르게 변환되는지 확인."""
    mock_history = MagicMock()
    mock_history.urls.return_value = ["https://example.com/1"]
    mock_history.action_names.return_value = ["click"]
    mock_history.final_result.return_value = "Done"

    route_map = history_to_route_map(mock_history)

    assert len(route_map.steps) == 1
    assert route_map.steps[0].url == "https://example.com/1"
    assert route_map.steps[0].action_taken == "click"
    assert route_map.final_url == "https://example.com/1"
    assert route_map.scout_summary == "Done"
