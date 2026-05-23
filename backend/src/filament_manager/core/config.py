from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./filament_manager.db"
    mqtt_keepalive_seconds: int = 30
    prometheus_enabled: bool = False
    prometheus_bearer_token: str | None = None
    raw_mqtt_hot_retention_hours: int = 24
    raw_mqtt_archive_enabled: bool = True

    model_config = SettingsConfigDict(
        env_prefix="FILAMENT_MANAGER_",
        env_file=".env",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
