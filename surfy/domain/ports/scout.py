from abc import ABC, abstractmethod

from surfy.domain.models.route import RouteMap


class ScoutPort(ABC):
    """정찰 탐색 포트. 브라우저 기반 탐색을 추상화한다."""

    @abstractmethod
    async def explore(self, task: str, max_steps: int = 20) -> RouteMap:
        """정찰 탐색을 수행하고 RouteMap을 반환한다."""
        ...
