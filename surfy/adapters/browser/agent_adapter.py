import asyncio
import logging
from pathlib import Path

from browser_use import Agent, BrowserSession
from browser_use.agent.service import AgentHistoryList
from browser_use.llm.base import BaseChatModel

from surfy.domain.models.messages import StepProgressMessageData
from surfy.domain.models.route import RouteMap, RouteStep
from surfy.domain.ports.scout import ScoutPort

logger = logging.getLogger(__name__)
PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"


def _load_scout_prompt() -> str:
    """Scout용 .prompty 파일에서 system 본문만 추출한다."""
    prompty_path = PROMPTS_DIR / "scout.prompty"
    content = prompty_path.read_text(encoding="utf-8")

    parts = content.split("---")
    if len(parts) >= 3:
        template = "---".join(parts[2:]).strip()
        if template.startswith("system:"):
            template = template[7:].strip()
        return template
    return content


class BrowserUseAgentAdapter(ScoutPort):
    """browser-use Agent를 감싸는 ScoutPort 구현체."""

    def __init__(self, session: BrowserSession, llm: BaseChatModel) -> None:
        self._session = session
        self._llm = llm
        self._scout_prompt = _load_scout_prompt()
        self.step_progress_queue: asyncio.Queue[StepProgressMessageData] = asyncio.Queue()

    async def explore(self, task: str, max_steps: int = 20) -> RouteMap:
        while not self.step_progress_queue.empty():
            self.step_progress_queue.get_nowait()

        agent = Agent(
            task=task,
            llm=self._llm,
            browser_session=self._session,
            extend_system_message=self._scout_prompt,
            enable_planning=False,
            use_thinking=False,
            use_vision=False,
            flash_mode=True,
            loop_detection_enabled=True,
            max_actions_per_step=1,
        )

        async def _on_new_step(_browser_state, agent_output, step_number: int) -> None:
            action_type: str | None = None
            actions = getattr(agent_output, "action", None)
            if isinstance(actions, list) and actions:
                first_action = actions[0]
                if hasattr(first_action, "model_dump"):
                    dumped = first_action.model_dump(exclude_none=True)
                    if isinstance(dumped, dict) and dumped:
                        action_type = next(iter(dumped.keys()))

            await self.step_progress_queue.put(
                StepProgressMessageData(
                    node="scout",
                    step_number=step_number,
                    description=getattr(agent_output, "next_goal", None) or "",
                    action_type=action_type,
                )
            )

        register_new_step_callback = getattr(agent, "register_new_step_callback", None)
        if callable(register_new_step_callback):
            register_new_step_callback(_on_new_step)

        logger.info("Scout Agent 탐색 시작: %s (max_steps=%d)", task[:50], max_steps)
        history = await agent.run(max_steps=max_steps)
        logger.info(
            "Scout Agent 탐색 완료: %d URLs 방문, final_result=%s",
            len(history.urls()),
            (history.final_result() or "")[:100],
        )
        return _history_to_route_map(history)


_LOGIN_PATH_PATTERNS = ("/login", "/signin", "/sign-in", "/auth", "/sso", "/cas/login", "/oauth")


def _is_login_wall(urls: list[str | None]) -> bool:
    if not urls:
        return False
    last_url = (urls[-1] or "").lower()
    from urllib.parse import urlparse

    path = urlparse(last_url).path
    return any(pattern in path for pattern in _LOGIN_PATH_PATTERNS)


def _history_to_route_map(history: AgentHistoryList) -> RouteMap:
    urls = history.urls()
    actions = history.action_names()
    scout_completed = history.is_successful() is True

    login_wall = _is_login_wall(urls)
    if scout_completed and login_wall:
        logger.info("Scout reported success but landed on login page — overriding scout_completed to False")
        scout_completed = False

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

    summary = history.final_result() or "Scout completed"
    if login_wall:
        summary += " [로그인 필요 — 인증 후 재시도 필요]"

    return RouteMap(
        steps=steps,
        final_url=(urls[-1] or "") if urls else "",
        scout_summary=summary,
        scout_completed=scout_completed,
    )
