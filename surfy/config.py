from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LLM_", env_file=".env", extra="ignore")

    model_name: str = "claude-sonnet-4-5-20250929"
    use_vision: bool = False


class BrowserSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BROWSER_", env_file=".env", extra="ignore")

    use_system_chrome: bool = True
    chrome_profile: str = "Default"
    cdp_url: str | None = None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: str = Field(..., repr=False)  # 로그/repr에서 숨김

    llm: LLMSettings = Field(default_factory=LLMSettings)
    browser: BrowserSettings = Field(default_factory=BrowserSettings)
