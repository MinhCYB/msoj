#!/usr/bin/env python3
"""Run release checks against disposable Compose MariaDB, never the host database."""
import os
from pathlib import Path
import subprocess

from .ops import parse_env

root = Path(__file__).resolve().parent.parent
env_file = root / '.env.docker.ci'
data_root = (root / '..' / 'msoj_docker_ci').resolve()
compose = ['docker', 'compose', '--env-file', str(env_file)]

# A previous local run that died before cleanup leaves its env file and root-owned database files
# behind; setup.py refuses to reuse either. Remove only this CI project's leftovers.
if env_file.exists():
    subprocess.run(compose + ['down'], cwd=root, check=False)
    env_file.unlink()
if data_root.is_dir() and any(data_root.iterdir()):
    # Files were created by container users, so clear them from inside a container, not the host.
    subprocess.run(['docker', 'run', '--rm', '-v', f'{data_root}:/data',
                    'busybox:1.37@sha256:bdf57e528e45e4433820e045b29b4597825a1c9e38353532d90a01445013f82e',
                    'sh', '-c', 'rm -rf /data/* /data/.[!.]*'], check=True)
subprocess.run(['python3', 'docker/setup.py', '--env-file', '.env.docker.ci',
                '--data-root', str(data_root), '--project', 'msoj-ci',
                '--http-port', '18080', '--bridge-port', '19999',
                '--site-url', 'http://localhost:18080'], cwd=root, check=True)
values = parse_env(env_file)

try:
    subprocess.run(compose + ['up', '-d', '--wait', 'db', 'redis', 'cache', 'events'], cwd=root, check=True)
    subprocess.run(compose + ['run', '--rm', 'migrate'], cwd=root, check=True)
    subprocess.run(compose + ['run', '--rm', 'web', 'python', '-m', 'docker.bootstrap'], cwd=root, check=True)
    # Only this disposable CI invocation gets root to create/drop its test database.
    test_env = {**os.environ, 'MARIADB_PASSWORD': values['MARIADB_ROOT_PASSWORD']}
    subprocess.run(compose + ['run', '--rm', '--no-deps', '-e', 'MARIADB_USER=root', '-e', 'MARIADB_PASSWORD',
                              'web', 'python', 'manage.py', 'test', 'judge.tests.test_polygon_sync',
                              'mentor.tests_polygon_tag_mapping', 'ai_gateway.tests', '--noinput'],
                   cwd=root, env=test_env, check=True)
    subprocess.run(compose + ['up', '-d', '--wait'], cwd=root, check=True)
    subprocess.run(compose + ['exec', '-T', 'proxy', 'nginx', '-t'], cwd=root, check=True)
finally:
    subprocess.run(compose + ['down'], cwd=root, check=False)
    env_file.unlink(missing_ok=True)
