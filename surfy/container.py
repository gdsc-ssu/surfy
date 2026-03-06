from dependency_injector import containers, providers

from surfy.adapters.browser import BrowserUseAdapter
from surfy.adapters.llm import AnthropicAdapter
from surfy.config import Settings
from surfy.domain.services import ActorService


class Container(containers.DeclarativeContainer):
    config = providers.Singleton(Settings)

    # Adapters
    llm = providers.Singleton(
        AnthropicAdapter,
        use_vision=config.provided.llm.use_vision,
        model_name=config.provided.llm.model_name,
    )

    browser = providers.Factory(
        BrowserUseAdapter.create,
        cdp_url=config.provided.browser.cdp_url,
    )

    # Services
    actor_service = providers.Factory(
        ActorService,
        browser=browser,
        llm=llm,
    )
