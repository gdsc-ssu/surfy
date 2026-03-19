from collections.abc import AsyncIterator

from dependency_injector import containers, providers

from surfy.adapters.browser import BrowserUseAdapter
from surfy.adapters.cache import JsonFileCacheAdapter
from surfy.adapters.llm import LangChainLLMAdapter
from surfy.config import Settings
from surfy.domain.services import ActorService


async def init_browser(
    use_system_chrome: bool,
    chrome_profile: str,
    cdp_url: str | None,
) -> AsyncIterator[BrowserUseAdapter]:
    adapter = await BrowserUseAdapter.create(
        cdp_url=cdp_url,
        use_system_chrome=use_system_chrome,
        chrome_profile=chrome_profile,
    )
    yield adapter
    await adapter.close()


class Container(containers.DeclarativeContainer):
    config = providers.Singleton(Settings)

    # Adapters
    # TODO: container.py는 현재 미사용. server.py가 직접 wiring.
    # LangChainLLMAdapter는 BaseChatModel 인스턴스를 받으므로 DI 컨테이너에서
    # 직접 생성하려면 chat_model provider가 필요함.
    llm = providers.Singleton(
        LangChainLLMAdapter,
        use_vision=config.provided.llm.use_vision,
    )

    browser = providers.Resource(
        init_browser,
        use_system_chrome=config.provided.browser.use_system_chrome,
        chrome_profile=config.provided.browser.chrome_profile,
        cdp_url=config.provided.browser.cdp_url,
    )

    scenario_cache = providers.Singleton(JsonFileCacheAdapter)

    # Services
    actor_service = providers.Factory(
        ActorService,
        browser=browser,
        llm=llm,
    )
