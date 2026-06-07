"""AgentProbe configuration."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # LLM Providers
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # Models
    default_model: str = "claude-sonnet-4-6"
    cheap_model: str = "gpt-4o-mini"

    # Database
    database_url: str = (
        "postgresql+asyncpg://agentprobe:agentprobe@localhost:5432/agentprobe"
    )

    # ChromaDB
    chroma_host: str = "localhost"
    chroma_port: int = 8100

    # AgentProbe Settings
    max_concurrent_tests: int = 10
    token_budget: int = 100_000
    default_timeout_seconds: int = 60
    log_level: str = "INFO"

    # Cost tracking (USD per 1M tokens)
    cost_per_1m_input: dict[str, float] = Field(
        default_factory=lambda: {
            "claude-sonnet-4-6": 3.0,
            "claude-sonnet-4-20250514": 3.0,
            "claude-haiku-4-5-20251001": 0.80,
            "gpt-4o-mini": 0.15,
            "gpt-4o": 2.50,
        }
    )
    cost_per_1m_output: dict[str, float] = Field(
        default_factory=lambda: {
            "claude-sonnet-4-6": 15.0,
            "claude-sonnet-4-20250514": 15.0,
            "claude-haiku-4-5-20251001": 4.0,
            "gpt-4o-mini": 0.60,
            "gpt-4o": 10.0,
        }
    )

    model_config = {"env_prefix": "AGENTPROBE_", "env_file": ".env", "extra": "ignore"}

    def estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        input_cost = self.cost_per_1m_input.get(model, 3.0) * input_tokens / 1_000_000
        output_cost = (
            self.cost_per_1m_output.get(model, 15.0) * output_tokens / 1_000_000
        )
        return round(input_cost + output_cost, 6)


@lru_cache
def get_settings() -> Settings:
    return Settings()
