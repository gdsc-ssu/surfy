from pathlib import Path
from string import Template

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage

from surfy.domain.models import ActorOutput, HistoryEntry, PageState, Task
from surfy.domain.ports import LLMPort

PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"
RECENT_HISTORY_COUNT = 5


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
    def __init__(self, *, use_vision: bool, model_name: str):
        self._use_vision = use_vision
        self._model = ChatAnthropic(model_name=model_name)  # type: ignore[call-arg]
        self._structured_model = self._model.with_structured_output(ActorOutput)
        self._prompt_template = _load_prompty("actor")

    async def decide_action(
        self,
        task: Task,
        page_state: PageState,
        history: list[HistoryEntry],
    ) -> ActorOutput:
        # {{var}} 형식을 ${var} 형식으로 변환하여 Template 사용
        template_str = self._prompt_template.replace("{{", "${").replace("}}", "}")
        template = Template(template_str)
        prompt = template.safe_substitute(
            task_description=task.description,
            url=page_state.url,
            title=page_state.title,
            dom_text=page_state.dom_text,
            formatted_history=self._format_history(history),
        )

        if self._use_vision and page_state.screenshot:
            messages = [
                HumanMessage(
                    content=[
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{page_state.screenshot}"},
                        },
                    ]
                )
            ]
        else:
            messages = [HumanMessage(content=prompt)]

        result = await self._structured_model.ainvoke(messages)
        if isinstance(result, dict):
            return ActorOutput(**result)
        return result  # type: ignore[return-value]

    def _format_history(self, history: list[HistoryEntry]) -> str:
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
