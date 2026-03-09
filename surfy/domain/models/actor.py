from pydantic import BaseModel, model_validator

from surfy.domain.models.action import ActionType, BrowserAction


class ActorOutput(BaseModel):
    evaluation_previous_goal: str = ""
    memory: str = ""
    next_goal: str = ""
    thinking: str  # 현재 상황 분석
    action_type: ActionType
    target_id: int | None = None
    value: str | None = None

    @model_validator(mode="after")
    def validate_required_fields(self) -> "ActorOutput":
        """ActionType별 필수 필드 검증."""
        if self.action_type == ActionType.CLICK and self.target_id is None:
            raise ValueError("CLICK action requires target_id")
        if self.action_type == ActionType.TYPE:
            if self.target_id is None:
                raise ValueError("TYPE action requires target_id")
            if self.value is None:
                raise ValueError("TYPE action requires value")
        if self.action_type == ActionType.GO_TO_URL and self.value is None:
            raise ValueError("GO_TO_URL action requires value (URL)")
        if self.action_type == ActionType.SEND_KEYS and self.value is None:
            raise ValueError("SEND_KEYS action requires value (key)")
        return self

    def to_browser_action(self) -> BrowserAction:
        return BrowserAction(
            action_type=self.action_type,
            target_id=self.target_id,
            value=self.value,
        )
