from __future__ import annotations

from pydantic import BaseModel

from surfy.domain.models.screen import PageState


class StepResult(BaseModel):
    success: bool
    message: str
    page_state: PageState | None = None