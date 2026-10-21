from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from judge.models import Contest, Language, Problem, ProblemGroup, Profile, Submission, SubmissionSource
from judge.models.problem import SubmissionSourceAccess


class WorkspaceSubmissionAccessTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='workspace-owner')
        self.other = User.objects.create_user(username='workspace-other')
        owner_profile = Profile.objects.create(user=self.owner)
        Profile.objects.create(user=self.other)
        self.problem = Problem.objects.create(
            code='workspace_access', name='Workspace access', description='Count numbers.',
            group=ProblemGroup.objects.create(name='workspace', full_name='Workspace'),
            time_limit=1, memory_limit=65536, points=100, is_public=True,
            submission_source_visibility_mode=SubmissionSourceAccess.ONLY_OWN,
        )
        self.language = Language.objects.create(
            key='WS_PY', name='Python', common_name='Python', ace='python',
            pygments='python', extension='py',
        )
        self.submission = Submission.objects.create(
            user=owner_profile, problem=self.problem, language=self.language,
            status='D', result='WA', case_points=25, case_total=100, points=25,
        )
        self.source = '\nprint("<private source>")\n\n'
        SubmissionSource.objects.create(submission=self.submission, source=self.source)

    def login(self, user):
        self.client.force_login(user, backend='django.contrib.auth.backends.ModelBackend')

    def test_fragment_cannot_bypass_owner_only_access(self):
        self.login(self.other)
        for path in ('submission', 'src'):
            response = self.client.get(f'/{path}/{self.submission.id}?workspace=1')
            self.assertEqual(response.status_code, 403)
            self.assertNotIn(b'private source', response.content)

    def test_anonymous_fragment_requires_login(self):
        for path in ('submission', 'src'):
            response = self.client.get(f'/{path}/{self.submission.id}?workspace=1')
            self.assertEqual(response.status_code, 302)
            self.assertNotIn(b'private source', response.content)

    def test_source_preserves_boundary_newlines_and_escapes_html(self):
        self.login(self.owner)
        response = self.client.get(f'/src/{self.submission.id}?workspace=1')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context_data['raw_source'], self.source)
        self.assertIn(b'&lt;private source&gt;', response.content)
        self.assertNotIn(b'<private source>', response.content)

    def test_active_contest_never_offers_new_review(self):
        self.login(self.owner)
        self.submission.contest_object = Contest.objects.create(
            key='workspace_contest', name='Workspace contest',
            start_time=timezone.now() - timedelta(hours=1),
            end_time=timezone.now() + timedelta(hours=1),
        )
        self.submission.save(update_fields=['contest_object'])
        response = self.client.get(f'/submission/{self.submission.id}?workspace=1&panel=review')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context_data['panel'], 'result')
        self.assertFalse(response.context_data.get('ai_review_can_request', False))

    def test_file_only_source_is_denied_even_to_owner(self):
        self.login(self.owner)
        self.language.file_only = True
        self.language.save(update_fields=['file_only'])
        response = self.client.get(f'/src/{self.submission.id}?workspace=1')
        self.assertEqual(response.status_code, 404)
        self.assertNotIn(b'private source', response.content)
