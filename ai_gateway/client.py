import os

from .errors import ConfigurationError
from .models import ModelRoute
from .providers.nine_router import NineRouterProvider


PROVIDERS = {'nine_router': NineRouterProvider}


def _resolve(role):
    route = ModelRoute.objects.select_related('connection').filter(role=role, enabled=True,
                                                                  connection__enabled=True).first()
    if route is None:
        raise ConfigurationError('AI model route is not enabled.')
    connection = route.connection
    key = os.environ.get(connection.api_key_env)
    if not key:
        raise ConfigurationError('AI provider credential is not configured.')
    provider_type = PROVIDERS.get(connection.adapter)
    if provider_type is None:
        raise ConfigurationError('Unknown AI provider adapter.')
    return provider_type(connection, key), route.model_id


def generate(role, messages, **options):
    provider, model_id = _resolve(role)
    return provider.generate(model_id, messages, **options)


def stream(role, messages, **options):
    provider, model_id = _resolve(role)
    return provider.stream(model_id, messages, **options)


def list_models(connection):
    if not connection.enabled:
        raise ConfigurationError('AI provider is not enabled.')
    key = os.environ.get(connection.api_key_env)
    if not key:
        raise ConfigurationError('AI provider credential is not configured.')
    provider_type = PROVIDERS.get(connection.adapter)
    if provider_type is None:
        raise ConfigurationError('Unknown AI provider adapter.')
    return provider_type(connection, key).list_models()
