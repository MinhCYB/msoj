"""Container-only local_settings override; copied into dmoj/local_settings.py.

Never copy the workstation's local_settings.py or .env into an image.
"""
import hashlib
import os
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured


def _bool(name, default=False):
    value = os.environ.get(name, str(default)).lower()
    if value not in ('true', 'false', '1', '0'):
        raise ImproperlyConfigured(f'{name} must be true or false')
    return value in ('true', '1')


_build = _bool('MSOJ_BUILD')


def _secret(name):
    value = os.environ.get(name, '')
    if not value and not _build:
        raise ImproperlyConfigured(f'{name} is required in the container environment')
    return value or f'build-only-not-a-runtime-secret-{name}'


SECRET_KEY = _secret('DJANGO_SECRET_KEY')
if len(SECRET_KEY) < 50 and not _build:
    raise ImproperlyConfigured('DJANGO_SECRET_KEY must contain at least 50 characters')
DEBUG = _bool('DJANGO_DEBUG')
SITE_NAME = 'MSOJ'
SITE_LONG_NAME = 'MSOJ: MSOJ Online Judge'
SITE_FULL_URL = os.environ.get('MSOJ_SITE_URL', 'http://localhost:8080').rstrip('/')
_site = urlsplit(SITE_FULL_URL)
if _site.scheme not in ('http', 'https') or not _site.hostname or _site.path or _site.query or _site.fragment or _site.username:
    raise ImproperlyConfigured('MSOJ_SITE_URL must be an http(s) origin without a path or credentials')
ALLOWED_HOSTS = [host.strip() for host in os.environ.get('DJANGO_ALLOWED_HOSTS', _site.hostname).split(',') if host.strip()]
if '*' in ALLOWED_HOSTS:
    raise ImproperlyConfigured('Use explicit DJANGO_ALLOWED_HOSTS, not *')
CSRF_TRUSTED_ORIGINS = [SITE_FULL_URL]
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = _site.scheme == 'https'
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'SAMEORIGIN'
SITE_ADMIN_EMAIL = os.environ.get('MSOJ_ADMIN_EMAIL', 'admin@localhost')
TERMS_OF_SERVICE_URL = SITE_FULL_URL + '/tos/'
LANGUAGE_CODE = os.environ.get('MSOJ_LANGUAGE', 'vi')
DEFAULT_USER_TIME_ZONE = 'Asia/Ho_Chi_Minh'
TIME_ZONE = 'UTC'
DMOJ_REQUIRE_STAFF_2FA = _bool('MSOJ_REQUIRE_STAFF_2FA', True)

DATABASES = {'default': {
    'ENGINE': 'django.db.backends.mysql',
    'HOST': os.environ.get('DB_HOST', 'db'),
    'PORT': os.environ.get('DB_PORT', '3306'),
    'NAME': os.environ.get('MARIADB_DATABASE', 'msoj'),
    'USER': os.environ.get('MARIADB_USER', 'msoj'),
    'PASSWORD': _secret('MARIADB_PASSWORD'),
    'CONN_MAX_AGE': 60,
    'OPTIONS': {'charset': 'utf8mb4', 'sql_mode': 'STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION'},
}}
if _build:
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}

# Cache eviction must never discard Celery broker messages. Use separate Redis services.
CACHES = {'default': {
    'BACKEND': 'django_redis.cache.RedisCache',
    'LOCATION': os.environ.get('CACHE_URL', 'redis://cache:6379/0'),
    'OPTIONS': {'CLIENT_CLASS': 'django_redis.client.DefaultClient'},
    'KEY_PREFIX': 'msoj',
}}
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://redis:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://redis:6379/1')
CELERY_BROKER_TRANSPORT_OPTIONS = {'visibility_timeout': 86400}
CELERY_RESULT_EXPIRES = 86400
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
if _build:
    CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}

MEDIA_ROOT = '/data/media'
STATIC_ROOT = '/app/static-build'
DMOJ_PROBLEM_DATA_ROOT = '/data/problems'
# CSS/JS are compiled into the release; runtime compressors must not write into the image.
COMPRESS_ENABLED = False
COMPRESS_OFFLINE = False
ENABLE_FTS = False
BRIDGED_JUDGE_ADDRESS = [('0.0.0.0', 9999)]
BRIDGED_DJANGO_ADDRESS = [('0.0.0.0', 9998)]
BRIDGED_DJANGO_CONNECT = ('bridge', 9998)
EVENT_DAEMON_USE = not _build
EVENT_DAEMON_POST = 'ws://events:9997/'
EVENT_DAEMON_GET = f'ws://{_site.netloc}/event/'
EVENT_DAEMON_GET_SSL = f'wss://{_site.netloc}/event/'
EVENT_DAEMON_POLL = '/channels/'
EVENT_DAEMON_POLL_SSL = '/channels/'
# The existing event daemon has no auth command. Publisher stays on a private Docker network.
EVENT_DAEMON_KEY = None
for _purpose in ('SUBMISSION', 'CONTEST', 'TICKET', 'NOTIFICATION'):
    globals()[f'EVENT_DAEMON_{_purpose}_KEY'] = hashlib.sha256(
        (SECRET_KEY + ':event:' + _purpose).encode(),
    ).hexdigest()
GLOBAL_API_KEY = hashlib.sha256((SECRET_KEY + ':internal-sync-api').encode()).hexdigest()
MSOJ_CLOUDFLARE_UPLOAD_WARNING = _bool('MSOJ_CLOUDFLARE_UPLOAD_WARNING', True)

# Defaults remain the policy in dmoj/settings.py; do not change Polygon scope here.
POLYGON_SYNC_AUTHOR = os.environ.get('POLYGON_SYNC_AUTHOR', 'admin')
EMAIL_BACKEND = os.environ.get('DJANGO_EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.environ.get('EMAIL_HOST', '')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = _bool('EMAIL_USE_TLS', True)
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', SITE_ADMIN_EMAIL)
SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = os.environ.get('GOOGLE_OAUTH_CLIENT_ID', '')
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET', '')
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {'container': {'format': '%(asctime)s %(levelname)s %(name)s %(message)s'}},
    'handlers': {'console': {'class': 'logging.StreamHandler', 'formatter': 'container'}},
    'root': {'handlers': ['console'], 'level': os.environ.get('DJANGO_LOG_LEVEL', 'INFO')},
}
