import base64
from unittest.mock import MagicMock

import pytest

from surfy.adapters.llm.langchain_adapter import (
    MAX_DOM_TEXT_LENGTH,
    MAX_IMAGE_BYTES,
    LangChainLLMAdapter,
)
from surfy.domain.models import PageState, Task


def _adapter_without_init() -> LangChainLLMAdapter:
    return object.__new__(LangChainLLMAdapter)


@pytest.mark.asyncio
async def test_decide_action_truncates_dom_text() -> None:
    # Arrange
    adapter = _adapter_without_init()
    adapter._actor_template = "DOM: ${dom_text}"
    adapter._use_vision = False
    adapter._handoff_on_auth = True
    adapter._format_history = MagicMock(return_value="")

    # Mock _actor_model.ainvoke
    mock_model = MagicMock()
    
    async def mock_ainvoke(*_):
        return MagicMock()
        
    mock_model.ainvoke = MagicMock(side_effect=mock_ainvoke)
    adapter._model = MagicMock()
    adapter._model.with_structured_output = MagicMock(return_value=mock_model)

    task = Task(description="test")
    long_dom = "a" * (MAX_DOM_TEXT_LENGTH + 100)
    page_state = PageState(url="http://test.com", title="test", dom_text=long_dom)

    # Act
    await adapter.decide_action(task, page_state, [])

    # Assert
    call_args = mock_model.ainvoke.call_args
    messages = call_args[0][0]
    prompt = messages[0].content

    expected_dom = long_dom[:MAX_DOM_TEXT_LENGTH] + "\n... (truncated)"
    assert f"DOM: {expected_dom}" == prompt


@pytest.mark.asyncio
async def test_decide_action_includes_auth_instruction_when_enabled() -> None:
    adapter = _adapter_without_init()
    adapter._actor_template = "TASK: ${task_description} AUTH: ${auth_instruction}"
    adapter._use_vision = False
    adapter._handoff_on_auth = True
    adapter._format_history = MagicMock(return_value="")

    mock_model = MagicMock()

    async def mock_ainvoke(*_):
        return MagicMock()

    mock_model.ainvoke = MagicMock(side_effect=mock_ainvoke)
    adapter._model = MagicMock()
    adapter._model.with_structured_output = MagicMock(return_value=mock_model)

    task = Task(description="test")
    page_state = PageState(url="http://test.com", title="test", dom_text="dom")

    await adapter.decide_action(task, page_state, [])

    prompt = mock_model.ainvoke.call_args[0][0][0].content
    assert "AUTH_REQUIRED" in prompt


@pytest.mark.asyncio
async def test_decide_action_omits_auth_instruction_when_disabled() -> None:
    adapter = _adapter_without_init()
    adapter._actor_template = "TASK: ${task_description} AUTH: ${auth_instruction}"
    adapter._use_vision = False
    adapter._handoff_on_auth = False
    adapter._format_history = MagicMock(return_value="")

    mock_model = MagicMock()

    async def mock_ainvoke(*_):
        return MagicMock()

    mock_model.ainvoke = MagicMock(side_effect=mock_ainvoke)
    adapter._model = MagicMock()
    adapter._model.with_structured_output = MagicMock(return_value=mock_model)

    task = Task(description="test")
    page_state = PageState(url="http://test.com", title="test", dom_text="dom")

    await adapter.decide_action(task, page_state, [])

    prompt = mock_model.ainvoke.call_args[0][0][0].content
    assert "AUTH_REQUIRED" not in prompt


def test_build_human_message_without_screenshot_returns_text_only() -> None:
    adapter = _adapter_without_init()
    message = adapter._build_human_message("hello", None)

    assert message.content == "hello"


def test_build_human_message_with_invalid_base64_returns_text_only() -> None:
    adapter = _adapter_without_init()
    message = adapter._build_human_message("hello", "not-base64!!")

    assert message.content == "hello"


def test_build_human_message_with_oversized_image_returns_text_only() -> None:
    adapter = _adapter_without_init()
    oversized = base64.b64encode(b"a" * (MAX_IMAGE_BYTES + 1)).decode("ascii")
    message = adapter._build_human_message("hello", oversized)

    assert message.content == "hello"


def test_build_human_message_with_small_image_includes_image_block() -> None:
    adapter = _adapter_without_init()
    small = base64.b64encode(b"png-bytes").decode("ascii")
    message = adapter._build_human_message("hello", small)

    content = message.content
    assert isinstance(content, list)
    assert any(isinstance(item, dict) and item.get("type") == "text" for item in content)
    assert any(isinstance(item, dict) and item.get("type") == "image_url" for item in content)
