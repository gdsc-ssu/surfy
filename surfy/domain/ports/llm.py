from abc import ABC, abstractmethod

from surfy.domain.models import ActorOutput, HistoryEntry, PageState, Task


class LLMPort(ABC):
    @abstractmethod
    async def decide_action(
        self,
        task: Task,
        page_state: PageState,
        history: list[HistoryEntry],
    ) -> ActorOutput:
        """현재 페이지 상태와 히스토리를 기반으로 다음 액션 결정."""
        ...

    # plan(), evaluate()는 Phase 3에서 추가
