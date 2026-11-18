from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# monorepo root ki .env; Docker me path chhota hota hai isliye .parent chain (kabhi IndexError nahi)
ROOT_ENV = Path(__file__).resolve().parent.parent.parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(ROOT_ENV, ".env"), env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AI Link Analysis"
    environment: str = "development"
    log_level: str = "INFO"

    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.1-flash-lite"
    gemini_fallback_model: str = "gemini-3.5-flash-lite"
    gemini_thinking_level: str = "low"
    gemini_max_output_tokens: int = 8192
    llm_timeout_seconds: float = 40.0
    llm_max_concurrency: int = 4
    # Google Search grounding se competitors real web data par based hote hain
    enable_search_grounding: bool = False

    # USD per 1M tokens, cost estimate ke liye (pricing badle to .env me update karo)
    price_input_per_million: float = 0.25
    price_output_per_million: float = 1.50

    fetch_timeout_seconds: float = 12.0
    fetch_max_bytes: int = 2_000_000
    fetch_max_redirects: int = 5
    fetch_extra_pages: int = 3
    content_char_budget: int = 24_000

    cache_ttl_seconds: int = 86_400
    cache_max_entries: int = 256

    rate_limit_requests: int = 10
    rate_limit_window_seconds: int = 60

    cors_origins: list[str] = Field(default_factory=list)
    static_dir: Path = Path(__file__).resolve().parent.parent / "static"


@lru_cache
def get_settings() -> Settings:
    return Settings()
