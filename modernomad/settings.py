# Django settings for modernomad project.

import logging
import os
import sys
from pathlib import Path
from urllib import parse

BASE_DIR = Path.cwd()

ALLOWED_HOSTS = [
    "0.0.0.0",
    "127.0.0.1",
    "localhost",
    os.getenv("DOMAIN_NAME"),
]

DEBUG = os.getenv("DEBUG") == "1"

LOCALDEV = os.getenv("LOCALDEV") == "1"

SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-OLGfXpLCkPPddMOXVlPXcz7Gmp")

CANONICAL_URL = "http://localhost:8000"
if not LOCALDEV and os.getenv("DOMAIN_NAME"):
    CANONICAL_URL = "https://" + os.getenv("DOMAIN_NAME")

STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")

# Database
# https://docs.djangoproject.com/en/3.0/ref/settings/#databases
database_url = os.getenv("DATABASE_URL")
database_url = parse.urlparse(database_url)
# e.g. postgres://modernomad:password@127.0.0.1:5432/modernomad
database_name = database_url.path[1:]  # url.path is '/modernomad'
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": parse.unquote(database_name or ""),
        "USER": parse.unquote(database_url.username or ""),
        "PASSWORD": parse.unquote(database_url.password or ""),
        "HOST": database_url.hostname,
        "PORT": database_url.port or "",
        "CONN_MAX_AGE": 500,
    }
}

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
TIME_ZONE = "America/Los_Angeles"
DATE_FORMAT = "%Y-%m-%d"

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = "en-us"

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale.
USE_L10N = True

# If you set this to False, Django will not use timezone-aware datetimes.
USE_TZ = True

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/media/"
MEDIA_ROOT = BASE_DIR / "media"

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://media.lawrence.com/media/", "http://example.com/media/"
MEDIA_URL = "/media/"

# Generate thumbnails on save
IMAGEKIT_DEFAULT_CACHEFILE_STRATEGY = "imagekit.cachefiles.strategies.Optimistic"

# Static files
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "static"
if not LOCALDEV:
    # Enable WhiteNoise storage backend
    STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"


AUTHENTICATION_BACKENDS = (
    "modernomad.backends.EmailOrUsernameModelBackend",
    "rules.permissions.ObjectPermissionBackend",
    "django.contrib.auth.backends.ModelBackend",
)

MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY")
if MAILGUN_API_KEY:
    EMAIL_BACKEND = "modernomad.backends.MailgunBackend"
    # This should only ever be true in the production environment. Defaults to False.
    MAILGUN_CAUTION_SEND_REAL_MAIL = os.getenv("MAILGUN_CAUTION_SEND_REAL_MAIL") == "1"
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"


# this will be used as the subject line prefix for all emails sent from this app.
EMAIL_SUBJECT_PREFIX = os.getenv("EMAIL_SUBJECT_PREFIX", "[Modernomad] ")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "stay@example.com")
LIST_DOMAIN = os.getenv("LIST_DOMAIN", "somedomain.com")


TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "templates",
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.debug",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.static",
                "django.template.context_processors.tz",
                "django.template.context_processors.request",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.location.location_variables",
                "core.context_processors.location.network_locations",
            ],
        },
    },
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.contrib.flatpages.middleware.FlatpageFallbackMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
if not LOCALDEV:
    # We need whitenoise right after the security middleware.
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

ROOT_URLCONF = "modernomad.urls.main"

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = "modernomad.wsgi.application"


INSTALLED_APPS = [
    "core",
    "bank",
    "gather",
    "modernomad",
    "api",
    "graphapi",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.admin",
    "django.contrib.flatpages",
    "django.contrib.admindocs",
    "django.contrib.humanize",
    "django_filters",
    "graphene_django",
    "imagekit",
    "rest_framework",
    "rules.apps.AutodiscoverRulesConfig",
]

AUTH_PROFILE_MODULE = "core.UserProfile"
ACCOUNT_ACTIVATION_DAYS = 7  # One week account activation window.

# If we add a page for the currently-logged-in user to view and edit
# their profile, we might want to use that here instead.
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"
LOGIN_URL = "/people/login/"
LOGOUT_URL = "/people/logout/"

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [],
    "DEFAULT_AUTHENTICATION_CLASSES": [],
}

NOSE_ARGS = ["--nocapture", "--nologcapture"]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "root": {"handlers": ["console"], "level": "DEBUG"},
    "handlers": {
        "console": {
            "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"),
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "formatters": {
        "verbose": {
            "format": "[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s",
            "datefmt": "%d/%b/%Y %H:%M:%S",
        },
        "simple": {"format": "%(levelname)s %(message)s"},
    },
}

# Suppress "Starting new HTTPS connection" messages
logging.getLogger("requests.packages.urllib3.connectionpool").setLevel(logging.ERROR)


class DisableMigrations:
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


TESTS_IN_PROGRESS = False
if "test" in sys.argv[1:]:
    PASSWORD_HASHERS = ("django.contrib.auth.hashers.MD5PasswordHasher",)
    TESTS_IN_PROGRESS = True
    MIGRATION_MODULES = DisableMigrations()

os.environ["DJANGO_LIVE_TEST_SERVER_ADDRESS"] = "localhost:8000-8010,8080,9200-9300"


# Enable Slack daily arrival/departure messages
# TODO: Change hook URLs to be configured in the database per location
ENABLE_SLACK = os.getenv("ENABLE_SLACK") == "1"


# Default primary key field type
# https://docs.djangoproject.com/en/3.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CSRF_TRUSTED_ORIGINS = [
    CANONICAL_URL,
]

CORS_ALLOWED_ORIGINS = [
    CANONICAL_URL,
]
CORS_ALLOW_CREDENTIALS = True


# Memberships settings

SHORT_TERM_MEMBERSHIP_COST = 90
LONG_TERM_MEMBERSHIP_COST = 200
REQUIRE_MEMBERSHIP_ON_ACCOUNT_CREATION = False
