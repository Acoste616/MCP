from typing import Any, List, Optional, Union

from pydantic import AnyHttpUrl, EmailStr, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=True, extra="ignore"
    )

    PROJECT_NAME: str = "My Server API"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development" # Added: e.g., development, production, testing
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 # 1 day

    # Rate Limiting
    DEFAULT_RATE_LIMIT: str = "100/15minutes" # Added

    # CORS Origins
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []
    CLIENT_URL: Optional[AnyHttpUrl] = None # Added: Optional client URL

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return [i.strip() for i in v if isinstance(i, str) and i.strip()]
        return [] # Return empty list if input is not valid

    # Database
    POSTGRES_SERVER: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    DATABASE_URI: Optional[PostgresDsn] = None

    @field_validator("DATABASE_URI", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Optional[str], values) -> Any:
        if isinstance(v, str):
            return v
        
        data = values.data 
        required_keys = ["POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_SERVER", "POSTGRES_DB"]
        if not all(data.get(key) for key in required_keys):
            return None

        return PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=data.get("POSTGRES_USER"),
            password=data.get("POSTGRES_PASSWORD"),
            host=data.get("POSTGRES_SERVER"),
            path=f"/{data.get('POSTGRES_DB') or ''}",
        )

    # File Uploads
    UPLOAD_DIRECTORY: str = "./static/uploads" # Default upload directory
    MAX_FILE_SIZE_MB: int = 5 # Max file size in Megabytes
    ALLOWED_IMAGE_TYPES: List[str] = ["image/jpeg", "image/png", "image/webp"]

    @field_validator("ALLOWED_IMAGE_TYPES", mode="before")
    @classmethod
    def assemble_allowed_image_types(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        elif isinstance(v, list):
            return [str(item).strip() for item in v if str(item).strip()]
        return []

    # Redis Cache (optional, uncomment and configure if used)
    # REDIS_HOST: str = "localhost"
    # REDIS_PORT: int = 6379
    # REDIS_DB: int = 0
    # REDIS_PASSWORD: Optional[str] = None
    # CACHE_EXPIRE_SECONDS: int = 60 # Default cache expiration

    # Email settings (example, can be uncommented and used)
    # SMTP_HOST: Optional[str] = None
    # SMTP_PORT: Optional[int] = 587
    # SMTP_USER: Optional[str] = None
    # SMTP_PASSWORD: Optional[str] = None
    # SMTP_TLS: bool = True
    # EMAILS_FROM_EMAIL: Optional[EmailStr] = None
    # EMAILS_FROM_NAME: Optional[str] = PROJECT_NAME
    # EMAIL_TEST_USER: EmailStr = "test@example.com" # type: ignore


settings = Settings() 