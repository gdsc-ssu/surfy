from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LLM_")

    model_name: str = "claude-sonnet-4-5-20250929"
    use_vision: bool = False


class BrowserSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BROWSER_")

    cdp_url: str = "http://localhost:9222"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: str

    llm: LLMSettings = LLMSettings()
    browser: BrowserSettings = BrowserSettings()
