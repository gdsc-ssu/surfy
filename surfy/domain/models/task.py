from pydantic import BaseModel, Field

from surfy.domain.models.criteria import SuccessCriteria


class Task(BaseModel):
    """Actor가 실행할 단일 태스크.

    Planner가 생성하고, Actor가 실행하고, Evaluator가 검증한다.
    """

    description: str
    """태스크 설명 — Actor가 이 설명을 보고 행동을 결정."""

    success_criteria: SuccessCriteria = Field(default_factory=SuccessCriteria)
    """완료 조건 — Evaluator가 이 기준으로 성공 여부 판정."""

    target_url: str | None = None
    """Scout이 발견한 목표 URL — Actor가 GO_TO_URL로 직접 이동할 수 있다."""
