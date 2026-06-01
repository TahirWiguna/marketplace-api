from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://marketplace_user:marketplace_password@localhost:5433/marketplace_db"
    AUTH_SERVICE_URL: str = "http://auth-service:8000"


settings = Settings()
