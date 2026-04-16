from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    jawafdehi_api_base_url: str = Field(
        default="https://portal.jawafdehi.org",
        alias="JAWAFDEHI_API_BASE_URL",
    )
    jawafdehi_api_token: str = Field(alias="JAWAFDEHI_API_TOKEN")
    nes_api_base_url: str = Field(
        default="https://nes.jawafdehi.org",
        alias="NES_API_BASE_URL",
    )
    news_article_limit: int = Field(default=6, alias="NEWS_ARTICLE_LIMIT")
    llm_model: str = Field(default="openai/claude-sonnet-4-6", alias="LLM_MODEL")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_base_url: str | None = Field(default=None, alias="OPENAI_BASE_URL")
    brave_search_api_key: str | None = Field(default=None, alias="BRAVE_SEARCH_API_KEY")
    agentspan_server_url: str | None = Field(default=None, alias="AGENTSPAN_SERVER_URL")
    agentspan_auth_key: str | None = Field(default=None, alias="AGENTSPAN_AUTH_KEY")
    agentspan_auth_secret: str | None = Field(
        default=None, alias="AGENTSPAN_AUTH_SECRET"
    )
    global_store_root: Path = Field(
        default_factory=lambda: Path.cwd() / "global_store",
        alias="GLOBAL_STORE_ROOT",
    )
    runs_root: Path = Field(
        default_factory=lambda: Path.cwd() / "runs",
        alias="RUNS_ROOT",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
