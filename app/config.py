from pydantic import Field, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuración centralizada de la aplicación.

    Lee variables de entorno y las valida con Pydantic.
    No usa Any — todos los campos tienen tipos concretos.
    """

    # Database
    DATABASE_URL: str = Field(
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

    # SMTP (Email)  # noqa: ERA001 — section header
    SMTP_HOST: str = Field(default="smtp.gmail.com", alias="SMTP_HOST")
    SMTP_PORT: int = Field(default=587, alias="SMTP_PORT")
    SMTP_USER: str = Field(default="", alias="SMTP_USER")
    SMTP_PASSWORD: str = Field(default="", alias="SMTP_PASSWORD")
    SMTP_FROM_EMAIL: str = Field(default="", alias="SMTP_FROM_EMAIL")
    SMTP_USE_TLS: bool = Field(default=True, alias="SMTP_USE_TLS")

    # Password Reset
    PASSWORD_RESET_EXPIRE_MINUTES: int = Field(default=30, alias="PASSWORD_RESET_EXPIRE_MINUTES")
    BASE_URL: str = Field(default="http://localhost:8000", alias="BASE_URL")

    # Email (Resend API)
    RESEND_API_KEY: str = Field(default="", alias="RESEND_API_KEY")
    RESEND_FROM_EMAIL: str = Field(default="onboarding@resend.dev", alias="RESEND_FROM_EMAIL")

    # Swagger protection
    SWAGGER_PASSWORD: str = Field(default="", alias="SWAGGER_PASSWORD")

    @model_validator(mode="after")
    def _check_prod_secrets(self) -> "Settings":
        # Defense-in-depth: nunca firmar JWT con la clave de desarrollo en prod.
        if self.APP_ENV == "production" and self.SECRET_KEY == "dev-secret-key-min-32-chars-change!":
            raise ValueError(
                "SECRET_KEY sigue siendo el default de desarrollo. "
                "Genera uno fuerte en el .env de produccion: openssl rand -hex 32"
            )
        return self

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore",
    }


settings = Settings()
