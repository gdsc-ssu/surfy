"""Evaluator 서비스 — 태스크 완료 여부 판정.

2단계 평가 전략으로 비용 절감:
1. 구조 체크 (URL, 텍스트) — 비용 없음
2. LLM 판정 — 구조 체크로 판단 불가 시에만 호출
"""

from surfy.domain.models import EvalResult, PageState, Task
from surfy.domain.ports import BrowserPort, LLMPort


class EvaluatorService:
    """태스크 완료 여부를 판정하는 서비스.

    Actor가 태스크를 실행한 후, 이 서비스가 성공 여부를 판정한다.
    구조 체크로 빠르게 판단하고, 불충분하면 LLM을 호출한다.
    """

    def __init__(self, browser: BrowserPort, llm: LLMPort):
        self._browser = browser
        self._llm = llm

    async def evaluate(self, task: Task, page_state: PageState) -> EvalResult:
        """태스크 완료 여부를 판정.

        Args:
            task: 평가할 태스크 (success_criteria 포함)
            page_state: 현재 페이지 상태

        Returns:
            EvalResult: 성공 여부와 판정 이유
        """
        criteria = task.success_criteria

        # 1단계: URL 패턴 체크 (비용 없음)
        if criteria.url_contains:
            if criteria.url_contains not in page_state.url:
                if not criteria.description:
                    return EvalResult(
                        success=False,
                        reason=f"URL에 '{criteria.url_contains}' 없음 (현재: {page_state.url})",
                    )

        # 1단계: 텍스트 가시성 체크 (비용 없음)
        if criteria.text_visible:
            visible = await self._browser.check_text_visible(criteria.text_visible)
            if not visible:
                if not criteria.description:
                    return EvalResult(
                        success=False,
                        reason=f"'{criteria.text_visible}' 텍스트가 화면에 보이지 않음",
                    )

        # 2단계: LLM 판정 (구조 체크로 판단 불가한 경우)
        if criteria.description:
            return await self._llm.evaluate(criteria, page_state)

        # 모든 구조 체크 통과 + description 없음 → 성공
        return EvalResult(success=True, reason="구조 체크 통과")
