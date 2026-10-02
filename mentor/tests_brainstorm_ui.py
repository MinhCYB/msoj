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
        self.assertIn('brainstorm.js?v=3', page)
        self.assertIn('problem-workspace.js?v=8', page)
        self.assertIn('problem-workspace.css?v=17', page)
        self.assertIn('class="ms-workspace-rail-nav"', page)
        self.assertIn('class="ms-workspace-tools"', page)
        nav = page.split('class="ms-workspace-rail-nav"', 1)[1].split('class="ms-workspace-tools"', 1)[0]
        tools = page.split('class="ms-workspace-tools"', 1)[1].split('</nav>', 1)[0]
        self.assertIn('href="#ms-statement"', nav)
        self.assertIn('href="#comments"', nav)
        self.assertNotIn('ms-mentor-launch', nav)
        self.assertNotIn('ms-annotate-launch', nav)
        self.assertIn('class="ms-annotate-launch"', tools)
        self.assertIn('class="ms-mentor-launch"', tools)
        self.assertIn('ms-mentor-panel', page)
        self.assertIn('Mentor sẽ sử dụng mã hiện tại trong trình soạn thảo để hiểu câu hỏi của bạn.', page)
        self.assertIn('class="ms-mentor-tooltip"', page)
        self.assertIn('class="ms-mentor-info-button"', page)
        header = page.split('<header class="ms-mentor-header">', 1)[1].split('</header>', 1)[0]
        composer = page.split('<form class="ms-mentor-composer">', 1)[1].split('</form>', 1)[0]
        self.assertIn('class="ms-mentor-info-button"', header)
        self.assertNotIn('class="ms-mentor-info"', composer)
        self.assertIn('class="ms-mentor-input"', composer)
        self.assertIn('class="ms-mentor-send"', composer)
        self.assertNotIn('ms-mentor-composer-footer', composer)
        self.assertIn('id="ms-mentor-question"', page)
        self.assertIn('placeholder="Hỏi Mentor về bài này..."', page)
        self.assertIn('class="ms-mentor-send"', page)
        self.assertIn('aria-label="Gửi câu hỏi cho Mentor"', page)
        self.assertIn('aria-label="Hỏi Mentor về bài này"', page)
        self.assertNotIn('Tin nhắn gửi AI Mentor', page)
        self.assertNotIn('ms-mentor-disclosure', page)
        self.assertIn('data-mentor="minimize"', page)
        self.assertIn('data-mentor="close"', page)
        for edge in ('top', 'right', 'corner'):
            self.assertIn(f'data-resize="{edge}"', page)
        self.assertNotIn('class="ms-mentor-resize"', page)
        self.assertNotIn('id="ms-mentor-approach"', page)
        self.assertNotIn('ms-mentor-hint', page)
        self.assertNotIn('Mức gợi ý', page)
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
        self.assertIn('approach: ""', source)
        self.assertNotIn('approach.value', source)
        self.assertNotIn('pair.hint_level', source)
        self.assertIn('sendTurn(ambiguous, generation)', source)
        self.assertIn('await loadSession(token)', source)
