import logging

from surfy.domain.models import ActionType, HistoryEntry, PageState, StepResult, Task
from surfy.domain.ports import BrowserPort, LLMPort

logger = logging.getLogger(__name__)


def _page_fingerprint(page_state: PageState) -> str:
    """Generate a fingerprint for loop detection."""
    return str(hash(page_state.url + page_state.dom_text[:500]))


class ActorService:
    def __init__(self, browser: BrowserPort, llm: LLMPort):
        self._browser = browser
        self._llm = llm

    async def execute_task(self, task: Task, max_steps: int = 15, initial_memory: str = "") -> StepResult:
        history: list[HistoryEntry] = []
        fingerprints: list[str] = []
        last_page_state: PageState | None = None
        previous_memory: str = initial_memory
        ultimate_goal: str = task.description

        login_url_patterns = ["login", "signin", "sign_in", "cmc/01", "selectLoginForm"]

        for step in range(max_steps):
            page_state = await self._browser.get_page_state()
            last_page_state = page_state

            if any(p in page_state.url for p in login_url_patterns):
                return StepResult(success=False, message="AUTH_REQUIRED: 로그인 페이지 감지됨", page_state=page_state)

            fp = _page_fingerprint(page_state)
            fingerprints.append(fp)

            if len(fingerprints) >= 5 and len(set(fingerprints[-5:])) == 1:
                logger.warning("Loop detected: 5 identical page states. Forcing STUCK.")
                return StepResult(success=False, message="Loop detected: stuck on same page", page_state=page_state)

            nudge = ""
            if len(fingerprints) >= 3 and len(set(fingerprints[-3:])) == 1:
                nudge += "\n\n⚠️ 같은 페이지에서 3번 연속 동일 상태입니다. 다른 접근 방식을 시도하세요."

            remaining = max_steps - step
            if remaining <= 2:
                if remaining == 1:
                    nudge += "\n\n🚨 이것이 마지막 스텝입니다. 반드시 DONE 또는 STUCK으로 종료하세요."
                else:
                    nudge += f"\n\n⚠️ 남은 스텝이 {remaining}개입니다. 현재 상태에서 DONE 또는 STUCK을 선택하세요."

            current_task = Task(
                description=ultimate_goal + nudge,
                success_criteria=task.success_criteria,
                target_url=task.target_url,
            )

            output = await self._llm.decide_action(current_task, page_state, history, previous_memory=previous_memory)

            logger.info(
                "Step %d: %s (target=%s, value=%s, eval=%s, next_goal=%s)",
                step + 1,
                output.action_type.value,
                output.target_id,
                output.value,
                output.evaluation_previous_goal,
                output.next_goal,
            )

            # 종료 조건 먼저 체크
            if output.action_type == ActionType.DONE:
                return StepResult(
                    success=True,
                    message=output.value or "Task completed",
                    page_state=page_state,
                )
            if output.action_type == ActionType.STUCK:
                return StepResult(
                    success=False,
                    message=output.value or "Agent stuck",
                    page_state=page_state,
                )

            previous_memory = f"[최종 목표: {ultimate_goal}]\n{output.memory}"
            action = output.to_browser_action()
            result = await self._browser.execute_action(action)
            history.append(HistoryEntry(action=output, result=result, step=step + 1))

        # max_steps 도달
        return StepResult(
            success=False,
            message=f"Max steps ({max_steps}) reached without completing task",
            page_state=last_page_state,
        )
