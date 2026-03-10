from abc import ABC, abstractmethod

from surfy.domain.models import ActorOutput, EvalResult, HistoryEntry, PageState, Task
from surfy.domain.models.criteria import SuccessCriteria
from surfy.domain.models.plan import Plan


class LLMPort(ABC):
    """LLM 서비스 포트.

    Planner, Actor, Evaluator가 각각 다른 메서드를 사용한다.
    """

    @abstractmethod
    async def decide_action(
        self,
        task: Task,
        page_state: PageState,
        history: list[HistoryEntry],
    ) -> ActorOutput:
        """Actor용: 현재 페이지 상태와 히스토리를 기반으로 다음 액션 결정."""
        ...

    @abstractmethod
    async def scout(
        self,
        task: Task,
        page_state: PageState,
        history: list[HistoryEntry],
    ) -> ActorOutput:
        """Scout용: 정찰 모드에서 다음 액션 결정.

        .. deprecated:: 0.1.0
            ScoutService가 BrowserUseAgentAdapter를 직접 사용하도록 변경됨에 따라 더 이상 사용되지 않음.
        """
        ...

    @abstractmethod
    async def plan(self, command: str, progress: str, route_observations: str = "", research_result: str = "") -> Plan:
        """Planner용: 사용자 명령과 진행 상황을 기반으로 Plan 생성.

        Args:
            command: 사용자 명령 또는 anchor (최종 목표)
            progress: 지금까지의 진행 요약 (빈 문자열이면 첫 호출)
            route_observations: Scout 단계에서 수집된 관찰 내용 (선택 사항)
            research_result: Research 단계에서 수집된 리서치 결과 (선택 사항)

        Returns:
            Plan: anchor, tasks, anchor_rationale을 포함한 계획
        """
        ...

    @abstractmethod
    async def evaluate(self, criteria: SuccessCriteria, page_state: PageState) -> EvalResult:
        """Evaluator용: 태스크 성공 여부 판정.

        구조 체크(URL, 텍스트)로 판단 불가한 경우에만 호출된다.

        Args:
            criteria: 태스크의 성공 기준 (description 필드 사용)
            page_state: 현재 페이지 상태 (DOM text + screenshot)

        Returns:
            EvalResult: success 여부와 판정 이유
        """
        ...
