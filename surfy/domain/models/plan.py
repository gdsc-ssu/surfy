from pydantic import BaseModel, Field


class SuccessCriteria(BaseModel):
    """태스크 완료를 판단하기 위한 기준입니다."""

    url_contains: str | None = Field(default=None, description="URL 패턴 (Planner가 예측 가능)")
    text_visible: str | None = Field(default=None, description="화면에 보여야 할 텍스트")
    description: str = Field(..., description="자연어 설명 (항상 채움)")


class Task(BaseModel):
    """계획의 구성 요소인 개별 태스크입니다."""

    description: str = Field(..., description="태스크에 대한 설명")
    success_criteria: SuccessCriteria = Field(..., description="태스크 완료 조건")


class Plan(BaseModel):
    """Plan Anchor 패턴을 따르는 전체 계획 모델입니다."""

    anchor: str = Field(..., description="불변 최종 목표 (절대 변경 안 됨)")
    tasks: list[Task] = Field(default_factory=list, description="현재 수립된 태스크들")
    anchor_rationale: str = Field(..., description="왜 이 분해가 anchor 달성에 최적인지")