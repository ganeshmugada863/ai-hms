import os
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables
load_dotenv()

# SECRET_KEY
SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "django-insecure-temporary-build-key"
)

# DEBUG
DEBUG = os.getenv("DEBUG", "False") == "True"

# ALLOWED_HOSTS
ALLOWED_HOSTS = ["*"]

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
CSRF_TRUSTED_ORIGINS = [
    'https://*.hf.space',
    'https://*.huggingface.co',
]

custom_domain = os.getenv("CUSTOM_DOMAIN")
if custom_domain:
    CSRF_TRUSTED_ORIGINS.append(f'https://{custom_domain}')
    CSRF_TRUSTED_ORIGINS.append(f'https://*.{custom_domain}')

# Cookie settings for iframe compatibility on Hugging Face Spaces
if DEBUG:
    CSRF_COOKIE_SAMESITE = 'Lax'
    CSRF_COOKIE_SECURE = False
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = False
else:
    CSRF_COOKIE_SAMESITE = 'None'
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = 'None'
    SESSION_COOKIE_SECURE = True


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'crispy_forms',
    'crispy_bootstrap5',

    'authentication',
    'admin_dashboard',
    'doctor_dashboard',
    'patient_dashboard',
    'patients',
    'doctors',
    'appointments',
    'prescriptions',
    'medical_records',
    'consultations',
    'reminders',
    'reports',
    'departments',
    'ml_module',
    'ml_booking_agent',
    'home',
    'ai_assistant',
]

AUTH_USER_MODEL = 'authentication.CustomUser'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    # 'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'hospital_management_system.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': False,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'reminders.context_processors.notifications_processor',
            ],
            # Cache compiled templates in memory for faster rendering
            # APP_DIRS must be False when using custom loaders
            'loaders': [
                ('django.template.loaders.cached.Loader', [
                    'django.template.loaders.filesystem.Loader',
                    'django.template.loaders.app_directories.Loader',
                ]),
            ],
        },
    },
]

WSGI_APPLICATION = 'hospital_management_system.wsgi.application'


# Database
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(DATABASE_URL)
    }
    # Remove pgbouncer automatically
    if "OPTIONS" in DATABASES["default"]:
        DATABASES["default"]["OPTIONS"].pop("pgbouncer", None)
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
            # SQLite performance optimizations
            'OPTIONS': {
                'timeout': 20,
            }
        }
    }

# Caching — in-memory cache for fast repeated lookups (context processors, etc.)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'hms-cache',
        'TIMEOUT': 300,  # 5 minutes default
        'OPTIONS': {
            'MAX_ENTRIES': 1000
        }
    }
}

# Use cached sessions for speed
SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'

STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

STATICFILES_DIRS = [BASE_DIR / 'static']

STATICFILES_STORAGE = (
    'whitenoise.storage.CompressedManifestStaticFilesStorage'
)

WHITENOISE_MANIFEST_STRICT = False



MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# Email Configuration
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# AI Assistant Configuration
AI_ASSISTANT = {
    'RETRAIN_THRESHOLD': 50,
    'MAX_FOLLOWUP_QUESTIONS': 3,
    'SYMPTOM_CONFIDENCE_THRESHOLD': 0.6,
    'DISEASE_CONFIDENCE_THRESHOLD': 0.5,
    'RISK_CRITICAL_KEYWORDS': ['chest pain', 'breathing difficulty', 'unconscious', 'seizure', 'severe bleeding', 'heart attack', 'stroke', 'difficulty breathing'],
    'SENTENCE_TRANSFORMER_MODEL': 'all-MiniLM-L6-v2',
    'TRUSTED_MEDICAL_URLS': ['who.int', 'mayoclinic.org', 'medlineplus.gov'],
}

# Login Redirects Configuration
LOGIN_URL = '/auth/login/'

AUTHENTICATION_BACKENDS = [
    'authentication.backends.EmailOrUsernameBackend',
    'django.contrib.auth.backends.ModelBackend',
]

