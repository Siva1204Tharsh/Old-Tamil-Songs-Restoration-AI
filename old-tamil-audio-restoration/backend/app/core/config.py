"""
Application configuration and settings.
"""
import os
from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings


BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Old Tamil Songs Restoration AI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Server
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    WORKERS: int = 1

    # Storage
    STORAGE_DIR: Path = BASE_DIR / "storage"
    UPLOADS_DIR: Path = BASE_DIR / "storage" / "uploads"
    PROCESSED_DIR: Path = BASE_DIR / "storage" / "processed"
    TEMP_DIR: Path = BASE_DIR / "storage" / "temporary"

    # File limits
    MAX_FILE_SIZE_MB: int = 200
    MAX_DURATION_SECONDS: float = 1800.0  # 30 minutes
    ALLOWED_EXTENSIONS: list = [".wav", ".mp3", ".flac", ".m4a", ".ogg", ".aiff", ".aif"]
    ALLOWED_MIME_TYPES: list = [
        "audio/wav", "audio/x-wav", "audio/mpeg", "audio/mp3",
        "audio/flac", "audio/x-flac", "audio/mp4", "audio/x-m4a",
        "audio/ogg", "audio/aiff", "audio/x-aiff",
    ]

    # Job management
    MAX_CONCURRENT_JOBS: int = 2
    JOB_RETENTION_HOURS: int = 24
    JOB_TIMEOUT_SECONDS: int = 3600

    # Audio processing
    DEFAULT_SAMPLE_RATE: int = 44100
    CHUNK_DURATION_SECONDS: float = 30.0
    CHUNK_OVERLAP_SECONDS: float = 1.0

    # Loudness
    DEFAULT_TARGET_LUFS: float = -16.0
    DEFAULT_TRUE_PEAK_DBTP: float = -1.0

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/restoration.log"

    # CORS
    CORS_ORIGINS: list = ["http://localhost:8501", "http://127.0.0.1:8501"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "arbitrary_types_allowed": True}

    def model_post_init(self, __context):
        # Ensure storage directories exist
        for d in [self.UPLOADS_DIR, self.PROCESSED_DIR, self.TEMP_DIR]:
            d.mkdir(parents=True, exist_ok=True)

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024


settings = Settings()
