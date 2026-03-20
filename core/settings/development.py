from .base import *

# ------------------------------------------------------------------------------
# CORE
# ------------------------------------------------------------------------------
DEBUG = True
ENVIRONMENT = "development"

ALLOWED_HOSTS = ALLOWED_HOSTS or ["127.0.0.1", "localhost", "192.168.43.13","[::1]"]

# ------------------------------------------------------------------------------
# DATABASE
# ------------------------------------------------------------------------------
# Uses DATABASE_URL from .env if provided.
# Fallback is already handled in base.py with sqlite.
# Example local Postgres:
# DATABASE_URL=postgres://postgres:postgres@localhost:5432/gocart_db

# ------------------------------------------------------------------------------
# CORS / CSRF
# ------------------------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = True
CSRF_TRUSTED_ORIGINS = CSRF_TRUSTED_ORIGINS or [
    "http://127.0.0.1:3000",
    "http://localhost:3000",
    "http://192.168.43.13:8000",
]

# ------------------------------------------------------------------------------
# DEVELOPMENT HELPERS
# ------------------------------------------------------------------------------
# EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Optional relaxed settings for local development
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False