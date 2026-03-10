from abc import ABC, abstractmethod

from surfy.domain.models.research import ResearchResult


class ResearchPort(ABC):
    """리서치 서비스 포트.

    Tavily, Exa 등 외부 검색 API나 브라우저 검색 어댑터의 인터페이스를 정의한다.
    """

    @abstractmethod
    async def research(self, query: str) -> ResearchResult:
        """주어진 쿼리에 대해 리서치를 수행하고 결과를 반환한다.

        Args:
            query: 검색 및 리서치할 쿼리 문자열.

        Returns:
            ResearchResult: 요약, 출처, 원본 검색 결과를 포함한 객체.
        """
        ...
