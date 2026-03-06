from pydantic import BaseModel

from surfy.domain.models.action import ActionType, BrowserAction


class ActorOutput(BaseModel):
    thinking: str  # 현재 상황 분석
    action_type: ActionType
    target_id: int | None = None
    value: str | None = None

    def to_browser_action(self) -> BrowserAction:
        return BrowserAction(
            action_type=self.action_type,
            target_id=self.target_id,
            value=self.value,
        )
