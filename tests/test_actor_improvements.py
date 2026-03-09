"""ActorService 개선 사항(루프 탐지, Force Done) 단위 테스트."""

import pytest

from surfy.domain.models import (
    ActionType,
    ActorOutput,
    BrowserAction,
    EvalResult,
    HistoryEntry,
    PageState,
    Plan,
    StepResult,
    SuccessCriteria,
    Task,
)
from surfy.domain.ports import BrowserPort, LLMPort
from surfy.domain.services.actor import ActorService, _page_fingerprint


class MockBrowser(BrowserPort):
    def __init__(self, same_state: bool = True):
        self.same_state = same_state
        self.step = 0

    async def get_page_state(self) -> PageState:
        self.step += 1
        if self.same_state:
            return PageState(
                url="https://example.com",
                title="Same Page",
                dom_text="Same content",
                screenshot=None,
            )
        else:
            return PageState(
                url=f"https://example.com/{self.step}",
                title=f"Page {self.step}",
                dom_text=f"Content {self.step}",
                screenshot=None,
            )

    async def execute_action(self, action: BrowserAction) -> StepResult:
        return StepResult(success=True, message="OK")

    async def check_text_visible(self, text: str) -> bool:
        return True

    async def close(self) -> None:
        pass


class MockLLM(LLMPort):
    def __init__(self):
        self.task_descriptions: list[str] = []

    async def decide_action(
        self, task: Task, page_state: PageState, history: list[HistoryEntry]
    ) -> ActorOutput:
        self.task_descriptions.append(task.description)
        # 항상 CLICK 반환하여 루프 유도
        return ActorOutput(thinking="Clicking", action_type=ActionType.CLICK, target_id=1)

    async def scout(
        self, task: Task, page_state: PageState, history: list[HistoryEntry]
    ) -> ActorOutput:
        return ActorOutput(thinking="Scout", action_type=ActionType.DONE)

    async def plan(self, command: str, progress: str, route_observations: str = "") -> Plan:
        return Plan(anchor=command, tasks=[], anchor_rationale="Mock plan")

    async def evaluate(self, criteria: SuccessCriteria, page_state: PageState) -> EvalResult:
        return EvalResult(success=True, reason="Mock evaluation")


def test_page_fingerprint():
    """_page_fingerprint 함수 검증."""
    state1 = PageState(url="https://a.com", title="A", dom_text="content1")
    state2 = PageState(url="https://a.com", title="A", dom_text="content1")
    state3 = PageState(url="https://b.com", title="B", dom_text="content2")

    assert _page_fingerprint(state1) == _page_fingerprint(state2)
    assert _page_fingerprint(state1) != _page_fingerprint(state3)


@pytest.mark.asyncio
async def test_loop_detection_nudge():
    """3번 연속 동일 상태 시 nudge 메시지가 추가되는지 확인."""
    browser = MockBrowser(same_state=True)
    llm = MockLLM()
    actor = ActorService(browser=browser, llm=llm)

    # 3번째 스텝에서 nudge가 추가되어야 함
    await actor.execute_task(Task(description="Test"), max_steps=3)

    assert any("3번 연속 동일 상태" in d for d in llm.task_descriptions)


@pytest.mark.asyncio
async def test_loop_detection_stuck():
    """5번 연속 동일 상태 시 STUCK으로 종료되는지 확인."""
    browser = MockBrowser(same_state=True)
    llm = MockLLM()
    actor = ActorService(browser=browser, llm=llm)

    result = await actor.execute_task(Task(description="Test"), max_steps=10)

    assert result.success is False
    assert "Loop detected" in result.message
    assert browser.step == 5


@pytest.mark.asyncio
async def test_force_done_nudge_remaining_2():
    """남은 스텝이 2개일 때 nudge 메시지가 추가되는지 확인."""
    browser = MockBrowser(same_state=False)  # 루프 방지
    llm = MockLLM()
    actor = ActorService(browser=browser, llm=llm)

    # max_steps=3일 때, step 2(index 1)은 remaining=2
    await actor.execute_task(Task(description="Test"), max_steps=3)

    assert any("남은 스텝이 2개" in d for d in llm.task_descriptions)


@pytest.mark.asyncio
async def test_force_done_nudge_last_step():
    """마지막 스텝일 때 nudge 메시지가 추가되는지 확인."""
    browser = MockBrowser(same_state=False)
    llm = MockLLM()
    actor = ActorService(browser=browser, llm=llm)

    # max_steps=1일 때, step 1은 remaining=1
    await actor.execute_task(Task(description="Test"), max_steps=1)

    assert any("마지막 스텝" in d for d in llm.task_descriptions)
