import logging

from browser_use import Agent, BrowserSession
from browser_use.agent.service import AgentHistoryList
from browser_use.llm.base import BaseChatModel

from surfy.domain.models.route import RouteMap, RouteStep

logger = logging.getLogger(__name__)


class BrowserUseAgentAdapter:
    """browser-use Agent를 감싸는 어댑터.

    Scout 정찰용으로 사용. Actor에서는 사용하지 않는다.
    """

    def __init__(self, session: BrowserSession, llm: BaseChatModel) -> None:
        self._session = session
        self._llm = llm

    async def explore(self, task: str, max_steps: int = 20) -> AgentHistoryList:
        """browser-use Agent로 정찰 탐색을 수행한다.

        Args:
            task: 탐색할 작업 설명
            max_steps: 최대 탐색 스텝 수

        Returns:
            AgentHistoryList: 탐색 히스토리 (urls, actions, final_result 등)
        """
        agent = Agent(
            task=task,
            llm=self._llm,
            browser_session=self._session,
            enable_planning=True,
            use_thinking=True,
            loop_detection_enabled=True,
            max_actions_per_step=3,
        )

        logger.info("Scout Agent 탐색 시작: %s (max_steps=%d)", task[:50], max_steps)
        history = await agent.run(max_steps=max_steps)
        logger.info(
            "Scout Agent 탐색 완료: %d URLs 방문, final_result=%s",
            len(history.urls()),
            (history.final_result() or "")[:100],
        )
        return history


def history_to_route_map(history: AgentHistoryList) -> RouteMap:
    """AgentHistoryList를 RouteMap으로 변환한다."""
    urls = history.urls()
    actions = history.action_names()

    steps: list[RouteStep] = []
    for i, url in enumerate(urls):
        action = actions[i] if i < len(actions) else "unknown"
        steps.append(
            RouteStep(
                url=url or "",
                title="",
                action_taken=action,
                observed_elements=[],
                notes="",
            )
        )

    return RouteMap(
        steps=steps,
        final_url=(urls[-1] or "") if urls else "",
        scout_summary=history.final_result() or "Scout completed",
    )
