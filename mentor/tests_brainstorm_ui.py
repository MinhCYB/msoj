"""Workspace language selection integration; no inference is invoked."""

from html.parser import HTMLParser

from django.test import TestCase
from django.urls import reverse

from judge.models import Judge

from .tests_brainstorm_service import BrainstormFixture


class LanguageOptions(HTMLParser):
    def __init__(self):
        super().__init__()
        self.options = []

    def handle_starttag(self, tag, attrs):
        if tag == 'option':
            self.options.append(dict(attrs))


class BrainstormWorkspaceTests(BrainstormFixture, TestCase):
    def test_problem_workspace_language_option_identifies_executor(self):
        self.problem.is_manually_managed = True
        self.problem.save(update_fields=['is_manually_managed'])
        judge = Judge.objects.create(name='brainstorm-ui', auth_key='test-only', online=True,
                                     storages=[self.problem.effective_storage])
        judge.runtimes.add(self.language)
        self.client.force_login(self.user)
        response = self.client.get(reverse('problem_detail', args=[self.problem.code]))
        self.assertEqual(response.status_code, 200)
        page = response.content.decode()
        options = LanguageOptions()
        options.feed(page)
        self.assertEqual(next(option['data-key'] for option in options.options
                              if option.get('value') == str(self.language.pk)), self.language.key)

