import os
import re
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.db import models


def validate_base_url(value):
    url = urlsplit(value)
    if (url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment
            or url.path.rstrip('/') != '/v1'):
        raise ValidationError('Base URL must be an HTTPS /v1 API root without credentials, query or fragment.')


class ProviderConnection(models.Model):
    NINE_ROUTER = 'nine_router'
    ADAPTER_CHOICES = ((NINE_ROUTER, '9Router (OpenAI-compatible)'),)

    slug = models.SlugField(unique=True)
    adapter = models.CharField(max_length=32, choices=ADAPTER_CHOICES, default=NINE_ROUTER)
    base_url = models.URLField(help_text='API root, e.g. https://router.example/v1', validators=[validate_base_url])
    api_key_env = models.CharField(max_length=128, help_text='Name of a server environment variable; never the key itself.')
    enabled = models.BooleanField(default=False)
    connect_timeout_seconds = models.PositiveSmallIntegerField(default=5)
    read_timeout_seconds = models.PositiveSmallIntegerField(default=60)
    retries = models.PositiveSmallIntegerField(default=1)

    def clean(self):
        super().clean()
        if self.api_key_env and not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', self.api_key_env):
            raise ValidationError({'api_key_env': 'Enter a valid environment variable name.'})
        if self.connect_timeout_seconds < 1 or self.read_timeout_seconds < 1 or self.retries > 3:
            raise ValidationError('Timeouts must be positive and retries must be at most 3.')

    def __str__(self):
        return self.slug

    @property
    def has_api_key(self):
        return bool(os.environ.get(self.api_key_env))


class ModelRoute(models.Model):
    role = models.SlugField(unique=True, help_text='Logical role used by feature services.')
    connection = models.ForeignKey(ProviderConnection, on_delete=models.PROTECT, related_name='routes')
    model_id = models.CharField(max_length=200, help_text='Opaque model or combo ID sent in body.model.')
    enabled = models.BooleanField(default=False)

    def __str__(self):
        return self.role
