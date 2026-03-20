"""Gemini Grounding API를 사용한 리서치 어댑터."""

import logging

from google import genai
from google.genai import types

from surfy.domain.models.research import ResearchResult, SearchResult
from surfy.domain.ports.research import ResearchPort

logger = logging.getLogger(__name__)


class GeminiGroundingAdapter(ResearchPort):
    """Gemini API의 Google Search Grounding을 사용하여 리서치를 수행한다."""

    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash") -> None:
        """GeminiGroundingAdapter 초기화.

        Args:
            api_key: Google AI API 키.
            model_name: 사용할 모델 이름. 기본값은 gemini-2.0-flash.
        """
        self._client = genai.Client(api_key=api_key)
        self._model_name = model_name

    async def research(self, query: str) -> ResearchResult:
        """Gemini Grounding으로 검색 + 합성 + 출처 URL을 반환한다.

        Args:
            query: 검색 및 리서치할 쿼리 문자열.

        Returns:
            ResearchResult: 요약, 출처, 원본 검색 결과를 포함한 객체.
        """
        logger.info("Gemini Grounding 시작: %s", query[:50])
        try:
            response = await self._client.aio.models.generate_content(
                model=self._model_name,
                contents=query,
                config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())]),
            )
            summary = response.text or ""
            candidates = response.candidates or []
            grounding_metadata = candidates[0].grounding_metadata if candidates else None
            chunks = []
            if grounding_metadata and grounding_metadata.grounding_chunks:
                chunks = grounding_metadata.grounding_chunks

            sources: list[str] = [chunk.web.uri for chunk in chunks if chunk.web and chunk.web.uri]
            raw_results = [
                SearchResult(title=chunk.web.title or "", url=chunk.web.uri, snippet="")
                for chunk in chunks
                if chunk.web and chunk.web.uri
            ]
            logger.info("Gemini Grounding 완료: sources=%d", len(sources))
            return ResearchResult(summary=summary, sources=sources, raw_results=raw_results)
        except Exception as e:
            logger.warning("Gemini Grounding 실패: %s", e)
            return ResearchResult(summary=f"리서치 실패: {e}", sources=[], raw_results=[])
