from abc import ABC, abstractmethod


class HumanPort(ABC):
    """에이전트가 사용자에게 개입을 요청하거나 상태를 알릴 때 사용하는 인터페이스."""

    @abstractmethod
    async def ask(self, question: str) -> str:
        """사용자에게 질문하고 응답을 받음."""
        ...

    @abstractmethod
    async def notify(self, message: str) -> None:
        """사용자에게 상태 알림 (응답 불필요)."""
        ...
