from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "DOCREADER Backend"
    API_VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ALLOWED_ORIGINS: list[str] = ["*"]
    DATABASE_URL: str = "sqlite:///./app.db"
    UPLOAD_DIR: str = "uploads"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


settings = Settings()
