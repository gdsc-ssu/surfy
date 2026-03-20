from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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


def test_gemini_grounding_adapter_implements_research_port():
    from surfy.adapters.research.gemini_grounding import GeminiGroundingAdapter

    adapter = GeminiGroundingAdapter(api_key="test-key")
    assert isinstance(adapter, ResearchPort)


@pytest.mark.asyncio
async def test_gemini_grounding_adapter_returns_structured_results():
    from surfy.adapters.research.gemini_grounding import GeminiGroundingAdapter

    # Mock response structure
    mock_chunk1 = MagicMock()
    mock_chunk1.web.uri = "https://example.com/1"
    mock_chunk1.web.title = "Example 1"

    mock_chunk2 = MagicMock()
    mock_chunk2.web.uri = "https://example.com/2"
    mock_chunk2.web.title = "Example 2"

    mock_response = MagicMock()
    mock_response.text = "테스트 요약 텍스트"
    mock_response.candidates = [MagicMock()]
    mock_response.candidates[0].grounding_metadata.grounding_chunks = [mock_chunk1, mock_chunk2]

    with patch("google.genai.Client") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        adapter = GeminiGroundingAdapter(api_key="test-key")
        result = await adapter.research("test query")

    assert result.summary == "테스트 요약 텍스트"
    assert result.sources == ["https://example.com/1", "https://example.com/2"]
    assert len(result.raw_results) == 2
    assert result.raw_results[0].title == "Example 1"
    assert result.raw_results[0].url == "https://example.com/1"


@pytest.mark.asyncio
async def test_gemini_grounding_adapter_handles_failure_gracefully():
    from surfy.adapters.research.gemini_grounding import GeminiGroundingAdapter

    with patch("google.genai.Client") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.aio.models.generate_content = AsyncMock(side_effect=Exception("API Error"))

        adapter = GeminiGroundingAdapter(api_key="test-key")
        result = await adapter.research("failing query")

    assert "리서치 실패" in result.summary
    assert result.sources == []
    assert result.raw_results == []


@pytest.mark.asyncio
async def test_gemini_grounding_adapter_handles_empty_grounding_chunks():
    from surfy.adapters.research.gemini_grounding import GeminiGroundingAdapter

    mock_response = MagicMock()
    mock_response.text = "요약은 있지만 출처는 없음"
    mock_response.candidates = [MagicMock()]
    mock_response.candidates[0].grounding_metadata.grounding_chunks = []

    with patch("google.genai.Client") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        adapter = GeminiGroundingAdapter(api_key="test-key")
        result = await adapter.research("empty query")

    assert result.summary == "요약은 있지만 출처는 없음"
    assert result.sources == []
    assert result.raw_results == []
