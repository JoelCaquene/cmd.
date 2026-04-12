"""
Django settings for cmb project.
Configurado para Produção no Render.com com o domínio cmbb.store.
"""

from pathlib import Path
import os
import dj_database_url
from decouple import config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
SECRET_KEY = config('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=False, cast=bool)

# ======================================================================
# CONFIGURAÇÃO DOS HOSTS PERMITIDOS
# ======================================================================
ALLOWED_HOSTS = [
    'www.cmbb.store',
    'cmbb.store',
    'cmd-ang.onrender.com',
    'localhost',
    '127.0.0.1',
]

if not DEBUG:
    RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
    if RENDER_EXTERNAL_HOSTNAME and RENDER_EXTERNAL_HOSTNAME not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

# ORIGENS CONFIÁVEIS PARA CSRF (Obrigatório para evitar erro 403 em produção)
CSRF_TRUSTED_ORIGINS = [
    'https://www.cmbb.store',
    'https://cmbb.store',
    'https://cmd-ang.onrender.com',
]

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # WhiteNoise para arquivos estáticos
    'whitenoise.runserver_nostatic',
    
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', 
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware', 
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'cmb.urls'

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
            ],
        },
    },
]

WSGI_APPLICATION = 'cmb.wsgi.application'

# ======================================================================
# DATABASE (SQLite Local, PostgreSQL em Produção)
# ======================================================================
DATABASES = {
    'default': dj_database_url.config(
        default=config('DATABASE_URL', default=f'sqlite:///{BASE_DIR}/db.sqlite3'),
        conn_max_age=600
    )
}

# Internationalization
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'Africa/Luanda'
USE_I18N = True
USE_TZ = True

# ======================================================================
# STATIC FILES
# ======================================================================
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

if not DEBUG:
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ======================================================================
# MEDIA FILES
# ======================================================================
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

if not os.path.exists(MEDIA_ROOT):
    os.makedirs(MEDIA_ROOT)

# ======================================================================
# SEGURANÇA E REDIRECIONAMENTO (WWW E HTTPS)
# ======================================================================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'core.CustomUser'
LOGIN_URL = 'login'

if not DEBUG:
    # FORÇA O REDIRECIONAMENTO PARA WWW (cmbb.store -> www.cmbb.store)
    PREPEND_WWW = True 
    
    # REDIRECIONA PARA HTTPS
    SECURE_SSL_REDIRECT = True
    
    # SEGURANÇA DE COOKIES E HEADERS
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    
    # HSTS (Segurança persistente no navegador)
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True  
    SECURE_HSTS_PRELOAD = True
    
    # HEADER PARA PROXY DO RENDER
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    