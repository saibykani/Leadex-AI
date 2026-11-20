from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../../.env"), extra="ignore")

    app_env: str = "local"  # local | staging | production | test
    app_name: str = "Leadex AI"
    # Runtime connection: must be a NON-superuser role (leadex_app) so PostgreSQL row-level security applies.
    database_url: str = "postgresql+psycopg://leadex_app:leadex_app@localhost:5433/leadex"
    # Schema owner used only by Alembic. Defaults to database_url (e.g. SQLite in tests).
    migration_database_url: str | None = None
    app_db_password: str = "leadex_app"  # password set on the leadex_app role by migration 0004

    @property
    def effective_migration_url(self) -> str:
        return self.migration_database_url or self.database_url
    redis_url: str | None = None
    jwt_secret: str = "change-me-local-only"
    # Dedicated Fernet key (urlsafe base64, 32 bytes) for secrets at rest. Required in production; outside
    # production the key falls back to an HKDF derivation of JWT_SECRET.
    encryption_key: str | None = None
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 14
    cors_origins: str = "http://localhost:3000"  # comma separated
    auth_rate_limit_per_minute: int = 20
    # "lax" when web and API share a site (app.x.com + api.x.com); "none" when they are on different sites
    # (e.g. two *.vercel.app projects). "none" always sends the cookie Secure-only.
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"

    @field_validator("redis_url", "migration_database_url", "encryption_key", mode="before")
    @classmethod
    def empty_is_none(cls, v):
        return v or None

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def outbound_simulated(self) -> bool:
        """Real outreach is impossible outside production."""
        return not self.is_production

    def validate_for_runtime(self) -> None:
        if self.is_production and (self.jwt_secret.startswith("change-me") or len(self.jwt_secret) < 32):
            raise RuntimeError("JWT_SECRET must be a strong secret (>=32 chars) in production")
        if self.is_production and self.app_db_password == "leadex_app":
            raise RuntimeError("APP_DB_PASSWORD must be set in production")
        if self.is_production and not self.encryption_key:
            raise RuntimeError(
                "ENCRYPTION_KEY must be set in production (generate: python -c \"from cryptography.fernet "
                "import Fernet;print(Fernet.generate_key().decode())\")")
        if self.encryption_key:
            from cryptography.fernet import Fernet

            try:
                Fernet(self.encryption_key.encode())
            except (ValueError, TypeError) as e:
                raise RuntimeError("ENCRYPTION_KEY must be a urlsafe-base64 encoded 32-byte Fernet key") from e


@lru_cache
def get_settings() -> Settings:
    return Settings()
