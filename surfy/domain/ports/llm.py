from abc import ABC, abstractmethod
from typing import Any

from surfy.domain.models import PageState


class LLMPort(ABC):
    """LLM 서비스와 통신하기 위한 추상 인터페이스입니다."""

    @abstractmethod
    async def plan(self, command: str, progress: str) -> "Plan":
        """
        사용자 명령과 현재까지의 진행 상황을 바탕으로 전체 계획(Plan)을 수립하거나 갱신합니다.
        """
        ...

    @abstractmethod
    async def decide_action(
        self, task: "Task", page_state: PageState, history: list[Any]
    ) -> "ActorOutput":
        """
        현재 수행 중인 태스크와 페이지 상태, 그리고 이전 액션 이력을 바탕으로
        다음에 수행할 브라우저 액션을 결정합니다.
        """
        ...

    @abstractmethod
    async def evaluate(
        self, criteria: "SuccessCriteria", page_state: PageState
    ) -> "EvalResult":
        """
        주어진 성공 조건(SuccessCriteria)이 현재 페이지 상태에서 충족되었는지 평가합니다.
        구조적 체크로 판단이 모호한 경우 LLM을 통해 최종 판단을 내립니다.
        """
        ...