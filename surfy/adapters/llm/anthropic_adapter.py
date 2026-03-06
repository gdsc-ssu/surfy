from pathlib import Path

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage

from surfy.domain.models import ActorOutput, PageState, StepResult, Task
from surfy.domain.ports import LLMPort

PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"


def _load_prompty(name: str) -> str:
    """Load prompt template from .prompty file, extracting content after the YAML frontmatter."""
    prompty_path = PROMPTS_DIR / f"{name}.prompty"
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
        self._model = ChatAnthropic(model_name=model_name)
        self._structured_model = self._model.with_structured_output(ActorOutput)
        self._prompt_template = _load_prompty("actor")

    async def decide_action(
        self,
        task: Task,
        page_state: PageState,
        history: list[tuple[ActorOutput, StepResult]],
    ) -> ActorOutput:
        # prompty uses {{var}} syntax, convert to Python format
        prompt = (
            self._prompt_template.replace("{{task_description}}", task.description)
            .replace("{{url}}", page_state.url)
            .replace("{{title}}", page_state.title)
            .replace("{{dom_text}}", page_state.dom_text)
            .replace("{{formatted_history}}", self._format_history(history))
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
        return result  # type: ignore[return-value]

    def _format_history(self, history: list[tuple[ActorOutput, StepResult]]) -> str:
        if not history:
            return "(No actions taken yet)"

        if len(history) <= 5:
            return "\n".join(
                [
                    f"Step {i + 1}: {h[0].action_type.value}({h[0].target_id or h[0].value or ''}) → {h[1].message}"
                    for i, h in enumerate(history)
                ]
            )

        # 5개 초과: 앞부분 압축 + 최근 5개 상세
        old_actions = [h[0].action_type.value for h in history[:-5]]
        old_summary = f"[Earlier {len(old_actions)} steps: {' → '.join(old_actions)}]"

        recent = history[-5:]
        recent_text = "\n".join(
            [
                f"Step {len(history) - 5 + i + 1}: "
                f"{h[0].action_type.value}({h[0].target_id or h[0].value or ''}) → {h[1].message}"
                for i, h in enumerate(recent)
            ]
        )
        return f"{old_summary}\n\n{recent_text}"
