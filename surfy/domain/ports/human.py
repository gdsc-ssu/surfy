from abc import ABC, abstractmethod


class HumanPort(ABC):
    """에이전트가 사용자에게 개입을 요청하거나 상태를 알릴 때 사용하는 인터페이스."""

    @abstractmethod # 이 메서드는 자식 클래스가 구현해야함
    async def ask(self, question: str) -> str:  # async def는 비동기 함수로 사용자 입력 기다리는 동안 다른 작업 가능
        """사용자에게 질문하고 응답을 받음."""    # question: str 은 타입힌트. 파라미터는 문자열
        ...

    @abstractmethod
    async def notify(self, message: str) -> None:
        """사용자에게 상태 알림 (응답 불필요)."""
        ...

# -> str는 문자열 반환, None은 반환값 없음.