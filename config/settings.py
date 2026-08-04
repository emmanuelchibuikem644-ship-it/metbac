"""
Django settings for the Kindred dating platform API.

This is now a decoupled REST API backend (Django + DRF + SimpleJWT) that
serves a separate Next.js frontend. Phase 1 scope: auth (signup / login /
email verification / password reset) and the subscription / premium-plan
system (Stripe placeholder integration), all exposed as JSON endpoints
under /api/.
"""

from pathlib import Path
from datetime import timedelta
import environ
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="dev-only-insecure-secret-key")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
SITE_URL = env("SITE_URL", default="http://localhost:8000")

# Render.com sets RENDER=true on all services
RENDER = env.bool("RENDER", default=False)
if RENDER:
    # Render provides the hostname via RENDER_EXTERNAL_HOSTNAME
    ALLOWED_HOSTS.append(env("RENDER_EXTERNAL_HOSTNAME", default=""))
    ALLOWED_HOSTS = [h for h in ALLOWED_HOSTS if h]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # third-party
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    # local apps
    "apps.accounts",
    "apps.core",
    "apps.subscriptions",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
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
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# --- Database -----------------------------------------------------------

# Render provides DATABASE_URL (e.g. postgres://user:pass@host:5432/dbname)
DATABASE_URL = env("DATABASE_URL", default="")

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    DB_ENGINE = env("DB_ENGINE", default="sqlite3")

    if DB_ENGINE == "postgresql":
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": env("DB_NAME", default="metlink"),
                "USER": env("DB_USER", default="metlink"),
                "PASSWORD": env("DB_PASSWORD", default="metlink"),
                "HOST": env("DB_HOST", default="localhost"),
                "PORT": env("DB_PORT", default="5432"),
            }
        }
    else:
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": BASE_DIR / env("DB_NAME", default="db.sqlite3"),
            }
        }

# --- Redis / Channels / Cache --------------------------------------------

REDIS_URL = env("REDIS_URL", default="redis://redis:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    }
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [REDIS_URL]},
    }
}

# --- Auth -----------------------------------------------------------------

AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "/django-admin/login/"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

PASSWORD_RESET_TIMEOUT = 60 * 60 * 2  # 2 hours
EMAIL_VERIFICATION_TIMEOUT_DAYS = 3

# --- Email ------------------------------------------------------------
# Use the console backend by default so signup/password-reset never hang on
# an unconfigured SMTP connection. SMTP is only used when real credentials
# (host + password) are provided — a short timeout prevents blocking.

EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=10)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Metlink <hello@metlink.example>")

# Only use the real SMTP backend when a host and password are actually set;
# otherwise fall back to the console backend (instant, never blocks).
if EMAIL_HOST and EMAIL_HOST_PASSWORD and EMAIL_HOST_PASSWORD != "placeholder-email-api-key":
    EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# --- Payments (placeholders — swap for real keys before launch) -----------

STRIPE_PUBLIC_KEY = env("STRIPE_PUBLIC_KEY", default="pk_test_placeholder")
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", default="sk_test_placeholder")
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", default="whsec_placeholder")
STRIPE_PRICE_PREMIUM_MONTHLY = env("STRIPE_PRICE_PREMIUM_MONTHLY", default="price_placeholder_monthly")
STRIPE_PRICE_PREMIUM_YEARLY = env("STRIPE_PRICE_PREMIUM_YEARLY", default="price_placeholder_yearly")

PAYPAL_CLIENT_ID = env("PAYPAL_CLIENT_ID", default="placeholder-paypal-client-id")
PAYPAL_CLIENT_SECRET = env("PAYPAL_CLIENT_SECRET", default="placeholder-paypal-client-secret")
PAYPAL_MODE = env("PAYPAL_MODE", default="sandbox")

# --- CORS (Next.js frontend runs on a different origin) -------------------

FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:3000")
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[FRONTEND_URL])
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[FRONTEND_URL])

# --- REST framework / JWT auth --------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=14),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# --- Seeded admin account ---------------------------------------------
# Used by the `create_default_admin` management command to guarantee there's
# always a way into /django-admin/ in dev/demo environments. CHANGE THESE
# (or override via env vars) before deploying anywhere real.

DEFAULT_ADMIN_EMAIL = env("DEFAULT_ADMIN_EMAIL", default="admin@metlink.example")
DEFAULT_ADMIN_PASSWORD = env("DEFAULT_ADMIN_PASSWORD", default="MetlinkAdmin!2026")

# --- i18n ------------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# --- Static / media -----------------------------------------------------

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Security -------------------------------------------------------------
# Sensible, mostly-safe-for-local-dev defaults. Tighten SESSION_COOKIE_SECURE,
# CSRF_COOKIE_SECURE and the HSTS settings to True once served over HTTPS.

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=not DEBUG)
SECURE_HSTS_SECONDS = 0 if DEBUG else 60 * 60 * 24 * 30
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG

# Render terminates TLS at the load balancer; trust the X-Forwarded-Proto header
if RENDER:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# --- Logging ----------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}