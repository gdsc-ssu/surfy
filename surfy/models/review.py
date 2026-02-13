from pydantic import BaseModel, Field

from surfy.models.screen import ScreenState


class ReviewResult(BaseModel):
    is_success: bool = Field(description="검증 성공 여부")
    rationale: str = Field(default="", description="판단 근거")
    expected: str = Field(default="", description="기대 결과 (자연어)")
    observed: ScreenState | None = Field(default=None, description="실제 관찰된 화면 상태")