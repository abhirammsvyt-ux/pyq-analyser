"""
Django settings for KTU PYQ Analyzer project.
Uses Google Gemini Flash 2.0 API for PDF reading and question extraction.
"""
import os
from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / '.env')
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get(
    'SECRET_KEY',
    'django-insecure-change-this-in-production-pyq-analyzer-secret-key'
)

DEBUG = os.environ.get('DEBUG', 'False').lower() in ('true', '1', 'yes')

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_extensions',
    'apps.core',
    'apps.users',
    'apps.subjects',
    'apps.papers',
    'apps.questions',
    'apps.analysis',
    'apps.analytics',
    'apps.reports',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.core.context_processors.global_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db' / 'pyq_analyzer.sqlite3',
        'OPTIONS': {
            'timeout': 30,
        },
    }
}

AUTH_USER_MODEL = 'users.User'

AUTHENTICATION_BACKENDS = [
    'apps.users.backends.EmailBackend',
    'django.contrib.auth.backends.ModelBackend',
]

LOGIN_URL = 'users:login'
LOGIN_REDIRECT_URL = 'core:dashboard'
LOGOUT_REDIRECT_URL = 'core:home'

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- API Provider Configuration ---
# Priority order: Groq (1) → GitHub Models (2) → OpenRouter (3) → Gemini (4)

# Groq API Configuration (PRIMARY — 14400 req/day per key, fastest)
GROQ_API_KEYS = [
    k.strip() for k in [
        os.environ.get('GROQ_API_KEY_1', ''),
        os.environ.get('GROQ_API_KEY_2', ''),
        os.environ.get('GROQ_API_KEY_3', ''),
    ] if k.strip()
]
GROQ_MODEL_TEXT = os.environ.get('GROQ_MODEL_TEXT', 'llama-3.3-70b-versatile')
GROQ_MODEL_VISION = os.environ.get('GROQ_MODEL_VISION', 'llama-3.2-11b-vision-preview')
GROQ_ENABLED = os.environ.get('GROQ_ENABLED', 'false').lower() in ('true', '1', 'yes')

# GitHub Models API Configuration (SECONDARY — 150 req/day free)
GITHUB_MODELS_TOKENS = [
    k.strip() for k in os.environ.get('GITHUB_MODELS_TOKEN', '').split(',') if k.strip()
]
GITHUB_MODELS_MODEL = os.environ.get('GITHUB_MODELS_MODEL', 'gpt-4o')

# OpenRouter API Configuration (TERTIARY — free models via single key)
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY', '').strip()
OPENROUTER_ENABLED = os.environ.get('OPENROUTER_ENABLED', 'false').lower() in ('true', '1', 'yes')
OPENROUTER_MODEL = os.environ.get(
    'OPENROUTER_MODEL', 'meta-llama/llama-3.2-11b-vision-instruct:free'
)

# Google Gemini API Configuration (LAST RESORT — 1500 req/day, 1M tokens/day free)
GEMINI_API_KEYS = [
    k.strip() for k in os.environ.get('GEMINI_API_KEYS', '').split(',') if k.strip()
]
GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-2.0-flash')

# Ollama Local Fallback Configuration
OLLAMA_BASE_URL = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')
OLLAMA_TEXT_MODEL = os.environ.get('OLLAMA_TEXT_MODEL', 'mistral')
OLLAMA_VISION_MODEL = os.environ.get('OLLAMA_VISION_MODEL', 'llava')

# Django cache for API router state (exhaustion tracking)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'pyq-api-router',
    }
}

# Embedding Model Configuration
EMBEDDING_MODEL = os.environ.get('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')

# File Upload Settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'pyq_analyzer.log',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
        'apps': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# Create necessary directories
for directory in ['db', 'logs', 'media/papers', 'media/reports']:
    (BASE_DIR / directory).mkdir(parents=True, exist_ok=True)
