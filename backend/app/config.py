from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "TLCA Command Center"
    microsoft_tenant_id: str | None = None
    microsoft_client_id: str | None = None
    microsoft_graph_scopes: str = "User.Read,Tasks.ReadWrite,Mail.Read,Contacts.ReadWrite"
    microsoft_authority_host: str = "https://login.microsoftonline.com"
    outlook_business_categories: str = "Klant/prospect,Leverancier,Partner"
    database_url: str | None = None
    database_backend: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def graph_configured(self) -> bool:
        return bool(self.microsoft_tenant_id and self.microsoft_client_id)

    @property
    def graph_scope_list(self) -> list[str]:
        return [scope.strip() for scope in self.microsoft_graph_scopes.split(",") if scope.strip()]

    @property
    def outlook_business_category_list(self) -> list[str]:
        return [category.strip() for category in self.outlook_business_categories.split(",") if category.strip()]

    @property
    def resolved_database_backend(self) -> str:
        configured_backend = (self.database_backend or "").strip().casefold()
        configured_url = (self.database_url or "").strip()
        if configured_backend and configured_backend not in {"sqlite", "postgresql"}:
            raise ValueError("DATABASE_BACKEND must be sqlite or postgresql")
        if not configured_url:
            if configured_backend == "postgresql":
                raise ValueError("DATABASE_URL is required when DATABASE_BACKEND is postgresql")
            return configured_backend or "sqlite"
        if configured_url.startswith(("postgresql://", "postgresql+psycopg://")):
            url_backend = "postgresql"
        elif configured_url.startswith("sqlite:///"):
            url_backend = "sqlite"
        else:
            raise ValueError("DATABASE_URL must use sqlite:/// or postgresql+psycopg://")
        if configured_backend and configured_backend != url_backend:
            raise ValueError("DATABASE_BACKEND does not match DATABASE_URL")
        return url_backend


@lru_cache
def get_settings() -> Settings:
    return Settings()
