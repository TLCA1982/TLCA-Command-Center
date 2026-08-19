from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "TLCA Command Center"
    microsoft_tenant_id: str | None = None
    microsoft_client_id: str | None = None
    microsoft_graph_scopes: str = "User.Read,Tasks.ReadWrite,Mail.Read"
    microsoft_authority_host: str = "https://login.microsoftonline.com"

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
