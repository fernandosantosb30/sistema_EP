"""Atalhos locais. Nenhum comando acessa o banco de produção."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def run(*args, settings='core.settings_local'):
    env = os.environ.copy()
    env['DJANGO_SETTINGS_MODULE'] = settings
    subprocess.run([sys.executable, str(ROOT / 'manage.py'), *args, '--settings=' + settings], cwd=ROOT, env=env, check=True)

if __name__ == '__main__':
    action = sys.argv[1] if len(sys.argv) == 2 else ''
    if action == 'setup':
        run('migrate', '--noinput')
        run('seed_demo')
    elif action == 'admin':
        run('createsuperuser')
    elif action == 'serve':
        run('runserver', '127.0.0.1:8000')
    elif action == 'check':
        run('check')
        run('makemigrations', '--check', '--dry-run')
        run('test', 'providers', settings='core.settings_test')
    else:
        raise SystemExit('Uso: python local.py setup|admin|serve|check')
