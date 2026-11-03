"""Per-client settings. Each client deployment gets its own env file (see deploy/clients/)."""

from functools import lru_cache
from typing import Annotated

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Read from MODKIT_* environment variables or a local .env file.

    Model strings are passed to LiteLLM as-is. To route everything through a LiteLLM proxy,
    set LiteLLM's own USE_LITELLM_PROXY / LITELLM_PROXY_API_BASE / LITELLM_PROXY_API_KEY and
    use the proxy's model names here.
    """

    model_config = SettingsConfigDict(env_prefix="MODKIT_", env_file=".env", extra="ignore")

    default_model: str = "anthropic/claude-sonnet-5-5"
    # Shown in the canvas model dropdowns (comma-separated in env); any other model can still be typed in.
    model_choices: Annotated[list[str], NoDecode] = [
        "anthropic/claude-sonnet-5-5",
        "anthropic/claude-opus-5-5",
        "anthropic/claude-haiku-5-5",
        "openai/gpt-5",
    ]

    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str | None = None
    smtp_password: SecretStr | None = None
    smtp_starttls: bool = False
    email_from: str = "noreply@example.com"

    @field_validator("model_choices", mode="before")
    @classmethod
    def _split_csv(cls, value):
        if isinstance(value, str):
            return [m.strip() for m in value.split(",") if m.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
