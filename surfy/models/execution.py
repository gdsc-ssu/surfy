from pydantic import BaseModel, Field

from surfy.models.screen import ScreenState


class ExecutionResult(BaseModel):
    success: bool = Field(description="실행 성공 여부")
    error_message: str = Field(default="", description="실패 시 에러 메시지")
    screen_after: ScreenState | None = Field(default=None, description="실행 후 화면 상태")