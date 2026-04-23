from .base import *

DEBUG = False
ENVIRONMENT = "production"

if not ALLOWED_HOSTS:
    raise ValueError("ALLOWED_HOSTS must be set in production")
if "*" in ALLOWED_HOSTS:
    raise ValueError("ALLOWED_HOSTS cannot contain '*' in production")

DATABASE_URL = os.getenv("DATABASE_URL", "")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL must be set in production")
if DATABASE_URL.startswith("sqlite"):
    raise ValueError("SQLite DATABASE_URL is not allowed in production")
if not CORS_ALLOWED_ORIGINS:
    raise ValueError("CORS_ALLOWED_ORIGINS must be set in production")

ALLOW_INSECURE_PRODUCTION_ORIGINS = env_bool("ALLOW_INSECURE_PRODUCTION_ORIGINS", False)
for origin in CORS_ALLOWED_ORIGINS + CSRF_TRUSTED_ORIGINS:
    if not origin.startswith("https://") and not ALLOW_INSECURE_PRODUCTION_ORIGINS:
        raise ValueError(
            "Production CORS/CSRF origins must use https:// unless "
            "ALLOW_INSECURE_PRODUCTION_ORIGINS=True is explicitly set"
        )

DATABASES = {
    "default": dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=600,
        conn_health_checks=True,
        ssl_require=os.getenv("DB_SSL_REQUIRE", "True").lower() in ("true", "1", "yes"),
    )
}

SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", 31536000))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

CORS_ALLOW_ALL_ORIGINS = False
if not CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS

STATIC_ROOT = BASE_DIR / "staticfiles"
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", EMAIL_BACKEND)
