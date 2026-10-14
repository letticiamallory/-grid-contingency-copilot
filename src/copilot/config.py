from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://copilot:copilot@localhost:5432/copilot"
    migrations_dir: str = "migrations"
    openrouter_api_key: str = ""
    embedding_model: str = "openai/text-embedding-3-small"
    # No default model on purpose: the choice is the operator's (and A/B are fixed at evaluation).
    llm_model: str = ""
    llm_fallback_model: str = ""
