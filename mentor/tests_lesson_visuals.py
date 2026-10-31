import json
from io import StringIO

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from lxml import html

from .lesson_visuals import render_lesson_markdown, validate_visual_blocks
from .roadmap_models import TopicLesson
from .visual_documents import convert_legacy
from .tests_roadmap import RoadmapFixture


def block(config):
    return '```msoj-visual\n' + json.dumps(config) + '\n```'


class LessonVisualTests(SimpleTestCase):
    def config(self, **changes):
        legacy = {'type': 'for-loop', 'version': 1, 'input': {'start': 1, 'end': 4, 'step': 1}, **changes}
        try:
            return convert_legacy(legacy)
        except ValueError:
            return legacy

    def test_multiple_blocks_preserve_prose_and_configuration_without_executable_markup(self):
        text = '# Before\n\n' + block(self.config()) + '\n\n**Between**\n\n' + block(self.config(allow_input_edit=False))
        tree = html.fragment_fromstring(str(render_lesson_markdown(text)), create_parent=True)
        widgets = tree.xpath('.//section[@data-visual-config]')
        self.assertEqual([json.loads(w.get('data-visual-config'))['document']['timeline']['input'] for w in widgets], [{'start': 1, 'end': 4, 'step': 1}] * 2)
        self.assertEqual(tree.find('h3').text, 'Before')
        self.assertEqual(tree.find('.//strong').text, 'Between')
        self.assertEqual(tree.xpath('.//script|.//*[@onclick]'), [])

    def test_rejects_executable_unknown_and_unbounded_inputs(self):
        bad = [self.config(type='javascript'), self.config(version=True), self.config(input={'start': 0, 'end': 4, 'step': 0}),
               self.config(input={'start': True, 'end': 4, 'step': 1}), self.config(script='alert(1)'),
               {'type': 'bfs', 'version': 1, 'input': {'n': 3, 'source': 0, 'edges': [[0, 1], [1, 0]]}},
               {'type': 'bfs', 'version': 1, 'input': {'n': 9, 'source': 0, 'edges': []}},
               {'type': 'dp-bitmask-matching', 'version': 1, 'input': {'matrix': [[1, 0]]}},
               {'type': 'dfs', 'version': 1, 'input': {'n': 3, 'source': 0, 'edges': [[0, 1], [1, 0]]}},
               {'type': 'dfs', 'version': 1, 'input': {'n': 3, 'source': True, 'edges': []}},
               {'type': 'matrix-chain', 'version': 1, 'input': {'dimensions': [10]}},
               {'type': 'matrix-chain', 'version': 1, 'input': {'dimensions': [10, True]}},
               {'type': 'dp-bitmask-matching', 'version': 1, 'input': {'matrix': [[True]]}}]
        for config in bad:
            with self.subTest(config=config), self.assertRaises(ValidationError):
                validate_visual_blocks(block(config))
        with self.assertRaises(ValidationError):
            validate_visual_blocks('\n\n'.join([block(self.config())] * 13))

    def test_literal_documentation_fence_is_not_mounted(self):
        for language in ('markdown', 'some-language title="example"'):
            text = '````' + language + '\n' + block(self.config()) + '\n````\n'
            tree = html.fragment_fromstring(str(render_lesson_markdown(text)), create_parent=True)
            self.assertEqual(tree.xpath('.//section[@data-visual-config]'), [])

    def test_invalid_saved_block_does_not_break_surrounding_lesson_or_execute_content(self):
        value = 'Before\n\n```msoj-visual\n{"type":"</section><script>alert(1)</script>"}\n```\n\nAfter'
        tree = html.fragment_fromstring(str(render_lesson_markdown(value)), create_parent=True)
        self.assertEqual(tree.xpath('.//script'), [])
        self.assertIn('Before', tree.text_content())
        self.assertIn('After', tree.text_content())
        self.assertTrue(tree.xpath('.//p[@class="mv-error"]'))
        with self.assertRaises(ValidationError):
            validate_visual_blocks('```msoj-visual\n{}')


class LessonVisualIntegrationTests(RoadmapFixture, TestCase):
    def test_invalid_block_is_rejected_on_save_without_losing_existing_body(self):
        lesson = TopicLesson.objects.create(topic=self.topic, title='Visual', slug='visual', body='Original')
        lesson.body = '```msoj-visual\n{"type":"unknown"}\n```'
        with self.assertRaises(ValidationError):
            lesson.save()
        lesson.refresh_from_db()
        self.assertEqual(lesson.body, 'Original')

    def test_preview_requires_author_permission_and_never_creates_lessons(self):
        self.client.force_login(self.learner)
        self.assertEqual(self.client.post('/roadmap/markdown-preview/', {'content': 'x', 'interactive_preview': '1'}).status_code, 403)
        self.client.force_login(self.staff)
        before = TopicLesson.objects.count()
        response = self.client.post('/roadmap/markdown-preview/', {'content': block(convert_legacy({'type': 'bfs', 'version': 1, 'input': {'n': 1, 'edges': [], 'source': 0}})), 'interactive_preview': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertEqual(TopicLesson.objects.count(), before)
        tree = html.fromstring(response.content)
        self.assertEqual(json.loads(tree.xpath('.//section[@data-visual-config]')[0].get('data-visual-config'))['document']['timeline']['input']['n'], 1)

    def test_sample_seed_dry_run_and_reapply_preserve_edited_content(self):
        before = TopicLesson.objects.count()
        call_command('seed_interactive_lessons', stdout=StringIO())
        self.assertEqual(TopicLesson.objects.count(), before)
        with self.settings(DEBUG=True):
            call_command('seed_interactive_lessons', apply=True, development=True, user=self.staff.username, stdout=StringIO())
            lesson = TopicLesson.objects.get(topic__slug='interactive-for-loop')
            self.assertEqual(lesson.status, 'DRAFT')
            lesson.body = '# Authored edit'
            lesson.save()
            revision = lesson.content_revision
            call_command('seed_interactive_lessons', apply=True, development=True, user=self.staff.username, stdout=StringIO())
        lesson.refresh_from_db()
        self.assertEqual((lesson.body, lesson.content_revision, lesson.status), ('# Authored edit', revision, 'DRAFT'))
        self.assertEqual(TopicLesson.objects.count(), before + 6)
