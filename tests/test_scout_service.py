"""ScoutService 단위 테스트."""

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
from surfy.domain.services import ScoutService


class MockBrowser(BrowserPort):
    def __init__(self):
        self.step = 0
        self.actions_executed: list[str] = []

    async def get_page_state(self) -> PageState:
        self.step += 1
        return PageState(
            url=f"https://example.com/step{self.step}",
            title=f"Step {self.step}",
            dom_text=f"Page content for step {self.step}\n[1] button: Click me",
            screenshot=None,
        )

    async def execute_action(self, action: BrowserAction) -> StepResult:
        self.actions_executed.append(action.action_type.value)
        return StepResult(success=True, message=f"Executed {action.action_type.value}")

    async def check_text_visible(self, text: str) -> bool:
        return True

    async def close(self) -> None:
        pass


class MockLLM(LLMPort):
    def __init__(self, actions: list[ActorOutput]):
        self._actions = actions
        self._index = 0

    async def decide_action(
        self, task: Task, page_state: PageState, history: list[HistoryEntry]
    ) -> ActorOutput:
        return ActorOutput(thinking="Decide", action_type=ActionType.DONE)

    async def scout(
        self, task: Task, page_state: PageState, history: list[HistoryEntry]
    ) -> ActorOutput:
        if self._index >= len(self._actions):
            return ActorOutput(thinking="Done", action_type=ActionType.DONE, value="Scout completed")
        action = self._actions[self._index]
        self._index += 1
        return action

    async def plan(self, command: str, progress: str, route_observations: str = "") -> Plan:
        return Plan(anchor=command, tasks=[], anchor_rationale="Mock plan")

    async def evaluate(self, criteria: SuccessCriteria, page_state: PageState) -> EvalResult:
        return EvalResult(success=True, reason="Mock evaluation")


@pytest.mark.asyncio
async def test_scout_completes_on_done():
    """DONE 액션 반환 시 정찰이 완료되고 RouteMap을 반환하는지 확인."""
    browser = MockBrowser()
    llm = MockLLM(
        [
            ActorOutput(thinking="Go to search", action_type=ActionType.CLICK, target_id=1),
            ActorOutput(thinking="Found it", action_type=ActionType.DONE, value="Found target page"),
        ]
    )
    scout_service = ScoutService(browser=browser, llm=llm)

    route_map = await scout_service.scout("Find something", max_steps=10)

    assert len(route_map.steps) == 2
    assert route_map.steps[0].url == "https://example.com/step1"
    assert route_map.steps[1].url == "https://example.com/step2"
    assert route_map.final_url == "https://example.com/step2"
    assert route_map.scout_summary == "Found target page"
    assert browser.actions_executed == ["CLICK"]


@pytest.mark.asyncio
async def test_scout_stops_on_stuck():
    """STUCK 액션 반환 시 정찰이 중단되고 부분적인 RouteMap을 반환하는지 확인."""
    browser = MockBrowser()
    llm = MockLLM(
        [
            ActorOutput(thinking="Try click", action_type=ActionType.CLICK, target_id=1),
            ActorOutput(thinking="Stuck here", action_type=ActionType.STUCK, value="Cannot find button"),
        ]
    )
    scout_service = ScoutService(browser=browser, llm=llm)

    route_map = await scout_service.scout("Find something", max_steps=10)

    assert len(route_map.steps) == 2
    assert route_map.scout_summary == "Scout stuck: Cannot find button"
    assert browser.actions_executed == ["CLICK"]


@pytest.mark.asyncio
async def test_scout_respects_max_steps():
    """max_steps 도달 시 정찰이 종료되는지 확인."""
    browser = MockBrowser()
    # 무한 클릭
    llm = MockLLM([ActorOutput(thinking="Click", action_type=ActionType.CLICK, target_id=1)] * 20)
    scout_service = ScoutService(browser=browser, llm=llm)

    route_map = await scout_service.scout("Find something", max_steps=3)

    assert len(route_map.steps) == 3
    assert route_map.scout_summary == "Max steps reached"
    assert len(browser.actions_executed) == 3


@pytest.mark.asyncio
async def test_scout_step_details():
    """RouteStep의 상세 필드들이 올바르게 채워지는지 확인."""
    browser = MockBrowser()
    llm = MockLLM(
        [
            ActorOutput(
                thinking="Thinking about step 1",
                memory="Memory of step 1",
                action_type=ActionType.CLICK,
                target_id=1
            ),
            ActorOutput(
                thinking="Thinking about step 2",
                action_type=ActionType.DONE,
                value="Finished"
            ),
        ]
    )
    scout_service = ScoutService(browser=browser, llm=llm)

    route_map = await scout_service.scout("Test", max_steps=5)

    step1 = route_map.steps[0]
    assert step1.url == "https://example.com/step1"
    assert step1.title == "Step 1"
    assert step1.action_taken == "CLICK(1)"
    assert "Page content for step 1" in step1.observed_elements[0]
    assert step1.notes == "Memory of step 1"

    step2 = route_map.steps[1]
    assert step2.action_taken == "DONE(Finished)"
    assert step2.notes == "Thinking about step 2"  # memory가 없으면 thinking 사용
