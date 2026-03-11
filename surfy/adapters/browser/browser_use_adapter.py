import logging
import platform
from pathlib import Path

from browser_use import BrowserSession
from browser_use.browser.events import (
    ClickElementEvent,
    GoBackEvent,
    NavigateToUrlEvent,
    ScrollEvent,
    SendKeysEvent,
    TypeTextEvent,
)
from browser_use.browser.views import BrowserStateSummary

from surfy.domain.models import ActionType, BrowserAction, PageState, StepResult
from surfy.domain.ports import BrowserPort

logger = logging.getLogger(__name__)


def _get_chrome_user_data_dir() -> str:
    system = platform.system()
    if system == "Darwin":
        return str(Path.home() / "Library/Application Support/Google/Chrome")
    if system == "Linux":
        return str(Path.home() / ".config/google-chrome")
    if system == "Windows":
        local_app_data = Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "User Data"
        return str(local_app_data)
    raise RuntimeError(f"Unsupported platform: {system}")


class BrowserUseAdapter(BrowserPort):
    def __init__(self, session: BrowserSession) -> None:
        self._session = session
        self._last_state: BrowserStateSummary | None = None

    @classmethod
    async def create(
        cls,
        cdp_url: str | None = None,
        *,
        use_system_chrome: bool = False,
        chrome_profile: str = "Default",
    ) -> "BrowserUseAdapter":
        if cdp_url is not None:
            session = BrowserSession(cdp_url=cdp_url, keep_alive=True)
            label = f"CDP {cdp_url}"
        elif use_system_chrome:
            user_data_dir = _get_chrome_user_data_dir()
            session = BrowserSession(
                user_data_dir=user_data_dir,
                profile_directory=chrome_profile,
                headless=False,
                keep_alive=True,
            )
            label = f"system chrome (profile={chrome_profile})"
        else:
            session = BrowserSession(headless=False, disable_security=True, keep_alive=True)
            label = "자동 실행"
        await session.start()
        logger.info("브라우저 연결 완료: %s", label)
        return cls(session)

    async def get_page_state(self) -> PageState:
        summary = await self._session.get_browser_state_summary()
        self._last_state = summary
        return PageState(
            url=summary.url,
            title=summary.title,
            dom_text=summary.dom_state.llm_representation(),
            screenshot=summary.screenshot,
        )

    async def execute_action(self, action: BrowserAction) -> StepResult:
        try:
            match action.action_type:
                case ActionType.GO_TO_URL:
                    assert action.value, "GO_TO_URL requires a URL"
                    event = self._session.event_bus.dispatch(NavigateToUrlEvent(url=action.value))
                    await event
                    await event.event_result(raise_if_any=True, raise_if_none=False)
                case ActionType.CLICK:
                    assert action.target_id is not None, "CLICK requires target_id"
                    node = await self._session.get_element_by_index(action.target_id)
                    if node is None:
                        raise ValueError(f"Element index {action.target_id} not found")
                    event = self._session.event_bus.dispatch(ClickElementEvent(node=node))
                    await event
                    await event.event_result(raise_if_any=True, raise_if_none=False)
                case ActionType.TYPE:
                    assert action.target_id is not None, "TYPE requires target_id"
                    assert action.value, "TYPE requires value"
                    node = await self._session.get_element_by_index(action.target_id)
                    if node is None:
                        raise ValueError(f"Element index {action.target_id} not found")
                    event = self._session.event_bus.dispatch(TypeTextEvent(node=node, text=action.value, clear=True))
                    await event
                    await event.event_result(raise_if_any=True, raise_if_none=False)
                case ActionType.SCROLL_DOWN:
                    event = self._session.event_bus.dispatch(ScrollEvent(direction="down", amount=500))
                    await event
                    await event.event_result(raise_if_any=True, raise_if_none=False)
                case ActionType.SCROLL_UP:
                    event = self._session.event_bus.dispatch(ScrollEvent(direction="up", amount=500))
                    await event
                    await event.event_result(raise_if_any=True, raise_if_none=False)
                case ActionType.SEND_KEYS:
                    assert action.value, "SEND_KEYS requires value"
                    event = self._session.event_bus.dispatch(SendKeysEvent(keys=action.value))
                    await event
                    await event.event_result(raise_if_any=True, raise_if_none=False)
                case ActionType.GO_BACK:
                    event = self._session.event_bus.dispatch(GoBackEvent())
                    await event
                    await event.event_result(raise_if_any=True, raise_if_none=False)
                case ActionType.DONE | ActionType.STUCK:
                    return StepResult(success=True, message=action.action_type.value)

            new_state = await self.get_page_state()
            return StepResult(
                success=True,
                message=f"{action.action_type.value} 완료",
                page_state=new_state,
            )
        except Exception as e:
            logger.exception("액션 실행 실패: %s", action)
            return StepResult(success=False, message=str(e))

    async def check_text_visible(self, text: str) -> bool:
        if self._last_state is None:
            await self.get_page_state()
        assert self._last_state is not None
        return text in self._last_state.dom_state.llm_representation()

    def get_session(self) -> BrowserSession:
        """browser-use Agent에 공유할 BrowserSession 반환."""
        return self._session

    async def close(self) -> None:
        await self._session.stop()
