import asyncio
import logging

from ddgs import DDGS

from surfy.domain.models.research import ResearchResult, SearchResult
from surfy.domain.ports.research import ResearchPort

logger = logging.getLogger(__name__)


class DdgsSearchAdapter(ResearchPort):
    """DuckDuckGo Search (ddgs) 패키지를 사용하여 리서치를 수행하는 어댑터."""

    def __init__(self):
        """DdgsSearchAdapter 초기화. 별도의 인자가 필요하지 않음."""
        pass

    async def research(self, query: str) -> ResearchResult:
        """DuckDuckGo에서 검색하여 결과를 수집한다.

        Args:
            query: 검색할 쿼리 문자열.

        Returns:
            ResearchResult: 검색 결과 요약, 출처 URL 목록, 상세 검색 결과 목록.
        """
        try:
            # ddgs.text()는 동기 함수이므로 asyncio.to_thread를 사용하여 비동기로 실행
            # region="kr-kr"로 한국 지역 검색 결과 우선, max_results=5로 제한
            results = await asyncio.to_thread(
                DDGS().text,
                query,
                region="kr-kr",
                max_results=5,
            )

            raw_results = []
            sources = []
            snippets = []

            for r in results:
                title = r.get("title", "")
                url = r.get("href", "")
                body = r.get("body", "")

                search_result = SearchResult(
                    title=title,
                    url=url,
                    snippet=body,
                )
                raw_results.append(search_result)
                sources.append(url)
                snippets.append(f"[{title}]({url}): {body}")

            # 요약 생성: snippets를 합쳐서 최대 500자까지
            combined_snippets = "\n".join(snippets)
            summary = combined_snippets[:500] if combined_snippets else f"'{query}'에 대한 검색 결과가 없습니다."

            return ResearchResult(
                summary=summary,
                sources=sources,
                raw_results=raw_results,
            )

        except Exception as e:
            logger.warning("DDGS Research failed: %s", e)
            return ResearchResult(
                summary=f"리서치 실패: {e}",
                sources=[],
                raw_results=[],
            )
