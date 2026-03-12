from pydantic import BaseModel


class RouteStep(BaseModel):
    """Scout Phase에서 기록되는 개별 브라우징 단계."""

    url: str
    """방문한 URL."""

    title: str
    """페이지 제목."""

    action_taken: str
    """해당 페이지에서 수행한 작업 (예: '검색어 입력', '링크 클릭')."""

    observed_elements: list[str]
    """페이지에서 발견한 주요 요소들의 설명."""

    notes: str
    """해당 단계에서의 특이사항이나 관찰 결과."""


class RouteMap(BaseModel):
    """Scout Phase의 결과물로, 목표 달성을 위한 최적의 경로 정보."""

    steps: list[RouteStep]
    """목표 페이지에 도달하기까지 거친 단계들."""

    final_url: str
    """최종적으로 도달한 목표 페이지의 URL."""

    scout_summary: str
    """전체 탐색 과정에 대한 요약 및 전략적 판단."""

    scout_completed: bool = False
    """Scout Phase가 성공적으로 완료되었는지 여부."""
