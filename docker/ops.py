#!/usr/bin/env python3
"""Safe operational commands for the Compose deployment."""
import argparse
import gzip
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
COMPOSE = ROOT / 'compose.yaml'


def parse_env(path):
    values = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        try:
            fields = shlex.split(value, comments=True)
            values[key] = fields[0] if fields else ''
        except ValueError as exc:
            raise SystemExit(f'Invalid environment file line for {key}: {exc}')
    return values


def compose_args(env_file):
    return ['docker', 'compose', '--env-file', str(env_file), '-f', str(COMPOSE)]


def run_compose(env_file, *args, **kwargs):
    return subprocess.run(compose_args(env_file) + list(args), cwd=ROOT, check=True, **kwargs)


def image_is_release(image):
    if '@sha256:' in image:
        return bool(re.fullmatch(r'.+@sha256:[0-9a-f]{64}', image))
    if not image:
        return False
    final = image.rsplit('/', 1)[-1]
    if ':' not in final:
        return False
    tag = final.rsplit(':', 1)[1]
    return bool(re.fullmatch(r'[0-9a-f]{40}|sha-[0-9a-f]{40}|v?\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?', tag))


def deploy(env_file, allow_bridge_restart):
    env = parse_env(env_file)
    for key in ('MSOJ_APP_IMAGE', 'MSOJ_PROXY_IMAGE', 'MSOJ_EVENTS_IMAGE'):
        if not image_is_release(env.get(key, '')):
            raise SystemExit(f'{key} must name a release version tag or SHA-256 digest')
    if not allow_bridge_restart:
        raise SystemExit('Deploy requires --allow-bridge-restart: judges disconnect and in-progress submissions may finish as IE')
    print('WARNING: this deploy disconnects judges; in-progress submissions may finish as IE.', file=sys.stderr)
    run_compose(env_file, 'pull', 'web', 'worker', 'beat', 'bridge', 'proxy', 'events')
    run_compose(env_file, 'up', '-d', '--wait', 'db', 'redis', 'cache', 'events')
    run_compose(env_file, 'stop', 'web', 'worker', 'beat', 'bridge')
    backup(env_file, None)
    run_compose(env_file, 'run', '--rm', 'migrate')
    run_compose(env_file, 'up', '-d', 'web', 'worker', 'beat', 'bridge', 'proxy')




def backup(env_file, output):
    env = parse_env(env_file)
    backup_root = env.get('MSOJ_BACKUP_DIR')
    if not backup_root:
        raise SystemExit('MSOJ_BACKUP_DIR is not set')
    backup_dir = Path(backup_root).expanduser()
    backup_dir.mkdir(parents=True, exist_ok=True)
    destination = output or (backup_dir / f'msoj-db-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.sql.gz')
    destination = Path(destination).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f'.{destination.name}.', suffix='.tmp', dir=destination.parent)
    os.chmod(temp_name, 0o600)
    try:
        command = compose_args(env_file) + [
            'exec', '-T', 'db', 'sh', '-c',
            'MYSQL_PWD="$MARIADB_PASSWORD" exec mariadb-dump -u "$MARIADB_USER" --single-transaction --quick --routines --events "$MARIADB_DATABASE"',
        ]
        with os.fdopen(fd, 'wb') as raw, gzip.GzipFile(fileobj=raw, mode='wb') as compressed:
            process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE)
            try:
                while chunk := process.stdout.read(1024 * 1024):
                    compressed.write(chunk)
            finally:
                process.stdout.close()
            if process.wait():
                raise subprocess.CalledProcessError(process.returncode, command)
        os.replace(temp_name, destination)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise
    print(f'Database backup written: {destination}')
    print('This does not back up media/problem files or guarantee a coordinated filesystem snapshot.')


def restore(env_file, source, confirmed):
    if not confirmed:
        raise SystemExit('Restore is destructive; rerun with --confirm REPLACE DATABASE')
    source = Path(source).expanduser().resolve()
    if not source.is_file():
        raise SystemExit(f'Backup file not found: {source}')
    try:
        with gzip.open(source, 'rb') as dump:
            while dump.read(1024 * 1024):
                pass
    except (OSError, EOFError) as exc:
        raise SystemExit(f'Backup is not a valid complete gzip stream: {exc}') from exc

    run_compose(env_file, 'up', '-d', '--wait', 'db', 'redis', 'cache', 'events')
    run_compose(env_file, 'stop', 'proxy', 'web', 'worker', 'beat', 'bridge')
    backup(env_file, None)
    command = compose_args(env_file) + ['exec', '-T', 'db', 'sh', '-c', 'MYSQL_PWD="$MARIADB_PASSWORD" exec mariadb -u "$MARIADB_USER" "$MARIADB_DATABASE"']
    process = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.PIPE)
    try:
        with gzip.open(source, 'rb') as dump:
            while chunk := dump.read(1024 * 1024):
                process.stdin.write(chunk)
        process.stdin.close()
    except BaseException:
        process.stdin.close()
        process.wait()
        raise
    if process.wait():
        raise subprocess.CalledProcessError(process.returncode, command)
    print('Database import completed. Services remain stopped; inspect the site and start services manually when ready.')
    print('Import does not remove tables absent from the dump. Restore media/problem files separately if required.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', default='.env.docker', type=Path)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('bootstrap', help='seed an empty install and configure Site')
    backup_parser = commands.add_parser('backup', help='write a compressed database dump')
    backup_parser.add_argument('--output', type=Path)
    deploy_parser = commands.add_parser('deploy', help='pull tagged images, migrate, and update services')
    deploy_parser.add_argument('--allow-bridge-restart', action='store_true')
    restore_parser = commands.add_parser('restore', help='replace the database from a gzip dump')
    restore_parser.add_argument('backup', type=Path)
    restore_parser.add_argument('--confirm', choices=['REPLACE DATABASE'])
    args = parser.parse_args()
    env_file = args.env_file.expanduser().resolve()
    if not env_file.is_file():
        parser.error(f'environment file does not exist: {env_file}')
    if args.command == 'bootstrap':
        run_compose(env_file, 'run', '--rm', 'web', 'python', '-m', 'docker.bootstrap')
        print('Bootstrap complete. Create the first admin with: docker compose --env-file', env_file,
              '-f', COMPOSE, 'run --rm web python manage.py createsuperuser')
        print('Then run this bootstrap command again to ensure that account has a Profile.')
    elif args.command == 'backup':
        backup(env_file, args.output)
    elif args.command == 'deploy':
        deploy(env_file, args.allow_bridge_restart)
    elif args.command == 'restore':
        restore(env_file, args.backup, args.confirm == 'REPLACE DATABASE')


if __name__ == '__main__':
    main()
