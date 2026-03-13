from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LLM_", env_file=".env", extra="ignore")

    provider: str = "gemini"
    model_name: str = "gemini-2.0-flash"
    use_vision: bool = False


class BrowserSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BROWSER_", env_file=".env", extra="ignore")

    use_system_chrome: bool = True
    chrome_profile: str = "Default"
    cdp_url: str | None = None


class ScoutSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SCOUT_", env_file=".env", extra="ignore")

    model_name: str = "gemini-3-flash-preview"
    use_vision: bool = False
    flash_mode: bool = True
    max_steps: int = 5


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: str | None = Field(default=None, repr=False)  # 로그/repr에서 숨김
    google_api_key: str | None = None

    llm: LLMSettings = Field(default_factory=LLMSettings)
    browser: BrowserSettings = Field(default_factory=BrowserSettings)
    scout: ScoutSettings = Field(default_factory=ScoutSettings)
