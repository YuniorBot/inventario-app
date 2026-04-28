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
