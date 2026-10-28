import os
import secrets
from datetime import timedelta
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# Production-safe default. Set DJANGO_DEBUG=true only for local development.
DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() in ("true", "1", "yes")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = secrets.token_urlsafe(50)
    else:
        raise ImproperlyConfigured(
            "Set DJANGO_SECRET_KEY in the environment before running with DJANGO_DEBUG=false."
        )

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get(
        "DJANGO_ALLOWED_HOSTS",
        "127.0.0.1,localhost,t-shoe-backend-1.onrender.com,.onrender.com",
    ).split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "store",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if DATABASE_URL:
    if not DATABASE_URL.startswith(("postgres://", "postgresql://t_shoe_db_user:9837FuIGsaDJ4OKrhca0j321bhB7UeCr@dpg-dbg6pd6gekts73b9p4sg-a/t_shoe_db")):
        raise ImproperlyConfigured(
            "DATABASE_URL must be a PostgreSQL connection URL, not an API/HTTP URL. "
            "Use the Internal Database URL from your Render PostgreSQL database."
        )
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            ssl_require=not DEBUG,
        )
    }
else:
    # Convenient for local development. Configure Render PostgreSQL in production.
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = []
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Dhaka"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOWED_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.environ.get(
        "CORS_ALLOWED_ORIGINS",
        "https://t-shoes.vercel.app,https://t-shoe-bd.vercel.app,http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]
CORS_ALLOW_CREDENTIALS = True

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.AllowAny",),
    "DEFAULT_THROTTLE_CLASSES": ("rest_framework.throttling.ScopedRateThrottle",),
    "DEFAULT_THROTTLE_RATES": {"auth": "10/min"},
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

BACKEND_PUBLIC_URL = os.environ.get(
    "BACKEND_PUBLIC_URL", "https://t-shoe-backend-1.onrender.com"
).rstrip("/")
FRONTEND_URL = os.environ.get(
    "FRONTEND_URL", "https://t-shoes.vercel.app"
).rstrip("/")

BKASH_BASE_URL = os.environ.get(
    "BKASH_BASE_URL",
    "https://tokenized.sandbox.bka.sh/v2/tokenized-checkout",
)
BKASH_APP_KEY = os.environ.get("BKASH_APP_KEY", "")
BKASH_APP_SECRET = os.environ.get("BKASH_APP_SECRET", "")
BKASH_USERNAME = os.environ.get("BKASH_USERNAME", "")
BKASH_PASSWORD = os.environ.get("BKASH_PASSWORD", "")

NAGAD_API_BASE_URL = os.environ.get(
    "NAGAD_API_BASE_URL",
    "https://sandboxapi.nagad.com.bd/remote-payment-gateway-1.0",
).rstrip("/")
NAGAD_MERCHANT_ID = os.environ.get("NAGAD_MERCHANT_ID", "")
NAGAD_MERCHANT_NUMBER = os.environ.get("NAGAD_MERCHANT_NUMBER", "")
NAGAD_MERCHANT_PRIVATE_KEY_PATH = os.environ.get(
    "NAGAD_MERCHANT_PRIVATE_KEY_PATH", ""
)
NAGAD_PG_PUBLIC_KEY_PATH = os.environ.get("NAGAD_PG_PUBLIC_KEY_PATH", "")
NAGAD_CLIENT_IP = os.environ.get("NAGAD_CLIENT_IP", "127.0.0.1")
