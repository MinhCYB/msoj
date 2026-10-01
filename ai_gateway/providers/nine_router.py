import json
import time

import requests

from ai_gateway.errors import (AuthenticationError, InvalidResponseError, RateLimitError, TimeoutError,
                               UpstreamError)
from ai_gateway.types import GatewayEvent, GatewayResult, ModelCatalog, Usage

from .base import AIProvider


def _usage(data):
    if not isinstance(data, dict):
        return None
    return Usage(data.get('prompt_tokens'), data.get('completion_tokens'), data.get('total_tokens'))


class NineRouterProvider(AIProvider):
    def __init__(self, connection, api_key):
        self.connection = connection
        self.api_key = api_key

    def _url(self, path):
        return self.connection.base_url.rstrip('/') + path

    def _headers(self):
        return {'Authorization': 'Bearer ' + self.api_key, 'Content-Type': 'application/json'}

    def _request(self, method, path, *, body=None, stream=False):
        for attempt in range(self.connection.retries + 1):
            try:
                response = requests.request(method, self._url(path), headers=self._headers(), json=body,
                                            timeout=(self.connection.connect_timeout_seconds,
                                                     self.connection.read_timeout_seconds), stream=stream,
                                            allow_redirects=False)
            except requests.exceptions.Timeout as exc:
                if attempt < self.connection.retries:
                    continue
                raise TimeoutError('AI provider timed out.') from exc
            except requests.exceptions.RequestException as exc:
                if attempt < self.connection.retries:
                    continue
                raise UpstreamError('AI provider is unavailable.') from exc
            if response.status_code in (401, 403):
                response.close()
                raise AuthenticationError('AI provider rejected its credential.')
            if response.status_code == 429:
                response.close()
                if attempt < self.connection.retries:
                    time.sleep(min(2 ** attempt, 2))
                    continue
                raise RateLimitError('AI provider rate limit reached.')
            if response.status_code >= 500:
                response.close()
                if attempt < self.connection.retries:
                    time.sleep(min(2 ** attempt, 2))
                    continue
                raise UpstreamError('AI provider is unavailable.')
            if 300 <= response.status_code < 400:
                response.close()
                raise InvalidResponseError('AI provider unexpectedly redirected the request.')
            if not response.ok:
                response.close()
                raise InvalidResponseError('AI provider rejected the request.')
            return response
        raise UpstreamError('AI provider is unavailable.')

    @staticmethod
    def _messages(messages):
        allowed = {'system', 'user', 'assistant', 'tool'}
        result = []
        for message in messages:
            item = message if isinstance(message, dict) else {'role': message.role, 'content': message.content}
            if item.get('role') not in allowed or 'content' not in item:
                raise ValueError('Invalid AI message.')
            result.append(dict(item))
        if not result:
            raise ValueError('AI messages cannot be empty.')
        return result

    def _body(self, model_id, messages, options, streaming):
        allowed = {'temperature', 'top_p', 'max_tokens', 'tools', 'tool_choice', 'stop'}
        if set(options) - allowed:
            raise ValueError('Unsupported AI provider option.')
        body = {'model': model_id, 'messages': self._messages(messages), 'stream': streaming}
        body.update({key: value for key, value in options.items() if value is not None})
        if streaming:
            body['stream_options'] = {'include_usage': True}
        return body

    def generate(self, model_id, messages, **options):
        response = self._request('POST', '/chat/completions', body=self._body(model_id, messages, options, False))
        try:
            data = response.json()
            choice = data['choices'][0]
            answer = choice['message']
            if not isinstance(answer.get('content'), (str, type(None))):
                raise ValueError('Invalid content')
            return GatewayResult(text=answer.get('content') or '', provider=self.connection.slug,
                                 requested_model=model_id, returned_model=data.get('model'),
                                 finish_reason=choice.get('finish_reason'), usage=_usage(data.get('usage')),
                                 tool_calls=answer.get('tool_calls') or [])
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise InvalidResponseError('AI provider returned an invalid response.') from exc
        finally:
            response.close()

    def stream(self, model_id, messages, **options):
        body = self._body(model_id, messages, options, True)
        return self._stream(body, model_id)

    def _stream(self, body, model_id):
        response = self._request('POST', '/chat/completions', body=body, stream=True)
        try:
            if 'text/event-stream' not in response.headers.get('Content-Type', '').lower():
                raise InvalidResponseError('AI provider did not return SSE.')
            parts = []
            tool_calls = {}
            usage = None
            returned_model = None
            finish_reason = None
            done = False
            frame = []
            for raw_line in response.iter_lines(decode_unicode=True):
                line = raw_line.decode('utf-8') if isinstance(raw_line, bytes) else raw_line
                if line:
                    if line.startswith('data:'):
                        frame.append(line[5:].strip())
                    continue
                if not frame:
                    continue
                payload = '\n'.join(frame)
                frame = []
                if payload == '[DONE]':
                    done = True
                    break
                try:
                    event = json.loads(payload)
                    if not isinstance(event, dict):
                        raise ValueError('Invalid SSE payload')
                    if 'error' in event:
                        raise UpstreamError('AI provider stream failed.')
                    returned_model = event.get('model') or returned_model
                    usage = _usage(event.get('usage')) or usage
                    for choice in event.get('choices', []):
                        finish_reason = choice.get('finish_reason') or finish_reason
                        delta = choice.get('delta') or {}
                        text = delta.get('content') or ''
                        if text:
                            parts.append(text)
                            yield GatewayEvent(type='text', text=text)
                        for call in delta.get('tool_calls') or []:
                            index = call['index']
                            target = tool_calls.setdefault(index, {'id': '', 'type': 'function',
                                                                   'function': {'name': '', 'arguments': ''}})
                            target['id'] += call.get('id') or ''
                            function = call.get('function') or {}
                            target['function']['name'] += function.get('name') or ''
                            target['function']['arguments'] += function.get('arguments') or ''
                except (ValueError, TypeError, KeyError, IndexError) as exc:
                    raise InvalidResponseError('AI provider returned an invalid SSE event.') from exc
            if not done:
                raise InvalidResponseError('AI provider stream ended without completion.')
            calls = [tool_calls[index] for index in sorted(tool_calls)]
            for call in calls:
                yield GatewayEvent(type='tool_call', tool_call=call)
            yield GatewayEvent(type='done', result=GatewayResult(''.join(parts), self.connection.slug, model_id,
                                                               returned_model, finish_reason, usage, calls))
        except requests.exceptions.Timeout as exc:
            raise TimeoutError('AI provider stream timed out.') from exc
        except requests.exceptions.RequestException as exc:
            raise UpstreamError('AI provider stream failed.') from exc
        finally:
            response.close()

    def list_models(self):
        response = self._request('GET', '/models')
        try:
            data = response.json()
            if not isinstance(data, dict) or data.get('object') != 'list' or not isinstance(data.get('data'), list):
                raise ValueError('Invalid catalog')
            ids = []
            for item in data['data']:
                if not isinstance(item, dict) or not isinstance(item.get('id'), str) or not item['id']:
                    raise ValueError('Invalid model ID')
                if item['id'] not in ids:
                    ids.append(item['id'])
            return ModelCatalog(tuple(ids))
        except (ValueError, TypeError, KeyError) as exc:
            raise InvalidResponseError('AI provider returned an invalid model catalog.') from exc
        finally:
            response.close()
