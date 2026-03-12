import asyncio
import base64
import binascii
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from string import Template

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage

from surfy.domain.models import ActorOutput, EvalResult, HistoryEntry, PageState, Task
from surfy.domain.models.criteria import SuccessCriteria
from surfy.domain.models.plan import Plan
from surfy.domain.ports import LLMPort

PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"
RECENT_HISTORY_COUNT = 10
MAX_DOM_TEXT_LENGTH = 5000  # 토큰 제한을 위한 DOM 텍스트 최대 길이
ANTHROPIC_MAX_IMAGE_BYTES = 5 * 1024 * 1024

logger = logging.getLogger(__name__)


def _load_prompty(name: str) -> str:
    """Load prompt template from .prompty file, extracting content after the YAML frontmatter.

    Raises:
        FileNotFoundError: 프롬프트 파일이 존재하지 않을 경우
    """
    prompty_path = PROMPTS_DIR / f"{name}.prompty"
    if not prompty_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompty_path}")

    content = prompty_path.read_text()

    # Split by '---' and take the part after the second '---'
    parts = content.split("---")
    if len(parts) >= 3:
        # parts[0] is empty (before first ---), parts[1] is YAML, parts[2] is template
        template = "---".join(parts[2:]).strip()
        # Remove 'system:' prefix if present
        if template.startswith("system:"):
            template = template[7:].strip()
        return template
    return content


class AnthropicAdapter(LLMPort):
    """Anthropic Claude를 사용하는 LLM 어댑터.

    Planner, Actor, Evaluator 세 가지 역할을 수행한다.
    """

    def __init__(self, *, use_vision: bool, model_name: str):
        self._use_vision = use_vision
        self._model = ChatAnthropic(model_name=model_name)  # type: ignore[call-arg]

        self._actor_template = _load_prompty("actor")
        self._planner_template = _load_prompty("planner")
        self._evaluator_template = _load_prompty("evaluator")

    @property
    def model(self) -> ChatAnthropic:
        return self._model

    @property
    def _actor_model(self):
        return self._model.with_structured_output(ActorOutput)

    @property
    def _planner_model(self):
        return self._model.with_structured_output(Plan)

    @property
    def _evaluator_model(self):
        return self._model.with_structured_output(EvalResult)

    async def decide_action(
        self,
        task: Task,
        page_state: PageState,
        history: list[HistoryEntry],
    ) -> ActorOutput:
        """Actor용: 현재 페이지 상태와 히스토리를 기반으로 다음 액션 결정."""
        template_str = self._actor_template.replace("{{", "${").replace("}}", "}")
        template = Template(template_str)
        prompt = template.safe_substitute(
            task_description=task.description,
            target_url=task.target_url or "(없음)",
            url=page_state.url,
            title=page_state.title,
            dom_text=page_state.dom_text,
            formatted_history=self._format_history(history),
        )

        messages = [self._build_human_message(prompt, page_state.screenshot if self._use_vision else None)]

        result = await self._actor_model.ainvoke(messages)
        if isinstance(result, dict):
            return ActorOutput(**result)
        return result  # type: ignore[return-value]

    async def plan(self, command: str, progress: str, route_observations: str = "", research_result: str = "") -> Plan:
        """Planner용: 사용자 명령과 진행 상황을 기반으로 Plan 생성."""
        template_str = self._planner_template.replace("{{", "${").replace("}}", "}")
        template = Template(template_str)
        prompt = template.safe_substitute(
            command=command,
            progress=progress or "(없음)",
            route_observations=route_observations or "(Scout 데이터 없음)",
            research_result=research_result or "(Research 데이터 없음)",
        )

        messages = [HumanMessage(content=prompt)]

        # Python 3.11 호환: 동기 invoke를 스레드풀에서 실행
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor() as pool:
            result = await loop.run_in_executor(pool, lambda: self._planner_model.invoke(messages))

        if isinstance(result, dict):
            return Plan(**result)
        return result  # type: ignore[return-value]

    async def evaluate(self, criteria: SuccessCriteria, page_state: PageState) -> EvalResult:
        """Evaluator용: 태스크 성공 여부 판정."""
        template_str = self._evaluator_template.replace("{{", "${").replace("}}", "}")
        template = Template(template_str)

        # DOM 텍스트 길이 제한
        dom_text = page_state.dom_text
        if len(dom_text) > MAX_DOM_TEXT_LENGTH:
            dom_text = dom_text[:MAX_DOM_TEXT_LENGTH] + "\n... (truncated)"

        prompt = template.safe_substitute(
            description=criteria.description,
            url=page_state.url,
            dom_text=dom_text,
        )

        messages = [self._build_human_message(prompt, page_state.screenshot if self._use_vision else None)]

        # Python 3.11 호환: 동기 invoke를 스레드풀에서 실행
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor() as pool:
            result = await loop.run_in_executor(pool, lambda: self._evaluator_model.invoke(messages))

        if isinstance(result, dict):
            return EvalResult(**result)
        return result  # type: ignore[return-value]

    def _format_history(self, history: list[HistoryEntry]) -> str:
        """액션 히스토리를 문자열로 포맷."""
        if not history:
            return "(No actions taken yet)"

        def _format_target(entry: HistoryEntry) -> str:
            """target_id가 0일 경우도 올바르게 처리."""
            target_id = entry.action.target_id
            if target_id is not None:
                return str(target_id)
            return entry.action.value or ""

        if len(history) <= RECENT_HISTORY_COUNT:
            return "\n".join(
                f"Step {i + 1}: {entry.action.action_type.value}({_format_target(entry)}) → {entry.result.message}"
                for i, entry in enumerate(history)
            )

        # RECENT_HISTORY_COUNT개 초과: 앞부분 압축 + 최근 N개 상세
        old_entries = history[:-RECENT_HISTORY_COUNT]
        old_actions = [entry.action.action_type.value for entry in old_entries]
        old_summary = f"[Earlier {len(old_actions)} steps: {' → '.join(old_actions)}]"

        recent = history[-RECENT_HISTORY_COUNT:]
        start_step = len(history) - RECENT_HISTORY_COUNT + 1
        recent_text = "\n".join(
            f"Step {start_step + i}: {entry.action.action_type.value}({_format_target(entry)}) → {entry.result.message}"
            for i, entry in enumerate(recent)
        )
        return f"{old_summary}\n\n{recent_text}"

    def _build_human_message(self, prompt: str, screenshot_b64: str | None) -> HumanMessage:
        if not screenshot_b64:
            return HumanMessage(content=prompt)

        try:
            image_bytes = base64.b64decode(screenshot_b64, validate=True)
        except (binascii.Error, ValueError):
            logger.warning("Invalid base64 screenshot. Sending text-only prompt.")
            return HumanMessage(content=prompt)

        image_size = len(image_bytes)
        if image_size > ANTHROPIC_MAX_IMAGE_BYTES:
            logger.warning(
                "Screenshot too large for Anthropic (%d bytes > %d). Sending text-only prompt.",
                image_size,
                ANTHROPIC_MAX_IMAGE_BYTES,
            )
            return HumanMessage(content=prompt)

        return HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"},
                },
            ]
        )
