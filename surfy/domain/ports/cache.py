from abc import ABC, abstractmethod

from surfy.domain.models.cache import CachedScenario


class CachePort(ABC):
    """시나리오 캐시 포트."""

    @abstractmethod
    def get(self, cache_key: str) -> CachedScenario | None:
        """캐시 키로 CachedScenario 조회. 없으면 None 반환."""
        ...

    @abstractmethod
    def set(self, scenario: CachedScenario) -> None:
        """CachedScenario를 캐시에 저장 (덮어쓰기)."""
        ...
