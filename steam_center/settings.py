import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")  # <— tự động nạp .env

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-secret-key")
DEBUG = os.getenv("DEBUG", "1") == "1"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
# Custom user model
AUTH_USER_MODEL = "accounts.User"

# Session settings
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
# Login settings - LOGIN_URL cần có namespace nếu URL được định nghĩa trong một app có app_name
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "common:dashboard"

# Application definition

INSTALLED_APPS = [
    # Django mặc định
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Thư viện bên thứ 3
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "widget_tweaks",
    "django_htmx",
    # Các app của hệ thống
    "apps.common",
    "apps.accounts.apps.AccountsConfig",
    "apps.centers.apps.CentersConfig",
    "apps.teachers",
    "apps.students",
    "apps.parents",
    "apps.curriculum.apps.CurriculumConfig",
    "apps.classes",
    "apps.class_sessions",
    "apps.enrollments",
    "apps.attendance",
    "apps.assessments",
    "apps.billing",
    "apps.notifications",
    "apps.reports",
    "apps.rewards",
    "apps.filters",
]
INSTALLED_APPS += ["django_seed"]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
]

ROOT_URLCONF = "steam_center.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "steam_center.wsgi.application"


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "steam_center"),
        "USER": os.getenv("POSTGRES_USER", "postgres"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "postgres"),
        "HOST": os.getenv("POSTGRES_HOST", "127.0.0.1"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

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


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

# Static files (CSS, JS, Images)
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]  # chứa source CSS/JS trong project
STATIC_ROOT = BASE_DIR / "staticfiles"  # thư mục collectstatic (deploy)

# Media files (upload: ảnh, tài liệu,…)
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Allowed student embed hosts (for safe iframe rendering)
# Extend this set per your needs (e.g., 'play.unity.com', 'glitch.me')
ALLOWED_STUDENT_EMBED_HOSTS = set([
    "youtube.com",
    "www.youtube.com",
    "youtu.be",
    "vimeo.com",
    "player.vimeo.com",
    "itch.io",
    "www.itch.io",
    "scratch.mit.edu",
    "codepen.io",
    "play.unity.com",
    "drive.google.com",
    "docs.google.com",
    "loom.com",
    "www.loom.com",
    "streamable.com",
])
