from enum import Enum

from pydantic import BaseModel


class ActionType(str, Enum):
    CLICK = "CLICK"
    TYPE = "TYPE"
    SCROLL_DOWN = "SCROLL_DOWN"
    SCROLL_UP = "SCROLL_UP"
    GO_TO_URL = "GO_TO_URL"
    SEND_KEYS = "SEND_KEYS"
    GO_BACK = "GO_BACK"
    DONE = "DONE"
    STUCK = "STUCK"


class BrowserAction(BaseModel):
    action_type: ActionType
    target_id: int | None = None
    value: str | None = None