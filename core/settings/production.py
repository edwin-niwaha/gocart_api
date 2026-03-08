from .base import *

# ------------------------------------------------------------------------------
# CORE
# ------------------------------------------------------------------------------
DEBUG = False
ENVIRONMENT = "production"

if not ALLOWED_HOSTS:
    raise ValueError("ALLOWED_HOSTS must be set in production")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL must be set in production")

if not CORS_ALLOWED_ORIGINS:
    raise ValueError("CORS_ALLOWED_ORIGINS must be set in production")

# ------------------------------------------------------------------------------
# DATABASE
# ------------------------------------------------------------------------------
DATABASES = {
    "default": dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=600,
        conn_health_checks=True,
        ssl_require=os.getenv("DB_SSL_REQUIRE", "True").lower() in ("true", "1", "yes"),
    )
}

# ------------------------------------------------------------------------------
# SECURITY
# ------------------------------------------------------------------------------
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", 31536000))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

SECURE_REFERRER_POLICY = "same-origin"
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# ------------------------------------------------------------------------------
# CORS / CSRF
# ------------------------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = False

if not CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS

# ------------------------------------------------------------------------------
# STATIC FILES
# ------------------------------------------------------------------------------
STATIC_ROOT = BASE_DIR / "staticfiles"

# ------------------------------------------------------------------------------
# EMAIL
# ------------------------------------------------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"