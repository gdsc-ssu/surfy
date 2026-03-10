from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """개별 검색 결과 모델."""

    title: str
    """검색 결과 제목."""

    url: str
    """검색 결과 URL."""

    snippet: str = ""
    """검색 결과 요약 문구."""


class ResearchResult(BaseModel):
    """리서치 수행 결과 모델."""

    summary: str
    """리서치 내용 요약."""

    sources: list[str] = Field(default_factory=list)
    """참고한 출처 URL 목록."""

    raw_results: list[SearchResult] = Field(default_factory=list)
    """수집된 원본 검색 결과 목록."""
