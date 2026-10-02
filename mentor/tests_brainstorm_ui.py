"""Workspace integration and static contract checks; no inference is invoked."""

from pathlib import Path
from html.parser import HTMLParser

from django.test import TestCase
from django.urls import reverse

from judge.models import Judge
from .models import BrainstormTurn

from .tests_brainstorm_service import BrainstormFixture


ROOT = Path(__file__).resolve().parent.parent


class LanguageOptions(HTMLParser):
    def __init__(self):
        super().__init__()
        self.options = []

    def handle_starttag(self, tag, attrs):
        if tag == 'option':
            self.options.append(dict(attrs))


class BrainstormWorkspaceTests(BrainstormFixture, TestCase):
    def test_problem_workspace_exposes_composer_editor_language_key_and_submit(self):
        self.problem.is_manually_managed = True
        self.problem.save(update_fields=['is_manually_managed'])
        judge = Judge.objects.create(name='brainstorm-ui', auth_key='test-only', online=True,
                                     storages=[self.problem.effective_storage])
        judge.runtimes.add(self.language)
        self.client.force_login(self.user)
        response = self.client.get(reverse('problem_detail', args=[self.problem.code]))
        self.assertEqual(response.status_code, 200)
        page = response.content.decode()
        self.assertIn('brainstorm.js?v=1', page)
        self.assertIn('problem-workspace.css?v=14', page)
        self.assertIn('ms-mentor-panel', page)
        self.assertIn('mã hiện tại trong trình soạn thảo sẽ được gửi tới AI', page)
        self.assertIn('id="ms-mentor-question"', page)
        self.assertIn('id="ms-mentor-approach"', page)
        self.assertIn('id="problem_submit"', page)
        self.assertIn('id="id_language"', page)
        self.assertIn('data-key="CLAIM"', page)
        options = LanguageOptions()
        options.feed(page)
        self.assertEqual(next(option['data-key'] for option in options.options
                              if option.get('value') == str(self.language.pk)), self.language.key)
        self.assertIn(reverse('mentor_brainstorm_send', args=[self.problem.code]), page)
        self.assertIn(reverse('mentor_brainstorm_post_turn', args=[self.problem.code]), page)
        self.assertIn(reverse('mentor_brainstorm_turn', args=[0]), page)
        self.assertNotIn('CHƯA KHẢ DỤNG', page)
        self.assertNotIn('[STUB]', page)
        self.assertEqual(BrainstormTurn.objects.count(), 0)

    def test_frontend_request_is_exact_and_untrusted_text_uses_textcontent(self):
        source = (ROOT / 'resources' / 'brainstorm.js').read_text()
        self.assertNotIn('innerHTML', source)
        self.assertNotIn('system_prompt', source)
        self.assertNotIn('provider:', source)
        self.assertNotIn('model:', source)
        self.assertNotIn('hint_level:', source)
        self.assertNotIn('scope_key:', source)
        self.assertIn('body.textContent = text', source)
        self.assertIn('editor.getSession().getValue()', source)
        self.assertIn('selected.dataset.key', source)
        self.assertIn('client_request_id: id', source)
        self.assertIn('sendTurn(ambiguous, generation)', source)
        self.assertIn('await loadSession(token)', source)
