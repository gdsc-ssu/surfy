from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from surfy.adapters.research.ddgs_search import DdgsSearchAdapter
from surfy.domain.models.research import ResearchResult
from surfy.domain.ports.research import ResearchPort
from surfy.domain.services.researcher import ResearcherService


def test_research_port_is_abstract():
    with pytest.raises(TypeError):
        ResearchPort()  # pyright: ignore[reportAbstractUsage]


@pytest.mark.asyncio
async def test_researcher_service_delegates_to_port():
    mock_port = MagicMock(spec=ResearchPort)
    expected = ResearchResult(summary="done", sources=["https://a.com"], raw_results=[])
    mock_port.research = AsyncMock(return_value=expected)

    service = ResearcherService(research_port=mock_port)
    result = await service.research("python asyncio")

    assert result == expected
    mock_port.research.assert_awaited_once_with("python asyncio")


def test_ddgs_search_adapter_implements_research_port():
    adapter = DdgsSearchAdapter()
    assert isinstance(adapter, ResearchPort)


@pytest.mark.asyncio
async def test_ddgs_search_adapter_returns_structured_results():
    # Mock asyncio.to_thread to return fake ddgs results
    fake_results = [
        {"title": "Result 1", "href": "https://a.com", "body": "Body 1"},
        {"title": "Result 2", "href": "https://b.com", "body": "Body 2"},
    ]
    with patch(
        "surfy.adapters.research.ddgs_search.asyncio.to_thread", new_callable=AsyncMock, return_value=fake_results
    ):
        adapter = DdgsSearchAdapter()
        result = await adapter.research("test query")

    assert len(result.raw_results) == 2
    assert result.raw_results[0].title == "Result 1"
    assert result.raw_results[0].url == "https://a.com"
    assert result.raw_results[0].snippet == "Body 1"
    assert result.sources == ["https://a.com", "https://b.com"]
    assert len(result.summary) > 0


@pytest.mark.asyncio
async def test_ddgs_search_adapter_handles_failure_gracefully():
    with patch(
        "surfy.adapters.research.ddgs_search.asyncio.to_thread",
        new_callable=AsyncMock,
        side_effect=RuntimeError("network error"),
    ):
        adapter = DdgsSearchAdapter()
        result = await adapter.research("failing query")

    assert result.sources == []
    assert result.raw_results == []
    assert "리서치 실패" in result.summary
