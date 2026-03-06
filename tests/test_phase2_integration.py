"""Phase 2 통합 검증 — Actor ReAct 루프 + LLM 연동.

실행:
  - Mock 테스트: uv run pytest tests/test_phase2_integration.py -v -k "mock"
  - 실제 테스트: uv run pytest tests/test_phase2_integration.py -v -k "real" (ANTHROPIC_API_KEY 필요)
"""

import platform
import shutil
import subprocess
import tempfile
import time

import pytest
import pytest_asyncio

from surfy.domain.models import ActionType, ActorOutput, PageState, StepResult, Task
from surfy.domain.ports import BrowserPort, LLMPort
from surfy.domain.services import ActorService

# ============================================================
# Mock 테스트 - API 없이 ReAct 루프 로직 검증
# ============================================================


class MockBrowser(BrowserPort):
    def __init__(self):
        self.step = 0
        self.actions_executed: list[str] = []

    async def get_page_state(self) -> PageState:
        self.step += 1
        return PageState(
            url=f"https://example.com/step{self.step}",
            title=f"Step {self.step}",
            dom_text="[1] button: Click me\n[2] input: Search",
            screenshot=None,
        )

    async def execute_action(self, action):
        self.actions_executed.append(action.action_type.value)
        return StepResult(success=True, message=f"Executed {action.action_type.value}")

    async def check_text_visible(self, text: str) -> bool:
        return True

    async def close(self):
        pass


class MockLLM(LLMPort):
    """Mock LLM that returns predefined actions."""

    def __init__(self, actions: list[ActorOutput]):
        self._actions = actions
        self._index = 0

    async def decide_action(self, task, page_state, history) -> ActorOutput:
        if self._index >= len(self._actions):
            return ActorOutput(thinking="Done", action_type=ActionType.DONE)
        action = self._actions[self._index]
        self._index += 1
        return action


@pytest.mark.asyncio
async def test_mock_react_loop_completes_on_done():
    """DONE 액션 반환 시 루프가 종료되는지 확인."""
    browser = MockBrowser()
    llm = MockLLM(
        [
            ActorOutput(thinking="Click button", action_type=ActionType.CLICK, target_id=1),
            ActorOutput(thinking="Type text", action_type=ActionType.TYPE, target_id=2, value="test"),
            ActorOutput(thinking="Task done", action_type=ActionType.DONE),
        ]
    )
    actor = ActorService(browser=browser, llm=llm)

    result = await actor.execute_task(Task(description="Test task"), max_steps=10)

    assert result.success
    assert browser.actions_executed == ["CLICK", "TYPE", "DONE"]


@pytest.mark.asyncio
async def test_mock_react_loop_respects_max_steps():
    """max_steps 초과 시 루프가 종료되는지 확인."""
    browser = MockBrowser()
    llm = MockLLM(
        [ActorOutput(thinking="Keep clicking", action_type=ActionType.CLICK, target_id=1)] * 100
    )
    actor = ActorService(browser=browser, llm=llm)

    await actor.execute_task(Task(description="Infinite task"), max_steps=5)

    assert len(browser.actions_executed) == 5


@pytest.mark.asyncio
async def test_mock_react_loop_stops_on_stuck():
    """STUCK 액션 반환 시 루프가 종료되는지 확인."""
    browser = MockBrowser()
    llm = MockLLM(
        [
            ActorOutput(thinking="Try click", action_type=ActionType.CLICK, target_id=1),
            ActorOutput(thinking="Cannot proceed", action_type=ActionType.STUCK),
        ]
    )
    actor = ActorService(browser=browser, llm=llm)

    result = await actor.execute_task(Task(description="Stuck task"), max_steps=10)

    assert result.success
    assert browser.actions_executed == ["CLICK", "STUCK"]


# ============================================================
# 실제 통합 테스트 - Chrome + Anthropic API 사용
# ============================================================

CDP_PORT = 9222


def _find_chrome() -> str:
    if platform.system() == "Darwin":
        return "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    elif platform.system() == "Windows":
        return r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    return "google-chrome"


@pytest.fixture(scope="module")
def chrome():
    user_data_dir = tempfile.mkdtemp(prefix="surfy_test_phase2_")
    proc = subprocess.Popen(
        [
            _find_chrome(),
            f"--remote-debugging-port={CDP_PORT}",
            f"--user-data-dir={user_data_dir}",
            "--no-first-run",
            "--no-default-browser-check",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(3)
    yield proc
    proc.terminate()
    proc.wait(timeout=5)
    shutil.rmtree(user_data_dir, ignore_errors=True)


@pytest.fixture(scope="module")
def container():
    from surfy.container import Container

    return Container()


@pytest_asyncio.fixture
async def browser(chrome, container):
    b = await container.browser()
    yield b
    await b.close()


@pytest.mark.asyncio
@pytest.mark.real
async def test_real_google_search(browser, container):
    """실제 Google 검색 태스크 수행."""
    llm = container.llm()
    actor = ActorService(browser=browser, llm=llm)

    task = Task(description="google.com에 접속해서 'hello'를 검색하세요")
    result = await actor.execute_task(task, max_steps=10)

    assert result.success
    page_state = await browser.get_page_state()
    assert "google.com" in page_state.url
    # 검색 결과 페이지에 도달했는지 확인 (search?q= 또는 hello 포함)
    assert "search" in page_state.url or "hello" in page_state.url.lower()


@pytest.mark.asyncio
@pytest.mark.real
async def test_real_korail_search(browser, container):
    """실제 코레일 기차편 검색 태스크 수행."""
    llm = container.llm()
    actor = ActorService(browser=browser, llm=llm)

    task = Task(
        description=(
            "코레일(korail.com)에 접속해서 내일 광명역에서 계룡역으로 가는 "
            "가장 빠른 기차편을 검색해주세요. 출발역: 광명, 도착역: 계룡, 날짜: 내일"
        )
    )
    result = await actor.execute_task(task, max_steps=20)

    assert result.success
    page_state = await browser.get_page_state()
    # 코레일 검색 결과 페이지에 도달했는지 확인
    assert "korail.com" in page_state.url
    assert "search" in page_state.url or "list" in page_state.url
