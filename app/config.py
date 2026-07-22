from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    github_token: str = ""
    github_org: str = ""
    database_url: str = "sqlite:///./pipeline_optimizer.db"
    port: int = 8100
    host: str = "0.0.0.0"
    anthropic_api_key: str = ""
    agent_model: str = "claude-sonnet-5"
    collect_repos: str = ""  # comma-separated list of owner/repo, or empty for all org repos
    cache_duration_hours: int = 1

    @property
    def repo_list(self) -> list[str]:
        if not self.collect_repos:
            return []
        return [r.strip() for r in self.collect_repos.split(",") if r.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
