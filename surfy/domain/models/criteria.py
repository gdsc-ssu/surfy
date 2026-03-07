from pydantic import BaseModel


class SuccessCriteria(BaseModel):
    """태스크 완료 조건.

    Planner가 DOM을 보지 않으므로 추상적 레벨만 사용.
    Evaluator가 이 기준으로 태스크 성공 여부를 판정한다.
    """

    url_contains: str | None = None
    """URL에 포함되어야 할 패턴 (Planner가 예측 가능)."""

    text_visible: str | None = None
    """화면에 보여야 할 텍스트."""

    description: str = ""
    """자연어 설명 (항상 채움). 구조 체크 불충분 시 LLM이 이 설명으로 판단."""
