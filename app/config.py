from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://juke:password@localhost:5432/juke_marketing"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # IMAP
    IMAP_HOST: str = "imap.gmail.com"
    IMAP_PORT: int = 993
    IMAP_USERNAME: str = "automation@jukemediakc.com"
    IMAP_PASSWORD: str = ""
    IMAP_MAILBOX: str = "INBOX"
    IMAP_POLL_INTERVAL_SECONDS: int = 120

    # Dropbox
    DROPBOX_ACCESS_TOKEN: str = ""
    DROPBOX_REFRESH_TOKEN: str = ""
    DROPBOX_APP_KEY: str = ""
    DROPBOX_APP_SECRET: str = ""
    DROPBOX_ROOT_FOLDER: str = "/Juke Media KC"

    # Anthropic / Claude
    ANTHROPIC_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-sonnet-4-6"
    CLAUDE_VISION_BATCH_SIZE: int = 5

    # App
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    TEMP_DIR: str = "/tmp/juke_projects"
    API_KEY: str = ""

    # Kling AI (video generation)
    KLING_ACCESS_KEY: str = ""
    KLING_SECRET_KEY: str = ""
    KLING_API_BASE_URL: str = "https://api.klingai.com"
    VIDEO_SCORE_FLOOR: float = 0.65
    VIDEO_MAX_PHOTOS: int = 10
    VIDEO_CLIP_DURATION: int = 5


settings = Settings()
