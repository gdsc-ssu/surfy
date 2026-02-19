import logging
from browser_use import BrowserSession
from browser_use.browser.views import BrowserStateSummary
from browser_use.actor.element import Element
from surfy.domain.models import PageState, BrowserAction, StepResult, ActionType
from surfy.domain.ports import BrowserPort

logger = logging.getLogger(__name__)

class BrowserUseAdapter(BrowserPort):
    """
    browser-use v0.11.x을 활용한 BrowserPort 구현체.
    CDP 연결, DOM 추출, 브라우저 액션 실행을 담당합니다.
    """

    def __init__(self):
        self._session: BrowserSession | None = None
        self._last_state: BrowserStateSummary | None = None

    async def connect(self, cdp_url: str) -> None:
        """
        기존에 실행 중인 Chrome에 CDP를 통해 연결합니다.
        """
        self._session = BrowserSession(cdp_url=cdp_url)
        await self._session.start()
        logger.info(f"Successfully connected to browser via CDP: {cdp_url}")

    async def get_page_state(self) -> PageState:
        """
        현재 페이지의 상태(URL, 제목, DOM 텍스트, 스크린샷)를 추출합니다.
        """
        if not self._session:
            raise RuntimeError("Browser not connected. Call connect() first.")

        summary = await self._session.get_browser_state_summary()
        self._last_state = summary  # selector_map 캐시를 위해 저장

        return PageState(
            url=summary.url,
            title=summary.title,
            dom_text=summary.dom_state.llm_representation(),
            screenshot=summary.screenshot
        )

    async def execute_action(self, action: BrowserAction) -> StepResult:
        """
        ActionType에 따라 브라우저 액션을 실행합니다.
        """
        if not self._session:
            return StepResult(success=False, message="Browser not connected")

        if action.action_type in (ActionType.DONE, ActionType.STUCK):
            return StepResult(success=True, message=f"{action.action_type.value}")

        try:
            page = await self._session.get_current_page()
            if page is None:
                return StepResult(success=False, message="No active page")

            match action.action_type:
                case ActionType.GO_TO_URL:
                    if not action.value:
                        return StepResult(success=False, message="URL is required")
                    await page.goto(action.value)
                case ActionType.CLICK:
                    element = self._resolve_element(action.target_id)
                    await element.click()
                case ActionType.TYPE:
                    element = self._resolve_element(action.target_id)
                    if action.value is None:
                        return StepResult(success=False, message="Value is required for TYPE")
                    await element.fill(action.value)
                case ActionType.SCROLL_DOWN:
                    await page.evaluate("(...args) => { window.scrollBy(0, 500); }")
                case ActionType.SCROLL_UP:
                    await page.evaluate("(...args) => { window.scrollBy(0, 500); }")
                case ActionType.SEND_KEYS:
                    if action.value:
                        element = self._resolve_element(target_id=action.target_id)
                        if action.value.lower() == "enter": # Enter 키는 fill("\n")로 처리
                            await element.fill("\n")
                        elif len(action.value) == 1:  # 일반 문자
                            await element.fill(action.value)
                        else:  # Tab, Escape, 화살표키 등
                            js = f"""
                            (...args) => {{
                                const e = new KeyboardEvent('keydown', {{
                                    key: '{action.value}',
                                    code: '{action.value}',
                                    bubbles: true
                                }});
                                document.activeElement.dispatchEvent(e);
                            }}
                            """
                            page = await self._session.get_current_page()
                            await page.evaluate(js)
                case ActionType.GO_BACK:
                    await page.go_back()

            new_state = await self.get_page_state()
            return StepResult(success=True, message=f"Executed {action.action_type.value}", page_state=new_state)
        except Exception as e:
            logger.exception(f"Failed to execute action {action.action_type}: {e}")
            return StepResult(success=False, message=str(e))

    def _resolve_element(self, target_id: int | None) -> Element:
        """selector_map index를 browser-use Element로 변환합니다."""
        if self._last_state is None:
            raise RuntimeError("Call get_page_state() before resolving elements")
        if target_id is None:
            raise ValueError("target_id is required for this action")

        node = self._last_state.dom_state.selector_map[target_id]
        return Element(
            browser_session=self._session,
            backend_node_id=node.backend_node_id,
            session_id=node.session_id,
        )

    async def check_text_visible(self, text: str) -> bool:
        """
        현재 DOM 텍스트 내에 특정 텍스트가 존재하는지 확인합니다.
        """
        state = await self.get_page_state()
        return text.lower() in state.dom_text.lower()

    async def close(self) -> None:
        """
        브라우저 세션을 종료하고 리소스를 정리합니다.
        """
        if self._session:
            await self._session.stop()
            self._session = None
            logger.info("Browser session closed")
