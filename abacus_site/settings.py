"""
Django settings for abacus_site project.
"""

from pathlib import Path
import os
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()   # loads variables from .env

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-zuv%+p=w_3sq*&xb5w!%a#&&b6z-*%php9p)d@7@re_lmgswok'
DEBUG = True
ALLOWED_HOSTS = []


# Application definition
INSTALLED_APPS = [
    'daphne',  # Must be first for Channels to work
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'channels',  # Django Channels for WebSockets
    'core',   # 👈 ADD THIS (your main app)
    # Portal apps you copied:
    'accounts',
    'dashboard',
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

# -------------------------
# ✅ CSRF CONFIGURATION (Cross-Site Request Forgery Protection)
# -------------------------
# These settings ensure CSRF tokens work reliably and don't become stale

# CSRF cookie settings - EXTENDED EXPIRY
CSRF_COOKIE_AGE = 157680000  # 5 years in seconds (effectively never expires)
CSRF_COOKIE_SECURE = False  # Set to True in production with HTTPS
CSRF_COOKIE_HTTPONLY = False  # Must be False so JavaScript can read it if needed
CSRF_COOKIE_SAMESITE = 'Lax'  # 'Lax' or 'Strict' - Lax is more flexible
CSRF_USE_SESSIONS = False  # False = use cookies (more reliable), True = use sessions
CSRF_COOKIE_NAME = 'csrftoken'  # Default cookie name
CSRF_HEADER_NAME = 'HTTP_X_CSRFTOKEN'  # Header name for AJAX requests

# CSRF trusted origins (add your production domains here)
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:8000',
    'http://127.0.0.1:8000',
    'http://localhost',
    'http://127.0.0.1',
]

# Session settings (related to CSRF) - EXTENDED EXPIRY
SESSION_COOKIE_AGE = 31449600  # 1 year in seconds (extended from 2 weeks)
SESSION_SAVE_EVERY_REQUEST = True  # Refresh session on every request
SESSION_COOKIE_SECURE = False  # Set to True in production with HTTPS
SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript access to session cookie
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_NAME = 'sessionid'  # Default session cookie name
SESSION_ENGINE = 'django.contrib.sessions.backends.db'  # Use database-backed sessions

# Custom CSRF failure view (shows user-friendly error page)
CSRF_FAILURE_VIEW = 'core.csrf_views.csrf_failure'

# -------------------------
# ✅ EMAIL CONFIGURATION
# -------------------------
# Development mode: Print emails to console instead of sending
import os

# Switch to Console backend for development (logs to terminal instead of sending)
# EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

# SMTP settings (for when you switch to production)
EMAIL_HOST = 'smtp.sendgrid.net'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'apikey'   # literal string
EMAIL_HOST_PASSWORD = os.getenv('SENDGRID_API_KEY')

DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'Emesys <sandeshkr07@gmail.com>')
FRANCHISE_NOTIFY_EMAIL = os.getenv('FRANCHISE_NOTIFY_EMAIL', 'viditrajanikanttaunk@gmail.com')

SERVER_EMAIL = DEFAULT_FROM_EMAIL
EMAIL_SUBJECT_PREFIX = '[AbacusMaster] '


ROOT_URLCONF = 'abacus_site.urls'

# -------------------------
# ✅ TEMPLATE CONFIGURATION
# -------------------------
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # 👇 Tell Django where to look for templates (inside your app)
        'DIRS': [
            BASE_DIR / 'core' / 'templates',    # your existing core templates
            BASE_DIR / 'templates',             # project templates root
            BASE_DIR / 'templates' / 'portal',  # <-- add this line
            BASE_DIR / 'templates' / 'portal' / 'student',
            BASE_DIR / 'templates' / 'portal' / 'teacher',
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'abacus_site.wsgi.application'

# -------------------------
# ✅ CHANNELS CONFIGURATION (WebSocket support)
# -------------------------
ASGI_APPLICATION = 'abacus_site.asgi.application'

# Channel layers configuration
# Using in-memory channel layer for development (no Redis needed)
# For production, switch to Redis backend
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer"
    }
}

# For production with Redis (uncomment when deploying):
# CHANNEL_LAYERS = {
#     "default": {
#         "BACKEND": "channels_redis.core.RedisChannelLayer",
#         "CONFIG": {
#             "hosts": [("127.0.0.1", 6379)],
#         },
#     },
# }



# -------------------------
# ✅ DATABASE (no change)
# -------------------------
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME'),
        'USER': os.environ.get('DB_USER'),
        'PASSWORD': os.environ.get('DB_PASSWORD'),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}


# -------------------------
# ✅ PASSWORD VALIDATION (no change)
# -------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
AUTH_USER_MODEL = 'accounts.CustomUser'
AUTHENTICATION_BACKENDS = [
    'accounts.backends.EmailBackend',   # copy this file into accounts/backends.py if Portal had it
    'django.contrib.auth.backends.ModelBackend',
]

# -------------------------
# ✅ INTERNATIONALIZATION (no change)
# -------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# -------------------------
# ✅ STATIC FILES CONFIGURATION
# -------------------------
STATIC_URL = '/static/'
STATICFILES_DIRS = [ BASE_DIR / 'static' ]

# For production (later)
# STATIC_ROOT = BASE_DIR / 'staticfiles'

# -------------------------
# ✅ MEDIA FILES CONFIGURATION (for uploads)
# -------------------------
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# -------------------------
# ✅ DEFAULT PRIMARY KEY TYPE
# -------------------------
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
