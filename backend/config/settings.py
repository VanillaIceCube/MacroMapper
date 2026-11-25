import math
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

from apps.mcp.framework.config import oauth_settings

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY.strip():
    if not DEBUG:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY is required in production.")
    SECRET_KEY = "macromapper-local-development-key-change-before-production-2026"


def environment_list(name):
    return [value.strip() for value in os.getenv(name, "").split(",") if value.strip()]


ALLOWED_HOSTS = environment_list("DJANGO_ALLOWED_HOSTS")
if DEBUG:
    ALLOWED_HOSTS += ["localhost", "127.0.0.1", "macromapper.localhost"]
elif not ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS is required in production.")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = False
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

FRONTEND_BASE_URL = os.getenv(
    "DJANGO_FRONTEND_BASE_URL", "http://macromapper.localhost:3000"
).rstrip("/")


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "anymail",
    "apps.authentication",
    "apps.foods",
    "apps.estimates",
    "apps.meals",
    "apps.notifications",
]


MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
]


CORS_ALLOWED_ORIGINS = environment_list("DJANGO_CORS_ALLOWED_ORIGINS")
CSRF_TRUSTED_ORIGINS = environment_list("DJANGO_CSRF_TRUSTED_ORIGINS")
local_origins = [
    "http://localhost:3000",
    "http://macromapper.localhost:3000",
    "http://macromapper.localhost:3001",
    "https://macromapper.localhost",
    "https://macromapper.localhost:8443",
]

if DEBUG:
    CORS_ALLOWED_ORIGINS += local_origins
    CSRF_TRUSTED_ORIGINS += local_origins


REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
}


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
            ],
        },
    },
]


WSGI_APPLICATION = "config.wsgi.application"


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("DJANGO_SQLITE_PATH") or BASE_DIR / "db.sqlite3",
    }
}


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


AUTH_USER_MODEL = "authentication.User"


# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


STATIC_URL = "static/"

STATIC_ROOT = BASE_DIR / "staticfiles"


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Email
EMAIL_BACKEND = (
    os.getenv("DJANGO_EMAIL_BACKEND")
    or "django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = os.getenv("DJANGO_EMAIL_HOST") or "smtp.resend.com"
EMAIL_PORT = int(os.getenv("DJANGO_EMAIL_PORT") or "587")
EMAIL_USE_TLS = os.getenv("DJANGO_EMAIL_USE_TLS", "1") == "1"
EMAIL_HOST_USER = os.getenv("DJANGO_EMAIL_HOST_USER") or "resend"
EMAIL_HOST_PASSWORD = os.getenv("DJANGO_EMAIL_HOST_KEY", "")
EMAIL_TIMEOUT = int(os.getenv("DJANGO_EMAIL_TIMEOUT") or "10")
ANYMAIL = {
    "REQUESTS_TIMEOUT": EMAIL_TIMEOUT if 0 < EMAIL_TIMEOUT <= 30 else 10,
    "DEBUG_API_REQUESTS": False,
}
if isinstance(EMAIL_HOST_PASSWORD, str) and EMAIL_HOST_PASSWORD.strip():
    ANYMAIL["RESEND_API_KEY"] = EMAIL_HOST_PASSWORD
DEFAULT_FROM_EMAIL = (
    os.getenv("DJANGO_DEFAULT_FROM_EMAIL")
    or "MacroMapper <no-reply@macromapper.localhost>"
)

# GPT-assisted meal proposals. The OpenAI key is intentionally optional so
# catalog-first matches and the rest of the application remain available when
# model estimation is not configured.
OPENAI_API_KEY = os.getenv("MACROMAPPER_OPENAI_API_KEY", "")
OPENAI_MEAL_ESTIMATION_MODEL = os.getenv("OPENAI_MEAL_ESTIMATION_MODEL", "gpt-5.6-luna")
OPENAI_MEAL_ESTIMATION_TIMEOUT = float(
    os.getenv("OPENAI_MEAL_ESTIMATION_TIMEOUT", "110")
)
if not math.isfinite(OPENAI_MEAL_ESTIMATION_TIMEOUT) or not (
    0 < OPENAI_MEAL_ESTIMATION_TIMEOUT <= 110
):
    raise ImproperlyConfigured(
        "OPENAI_MEAL_ESTIMATION_TIMEOUT must be greater than 0 and at most 110 seconds."
    )


# Optional MCP has no routes, OAuth tables or application tools unless explicitly enabled.
MCP_ENABLED = os.getenv("DJANGO_MCP_ENABLED", "0") == "1"
MCP_NAME = "MacroMapper"
MCP_BASE_URL = os.getenv("DJANGO_MCP_BASE_URL", "http://localhost:8000").rstrip("/")
MCP_RESOURCE_URL = f"{MCP_BASE_URL}/mcp"
MCP_SERVER_FACTORY = (
    os.getenv("DJANGO_MCP_SERVER_FACTORY") or "apps.mcp.tools.server.create_server"
)
TRUSTED_PROXY_IPS = [
    address.strip()
    for address in os.getenv("DJANGO_TRUSTED_PROXY_IPS", "").split(",")
    if address.strip()
]
MCP_CONSENT_SALT = "macromapper.mcp.consent"
MCP_REQUIRED_SCOPES = ["macromapper:read"]
MCP_ACTION_APPROVAL_HANDLER = "apps.mcp.tools.services.action_approval"
OAUTH2_PROVIDER = oauth_settings(
    base_url=MCP_BASE_URL,
    scopes={
        "macromapper:read": "Read your meals, proposals, notifications and accessible foods",
        "macromapper:write": "Make additions and edits directly, including item replacements; archiving and permanent deletion require your separate approval in MacroMapper",
        "macromapper:estimate": "Run paid AI work directly that can spend credits and publish shared food definitions (also requires read/write access); no separate per-action app approval",
    },
    required_scopes=MCP_REQUIRED_SCOPES,
)

INSTALLED_APPS += ["apps.mcp.framework", "apps.mcp.tools.apps.MacroMapperMCPConfig"]
if MCP_ENABLED:
    INSTALLED_APPS += ["oauth2_provider"]
    SECURE_PROXY_SSL_HEADER = None
    SESSION_COOKIE_SECURE = not DEBUG
    CSRF_COOKIE_SECURE = not DEBUG
ASGI_APPLICATION = "config.asgi.application"
