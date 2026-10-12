from datetime import timedelta
from unittest.mock import patch

from copy import deepcopy
from uuid import uuid4
from django.contrib.auth.models import User
from django.db import connection, connections
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from .tests_roadmap_migrations import RehearsalRouter

from judge.models import Contest, Language, Problem, ProblemGroup, Profile, Submission, SubmissionSource, SubmissionTestCase
from judge.judgeapi import judge_submission

from .models import AIReview, AIReviewApproach, AIReviewAttempt
from .review_context import SubmissionContextBuilder, UnsupportedReview, review_eligibility, review_is_current


class ReviewContextTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username='review-student')
        profile = Profile.objects.create(user=user)
        self.problem = Problem.objects.create(
            code='review_problem', name='Review problem', description='Count numbers.',
            group=ProblemGroup.objects.create(name='review-group', full_name='Review group'),
            time_limit=1, memory_limit=65536, points=100, is_public=True,
        )
        self.language = Language.objects.create(key='REV_PY', name='Review Python', common_name='Python',
                                                ace='python', pygments='python', extension='py')
        self.submission = Submission.objects.create(user=profile, problem=self.problem, language=self.language,
                                                     status='D', result='WA', time=1.2, memory=123.0,
                                                     judge_generation=1)
        SubmissionSource.objects.create(submission=self.submission, source='print(0)')
        self.builder = SubmissionContextBuilder()

    def test_deterministic_and_bounded_allowlist(self):
        # Prime relations before counting queries (never touch test_cases).
        SubmissionTestCase.objects.create(submission=self.submission, case=1, status='WA',
                                          output='HIDDEN_OUTPUT', extended_feedback='HIDDEN_FEEDBACK')
        self.submission.problem = self.problem
        self.submission.language = self.language
        self.submission.source = SubmissionSource.objects.get(submission=self.submission)
        with self.assertNumQueries(0):
            first = self.builder.build(self.submission)
            second = self.builder.build(self.submission)
        self.assertEqual(first, second)
        self.assertEqual(set(first.problem), {'code', 'name', 'description', 'time_limit', 'memory_limit'})
        self.assertEqual(set(first.language), {'key', 'name'})
        self.assertEqual(set(first.submission), {'status', 'result', 'time', 'memory', 'error',
                                                 'is_pretested', 'judge_generation'})
        self.assertEqual(first.source, 'print(0)')
        self.assertNotIn('test_cases', str(first))
        self.assertNotIn('extended_feedback', str(first))
        self.assertNotIn('HIDDEN_OUTPUT', str(first))
        self.assertNotIn('HIDDEN_FEEDBACK', str(first))

    def test_source_result_generation_and_pretest_change_revision(self):
        base = self.builder.build(self.submission)
        self.submission.source.source = 'print(1)'
        changed_source = self.builder.build(self.submission)
        self.assertNotEqual(base.source_digest, changed_source.source_digest)
        self.assertNotEqual(base.revision, changed_source.revision)
        self.submission.source.source = 'print(0)'
        self.submission.result = 'AC'
        changed_result = self.builder.build(self.submission)
        self.assertNotEqual(base.result_digest, changed_result.result_digest)
        self.submission.result = 'WA'
        self.submission.judge_generation += 1
        same_verdict_rejudge = self.builder.build(self.submission)
        self.assertNotEqual(base.revision, same_verdict_rejudge.revision)
        self.submission.is_pretested = True
        pretest = self.builder.build(self.submission)
        self.assertTrue(pretest.submission['is_pretested'])
        self.assertNotEqual(same_verdict_rejudge.revision, pretest.revision)

    def test_rejudge_revision_invalidates_succeeded_review(self):
        revision = self.builder.build(self.submission).revision
        review = AIReview.objects.create(submission=self.submission, status='succeeded',
                                         current_revision=revision, overall_feedback='Helpful feedback')
        self.assertTrue(review_is_current(review, self.submission))
        self.submission.judge_generation += 1
        self.assertFalse(review_is_current(review, self.submission))

    def test_allowed_and_denied_results(self):
        for status, result in [('CE', 'CE'), ('D', 'WA'), ('D', 'AC'), ('D', 'TLE'), ('D', 'PAC')]:
            self.submission.status, self.submission.result = status, result
            self.assertIsNone(review_eligibility(self.submission))
        for status, result in [('IE', 'IE'), ('AB', 'AB'), ('QU', None), ('D', None), ('D', 'CE')]:
            self.submission.status, self.submission.result = status, result
            self.assertEqual(review_eligibility(self.submission), 'judge_result_unsupported')

    def test_live_contest_denied_ended_allowed(self):
        contest = Contest.objects.create(key='review_contest', name='Review contest',
                                         start_time=timezone.now() - timedelta(hours=1),
                                         end_time=timezone.now() + timedelta(hours=1))
        self.submission.contest_object = contest
        self.assertEqual(review_eligibility(self.submission), 'contest_active')
        with self.assertRaises(UnsupportedReview) as caught:
            self.builder.build(self.submission)
        self.assertEqual(caught.exception.reason, 'contest_active')
        contest.end_time = timezone.now() - timedelta(seconds=1)
        self.assertIsNone(review_eligibility(self.submission))
        self.assertEqual(self.builder.build(self.submission).source, 'print(0)')

    def test_file_only_and_pdf_only_denied(self):
        self.language.file_only = True
        self.assertEqual(review_eligibility(self.submission), 'file_only_source')
        with self.assertRaises(UnsupportedReview):
            self.builder.build(self.submission)
        self.language.file_only = False
        self.problem.description = ''
        self.problem.pdf_url = 'https://example.test/statement.pdf'
        self.assertEqual(review_eligibility(self.submission), 'text_statement_missing')

    @patch('judge.judgeapi.judge_request')
    @patch('judge.judgeapi._post_update_submission')
    def test_judge_dispatch_increments_only_when_update_succeeds(self, notify, request):
        request.return_value = {'name': 'submission-received', 'submission-id': self.submission.id}
        self.assertTrue(judge_submission(self.submission, rejudge=True))
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.judge_generation, 2)
        self.assertEqual(self.submission.status, 'QU')
        request.assert_called_once()
        self.assertFalse(judge_submission(self.submission, rejudge=True))
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.judge_generation, 2)
        request.assert_called_once()
        self.submission.status = 'P'
        self.submission.save(update_fields=['status'])
        self.assertFalse(judge_submission(self.submission, rejudge=True))
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.judge_generation, 2)
        request.assert_called_once()

    @patch('judge.judgeapi.judge_request')
    @patch('judge.judgeapi._post_update_submission')
    def test_initial_dispatch_increments_once(self, notify, request):
        self.submission.status = 'QU'
        self.submission.judge_generation = 0
        self.submission.save(update_fields=['status', 'judge_generation'])
        request.return_value = {'name': 'submission-received', 'submission-id': self.submission.id}
        self.assertTrue(judge_submission(self.submission))
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.judge_generation, 1)
        self.assertFalse(judge_submission(self.submission))
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.judge_generation, 1)
        request.assert_called_once()


class LegacyReviewMigrationTests(TransactionTestCase):
    databases = {'default'}
    migrate_from = [('mentor', '0001_initial'), ('judge', '0236_judge_storages')]
    migrate_to = [('mentor', '0002_review_history'), ('judge', '0237_submission_judge_generation')]

    def setUp(self):
        super().setUp()
        default = connections['default']
        if default.vendor != 'mysql':
            self.skipTest('Migration rehearsal uses the deployment-compatible MySQL backend.')
        self.database_name = 'test_review_mig_' + uuid4().hex[:12]
        self.alias = 'review_migration'
        config = deepcopy(default.settings_dict)
        config['NAME'] = self.database_name
        config['TEST']['MIRROR'] = None
        with default.cursor() as cursor:
            cursor.execute(f'CREATE DATABASE `{self.database_name}` CHARACTER SET utf8mb4')
        connections.databases[self.alias] = config
        self.db = connections[self.alias]
        self.addCleanup(self.cleanup_database)
        executor = MigrationExecutor(self.db)
        with override_settings(DATABASE_ROUTERS=[RehearsalRouter(self.alias)]):
            executor.migrate(self.migrate_from)
        self.old = executor.loader.project_state(self.migrate_from).apps

    def cleanup_database(self):
        self.db.close()
        del connections[self.alias]
        del connections.databases[self.alias]
        with connections['default'].cursor() as cursor:
            cursor.execute(f'DROP DATABASE `{self.database_name}`')

    def test_legacy_review_is_stale_and_approaches_are_preserved(self):
        old = self.old
        with override_settings(DATABASE_ROUTERS=[RehearsalRouter(self.alias)]):
            user = old.get_model('auth', 'User').objects.using(self.alias).create(username='legacy-review-user')
            profile = old.get_model('judge', 'Profile').objects.using(self.alias).create(user_id=user.pk)
            group = old.get_model('judge', 'ProblemGroup').objects.using(self.alias).create(name='legacy-review-group', full_name='Legacy')
            problem = old.get_model('judge', 'Problem').objects.using(self.alias).create(
                code='legacy_review_problem', name='Legacy', group_id=group.pk,
                time_limit=1, memory_limit=65536, points=100)
            language = old.get_model('judge', 'Language').objects.using(self.alias).create(
                key='LEGACY_REV', name='Legacy', common_name='Legacy', ace='text', pygments='text', extension='txt')
            submission = old.get_model('judge', 'Submission').objects.using(self.alias).create(
                user_id=profile.pk, problem_id=problem.pk, language_id=language.pk)
            review = old.get_model('mentor', 'AIReview').objects.using(self.alias).create(
                submission_id=submission.pk, overall_feedback='legacy feedback')
            old.get_model('mentor', 'AIReviewApproach').objects.using(self.alias).create(
                review_id=review.pk, title='Old approach', description='Old text', complexity='O(n)', practicality='high')

            executor = MigrationExecutor(self.db)
            executor.migrate(self.migrate_to)
            migrated = executor.loader.project_state(self.migrate_to).apps
            current = migrated.get_model('mentor', 'AIReview').objects.using(self.alias).get(pk=review.pk)
            attempt = migrated.get_model('mentor', 'AIReviewAttempt').objects.using(self.alias).get(review_id=review.pk)
            approach = migrated.get_model('mentor', 'AIReviewApproach').objects.using(self.alias).get(attempt_id=attempt.pk)
            self.assertEqual((current.status, current.current_revision, current.overall_feedback), ('stale', '', ''))
            self.assertEqual((attempt.status, attempt.generation, attempt.overall_feedback),
                             ('stale', 0, 'legacy feedback'))
            self.assertEqual(approach.title, 'Old approach')
