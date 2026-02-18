import logging

from browser_use import BrowserSession
from browser_use.actor.element import Element
from browser_use.browser.views import BrowserStateSummary

from surfy.domain.models import ActionType, BrowserAction, PageState, StepResult
from surfy.domain.ports import BrowserPort

logger = logging.getLogger(__name__)


class BrowserUseAdapter(BrowserPort):
    def __init__(self, session: BrowserSession) -> None:
        self._session = session
        self._last_state: BrowserStateSummary | None = None

    @classmethod
    async def create(cls, cdp_url: str) -> "BrowserUseAdapter":
        session = BrowserSession(cdp_url=cdp_url)
        await session.start()
        logger.info("CDP 연결 완료: %s", cdp_url)
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
        if action.action_type in (ActionType.DONE, ActionType.STUCK):
            return StepResult(success=True, message=action.action_type.value)

        try:
            cdp = self._session.cdp_client

            match action.action_type:
                case ActionType.GO_TO_URL:
                    assert action.value is not None, "GO_TO_URL에는 value(URL)가 필요합니다"
                    await self._session.navigate_to(action.value)
                case ActionType.CLICK:
                    element = self._resolve_element(action.target_id)
                    await element.click()
                case ActionType.TYPE:
                    assert action.value is not None, "TYPE에는 value(입력값)가 필요합니다"
                    element = self._resolve_element(action.target_id)
                    await element.fill(action.value)
                case ActionType.SCROLL_DOWN:
                    await cdp.send.Runtime.evaluate(
                        params={"expression": "window.scrollBy(0, 500)"}
                    )
                case ActionType.SCROLL_UP:
                    await cdp.send.Runtime.evaluate(
                        params={"expression": "window.scrollBy(0, -500)"}
                    )
                case ActionType.SEND_KEYS:
                    assert action.value is not None
                    await self._send_key(action.value)
                case ActionType.GO_BACK:
                    await self._go_back()

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

    async def close(self) -> None:
        await self._session.stop()

    def _resolve_element(self, target_id: int | None) -> Element:
        if self._last_state is None:
            raise RuntimeError("get_page_state()를 먼저 호출해야 합니다")
        if target_id is None:
            raise ValueError("CLICK/TYPE 액션에는 target_id가 필요합니다")

        node = self._last_state.dom_state.selector_map[target_id]
        return Element(
            browser_session=self._session,
            backend_node_id=node.backend_node_id,
            session_id=node.session_id,
        )

    async def _send_key(self, key: str) -> None:
        """CDP를 통해 키보드 이벤트 전송 (Enter, Tab, Escape 등)."""
        cdp = self._session.cdp_client
        await cdp.send.Input.dispatchKeyEvent(
            params={"type": "keyDown", "key": key}
        )
        await cdp.send.Input.dispatchKeyEvent(
            params={"type": "keyUp", "key": key}
        )

    async def _go_back(self) -> None:
        """CDP를 통해 브라우저 히스토리 뒤로가기."""
        cdp = self._session.cdp_client
        history = await cdp.send.Page.getNavigationHistory()
        current_index = history["currentIndex"]
        if current_index > 0:
            entry_id = history["entries"][current_index - 1]["id"]
            await cdp.send.Page.navigateToHistoryEntry(params={"entryId": entry_id})