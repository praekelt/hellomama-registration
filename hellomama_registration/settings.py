"""
Django settings for hellomama_registration project.

For more information on this file, see
https://docs.djangoproject.com/en/1.9/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.9/ref/settings/
"""

from kombu import Exchange, Queue

import os
import djcelery
import dj_database_url
import mimetypes

# Support SVG on admin
mimetypes.add_type("image/svg+xml", ".svg", True)
mimetypes.add_type("image/svg+xml", ".svgz", True)


# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(__file__))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.9/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', 'REPLACEME')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'false').lower() == 'true'

TEMPLATE_DEBUG = DEBUG

ALLOWED_HOSTS = ['*']


# Application definition

INSTALLED_APPS = (
    # admin
    'django.contrib.admin',
    # core
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # 3rd party
    'djcelery',
    'raven.contrib.django.raven_compat',
    'rest_framework',
    'rest_framework.authtoken',
    'django_filters',
    'rest_hooks',
    # documentation
    'rest_framework_docs',
    # us
    'registrations',
    'changes',
    'uniqueids'

)

MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
)

ROOT_URLCONF = 'hellomama_registration.urls'

WSGI_APPLICATION = 'hellomama_registration.wsgi.application'


# Database
# https://docs.djangoproject.com/en/1.9/ref/settings/#databases

DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get(
            'REGISTRATIONS_DATABASE',
            'postgres://localhost/hellomama_registration')),
}


# Internationalization
# https://docs.djangoproject.com/en/1.9/topics/i18n/

LANGUAGE_CODE = 'en-gb'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.9/howto/static-files/

STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'django.contrib.staticfiles.finders.FileSystemFinder',
)

STATIC_ROOT = 'staticfiles'
STATIC_URL = '/static/'

# TEMPLATE_CONTEXT_PROCESSORS = (
#     "django.core.context_processors.request",
# )

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.contrib.auth.context_processors.auth',
                'django.template.context_processors.debug',
                'django.template.context_processors.i18n',
                'django.template.context_processors.media',
                'django.template.context_processors.static',
                'django.template.context_processors.tz',
                'django.contrib.messages.context_processors.messages',
            ],
            'debug': DEBUG,
        },
    },
]

# Sentry configuration
RAVEN_CONFIG = {
    # DevOps will supply you with this.
    'dsn': os.environ.get('REGISTRATIONS_SENTRY_DSN', None),
}

# REST Framework conf defaults
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': ('rest_framework.permissions.IsAdminUser',),
    'PAGE_SIZE': 1000,
    'DEFAULT_PAGINATION_CLASS':
        'rest_framework.pagination.LimitOffsetPagination',
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.BasicAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_FILTER_BACKENDS': ('rest_framework.filters.DjangoFilterBackend',)
}

# Webhook event definition
HOOK_EVENTS = {
    # 'any.event.name': 'App.Model.Action' (created/updated/deleted)
    'subscriptionrequest.added': 'registrations.SubscriptionRequest.created+'
}

HOOK_DELIVERER = 'registrations.tasks.deliver_hook_wrapper'

HOOK_AUTH_TOKEN = os.environ.get('HOOK_AUTH_TOKEN', 'REPLACEME')

# Celery configuration options
CELERY_RESULT_BACKEND = 'djcelery.backends.database:DatabaseBackend'
CELERYBEAT_SCHEDULER = 'djcelery.schedulers.DatabaseScheduler'

BROKER_URL = os.environ.get('BROKER_URL', 'redis://localhost:6379/0')

CELERY_DEFAULT_QUEUE = 'hellomama_registration'
CELERY_QUEUES = (
    Queue('hellomama_registration',
          Exchange('hellomama_registration'),
          routing_key='hellomama_registration'),
)

CELERY_ALWAYS_EAGER = False

# Tell Celery where to find the tasks
CELERY_IMPORTS = (
    'registrations.tasks',
    'changes.tasks'
)

CELERY_CREATE_MISSING_QUEUES = True
CELERY_ROUTES = {
    'celery.backend_cleanup': {
        'queue': 'mediumpriority',
    },
    'registrations.tasks.validate_registration': {
        'queue': 'priority',
    },
    'changes.tasks.implement_action': {
        'queue': 'priority',
    },
    'registrations.tasks.DeliverHook': {
        'queue': 'priority',
    },
    'registrations.tasks.fire_metric': {
        'queue': 'metrics',
    },
    'uniqueids.tasks.add_unique_id_to_identity': {
        'queue': 'priority',
    },
    'registrations.tasks.repopulate_metrics': {
        'queue': 'mediumpriority',
    },
}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'TIMEOUT': None,
    },
}

MSG_TYPES = ["text", "audio"]
RECEIVER_TYPES = [
    "mother_father", "mother_only", "father_only", "mother_family",
    "mother_friend", "friend_only", "family_only"]
LANGUAGES = ["eng_NG", "hau_NG", "ibo_NG", "yor_NG", "pcm_NG"]
STATES = ["ebonyi", "cross_river", "abuja"]
ROLES = ["oic", "cv", "midwife", "chew", "mama"]

METRICS_REALTIME = [
    'registrations.created.sum',
    'registrations.created.total.last',
    'registrations.unique_operators.sum',
    'change.language.sum',
]
METRICS_REALTIME.extend(
    ['registrations.msg_type.%s.sum' % mt for mt in MSG_TYPES])
METRICS_REALTIME.extend(
    ['registrations.msg_type.%s.total.last' % mt for mt in MSG_TYPES])
METRICS_REALTIME.extend(
    ['registrations.receiver_type.%s.sum' % rt for rt in RECEIVER_TYPES])
METRICS_REALTIME.extend(
    ['registrations.receiver_type.%s.total.last' % rt for rt in RECEIVER_TYPES]
)
METRICS_REALTIME.extend(
    ['registrations.language.%s.sum' % l for l in LANGUAGES])
METRICS_REALTIME.extend(
    ['registrations.language.%s.total.last' % l for l in LANGUAGES])
METRICS_REALTIME.extend(
    ['registrations.state.%s.sum' % s for s in STATES])
METRICS_REALTIME.extend(
    ['registrations.state.%s.total.last' % s for s in STATES])
METRICS_REALTIME.extend(
    ['registrations.role.%s.sum' % r for r in ROLES])
METRICS_REALTIME.extend(
    ['registrations.role.%s.total.last' % r for r in ROLES])
METRICS_SCHEDULED = [
]
METRICS_SCHEDULED_TASKS = [
]

METRICS_AUTH_TOKEN = os.environ.get("METRICS_AUTH_TOKEN", "REPLACEME")
METRICS_URL = os.environ.get("METRICS_URL", None)

CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_IGNORE_RESULT = True

PREBIRTH_MIN_WEEKS = int(os.environ.get('PREBIRTH_MIN_WEEKS', '10'))
PREBIRTH_MAX_WEEKS = int(os.environ.get('PREBIRTH_MAX_WEEKS', '42'))
POSTBIRTH_MIN_WEEKS = int(os.environ.get('POSTBIRTH_MIN_WEEKS', '0'))
POSTBIRTH_MAX_WEEKS = int(os.environ.get('POSTBIRTH_MAX_WEEKS', '52'))

STAGE_BASED_MESSAGING_URL = os.environ.get('STAGE_BASED_MESSAGING_URL',
                                           'http://localhost:8005/api/v1')
STAGE_BASED_MESSAGING_TOKEN = os.environ.get('STAGE_BASED_MESSAGING_TOKEN',
                                             'REPLACEME')
IDENTITY_STORE_URL = os.environ.get('IDENTITY_STORE_URL',
                                    'http://localhost:8001/api/v1')
IDENTITY_STORE_TOKEN = os.environ.get('IDENTITY_STORE_TOKEN',
                                      'REPLACEME')
MESSAGE_SENDER_URL = os.environ.get('MESSAGE_SENDER_URL',
                                    'http://localhost:8006/api/v1')
MESSAGE_SENDER_TOKEN = os.environ.get('MESSAGE_SENDER_TOKEN',
                                      'REPLACEME')
PUBLIC_HOST = os.environ.get('PUBLIC_HOST',
                             'http://registration.dev.example.org')
MOTHER_WELCOME_TEXT_NG_ENG = os.environ.get(
    'MOTHER_WELCOME_TEXT_NG_ENG', 'Welcome to HelloMama!')
HOUSEHOLD_WELCOME_TEXT_NG_ENG = os.environ.get(
    'HOUSEHOLD_WELCOME_TEXT_NG_ENG', 'Welcome household to HelloMama!')

djcelery.setup_loader()
