import warnings

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_SECRET = "changeme-in-production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://auth_user:auth_password@localhost:5432/auth_db"
    JWT_SECRET_KEY: str = _DEFAULT_SECRET
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15

    @model_validator(mode="after")
    def warn_default_secret(self) -> "Settings":
        if self.JWT_SECRET_KEY == _DEFAULT_SECRET:
            warnings.warn(
                "JWT_SECRET_KEY is using the insecure default value. Set JWT_SECRET_KEY in your environment.",
                stacklevel=2,
            )
        return self


settings = Settings()
