import os
import sys
from pathlib import Path

from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, os.path.join(BASE_DIR, "apps"))

URL_PREFIX = "pmt"

# Chat module (apps/chat)
CHAT_MAX_ATTACHMENT_SIZE = config("CHAT_MAX_ATTACHMENT_SIZE", default=10 * 1024 * 1024, cast=int)  # 10MB
CLAMAV_HOST = config("CLAMAV_HOST", default="localhost")
CLAMAV_PORT = config("CLAMAV_PORT", default=3310, cast=int)

SECRET_KEY = config("SECRET_KEY", default="django-insecure-change-me-in-production")
DEBUG = config("DEBUG", default=False, cast=bool)

ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="*").split(",")

CORS_ORIGIN_ALLOW_ALL = DEBUG
CORS_ALLOWED_ORIGINS = config("CORS_ALLOWED_ORIGINS", default="http://localhost:3000").split(",")
CSRF_TRUSTED_ORIGINS = config("CORS_ALLOWED_ORIGINS", default="http://localhost:3000").split(",")

LANGUAGE_CODE = "en-us"
TIME_ZONE = config("TIME_ZONE", default="Asia/Kolkata")
USE_I18N = False
USE_L10N = True
USE_TZ = True

PROJECT_APPS = [
    "apps.common",
    "apps.master",
    "packages.workflow",
    "apps.accounts",
    "apps.projects",
    "apps.timesheets",
    "apps.workitems",
    "apps.tickets",
    "apps.allocation",
    "apps.dashboard",
    "apps.reports",
    "apps.attendance",
    "apps.payroll",
    "apps.compliance",
    "apps.payment",
    "apps.notifications",
    "apps.integrations",
    "apps.finance",
    "apps.expenses",
    "apps.followups",
    "apps.leads",
    "apps.sales",
    "apps.todos",
    "apps.workspace",
    "apps.social_feed",
    "apps.chat",
]

THIRD_PARTY_LIBRARIES = [
    "rest_framework",
    "corsheaders",
    "django_filters",
    "django_extensions",
    "drf_spectacular",
    "django_celery_beat",
    "django_celery_results",
    "simple_history",
    "django_cleanup.apps.CleanupConfig",
]

INSTALLED_APPS = (
    [
        "jazzmin",  # must be before django.contrib.admin
        "daphne",   # must be before django.contrib.staticfiles so it takes over `runserver` for ASGI/WebSockets
        "django.contrib.admin",
        "django.contrib.auth",
        "django.contrib.contenttypes",
        "django.contrib.sessions",
        "django.contrib.messages",
        "django.contrib.staticfiles",
        "channels",
    ]
    + PROJECT_APPS
    + THIRD_PARTY_LIBRARIES
)

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
]

ROOT_URLCONF = "core.urls"
WSGI_APPLICATION = "core.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
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

AUTH_USER_MODEL = "accounts.Employee"

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "apps.common.permissions.IsAuthenticated",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.common.authentication.KeycloakAuthentication",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "EXCEPTION_HANDLER": "apps.common.exceptions.custom_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

STATIC_URL = f"/{URL_PREFIX}/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STATICFILES_DIRS = []

MEDIA_URL = f"/{URL_PREFIX}/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Workflow slugs excluded from due / overdue / delayed tracking (comma-separated env override).
PROJECT_DUE_EXCLUDED_WORKFLOW_SLUGS = [
    s.strip()
    for s in config("PROJECT_DUE_EXCLUDED_WORKFLOW_SLUGS", default="close,cancelled").split(",")
    if s.strip()
]
 
WHITENOISE_MANIFEST_STRICT = False 
