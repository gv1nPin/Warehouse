"""Настройки Django для сайта Warehouse. Секреты и режим берутся из .env."""

import os
import sys
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.core.management.utils import get_random_secret_key
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

SRC_DIR = str(BASE_DIR / 'src')
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

load_dotenv(BASE_DIR / '.env')


def env_bool(name: str, default: bool = False) -> bool:
    """Флаг из окружения: 1, true, yes, on считаются включёнными."""
    return os.getenv(name, str(default)).strip().lower() in {'1', 'true', 'yes', 'on'}


def env_secret(name: str) -> str:
    """Секрет из окружения; без него в DEBUG выдумывается временный, иначе ошибка."""
    value = os.getenv(name, '').strip()
    if value:
        return value
    if DEBUG:
        return get_random_secret_key()
    raise ImproperlyConfigured(f'В .env не задан {name}')


DEBUG = env_bool('DEBUG')

SECRET_KEY = env_secret('SECRET_KEY')
JWT_SECRET = env_secret('JWT_SECRET')
JWT_EXPIRE_MINUTES = int(os.getenv('JWT_EXPIRE_MINUTES', 8 * 60))

ALLOWED_HOSTS = [h.strip() for h in os.getenv('ALLOWED_HOSTS', '').split(',') if h.strip()]


INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'web.apps.WebConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'web.middleware.SQLAlchemyAndBusinessErrorMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.messages.context_processors.messages',
                'web.context.current_user',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# SQLite — только база самого Django (сессии). Данные склада живут в PostgreSQL.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

SESSION_COOKIE_AGE = JWT_EXPIRE_MINUTES * 60
SESSION_COOKIE_HTTPONLY = True
LOGIN_URL = 'login'


LANGUAGE_CODE = 'ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True


STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

MAX_UPLOAD_SIZE = 10 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_SIZE
