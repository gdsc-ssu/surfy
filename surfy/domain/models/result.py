from __future__ import annotations

from pydantic import BaseModel

from surfy.domain.models.screen import PageState


class StepResult(BaseModel):
    """Actor의 단일 액션 실행 결과."""

    success: bool
    message: str
    page_state: PageState | None = None


class EvalResult(BaseModel):
    """Evaluator의 태스크 완료 판정 결과.

    구조 체크(URL, 텍스트) 또는 LLM 판정의 결과를 담는다.
    """

    success: bool
    """태스크 성공 여부."""

    reason: str
    """판정 이유. 실패 시 왜 실패했는지, 성공 시 어떤 기준으로 판단했는지."""
