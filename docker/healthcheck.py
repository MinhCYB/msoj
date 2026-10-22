"""Read-only container liveness checks (no DB mutations)."""
import os
import socket
import sys
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


kind = sys.argv[1]
if kind == 'web':
    host = urlsplit(os.environ.get('MSOJ_SITE_URL', 'http://localhost:8080')).netloc
    request = Request('http://127.0.0.1:8000/_healthz', headers={'Host': host})
    with urlopen(request, timeout=5) as response:
        if response.status != 200:
            sys.exit(1)
elif kind == 'bridge':
    with socket.create_connection(('127.0.0.1', 9998), timeout=3):
        pass
elif kind == 'worker':
    from dmoj_celery import app
    replies = app.control.ping(destination=[f'worker@{socket.gethostname()}'], timeout=5)
    sys.exit(0 if replies else 1)
else:
    raise SystemExit('Unknown healthcheck')
