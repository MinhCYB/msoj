from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase

from . import client
from .errors import AuthenticationError, InvalidResponseError
from .models import ModelRoute, ProviderConnection
from .providers.nine_router import NineRouterProvider
from .types import Message, ModelCatalog


class NineRouterProviderTests(SimpleTestCase):
    def setUp(self):
        connection = SimpleNamespace(base_url='https://router.example/v1/', slug='router',
                                     retries=0, connect_timeout_seconds=3, read_timeout_seconds=10)
        self.provider = NineRouterProvider(connection, 'test-key')

    @patch('ai_gateway.providers.nine_router.requests.request')
    def test_generate_contract(self, request):
        response = Mock(status_code=200, ok=True)
        response.json.return_value = {'model': 'actual-model', 'choices': [
            {'message': {'content': 'hint'}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 2, 'completion_tokens': 3, 'total_tokens': 5}}
        request.return_value = response
        result = self.provider.generate('combo-id', [Message('system', 'policy'), Message('user', 'code')])
        args, kwargs = request.call_args
        self.assertEqual(args, ('POST', 'https://router.example/v1/chat/completions'))
        self.assertEqual(kwargs['json'], {'model': 'combo-id', 'messages': [
            {'role': 'system', 'content': 'policy'}, {'role': 'user', 'content': 'code'}], 'stream': False})
        self.assertEqual(kwargs['headers']['Authorization'], 'Bearer test-key')
        self.assertEqual((result.text, result.requested_model, result.returned_model),
                         ('hint', 'combo-id', 'actual-model'))
        self.assertEqual(result.usage.total_tokens, 5)
        response.close.assert_called_once()

    @patch('ai_gateway.providers.nine_router.requests.request')
    def test_stream_contract_and_usage(self, request):
        response = Mock(status_code=200, ok=True, headers={'Content-Type': 'text/event-stream'})
        response.iter_lines.return_value = iter([
            b'data: {"choices":[{"delta":{"content":"hello"}}]}', b'',
            b'data: {"choices":[{"finish_reason":"stop","delta":{}}],"usage":{"prompt_tokens":1}}',
            b'', b'data: [DONE]', b'',
        ])
        request.return_value = response
        events = list(self.provider.stream('combo-id', [Message('user', 'hi')]))
        self.assertEqual([event.type for event in events], ['text', 'done'])
        self.assertEqual(events[-1].result.text, 'hello')
        self.assertEqual(events[-1].result.usage.input_tokens, 1)
        self.assertTrue(request.call_args.kwargs['json']['stream'])
        self.assertTrue(request.call_args.kwargs['stream'])
        response.close.assert_called_once()

    @patch('ai_gateway.providers.nine_router.requests.request')
    def test_catalog_and_authentication(self, request):
        response = Mock(status_code=200, ok=True)
        response.json.return_value = {'object': 'list', 'data': [
            {'id': 'prod', 'object': 'model'}, {'id': 'model'}, {'id': 'prod'}]}
        request.return_value = response
        catalog = self.provider.list_models()
        self.assertEqual(catalog.ids, ('prod', 'model'))
        self.assertTrue(catalog.contains('prod'))
        self.assertFalse(catalog.contains('missing'))
        self.assertEqual(request.call_args.args, ('GET', 'https://router.example/v1/models'))
        request.return_value = Mock(status_code=401)
        with self.assertRaises(AuthenticationError):
            self.provider.list_models()

    @patch('ai_gateway.providers.nine_router.requests.request')
    def test_malformed_catalog_is_rejected(self, request):
        response = Mock(status_code=200, ok=True)
        response.json.return_value = {'object': 'list', 'data': [{'id': None}]}
        request.return_value = response
        with self.assertRaises(InvalidResponseError):
            self.provider.list_models()
        response.close.assert_called_once()

    @patch('ai_gateway.providers.nine_router.requests.request')
    def test_incomplete_stream_is_rejected(self, request):
        response = Mock(status_code=200, ok=True, headers={'Content-Type': 'text/event-stream'})
        response.iter_lines.return_value = iter([b'data: {"choices":[{"delta":{"content":"partial"}}]}', b''])
        request.return_value = response
        with self.assertRaises(InvalidResponseError):
            list(self.provider.stream('model', [Message('user', 'hi')]))

    @patch('ai_gateway.providers.nine_router.requests.request')
    def test_stream_reassembles_function_call(self, request):
        response = Mock(status_code=200, ok=True, headers={'Content-Type': 'text/event-stream'})
        response.iter_lines.return_value = iter([
            b'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_1","function":{"name":"lookup","arguments":"{\\"id\\":"}}]}}]}', b'',
            b'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"2}"}}]},"finish_reason":"tool_calls"}]}', b'',
            b'data: [DONE]', b'',
        ])
        request.return_value = response
        events = list(self.provider.stream('combo-id', [Message('user', 'hi')]))
        self.assertEqual([event.type for event in events], ['tool_call', 'done'])
        self.assertEqual(events[0].tool_call['function']['arguments'], '{"id":2}')
        self.assertEqual(events[-1].result.finish_reason, 'tool_calls')

    @patch('ai_gateway.providers.nine_router.requests.request')
    def test_redirect_is_not_followed(self, request):
        request.return_value = Mock(status_code=302, ok=True)
        with self.assertRaises(InvalidResponseError):
            self.provider.list_models()
        self.assertFalse(request.call_args.kwargs['allow_redirects'])


class GatewayRoutingTests(TestCase):
    @patch.dict('os.environ', {'MSOJ_TEST_AI_KEY': 'not-a-real-key'})
    @patch('ai_gateway.providers.nine_router.requests.request')
    def test_role_resolves_connection_and_model(self, request):
        connection = ProviderConnection.objects.create(slug='router', base_url='https://router.example/v1',
                                                       api_key_env='MSOJ_TEST_AI_KEY', enabled=True)
        ModelRoute.objects.create(role='review_default', connection=connection, model_id='combo', enabled=True)
        response = Mock(status_code=200, ok=True)
        response.json.return_value = {'choices': [{'message': {'content': 'ok'}, 'finish_reason': 'stop'}]}
        request.return_value = response
        result = client.generate('review_default', [Message('user', 'test')])
        self.assertEqual(result.text, 'ok')
        self.assertEqual(request.call_args.kwargs['json']['model'], 'combo')
        self.assertFalse(request.call_args.kwargs['allow_redirects'])

    @patch('ai_gateway.management.commands.ai_gateway_smoke.client.generate')
    @patch('ai_gateway.management.commands.ai_gateway_smoke.client.list_models')
    def test_discovery_smoke_does_not_generate_without_explicit_confirmation(self, list_models, generate):
        connection = ProviderConnection.objects.create(slug='router', base_url='https://router.example/v1',
                                                       api_key_env='MSOJ_TEST_AI_KEY', enabled=True)
        ModelRoute.objects.create(role='review_default', connection=connection, model_id='combo', enabled=True)
        list_models.return_value = ModelCatalog(('combo',))
        output = StringIO()
        call_command('ai_gateway_smoke', connection='router', role='review_default', stdout=output)
        self.assertIn('Selected model in catalog: YES', output.getvalue())
        generate.assert_not_called()
        with self.assertRaises(CommandError):
            call_command('ai_gateway_smoke', connection='router', role='review_default', generate=True,
                         stdout=StringIO())
        generate.assert_not_called()

    @patch('ai_gateway.management.commands.ai_gateway_smoke.client.generate')
    @patch('ai_gateway.management.commands.ai_gateway_smoke.client.list_models')
    def test_paid_smoke_uses_short_system_and_user_messages(self, list_models, generate):
        connection = ProviderConnection.objects.create(slug='router', base_url='https://router.example/v1',
                                                       api_key_env='MSOJ_TEST_AI_KEY', enabled=True)
        ModelRoute.objects.create(role='review_default', connection=connection, model_id='combo', enabled=True)
        list_models.return_value = ModelCatalog(('combo',))
        generate.return_value = SimpleNamespace(requested_model='combo', returned_model=None,
                                                 text='OK', finish_reason='stop', usage=None)
        output = StringIO()
        call_command('ai_gateway_smoke', connection='router', role='review_default', generate=True,
                     confirm_paid_request=True, stdout=output)
        generate.assert_called_once_with('review_default', [Message('system', 'Reply with exactly: OK'),
                                                            Message('user', 'ping')], max_tokens=8)
        self.assertIn("text='OK'", output.getvalue())
