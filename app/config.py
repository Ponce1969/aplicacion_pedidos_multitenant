from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuración centralizada de la aplicación.

    Lee variables de entorno y las valida con Pydantic.
    No usa Any — todos los campos tienen tipos concretos.
    """

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://barraca_user:password@db:5432/barraca",
        alias="DATABASE_URL",
    )
    DATABASE_POOL_SIZE: int = Field(default=20, alias="DATABASE_POOL_SIZE")
    DATABASE_MAX_OVERFLOW: int = Field(default=10, alias="DATABASE_MAX_OVERFLOW")

    # App
    APP_NAME: str = "Barraca Pedidos"
    APP_ENV: str = "development"
    DEBUG: bool = False

    # Security
    SECRET_KEY: str = Field(default="dev-secret-key-min-32-chars-change!", min_length=32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, alias="REFRESH_TOKEN_EXPIRE_DAYS")

    # Argon2
    ARGON2_TIME_COST: int = 2
    ARGON2_MEMORY_COST: int = 102400  # 100 MB
    ARGON2_PARALLELISM: int = 8
    ARGON2_HASH_LEN: int = 32
    ARGON2_SALT_LEN: int = 16

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore",
    }


settings = Settings()
