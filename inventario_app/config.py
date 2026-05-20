import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
STORAGE_ROOT = Path(os.environ.get("STORAGE_ROOT", BASE_DIR / "instance" / "storage"))
UPLOAD_DIR = STORAGE_ROOT / "uploads"
PDF_DIR = STORAGE_ROOT / "pdfs"
DB_PATH = BASE_DIR / "inventario.db"

APP_ENV = os.environ.get("APP_ENV", os.environ.get("FLASK_ENV", "development")).lower()
IS_PRODUCTION = APP_ENV in {"production", "prod"}


def normalize_database_url(database_url: str | None) -> str:
    if not database_url:
        return f"sqlite:///{DB_PATH}"
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql://", 1)
    return database_url


def get_runtime_secret_key() -> str:
    secret_key = os.environ.get("SECRET_KEY")
    if secret_key:
        return secret_key
    if IS_PRODUCTION:
        raise RuntimeError(
            "Configura la variable de entorno SECRET_KEY antes de iniciar en produccion."
        )
    return "dev-secret-local-only"


class Config:
    SECRET_KEY = get_runtime_secret_key()
    SQLALCHEMY_DATABASE_URI = normalize_database_url(os.environ.get("DATABASE_URL"))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    APP_BASE_URL = os.environ.get("APP_BASE_URL")
    STORAGE_BACKEND = os.environ.get("STORAGE_BACKEND", "local").lower()
    STORAGE_ROOT = str(STORAGE_ROOT)
    UPLOAD_FOLDER = str(UPLOAD_DIR)
    PDF_FOLDER = str(PDF_DIR)
    AWS_REGION = os.environ.get("AWS_REGION")
    AWS_SES_FROM_EMAIL = os.environ.get("AWS_SES_FROM_EMAIL")
    AWS_SES_FROM_NAME = os.environ.get("AWS_SES_FROM_NAME", "Intoryx")
    S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")
    S3_UPLOAD_PREFIX = os.environ.get("S3_UPLOAD_PREFIX", "uploads")
    S3_PDF_PREFIX = os.environ.get("S3_PDF_PREFIX", "pdfs")
    S3_SIGNED_URL_EXPIRES = int(os.environ.get("S3_SIGNED_URL_EXPIRES", 300))
    PASSWORD_RESET_TOKEN_TTL_SECONDS = int(
        os.environ.get("PASSWORD_RESET_TOKEN_TTL_SECONDS", 300)
    )
    DASHBOARD_PER_PAGE = int(os.environ.get("DASHBOARD_PER_PAGE", 12))
    PUBLIC_SECTIONS_PER_PAGE = int(os.environ.get("PUBLIC_SECTIONS_PER_PAGE", 10))
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 32 * 1024 * 1024))
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    PDF_QUEUE_NAME = os.environ.get("PDF_QUEUE_NAME", "pdfs")
    PDF_JOB_TIMEOUT_SECONDS = int(os.environ.get("PDF_JOB_TIMEOUT_SECONDS", 900))
    PDF_STALE_AFTER_SECONDS = int(os.environ.get("PDF_STALE_AFTER_SECONDS", 300))
    PDF_QUEUE_SYNC = os.environ.get("PDF_QUEUE_SYNC", "0") in {"1", "true", "TRUE"}
    PDF_IMAGE_MAX_WIDTH = int(os.environ.get("PDF_IMAGE_MAX_WIDTH", 900))
    PDF_IMAGE_MAX_HEIGHT = int(os.environ.get("PDF_IMAGE_MAX_HEIGHT", 650))
    PDF_IMAGE_JPEG_QUALITY = int(os.environ.get("PDF_IMAGE_JPEG_QUALITY", 65))
    UPLOAD_IMAGE_MAX_WIDTH = int(os.environ.get("UPLOAD_IMAGE_MAX_WIDTH", 1600))
    UPLOAD_IMAGE_MAX_HEIGHT = int(os.environ.get("UPLOAD_IMAGE_MAX_HEIGHT", 1200))
    UPLOAD_IMAGE_JPEG_QUALITY = int(os.environ.get("UPLOAD_IMAGE_JPEG_QUALITY", 80))
    VIDEO_MAX_UPLOAD_BYTES = int(os.environ.get("VIDEO_MAX_UPLOAD_BYTES", 500 * 1024 * 1024))
    VIDEO_UPLOAD_EXPIRES_SECONDS = int(os.environ.get("VIDEO_UPLOAD_EXPIRES_SECONDS", 900))
    VIDEO_QUEUE_NAME = os.environ.get("VIDEO_QUEUE_NAME", "videos")
    VIDEO_QUEUE_SYNC = os.environ.get("VIDEO_QUEUE_SYNC", "0") in {"1", "true", "TRUE"}
    VIDEO_PROCESSING_TIMEOUT_SECONDS = int(
        os.environ.get("VIDEO_PROCESSING_TIMEOUT_SECONDS", 1800)
    )
    VIDEO_OUTPUT_MAX_WIDTH = int(os.environ.get("VIDEO_OUTPUT_MAX_WIDTH", 1280))
    VIDEO_OUTPUT_MAX_HEIGHT = int(os.environ.get("VIDEO_OUTPUT_MAX_HEIGHT", 720))
    VIDEO_OUTPUT_CRF = int(os.environ.get("VIDEO_OUTPUT_CRF", 28))
    VIDEO_OUTPUT_PRESET = os.environ.get("VIDEO_OUTPUT_PRESET", "veryfast")
    VIDEO_OUTPUT_AUDIO_BITRATE = os.environ.get("VIDEO_OUTPUT_AUDIO_BITRATE", "96k")
    VIDEO_ORIGINAL_PREFIX = os.environ.get(
        "VIDEO_ORIGINAL_PREFIX", "videos/originals"
    )
    VIDEO_PROCESSED_PREFIX = os.environ.get(
        "VIDEO_PROCESSED_PREFIX", "videos/processed"
    )
