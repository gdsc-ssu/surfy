from __future__ import annotations

from typing import Any

from browser_use import BrowserSession
from browser_use.tools.service import Controller

from surfy.domain.models import ActionType, BrowserAction, PageState, StepResult
from surfy.domain.ports import BrowserPort


class BrowserUseAdapter(BrowserPort):
    def __init__(self) -> None:
        self._session: BrowserSession | None = None
        self._controller: Controller | None = None
        self._action_model: type | None = None

    def _ensure_session(self) -> BrowserSession:
        if self._session is None:
            raise RuntimeError("connect()를 먼저 호출하세요")
        return self._session

    def _ensure_controller(self) -> Controller:
        if self._controller is None:
            raise RuntimeError("connect()를 먼저 호출하세요")
        return self._controller

    def _create_action(self, data: dict[str, Any]) -> Any:
        """registry의 ActionModel로 래핑하여 반환"""
        if self._action_model is None:
            self._action_model =(
                self._ensure_controller().registry.create_action_model()
            ) 
        return self._action_model.model_validate(data)

    async def connect(self, cdp_url: str) -> None:
        self._session = BrowserSession(cdp_url=cdp_url, is_local=False)  # type: ignore[call-overload]
        await self._session.start()
        self._controller = Controller()

    async def get_page_state(self) -> PageState:
        """take_screenshot() 직접 호출"""
        session = self._ensure_session()
        state = await session.get_browser_state_summary(include_screenshot=False)
        screenshot_bytes = await session.take_screenshot()
        return PageState(
            url=state.url,
            title=state.title,
            dom_text=state.dom_state.llm_representation(),
            screenshot=screenshot_bytes,
        )

    async def execute_action(self, action: BrowserAction) -> StepResult:
        session = self._ensure_session()
        controller = self._ensure_controller()

        try:
            match action.action_type:
                case ActionType.CLICK:
                    await controller.act(
                        self._create_action({"click": {"index": action.target_id}}),
                        session,
                    )
                case ActionType.TYPE:
                    await controller.act(
                        self._create_action(
                            {
                                "input": {
                                    "index": action.target_id, 
                                    "text": action.value or ""
                                }
                            }
                        ),
                        session,
                    )
                case ActionType.SCROLL_DOWN:
                    await controller.act(
                        self._create_action({"scroll": {"down": True}}),
                        session,
                    )
                case ActionType.SCROLL_UP:
                    await controller.act(
                        self._create_action({"scroll": {"down": False}}),
                        session,
                    )
                case ActionType.GO_TO_URL:
                    await controller.act(
                        self._create_action({"navigate": {"url": action.value or ""}}),
                        session,
                    )
                case ActionType.DONE | ActionType.STUCK:
                    return StepResult(
                        success=action.action_type == ActionType.DONE,
                        message=action.value or action.action_type.value,
                    )

            return StepResult(success=True, message=f"{action.action_type.value} 완료")
        except Exception as e:
            return StepResult(success=False, message=str(e))

    async def check_text_visible(self, text: str) -> bool:
        session = self._ensure_session()
        state = await session.get_browser_state_summary(include_screenshot=False)
        return text in state.dom_state.llm_representation()

    async def close(self) -> None:
        if self._session:
            await self._session.stop()
            self._session = None
            self._controller = None
