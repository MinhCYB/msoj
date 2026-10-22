#!/usr/bin/env python3
"""Create private environment and external bind directories; never import host settings."""
import argparse
import os
from pathlib import Path
import secrets
import shlex
from urllib.parse import urlsplit


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--env-file', default='.env.docker')
parser.add_argument('--data-root', default='../msoj_docker_data')
parser.add_argument('--site-url', default='http://localhost:8080')
parser.add_argument('--http-port', type=int, default=8080)
parser.add_argument('--bridge-port', type=int, default=9999)
parser.add_argument('--project', default='msoj')
args = parser.parse_args()
origin = urlsplit(args.site_url)
if origin.scheme not in ('http', 'https') or not origin.hostname or origin.path or origin.query or origin.fragment or origin.username:
    parser.error('--site-url must be an http(s) origin without a path or credentials')
if not 1 <= args.http_port <= 65535 or not 1 <= args.bridge_port <= 65535:
    parser.error('Ports must be between 1 and 65535')
root = Path(args.data_root).expanduser().resolve()
env_path = Path(args.env_file).resolve()
if env_path.exists():
    parser.error(f'{env_path} already exists; refusing to replace secrets')
if root == Path('/') or root == Path.cwd() or Path.cwd() in root.parents:
    parser.error('Data root must be outside the repository')
root.mkdir(parents=True, exist_ok=True)
for name in ('database', 'redis', 'media', 'problems', 'backups'):
    folder = root / name
    folder.mkdir(exist_ok=True)
    if any(folder.iterdir()):
        parser.error(f'{folder} is not empty; refusing to reuse existing data')
values = {
    'COMPOSE_PROJECT_NAME': args.project,
    'MSOJ_ENV_FILE': str(env_path),
    'MSOJ_SITE_URL': args.site_url,
    'DJANGO_ALLOWED_HOSTS': ','.join(dict.fromkeys((origin.hostname, 'localhost', '127.0.0.1'))),
    'MSOJ_HTTP_PORT': str(args.http_port),
    'MSOJ_BRIDGE_PORT': str(args.bridge_port),
    'MSOJ_DB_DIR': str(root / 'database'),
    'MSOJ_REDIS_DIR': str(root / 'redis'),
    'MSOJ_MEDIA_DIR': str(root / 'media'),
    'MSOJ_PROBLEM_DIR': str(root / 'problems'),
    'MSOJ_BACKUP_DIR': str(root / 'backups'),
    'APP_UID': str(os.getuid()),
    'APP_GID': str(os.getgid()),
    'DJANGO_SECRET_KEY': secrets.token_urlsafe(64),
    'MARIADB_DATABASE': 'msoj',
    'MARIADB_USER': 'msoj',
    'MARIADB_PASSWORD': secrets.token_hex(32),
    'MARIADB_ROOT_PASSWORD': secrets.token_hex(32),
    'MSOJ_CLOUDFLARE_UPLOAD_WARNING': 'true',
}
# O_EXCL and 0600 from creation: credentials never briefly world-readable.
with os.fdopen(os.open(env_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as output:
    for key, value in values.items():
        output.write(f'{key}={shlex.quote(value)}\n')
print(f'Created private environment: {env_path}')
print(f'External bind data: {root}')
print('No existing database, settings, or problem data was changed.')
