"""Ambiente local isolado: nunca utiliza DATABASE_URL nem credenciais externas."""
from .settings import *
import secrets

DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]']
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / '.local' / 'db.sqlite3'}}
local_dir = BASE_DIR / '.local'
local_dir.mkdir(mode=0o700, exist_ok=True)
key_file = local_dir / 'secret_key'
try:
    with key_file.open('x') as stream:
        key_file.chmod(0o600)
        stream.write(secrets.token_urlsafe(64))
except FileExistsError:
    pass
SECRET_KEY = key_file.read_text().strip()

# runserver fornece os arquivos locais; WhiteNoise é usado na produção.
MIDDLEWARE = [m for m in MIDDLEWARE if m != 'whitenoise.middleware.WhiteNoiseMiddleware']

STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'}, 'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
