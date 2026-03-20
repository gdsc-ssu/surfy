"""Settings 및 ScoutSettings 단위 테스트."""

import os
from unittest import mock

from surfy.config import LLMSettings, ScoutSettings, Settings


def test_scout_settings_defaults():
    """ScoutSettings 기본값 검증."""
    with mock.patch.dict(os.environ, {}, clear=True):
        settings = ScoutSettings(_env_file=None)
        assert settings.model_name == "gemini-3-flash-preview"
        assert settings.use_vision is False
        assert settings.flash_mode is True
        assert settings.max_steps == 15


def test_llm_settings_defaults():
    """LLMSettings 기본값 검증."""
    with mock.patch.dict(os.environ, {}, clear=True):
        settings = LLMSettings(_env_file=None)
        assert settings.provider == "gemini"
        assert settings.model_name == "gemini-2.0-flash"
        assert settings.use_vision is False


def test_settings_includes_scout():
    """Settings 클래스에 ScoutSettings가 포함되어 있는지 검증."""
    with mock.patch.dict(os.environ, {}, clear=True):
        settings = Settings(_env_file=None, scout=ScoutSettings(_env_file=None))
        assert isinstance(settings.scout, ScoutSettings)
        assert settings.scout.model_name == "gemini-3-flash-preview"


def test_settings_anthropic_api_key_optional():
    """anthropic_api_key가 선택 사항이며 기본값이 None인지 검증."""
    with mock.patch.dict(os.environ, {}, clear=True):
        settings = Settings(_env_file=None)
        assert settings.anthropic_api_key is None

    # 환경 변수로 설정 가능한지 확인
    with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=True):
        settings = Settings(_env_file=None)
        assert settings.anthropic_api_key == "test-key"


def test_settings_google_api_key_optional():
    """google_api_key가 선택 사항이며 기본값이 None인지 검증."""
    with mock.patch.dict(os.environ, {}, clear=True):
        settings = Settings(_env_file=None)
        assert settings.google_api_key is None

    with mock.patch.dict(os.environ, {"GOOGLE_API_KEY": "google-test-key"}, clear=True):
        settings = Settings(_env_file=None)
        assert settings.google_api_key == "google-test-key"


def test_settings_handoff_on_auth_defaults_true():
    with mock.patch.dict(os.environ, {}, clear=True):
        settings = Settings(_env_file=None)
        assert settings.handoff_on_auth is True


def test_settings_handoff_on_auth_env_override():
    with mock.patch.dict(os.environ, {"HANDOFF_ON_AUTH": "false"}, clear=True):
        settings = Settings(_env_file=None)
        assert settings.handoff_on_auth is False
