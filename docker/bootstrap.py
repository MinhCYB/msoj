#!/usr/bin/env python3
"""Idempotently seed empty installation tables and align the Django Site."""
import os
import json
from pathlib import Path
from urllib.parse import urlsplit

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dmoj.settings')

import django

django.setup()

from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.core.management import call_command
from django.db import transaction

from judge.models import Language, NavigationBar, ProblemGroup, ProblemType, Profile


@transaction.atomic
def bootstrap():
    # AppConfig.ready creates a PY3 placeholder before bootstrap; do not let that
    # suppress the runtime catalog. Match by language key, never overwrite IDs
    # already referenced by Profiles or submissions.
    if not Language.objects.exclude(key='PY3').exists():
        fixture = Path(__file__).resolve().parents[1] / 'judge/fixtures/language_all.json'
        for entry in json.loads(fixture.read_text()):
            fields = entry['fields'].copy()
            key = fields.pop('key')
            Language.objects.get_or_create(key=key, defaults=fields)
    if not NavigationBar.objects.exists():
        call_command('loaddata', 'navbar.json', verbosity=0)
    if not ProblemGroup.objects.exists():
        ProblemGroup.objects.create(name='Uncategorized', full_name='Uncategorized')
    if not ProblemType.objects.exists():
        ProblemType.objects.create(name='Uncategorized', full_name='Uncategorized')

    url = urlsplit(os.environ.get('MSOJ_SITE_URL', 'http://localhost:8080'))
    if not url.hostname:
        raise ValueError('MSOJ_SITE_URL must contain a hostname')
    site, _ = Site.objects.get_or_create(id=1, defaults={'domain': url.netloc, 'name': 'MSOJ'})
    site.domain = url.netloc
    site.name = os.environ.get('MSOJ_SITE_NAME', 'MSOJ')
    site.save(update_fields=('domain', 'name'))

    from django.conf import settings
    language = Language.objects.filter(key=settings.DEFAULT_USER_LANGUAGE).first()
    if language is None and settings.DEFAULT_USER_LANGUAGE == 'CPP20':
        cpp17 = Language.objects.get(key='CPP17')
        fields = {field.name: getattr(cpp17, field.name) for field in Language._meta.fields
                  if field.name not in ('id', 'key')}
        fields.update(name='C++20', short_name='C++20', description='C++20 executor on the judge host.')
        language, _ = Language.objects.get_or_create(key='CPP20', defaults=fields)
    if language is None:
        raise RuntimeError('Configured DEFAULT_USER_LANGUAGE is absent; register it before creating users')
    if language is not None:
        for user in User.objects.filter(is_superuser=True).iterator():
            Profile.objects.get_or_create(user=user, defaults={'language': language})

if __name__ == '__main__':
    bootstrap()
