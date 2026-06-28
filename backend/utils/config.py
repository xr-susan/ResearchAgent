"""
Configuration management for ResearchAgent.

Loads settings from environment variables with sensible defaults.
Supports .env files via python-dotenv.
"""

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # --- LLM Provider ---
    llm_provider: str = Field(default="openai", description="LLM provider: openai or anthropic")
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    openai_model: str = Field(default="gpt-4o", description="OpenAI model name")
    openai_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    openai_max_tokens: int = Field(default=4096, gt=0)
    anthropic_api_key: Optional[str] = Field(default=None, description="Anthropic API key")
    anthropic_model: str = Field(default="claude-sonnet-4-20250514", description="Anthropic model name")

    # --- Search ---
    search_engine: str = Field(default="duckduckgo", description="Search engine: duckduckgo or serpapi")
    serpapi_key: Optional[str] = Field(default=None)

    # --- Application ---
    app_env: str = Field(default="development")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    database_url: str = Field(default="sqlite:///./data/research_agent.db")
    log_level: str = Field(default="INFO")
    max_concurrent_tasks: int = Field(default=5)
    cache_ttl: int = Field(default=3600, description="Cache TTL in seconds")

    # --- File Settings ---
    max_upload_size_mb: int = Field(default=50)
    upload_dir: str = Field(default="./data/uploads")
    reports_dir: str = Field(default="./data/reports")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "case_sensitive": False}

    @property
    def base_dir(self) -> Path:
        """Get the base project directory."""
        return Path(__file__).parent.parent.parent

    @property
    def data_dir(self) -> Path:
        """Get the data directory, creating it if needed."""
        path = self.base_dir / "data"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def db_path(self) -> Path:
        """Get the SQLite database path."""
        return self.data_dir / "research_agent.db"

    @property
    def uploads_path(self) -> Path:
        """Get the uploads directory, creating it if needed."""
        path = Path(self.upload_dir)
        if not path.is_absolute():
            path = self.base_dir / path
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def reports_path(self) -> Path:
        """Get the reports directory, creating it if needed."""
        path = Path(self.reports_dir)
        if not path.is_absolute():
            path = self.base_dir / path
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.app_env == "development"

    @property
    def default_model(self) -> str:
        """Return the model for the selected provider."""
        return self.anthropic_model if self.llm_provider.lower() == "anthropic" else self.openai_model


# Global settings instance
settings = Settings()
