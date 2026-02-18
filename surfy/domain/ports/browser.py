from abc import ABC, abstractmethod

from surfy.domain.models import BrowserAction, PageState, StepResult


class BrowserPort(ABC):
    @abstractmethod
    async def get_page_state(self) -> PageState: ...

    @abstractmethod
    async def execute_action(self, action: BrowserAction) -> StepResult: ...

    @abstractmethod
    async def check_text_visible(self, text: str) -> bool: ...

    @abstractmethod
    async def close(self) -> None: ...