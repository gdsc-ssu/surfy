from abc import ABC, abstractmethod

from surfy.domain.models.action import BrowserAction
from surfy.domain.models.result import StepResult
from surfy.domain.models.screen import PageState


class BrowserPort(ABC):
    @abstractmethod
    async def get_page_state(self) -> PageState:
        ...

    @abstractmethod
    async def execute_action(self, action: BrowserAction) -> StepResult:
        ...

    @abstractmethod
    async def check_text_visible(self, text: str) -> bool:
        ...

    @abstractmethod
    async def connect(self, cdp_url: str) -> None:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...
