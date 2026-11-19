"""Application settings loaded from environment variables (.env)."""

from functools import lru_cache
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Core ---
    app_name: str = "ShopMate AI"
    environment: str = "development"  # development | staging | production
    debug: bool = True

    # --- URLs ---
    frontend_url: str = "http://localhost:3000"
    backend_url: str = "http://localhost:8000"

    # --- Database ---
    # PostgreSQL in production; SQLite is accepted for local tests.
    database_url: str = "sqlite:///./shopmate.db"

    @field_validator("database_url", mode="before")
    @classmethod
    def _psycopg3_scheme(cls, value: object) -> object:
        """Accept plain `postgresql://` URLs from managed hosts (Render, Neon…).

        Only the psycopg3 driver is installed, so SQLAlchemy needs the
        explicit `postgresql+psycopg://` scheme — the bare form would make it
        import the absent psycopg2 module and crash at startup (this also
        covers `alembic upgrade head`, which reads the same setting).
        """
        if isinstance(value, str):
            for legacy in ("postgres://", "postgresql://"):
                if value.startswith(legacy):
                    return "postgresql+psycopg://" + value[len(legacy):]
        return value

    # --- Redis (optional; graceful in-memory fallback when unavailable) ---
    redis_url: str = "redis://localhost:6379/0"

    # --- Security ---
    secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days
    bcrypt_rounds: int = 12
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # --- Google OAuth ---
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"

    # --- LLM providers ---
    hf_token: str = ""
    hf_model_id: str = "mistralai/Mistral-7B-Instruct-v0.3"
    hf_api_url: str = "https://api-inference.huggingface.co/models"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    llm_timeout_seconds: float = 60.0
    # "auto" picks Ollama -> HuggingFace -> rule-based fallback
    llm_provider: str = "auto"

    # --- Product data providers ---
    # Authorized merchant / affiliate API (optional). When unset, the
    # clearly-labelled sample dataset provider is used for discovery.
    merchant_api_url: str = ""
    merchant_api_key: str = ""
    provider_timeout_seconds: float = 10.0
    flipkart_affiliate_id: str = ""
    flipkart_affiliate_token: str = ""
    amazon_creators_client_id: str = ""
    amazon_creators_client_secret: str = ""
    amazon_creators_credential_version: str = "3.2"
    amazon_associate_tag: str = ""
    amazon_marketplace: str = "www.amazon.in"

    # --- Email (optional; SMTP creds absent => console/development mode) ---
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_use_tls: bool = True
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = "no-reply@shopmate.ai"

    # --- Recommendation engine weights (overridable per category) ---
    weight_spec: float = 0.35
    weight_budget: float = 0.25
    weight_preference: float = 0.20
    weight_review: float = 0.20

    # --- Rate limiting (requests / window per IP) ---
    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def google_oauth_configured(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def flipkart_affiliate_configured(self) -> bool:
        return bool(self.flipkart_affiliate_id and self.flipkart_affiliate_token)

    @property
    def amazon_creators_configured(self) -> bool:
        return bool(
            self.amazon_creators_client_id
            and self.amazon_creators_client_secret
            and self.amazon_associate_tag
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
