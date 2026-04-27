from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(os.path.join(BASE_DIR, ".env.dev"))

# ==========================
# SEGURIDAD — ISO 27001 A.10
# ==========================
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "unsafe-dev-secret-change-in-production")

# V-05 Fix: Aceptar "1", "true", "True" como valores válidos
_debug_raw = os.getenv("DJANGO_DEBUG", os.getenv("DEBUG", "False"))
DEBUG = _debug_raw.lower() in ("1", "true", "yes")

# V-08 Fix: ALLOWED_HOSTS con default funcional para desarrollo
_allowed_hosts_raw = os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
ALLOWED_HOSTS = [h.strip() for h in _allowed_hosts_raw.split(",") if h.strip()]

# ==========================
# APPS
# ==========================
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party
    "rest_framework",
    "corsheaders",

    # Apps del proyecto
    "config.apps.users",
    "config.apps.inventory",
]

# ==========================
# MIDDLEWARE — ISO 27001 A.13
# V-12 Fix: SecurityMiddleware primero, cabeceras personalizadas al final
# ==========================
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",   # Debe ser primero
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Cabeceras de seguridad personalizadas (ISO 27001 A.13.1.3)
    "config.utils.security_middleware.SecurityHeadersMiddleware",
]

# ==========================
# CORS — ISO 27001 A.13.2.1
# V-07 Fix: Restringir orígenes según entorno
# ==========================
if DEBUG:
    # En desarrollo: permitir localhost
    CORS_ALLOWED_ORIGINS = os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:8080,http://127.0.0.1:8080"
    ).split(",")
    CORS_ALLOW_ALL_ORIGINS = False
else:
    # En producción: leer de variable de entorno (no permitir all)
    CORS_ALLOWED_ORIGINS = [
        o.strip() for o in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
        if o.strip()
    ]
    CORS_ALLOW_ALL_ORIGINS = False

CORS_ALLOW_CREDENTIALS = True

# ==========================
# CABECERAS DE SEGURIDAD DJANGO — ISO 27001 A.13
# ==========================
# Forzar HTTPS en producción
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 0 if DEBUG else 31536000       # 1 año en producción
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True

ROOT_URLCONF = "config.urls"

# ==========================
# TEMPLATES
# ==========================
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

# ==========================
# WSGI / ASGI
# ==========================
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ==========================
# DATABASE (SQLite — solo para Django admin y sesiones)
# Los modelos del negocio usan MongoDB via MongoEngine
# ==========================
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# ============================================================
# PASSWORD HASHERS — ISO 27001 A.10.1 (Criptografía)
# Argon2 como hasher principal (ganador Password Hashing Competition 2015)
# Los passwords existentes se re-hashean automáticamente en el próximo login
# ============================================================
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

# ==========================
# INTERNACIONALIZACIÓN
# ==========================
LANGUAGE_CODE = os.getenv("DJANGO_LANGUAGE_CODE", "es-ec")
TIME_ZONE = os.getenv("DJANGO_TIME_ZONE", "America/Guayaquil")
USE_I18N = True
USE_TZ = True

# ==========================
# STATIC FILES
# ==========================
STATIC_URL = "/static/"

# ============================================================
# DJANGO REST FRAMEWORK — ISO 9001 (validación) + ISO 27001 A.9
# ============================================================
REST_FRAMEWORK = {
    # Autenticación global (JWT personalizado)
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "config.apps.users.authentication.JWTAuthentication",
    ],

    # Todos los endpoints requieren usuario autenticado por defecto
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],

    # API JSON only
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],

    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],

    # Exception handler estandarizado (ISO 9001 — respuestas consistentes)
    "EXCEPTION_HANDLER": "config.utils.exception_handler.custom_exception_handler",

    # V-11 Fix: Throttling para prevenir abusos (ISO 27001 A.9.1.2)
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/minute",      # Usuarios anónimos: 60 req/min
        "user": "300/minute",     # Usuarios autenticados: 300 req/min
        "login": "5/minute",      # Login: máximo 5 intentos/min (brute force)
        "sustained": "1000/day",  # Límite diario por usuario
    },
}

# ============================================================
# DEFAULT FIELD
# ============================================================
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ============================================================
# LOGGING — ISO 27001 A.12.4 (Audit logging)
# ============================================================
LOG_LEVEL = os.getenv("LOG_LEVEL", "WARNING" if not DEBUG else "INFO")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": LOG_LEVEL,
    },
    "loggers": {
        "django.security": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "config.apps": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
    },
}
