import hashlib
import io
import zipfile
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from judge.models import PolygonProblem, PolygonTagMapping, Problem, ProblemGroup, ProblemType, Profile
from judge.utils.polygon_api import PolygonAPIError, PolygonClient
from judge.utils.polygon_sync import PolygonSync, PolygonSyncError, map_tags, normalize_code, pick_full_package, statement_config

PROBLEM_XML = b"""<problem>
  <statements>
    <statement language="english" type="application/x-tex" path="statements/english/problem.tex"/>
    <statement language="vietnamese" type="application/x-tex" path="statements/vietnamese/problem.tex"/>
    <statement language="english" type="text/html" path="statements/.html/english/problem.html"/>
  </statements>
</problem>"""


class FakeClient:
    """Stands in for PolygonClient; `problems` is what problems.list returns."""

    def __init__(self, problems, tags=None, packages=None):
        self.problems = problems
        self.tags = tags or {}
        self.packages_by_id = packages or {}
        self.tag_calls = []

    def list_problems(self):
        return self.problems

    def call(self, method, **params):
        assert method == 'problems.list'
        return [p for p in self.problems if p['id'] == params['id']]

    def view_tags(self, problem_id):
        self.tag_calls.append(problem_id)
        return self.tags.get(problem_id, [])

    def packages(self, problem_id):
        return self.packages_by_id.get(problem_id, [])


def remote(pid, name, owner='someone', revision=3, latest=3, deleted=False):
    item = {'id': pid, 'name': name, 'owner': owner, 'revision': revision, 'deleted': deleted}
    if latest is not None:
        item['latestPackage'] = latest
    return item


class NormalizeTests(SimpleTestCase):
    def test_polygon_name_becomes_valid_code(self):
        self.assertEqual(normalize_code('XVB-lc.KSL1-5'), 'xvb_lc_ksl1_5')

    def test_long_names_fit_problem_code_column(self):
        self.assertEqual(len(normalize_code('example-interactive-binary-search')), 32)


class PackageSelectionTests(SimpleTestCase):
    def test_only_ready_linux_package_counts_and_newest_wins(self):
        packages = [
            {'id': 1, 'revision': 2, 'state': 'READY', 'type': 'standard'},
            {'id': 2, 'revision': 2, 'state': 'READY', 'type': 'linux'},
            {'id': 3, 'revision': 4, 'state': 'FAILED', 'type': 'linux'},
            {'id': 4, 'revision': 3, 'state': 'READY', 'type': 'linux'},
        ]
        self.assertEqual(pick_full_package(packages)['id'], 4)

    def test_no_full_package(self):
        self.assertIsNone(pick_full_package([{'id': 1, 'revision': 2, 'state': 'READY', 'type': 'standard'}]))


class StatementConfigTests(SimpleTestCase):
    def test_english_is_main_and_vietnamese_maps_to_site_language(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as z:
            z.writestr('problem.xml', PROBLEM_XML)
        config = statement_config(zipfile.ZipFile(buf))
        self.assertEqual(config['main_statement_language'], 'english')
        self.assertEqual(config['polygon_to_site_language_map'], {'vietnamese': 'vi'})


class SignatureTests(SimpleTestCase):
    def test_signature_follows_polygon_spec(self):
        client = PolygonClient(key='k', secret='s', min_interval=0)
        with mock.patch('judge.utils.polygon_api.time.time', return_value=1700000000):
            signed = client._signed('problem.info', {'problemId': 7, 'pin': None})
        rand, digest = signed['apiSig'][:6], signed['apiSig'][6:]
        expected = hashlib.sha512(
            f'{rand}/problem.info?apiKey=k&problemId=7&time=1700000000#s'.encode(),
        ).hexdigest()
        self.assertEqual(digest, expected)
        self.assertNotIn('pin', signed)

    def test_missing_credentials_are_rejected(self):
        with mock.patch.dict('os.environ', {}, clear=True), self.assertRaises(PolygonAPIError):
            PolygonClient(key=None, secret=None)


class FakeResponse:
    def __init__(self, status, body=None):
        self.status_code = status
        self._body = body

    def json(self):
        return self._body

    def close(self):
        pass


class RetryTests(SimpleTestCase):
    def test_429_is_retried_then_succeeds(self):
        client = PolygonClient(key='k', secret='s', min_interval=0)
        client.session = mock.Mock()
        client.session.post.side_effect = [FakeResponse(429), FakeResponse(200, {'status': 'OK', 'result': [1]})]
        with mock.patch('judge.utils.polygon_api.time.sleep'):
            self.assertEqual(client.call('problems.list'), [1])
        self.assertEqual(client.session.post.call_count, 2)

    def test_failed_status_raises_with_comment(self):
        client = PolygonClient(key='k', secret='s', min_interval=0)
        client.session = mock.Mock()
        client.session.post.return_value = FakeResponse(200, {'status': 'FAILED', 'comment': 'no access'})
        with self.assertRaisesMessage(PolygonAPIError, 'no access'):
            client.call('problem.info', problemId=1)


@override_settings(POLYGON_SKIP_TAGS=('yb-boclot',), POLYGON_IGNORED_TAGS=('cyb-boclot',),
                   POLYGON_PREFERRED_OWNER='ms24', POLYGON_SYNC_AUTHOR='admin')
class ClassificationTests(TestCase):
    def sync(self, problems, tags=None):
        client = FakeClient(problems, tags)
        sync = PolygonSync(client=client)
        return sync, client, {pp.polygon_id: pp for pp in sync.refresh_index()}

    def test_skip_tag_is_case_insensitive_and_wins_over_everything(self):
        _, _, rows = self.sync([remote(1, 'a')], {1: ['Dp', 'YB-BoClot']})
        self.assertEqual(rows[1].status, PolygonProblem.SKIPPED)

    def test_cyb_boclot_problem_is_synced_not_skipped(self):
        _, _, rows = self.sync([remote(1, 'a')], {1: ['cyb-boclot']})
        self.assertEqual(rows[1].status, PolygonProblem.NEW)

    @override_settings(POLYGON_SKIP_OWNERS=('dang', 'longvu1305'))
    def test_blocked_owners_are_skipped_even_with_unreadable_tags(self):
        for owner in ('dang', 'LONGVU1305'):
            with self.subTest(owner=owner):
                pp = PolygonProblem(owner=owner, tags_error='unavailable')
                status, _ = PolygonSync._status_of(pp, {})
                self.assertEqual(status, PolygonProblem.SKIPPED)

    @override_settings(POLYGON_SKIP_OWNERS=('dang', 'longvu1305'), POLYGON_PREFERRED_OWNER='dang')
    def test_blocked_owner_cannot_claim_duplicate_code(self):
        _, _, rows = self.sync([remote(1, 'same', owner='dang'), remote(2, 'same', owner='allowed')])
        self.assertEqual(rows[1].status, PolygonProblem.SKIPPED)
        self.assertEqual(rows[2].status, PolygonProblem.NEW)

    def test_deleted_polygon_problems_are_ignored(self):
        _, _, rows = self.sync([remote(1, 'a', deleted=True)])
        self.assertEqual(rows, {})

    def test_duplicate_code_prefers_configured_owner_regardless_of_order_or_id(self):
        _, _, rows = self.sync([
            remote(10, 'hhy-cd', owner='linhdieu'),
            remote(20, 'hhy_cd', owner='ms24'),
        ])
        self.assertEqual(rows[20].status, PolygonProblem.NEW)
        self.assertEqual(rows[10].status, PolygonProblem.DUPLICATE)

    def test_skipped_problem_does_not_win_a_duplicate_code(self):
        _, _, rows = self.sync(
            [remote(1, 'dup', owner='ms24'), remote(2, 'dup', owner='other')],
            {1: ['yb-boclot']},
        )
        self.assertEqual(rows[1].status, PolygonProblem.SKIPPED)
        self.assertEqual(rows[2].status, PolygonProblem.NEW)

    def test_existing_unmanaged_problem_blocks_sync_instead_of_being_overwritten(self):
        Problem.objects.create(code='taken', name='Mine', time_limit=1, memory_limit=1024, points=1,
                               group=ProblemGroup.objects.create(name='g', full_name='G'))
        _, _, rows = self.sync([remote(1, 'taken')])
        self.assertEqual(rows[1].status, PolygonProblem.CONFLICT)

    def test_synced_problem_becomes_outdated_when_polygon_revision_moves(self):
        problem = Problem.objects.create(code='alpha', name='A', time_limit=1, memory_limit=1024, points=1,
                                         group=ProblemGroup.objects.create(name='g', full_name='G'))
        sync, client, rows = self.sync([remote(1, 'alpha', latest=3)])
        PolygonProblem.objects.filter(polygon_id=1).update(problem=problem, synced_revision=3)
        client.problems = [remote(1, 'alpha', latest=4, revision=4)]
        rows = {pp.polygon_id: pp for pp in sync.refresh_index()}
        self.assertEqual(rows[1].status, PolygonProblem.OUTDATED)

    def test_unreadable_tags_fail_that_problem_only_and_never_sync_it(self):
        class FlakyTags(FakeClient):
            def view_tags(self, problem_id):
                if problem_id == 1:
                    raise PolygonAPIError('HTTP 500')
                return super().view_tags(problem_id)

        sync = PolygonSync(client=FlakyTags([remote(1, 'broken'), remote(2, 'fine')]))
        rows = {pp.polygon_id: pp for pp in sync.refresh_index()}
        self.assertEqual(rows[1].status, PolygonProblem.FAILED)
        self.assertIn('HTTP 500', rows[1].message)
        self.assertEqual(rows[2].status, PolygonProblem.NEW)

        sync.client.view_tags = lambda problem_id: ['yb-boclot']
        rows = {pp.polygon_id: pp for pp in sync.refresh_index()}
        self.assertEqual(rows[1].status, PolygonProblem.SKIPPED)

    def test_tags_are_refetched_only_when_revision_changes(self):
        sync, client, _ = self.sync([remote(1, 'a', revision=3)], {1: ['dp']})
        sync.refresh_index()
        self.assertEqual(client.tag_calls, [1])
        client.problems = [remote(1, 'a', revision=4)]
        sync.refresh_index()
        self.assertEqual(client.tag_calls, [1, 1])


@override_settings(POLYGON_IGNORED_TAGS=('cyb-boclot',))
class TagMappingTests(TestCase):
    def test_group_comes_from_first_mapped_tag_and_types_accumulate_without_ignored_tag(self):
        group = ProblemGroup.objects.create(name='g1', full_name='G1')
        other_group = ProblemGroup.objects.create(name='g2', full_name='G2')
        dp = ProblemType.objects.create(name='dp', full_name='DP')
        graph = ProblemType.objects.create(name='graph', full_name='Graph')
        PolygonTagMapping.objects.create(tag='DP ', problem_type=dp, problem_group=group)
        PolygonTagMapping.objects.create(tag='mst', problem_type=graph, problem_group=other_group)
        PolygonTagMapping.objects.create(tag='cyb-boclot', problem_type=graph, problem_group=other_group)

        got_group, got_types = map_tags(['cyb-boclot', 'Unknown', 'dp', 'mst'])
        self.assertEqual(got_group, group)
        self.assertEqual(got_types, [dp, graph])

    def test_unmapped_tags_yield_nothing(self):
        self.assertEqual(map_tags(['nope']), (None, []))


@override_settings(POLYGON_SKIP_TAGS=('yb-boclot',), POLYGON_PREFERRED_OWNER='ms24', POLYGON_SYNC_AUTHOR='admin')
class SyncProblemTests(TestCase):
    def setUp(self):
        Profile.objects.create(user=get_user_model().objects.create_user('admin'))

    def test_missing_full_package_is_recorded_as_failure_not_raised(self):
        client = FakeClient([remote(1, 'a')], packages={1: [{'id': 9, 'revision': 3, 'state': 'READY',
                                                             'type': 'standard'}]})
        sync = PolygonSync(client=client)
        sync.refresh_index()
        pp = sync.sync_problem(PolygonProblem.objects.get(polygon_id=1))
        self.assertEqual(pp.status, PolygonProblem.FAILED)
        self.assertIn('full', pp.message)

    def test_skipped_problem_never_downloads_anything(self):
        client = FakeClient([remote(1, 'a')], tags={1: ['yb-boclot']})
        client.download_package = mock.Mock()
        sync = PolygonSync(client=client)
        sync.refresh_index()
        sync.sync_all()
        client.download_package.assert_not_called()
        self.assertEqual(PolygonProblem.objects.get(polygon_id=1).status, PolygonProblem.SKIPPED)

    @override_settings(POLYGON_SKIP_OWNERS=('dang', 'longvu1305'))
    def test_owner_exclusion_blocks_bulk_and_forced_sync_without_removing_existing_problem(self):
        group = ProblemGroup.objects.create(name='g', full_name='G')
        problem = Problem.objects.create(code='blocked', name='Keep me', time_limit=1,
                                         memory_limit=1024, points=1, group=group, is_public=True)
        client = FakeClient([remote(1, 'blocked', owner='longvu1305')])
        client.download_package = mock.Mock(side_effect=AssertionError('Blocked problem downloaded'))
        sync = PolygonSync(client=client)
        pp = PolygonProblem.objects.create(polygon_id=1, owner='longvu1305', name='blocked',
                                           code='blocked', problem=problem, synced_revision=2)
        sync.sync_all([pp], force=True)
        pp = sync.sync_problem(pp, force=True)
        self.assertEqual(pp.status, PolygonProblem.SKIPPED)
        self.assertEqual(pp.problem_id, problem.pk)
        self.assertEqual(pp.synced_revision, 2)
        self.assertIsNone(pp.last_synced)
        problem.refresh_from_db()
        self.assertTrue(problem.is_public)
        self.assertEqual(problem.name, 'Keep me')
        client.download_package.assert_not_called()

    def test_importer_failure_is_recorded_and_other_problems_continue(self):
        full = [{'id': 9, 'revision': 3, 'state': 'READY', 'type': 'linux'}]
        client = FakeClient([remote(1, 'bad'), remote(2, 'good')], packages={1: full, 2: full})
        client.download_package = mock.MagicMock(side_effect=PolygonAPIError('boom'))
        sync = PolygonSync(client=client)
        sync.refresh_index()
        counts = sync.sync_all()
        self.assertEqual(counts, {PolygonProblem.FAILED: 2})
        self.assertEqual(client.download_package.call_count, 2)

    def test_missing_sync_author_aborts_before_any_work(self):
        get_user_model().objects.filter(username='admin').delete()
        client = FakeClient([remote(1, 'a')])
        sync = PolygonSync(client=client)
        sync.refresh_index()
        with self.assertRaises(PolygonSyncError):
            sync.sync_all()


class AdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.staff = User.objects.create_user('staff', is_staff=True)
        cls.owner = User.objects.create_user('owner', is_staff=True)
        for user in (cls.staff, cls.owner):
            Profile.objects.create(user=user)
        cls.owner.user_permissions.add(Permission.objects.get(codename='import_polygon_package'))
        cls.pp = PolygonProblem.objects.create(polygon_id=5, owner='ms24', name='alpha', code='alpha',
                                               latest_revision=2, tags=['dp'])

    def post(self, user, name, *args):
        self.client.force_login(user)
        return self.client.post(reverse(f'admin:judge_polygonproblem_{name}', args=args))

    def test_changelist_requires_polygon_permission(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse('admin:judge_polygonproblem_changelist')).status_code, 403)
        self.client.force_login(self.owner)
        response = self.client.get(reverse('admin:judge_polygonproblem_changelist'))
        self.assertContains(response, 'alpha')
        self.assertContains(response, reverse('admin:judge_polygonproblem_sync_all'))

    def test_sync_actions_reject_users_without_permission(self):
        with mock.patch('judge.admin.polygon.polygon_sync_all') as task:
            self.assertEqual(self.post(self.staff, 'sync_all').status_code, 403)
            task.delay.assert_not_called()

    def test_sync_actions_are_post_only(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse('admin:judge_polygonproblem_sync_all')).status_code, 405)

    def test_sync_one_queues_a_forced_sync_of_that_problem(self):
        with mock.patch('judge.admin.polygon.polygon_sync_busy', return_value=False), \
                mock.patch('judge.admin.polygon.polygon_sync_problems') as task:
            self.assertEqual(self.post(self.owner, 'sync', self.pp.pk).status_code, 302)
            task.delay.assert_called_once_with([5], force=True)

    def test_nothing_is_queued_while_another_sync_runs(self):
        with mock.patch('judge.admin.polygon.polygon_sync_busy', return_value=True), \
                mock.patch('judge.admin.polygon.polygon_sync_all') as task:
            self.assertEqual(self.post(self.owner, 'sync_all').status_code, 302)
            task.delay.assert_not_called()

    def test_mirror_rows_cannot_be_edited_or_deleted(self):
        self.client.force_login(self.owner)
        self.assertEqual(
            self.client.post(reverse('admin:judge_polygonproblem_delete', args=[self.pp.pk]), {'post': 'yes'})
            .status_code, 403)
        self.assertTrue(PolygonProblem.objects.filter(pk=self.pp.pk).exists())
