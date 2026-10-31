"""Behavioral boundaries for stateless learner trace regeneration."""
import json

from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .visual_documents import convert_legacy


@override_settings(SECURE_SSL_REDIRECT=False)
class VisualCompileEndpointTests(TestCase):
    def document(self):
        return convert_legacy({
            'version': 1, 'type': 'for-loop',
            'input': {'start': 1, 'end': 4, 'step': 1},
        })

    def test_recompile_changes_result_without_writing_or_reusing_old_trace(self):
        document = self.document()
        response = self.client.post(reverse('roadmap_visual_compile'), json.dumps({
            'document': document, 'input': {'start': 2, 'end': 6, 'step': 2},
        }), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        compiled = response.json()
        self.assertEqual(compiled['document']['timeline']['input'], {'start': 2, 'end': 6, 'step': 2})
        self.assertEqual(compiled['frames'][-2]['output'], '12\n')
        self.assertEqual(document['timeline']['input'], {'start': 1, 'end': 4, 'step': 1})
        self.assertEqual(response['Cache-Control'], 'no-store')

    def test_invalid_input_and_duplicate_envelope_keys_are_not_compiled(self):
        url = reverse('roadmap_visual_compile')
        for value in [True, 0, -1, 6]:
            with self.subTest(step=value):
                response = self.client.post(url, json.dumps({
                    'document': self.document(), 'input': {'start': 1, 'end': 4, 'step': value},
                }), content_type='application/json')
                self.assertEqual(response.status_code, 400)
                self.assertNotIn('frames', response.json())
        duplicate = '{"document":{},"document":{},"input":{}}'
        response = self.client.post(url, duplicate, content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_csrf_and_request_size_limits_apply_without_staff_privilege(self):
        response = Client(enforce_csrf_checks=True).post(
            reverse('roadmap_visual_compile'), json.dumps({'document': self.document(), 'input': {}}),
            content_type='application/json')
        self.assertRedirects(response, reverse('roadmap_visual_compile'), fetch_redirect_response=False)
        response = self.client.post(reverse('roadmap_visual_compile'), ' ' * (128 * 1024 + 1), content_type='application/json')
        self.assertEqual(response.status_code, 413)
        response = self.client.get(reverse('roadmap_visual_compile'))
        self.assertEqual(response.status_code, 405)

    def test_malformed_controls_are_rejected_without_server_error(self):
        document = self.document()
        for controls in ([1], {'bad': 1}, None):
            with self.subTest(controls=controls):
                document['controls'] = controls
                response = self.client.post(reverse('roadmap_visual_compile'), json.dumps({
                    'document': document, 'input': {'start': 1, 'end': 4, 'step': 1},
                }), content_type='application/json')
                self.assertEqual(response.status_code, 400)
                self.assertNotIn('frames', response.json())

