"""Evaluator 서비스 — 태스크 완료 여부 판정.

구조 체크(URL, 텍스트)만으로 판정한다.
판단이 불충분한 경우에는 success=True를 반환하며,
completion_check 유저 interrupt에서 최종 확인한다.
"""

from surfy.domain.models import EvalResult, PageState, Task
from surfy.domain.ports import BrowserPort


class EvaluatorService:
    """태스크 완료 여부를 판정하는 서비스.

    구조 체크(URL 패턴, 텍스트 가시성)로만 판정한다.
    description은 Planner의 태스크 설명용이며 평가에 사용하지 않는다.
    """

    def __init__(self, browser: BrowserPort):
        self._browser = browser

    async def evaluate(self, task: Task, page_state: PageState) -> EvalResult:
        """태스크 완료 여부를 판정.

        Args:
            task: 평가할 태스크 (success_criteria 포함)
            page_state: 현재 페이지 상태

        Returns:
            EvalResult: 성공 여부와 판정 이유
        """
        criteria = task.success_criteria

        if criteria.url_contains:
            if criteria.url_contains not in page_state.url:
                return EvalResult(
                    success=False,
                    reason=f"URL에 '{criteria.url_contains}' 없음 (현재: {page_state.url})",
                )

        if criteria.text_visible:
            visible = await self._browser.check_text_visible(criteria.text_visible)
            if not visible:
                return EvalResult(
                    success=False,
                    reason=f"'{criteria.text_visible}' 텍스트가 화면에 보이지 않음",
                )

        return EvalResult(success=True, reason="구조 체크 통과")
