from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "DOCREADER Backend"
    API_VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ALLOWED_ORIGINS: list[str] = ["*"]
    DATABASE_URL: str = "sqlite:///./app.db"
    UPLOAD_DIR: str = "uploads"
    STRUCTURED_OUTPUT_DIR: str = "structured_outputs"
    MAX_UPLOAD_SIZE_BYTES: int = 20 * 1024 * 1024
    BATCH_UPLOAD_MAX_WORKERS: int = 2
    TESSERACT_CMD: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


settings = Settings()
