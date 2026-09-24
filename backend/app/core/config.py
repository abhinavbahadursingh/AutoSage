"""Application settings loaded from the environment (.env).

Phase 1: environment-based configuration only. All values have sane
development defaults so the service boots without a .env file; production
overrides everything via real environment variables.
"""
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "AutoSage API"
    APP_ENV: str = "development"
    DEBUG: bool = True
    APP_SECRET_KEY: str = "insecure-default-change-me"
    LOG_LEVEL: str = "INFO"

    # Database (PostgreSQL + pgvector, async driver)
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/autosage"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_POOL_TIMEOUT: int = 30
    # SQL statement echo (very verbose). Off by default; enable via SQL_ECHO=True.
    SQL_ECHO: bool = False

    # Redis (broker / cache — wired in later phases)
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- Phase 5: Celery + Redis (async experiment execution) ---
    # Empty broker/backend URLs fall back to REDIS_URL (see properties below).
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""
    CELERY_EXPERIMENT_QUEUE: str = "experiments"
    CELERY_TASK_ALWAYS_EAGER: bool = False  # True in tests: run inline, no broker
    CELERY_TASK_TIME_LIMIT: int = 1800  # hard kill (s) per experiment task
    CELERY_TASK_SOFT_TIME_LIMIT: int = 1500  # SoftTimeLimitExceeded (s) warning
    CELERY_RETRY_BACKOFF_BASE: int = 60  # countdown = base * 2**attempt (s)
    CELERY_RETRY_BACKOFF_MAX: int = 3600  # countdown cap (s)

    # --- Phase 6: LangGraph workflow ---
    WORKFLOW_MAX_ATTEMPTS: int = 2  # verification retry passes inside one run

    # --- Phase 8: LLM providers (OpenRouter / Groq / HuggingFace) ---
    # API keys are read from the environment (.env is gitignored).
    OPENROUTER_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    HUGGINGFACE_API_TOKEN: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    HUGGINGFACE_BASE_URL: str = "https://router.huggingface.co/v1"
    # Central model configuration (model ids may be "provider/model").
    DEFAULT_FAST_MODEL: str = "groq/llama-3.1-8b-instant"
    DEFAULT_REASONING_MODEL: str = "openrouter/meta-llama/llama-3.3-70b-instruct"
    DEFAULT_MODEL: str = ""  # optional hard override for all tiers
    # Ordered provider fallback (only providers with an API key participate).
    LLM_FALLBACK_ORDER: List[str] = ["groq", "openrouter", "huggingface"]
    LLM_TIMEOUT_SECONDS: float = 30.0
    # Max seconds to wait on a 429 before falling through to the next provider.
    LLM_RATE_LIMIT_WAIT_SECONDS: float = 1.0
    # When true, agents degrade to deterministic heuristics if no provider
    # is configured or every provider fails (keeps local/dev workflows alive).
    LLM_ALLOW_HEURISTIC_FALLBACK: bool = True

    # --- Phase 13: Embedding providers ---
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENROUTER_EMBEDDING_MODEL: str = "openai/text-embedding-3-small"
    GROQ_EMBEDDING_MODEL: str = "text-embedding-3-small"
    HUGGINGFACE_EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # MLflow (Phase 11)
    MLFLOW_TRACKING_URI: str = "http://localhost:5000"
    MLFLOW_EXPERIMENT_NAME: str = "autosage_default"
    MLFLOW_ARTIFACT_ROOT: str = "./mlflow_artifacts"

    # Sandbox (later phases)
    DOCKER_SANDBOX_IMAGE: str = "autosage-runner:latest"
    SANDBOX_TIMEOUT_SECONDS: int = 300

    # --- Phase 2: Authentication (Supabase Auth / Better Auth as identity provider) ---
    # Supabase Auth issues RS256 JWTs via JWKS. Better Auth issues HS256 JWTs
    # with a shared secret. The backend supports both: RS256 via JWKS or HS256
    # via shared secret (BETTER_AUTH_SECRET). Frontend must use UUID user IDs
    # (`advanced.database.generateId: "uuid"`) so `sub` matches users.id.
    SUPABASE_URL: str = ""  # e.g., "https://xyz.supabase.co"
    SUPABASE_ANON_KEY: str = ""  # public anon key for client
    SUPABASE_SERVICE_ROLE_KEY: str = ""  # service role key for admin operations
    BETTER_AUTH_SECRET: str = ""  # Shared secret for Better Auth (HS256)
    BETTER_AUTH_URL: str = "http://localhost:3000"
    JWT_ALGORITHM: str = "HS256"  # Default, can be overridden by env
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # dev-issued tokens only
    AUTH_DEV_TOKEN_ENABLED: bool = True  # POST /auth/dev-token; disable in prod

    # Supabase Storage (Phase 14)
    SUPABASE_STORAGE_BUCKET: str = "autosage-files"

    # Storage paths
    UPLOAD_DIR: str = "./data/uploads"
    ARTIFACT_DIR: str = "./data/artifacts"

    # --- Phase 16: Observability (OpenTelemetry) ---
    OTEL_EXPORTER_OTLP_ENDPOINT: str = ""  # e.g. "http://localhost:4318/v1/traces"

    # --- Phase 20A: Security Hardening ---
    # Rate limiting (requests per minute/hour)
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000
    RATE_LIMIT_BURST: int = 10
    # Request body size limit (bytes)
    MAX_REQUEST_BODY_SIZE: int = 10 * 1024 * 1024  # 10 MB
    # File upload limits
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024  # 50 MB
    ALLOWED_UPLOAD_TYPES: list[str] = ["text/csv", "application/csv", "text/plain"]
    # Production secret enforcement
    ENFORCE_PRODUCTION_SECRETS: bool = True
    # Sandbox security
    SANDBOX_PIDS_LIMIT: int = 100
    SANDBOX_READONLY_ROOTFS: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def _split_cors(cls, value: object) -> object:
        # Allow comma-separated string: BACKEND_CORS_ORIGINS="http://a,http://b"
        # Also handle JSON array format from env
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("["):
                import json
                return json.loads(value)
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def sync_database_url(self) -> str:
        """Sync (psycopg) URL for Alembic, derived from the async URL."""
        return self.DATABASE_URL.replace("+asyncpg", "")

    @property
    def jwt_secret(self) -> str:
        """Signing secret for JWT verification.

        Supports both Supabase (RS256 via JWKS - secret not used for verify)
        and Better Auth (HS256 with shared secret). Falls back to app secret.
        """
        return self.BETTER_AUTH_SECRET or self.APP_SECRET_KEY

    @property
    def uses_jwks(self) -> bool:
        """Whether to use JWKS for token verification (Supabase Auth)."""
        return self.JWT_ALGORITHM.startswith("RS") or self.JWT_ALGORITHM.startswith("ES")

    @property
    def celery_broker_url(self) -> str:
        """Celery broker URL (falls back to REDIS_URL when unset)."""
        return self.CELERY_BROKER_URL or self.REDIS_URL

    @property
    def celery_result_backend(self) -> str:
        """Celery result backend URL (falls back to REDIS_URL when unset)."""
        return self.CELERY_RESULT_BACKEND or self.REDIS_URL


settings = Settings()
