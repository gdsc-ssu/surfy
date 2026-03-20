"""ScoutService 단위 테스트."""

import pytest

from surfy.domain.models.research import ResearchResult
from surfy.domain.models.route import RouteMap, RouteStep
from surfy.domain.ports.scout import ScoutPort
from surfy.domain.services import ScoutService


class MockScout(ScoutPort):
    def __init__(self, route_map: RouteMap | None = None, error: Exception | None = None):
        self._route_map = route_map
        self._error = error
        self.last_task: str | None = None
        self.last_max_steps: int | None = None

    async def explore(self, task: str, max_steps: int = 20) -> RouteMap:
        self.last_task = task
        self.last_max_steps = max_steps
        if self._error:
            raise self._error
        assert self._route_map is not None
        return self._route_map


@pytest.fixture
def sample_route_map():
    return RouteMap(
        steps=[
            RouteStep(url="https://example.com/1", title="", action_taken="go_to_url", observed_elements=[], notes=""),
            RouteStep(
                url="https://example.com/2", title="", action_taken="click_element", observed_elements=[], notes=""
            ),
        ],
        final_url="https://example.com/2",
        scout_summary="Found target page",
    )


@pytest.fixture
def mock_scout(sample_route_map):
    return MockScout(route_map=sample_route_map)


@pytest.fixture
def scout_service(mock_scout):
    return ScoutService(scout=mock_scout)


@pytest.mark.asyncio
async def test_scout_completes_successfully(scout_service, mock_scout):
    route_map = await scout_service.scout("Find something", max_steps=10)

    assert len(route_map.steps) == 2
    assert route_map.steps[0].url == "https://example.com/1"
    assert route_map.steps[1].url == "https://example.com/2"
    assert route_map.final_url == "https://example.com/2"
    assert route_map.scout_summary == "Found target page"
    assert mock_scout.last_task == "정찰: Find something"
    assert mock_scout.last_max_steps == 10


@pytest.mark.asyncio
async def test_scout_handles_exception():
    failing_scout = MockScout(error=Exception("Agent failed"))
    service = ScoutService(scout=failing_scout)

    route_map = await service.scout("Find something")

    assert len(route_map.steps) == 0
    assert route_map.final_url == ""
    assert "Scout failed: Agent failed" in route_map.scout_summary


@pytest.mark.asyncio
async def test_scout_with_research_result_includes_urls_in_task(mock_scout):
    service = ScoutService(scout=mock_scout)

    research_result = ResearchResult(
        summary="Research summary",
        sources=["https://a.com", "https://b.com"],
        raw_results=[],
    )

    await service.scout("Find something", research_result=research_result)

    assert mock_scout.last_task is not None
    assert "https://a.com" in mock_scout.last_task
    assert "https://b.com" in mock_scout.last_task
    assert "출처 URL" in mock_scout.last_task
    assert "사전 조사 요약" in mock_scout.last_task
    assert "Research summary" in mock_scout.last_task
