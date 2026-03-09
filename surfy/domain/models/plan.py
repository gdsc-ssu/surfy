from pydantic import BaseModel

from surfy.domain.models.task import Task


class Plan(BaseModel):
    """Plan Anchor 패턴 — 불변 최종 목표(anchor)를 중심으로 rolling wave 계획.

    WebAnchor 논문의 핵심 발견: 첫 번째 계획 스텝이 틀리면 전체 성공률이 23~31% 하락.
    anchor는 절대 변경되지 않으며, 실패 시 해당 구간만 재계획한다.
    """

    anchor: str
    """불변 최종 목표. 어떤 상황에서도 변경되지 않는다."""

    tasks: list[Task]
    """현재 수립된 태스크들. rolling wave 방식으로 1~2개씩 생성."""

    anchor_rationale: str
    """왜 이 분해가 anchor 달성에 최적인지 설명."""
