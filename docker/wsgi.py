"""Container WSGI entrypoint with a private readiness endpoint."""
from ipaddress import ip_address
from dmoj.wsgi import application as django_application
from django.db import connection


def application(environ, start_response):
    # Only nginx can expose this internal HTTP application to users. Nginx
    # overwrites X-Real-IP; never trust a client-supplied forwarding chain.
    forwarded_ip = environ.get('HTTP_X_REAL_IP')
    if forwarded_ip:
        try:
            environ['REMOTE_ADDR'] = str(ip_address(forwarded_ip))
        except ValueError:
            pass
    if environ.get('PATH_INFO') != '/_healthz':
        return django_application(environ, start_response)
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
    except Exception:
        start_response('503 Service Unavailable', [('Content-Type', 'text/plain'), ('Cache-Control', 'no-store')])
        return [b'unavailable\n']
    start_response('200 OK', [('Content-Type', 'text/plain'), ('Cache-Control', 'no-store')])
    return [b'ok\n']
