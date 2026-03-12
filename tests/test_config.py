"""Settings 및 ScoutSettings 단위 테스트."""

import os
from unittest import mock

from surfy.config import ScoutSettings, Settings


def test_scout_settings_defaults():
    """ScoutSettings 기본값 검증."""
    settings = ScoutSettings()
    assert settings.model_name == "gemini-3-flash-preview"
    assert settings.use_vision is False
    assert settings.flash_mode is True
    assert settings.max_steps == 5


def test_settings_includes_scout():
    """Settings 클래스에 ScoutSettings가 포함되어 있는지 검증."""
    # anthropic_api_key는 필수 필드이므로 환경 변수 모킹
    with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
        settings = Settings()
        assert isinstance(settings.scout, ScoutSettings)
        assert settings.scout.model_name == "gemini-3-flash-preview"


def test_settings_google_api_key_optional():
    """google_api_key가 선택 사항이며 기본값이 None인지 검증."""
    with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
        settings = Settings()
        assert settings.google_api_key is None

    # 환경 변수로 설정 가능한지 확인
    with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key", "GOOGLE_API_KEY": "google-test-key"}):
        settings = Settings()
        assert settings.google_api_key == "google-test-key"
