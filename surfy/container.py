from collections.abc import AsyncIterator

from dependency_injector import containers, providers

from surfy.adapters.browser import BrowserUseAdapter
from surfy.adapters.llm import AnthropicAdapter
from surfy.config import Settings
from surfy.domain.services import ActorService


async def init_browser(cdp_url: str) -> AsyncIterator[BrowserUseAdapter]:
    """Browser adapter lifecycle 관리를 위한 async generator."""
    adapter = await BrowserUseAdapter.create(cdp_url)
    yield adapter
    await adapter.close()


class Container(containers.DeclarativeContainer):
    config = providers.Singleton(Settings)

    # Adapters
    llm = providers.Singleton(
        AnthropicAdapter,
        use_vision=config.provided.llm.use_vision,
        model_name=config.provided.llm.model_name,
    )

    browser = providers.Resource(
        init_browser,
        cdp_url=config.provided.browser.cdp_url,
    )

    # Services
    actor_service = providers.Factory(
        ActorService,
        browser=browser,
        llm=llm,
    )
