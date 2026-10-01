class GatewayError(Exception):
    code = 'gateway_error'
    retryable = False


class ConfigurationError(GatewayError):
    code = 'not_configured'


class AuthenticationError(GatewayError):
    code = 'authentication_failed'


class RateLimitError(GatewayError):
    code = 'rate_limited'
    retryable = True


class UpstreamError(GatewayError):
    code = 'upstream_unavailable'
    retryable = True


class TimeoutError(GatewayError):
    code = 'timeout'
    retryable = True


class InvalidResponseError(GatewayError):
    code = 'invalid_response'
