from hellomama_registration.settings import *  # flake8: noqa

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'TESTSEKRET'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

TEMPLATES[0]['OPTIONS']['debug'] = True

CELERY_EAGER_PROPAGATES_EXCEPTIONS = True
CELERY_ALWAYS_EAGER = True
BROKER_BACKEND = 'memory'
CELERY_RESULT_BACKEND = 'djcelery.backends.database:DatabaseBackend'

METRICS_URL = "http://metrics-url"
METRICS_AUTH_TOKEN = "REPLACEME"

PASSWORD_HASHERS = ('django.contrib.auth.hashers.MD5PasswordHasher',)

REST_FRAMEWORK['PAGE_SIZE'] = 2

V2N_VOICE_URL = 'http://v2n.com/praekelt/download.php'

V2N_FTP_HOST = 'localhost'
V2N_FTP_PORT = '2222'
V2N_FTP_USER = 'test'
V2N_FTP_PASS = 'secret'
V2N_FTP_ROOT = 'test_directory'
