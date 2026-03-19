from pydantic import BaseModel

from surfy.domain.models.plan import Plan
from surfy.domain.models.route import RouteMap


class CommandIntent(BaseModel):
    """LLM이 명령어에서 추출한 구조화된 의도."""

    service: str
    """사용할 웹 서비스 (예: srt, ktx, 정부24, 인터파크). 알 수 없으면 'unknown'."""

    from_location: str | None = None
    """출발지. 해당 없으면 None."""

    to_location: str | None = None
    """도착지. 해당 없으면 None."""

    action: str = "navigate"
    """수행할 작업 (예: 예매, 조회, 신청, navigate)."""


class CachedScenario(BaseModel):
    """Scout + Planner 결과의 영속 캐시 단위."""

    cache_key: str
    """SHA-256 기반 16자 헥스 키."""

    command_normalized: str
    """캐시 키 생성에 사용된 정규화된 명령어 (디버그용)."""

    route_map: RouteMap
    plan: Plan
