import base64

from surfy.adapters.llm.anthropic_adapter import ANTHROPIC_MAX_IMAGE_BYTES, AnthropicAdapter


def _adapter_without_init() -> AnthropicAdapter:
    return object.__new__(AnthropicAdapter)


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
    oversized = base64.b64encode(b"a" * (ANTHROPIC_MAX_IMAGE_BYTES + 1)).decode("ascii")
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
