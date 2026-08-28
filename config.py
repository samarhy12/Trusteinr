import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


def _require_database_uri(database_url):
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL must be set in the environment or .env file to use your cPanel database. "
            "Local SQLite fallback is disabled."
        )

    if database_url.startswith("sqlite") and os.environ.get("USE_SQLITE", "0") != "1":
        raise RuntimeError(
            "SQLite is disabled unless USE_SQLITE=1 is set for local testing. "
            "Set DATABASE_URL to your cPanel MySQL/PostgreSQL connection string in production."
        )

    return database_url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    if not SECRET_KEY:
        raise RuntimeError("SECRET_KEY must be configured in the environment or .env file")

    SQLALCHEMY_DATABASE_URI = _require_database_uri(os.environ.get("DATABASE_URL"))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {}

    # Business rules
    MONTHLY_INTEREST_RATE = 0.10   # standard/default interest rate per month — staff can override per loan
    MINIMUM_CUSTOMER_AGE = 18      # customers (and guarantors) must be at least this old

    # File uploads (customer/guarantor passport pictures)
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads", "customers")
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg"}
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB max upload size

    # ---- Security ----
    PASSWORD_MIN_LENGTH = 8
    LOGIN_MAX_ATTEMPTS = 5             # failed attempts before an account is temporarily locked
    LOGIN_LOCKOUT_MINUTES = 15         # how long a lockout lasts

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Only set the cookie's Secure flag when actually serving over HTTPS (set FORCE_HTTPS=1 in production).
    SESSION_COOKIE_SECURE = os.environ.get("FORCE_HTTPS", "0") == "1"

    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)     # default session length
    REMEMBER_COOKIE_DURATION = timedelta(days=14)        # only used if "Remember me" is checked
    DEFAULT_PAGE_SIZE = 20
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
