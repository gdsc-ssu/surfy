from __future__ import annotations

from pydantic import BaseModel

from surfy.domain.models.actor import ActorOutput
from surfy.domain.models.result import StepResult


class HistoryEntry(BaseModel):
    """Actor 실행 히스토리의 단일 항목.

    Attributes:
        action: LLM이 결정한 액션 출력
        result: 액션 실행 결과
        step: 스텝 번호 (1-indexed, 확장용)
    """

    action: ActorOutput
    result: StepResult
    step: int | None = None  # 확장용: 스텝 번호
    # 향후 추가 가능: timestamp: datetime | None = None
