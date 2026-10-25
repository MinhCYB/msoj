import io
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from judge.utils.polygon_api import PolygonAPIError


def package(pid, state, kind='linux', revision=3):
    return {'id': pid, 'state': state, 'type': kind, 'revision': revision, 'comment': 'generator failed'}


@override_settings(POLYGON_SKIP_OWNERS=('dang', 'longvu1305'))
class PackageBuildTests(SimpleTestCase):
    def polygon_client(self, owner='ms24', tags=()):
        client = mock.Mock(max_retries=6)
        client.list_problems.return_value = [
            {'id': 1, 'name': 'alpha', 'owner': owner, 'revision': 3, 'accessType': 'WRITE', 'modified': False},
        ]
        client.view_tags.return_value = list(tags)
        return client

    def run_command(self, client, **options):
        output = io.StringIO()
        with mock.patch('judge.management.commands.build_polygon_packages.PolygonClient', return_value=client), \
                mock.patch('judge.management.commands.build_polygon_packages.time.sleep'):
            call_command('build_polygon_packages', stdout=output, **options)
        return output.getvalue()

    def test_new_build_waits_for_current_full_package_not_old_or_standard_package(self):
        client = self.polygon_client()
        client.packages.side_effect = [
            [package(1, 'READY', revision=2), package(2, 'READY', kind='standard')],
            [package(3, 'RUNNING')],
            [package(3, 'READY')],
        ]
        output = self.run_command(client)
        self.assertIn('built=1', output)
        client.call.assert_called_once_with('problem.buildPackage', problemId=1, full='true', verify='true')

    def test_dry_run_never_builds(self):
        client = self.polygon_client()
        client.packages.return_value = []
        self.assertIn('would_build=1', self.run_command(client, dry_run=True))
        client.call.assert_not_called()

    def test_exclusions_prevent_remote_build(self):
        for owner, tags in [('DANG', []), ('ms24', ['YB-BoClot']), ('ms24', ['CYB-BoClot'])]:
            with self.subTest(owner=owner, tags=tags):
                client = self.polygon_client(owner, tags)
                client.packages.return_value = []
                self.assertIn('skipped=1', self.run_command(client))
                if owner.lower() in ('dang', 'longvu1305'):
                    client.view_tags.assert_not_called()
                client.packages.assert_not_called()
                client.call.assert_not_called()

    def test_current_ready_and_active_builds_are_not_rebuilt(self):
        client = self.polygon_client()
        client.packages.return_value = [package(1, 'READY')]
        self.assertIn('ready=1', self.run_command(client))
        client.call.assert_not_called()
        client.packages.side_effect = [[package(1, 'RUNNING')], [package(1, 'READY')]]
        self.assertIn('ready=1', self.run_command(client))
        client.call.assert_not_called()

    def test_failed_build_is_reported_as_failure_and_not_success(self):
        client = self.polygon_client()
        client.packages.side_effect = [[], [package(1, 'FAILED')]]
        with self.assertRaises(CommandError):
            self.run_command(client)
        client.call.assert_called_once()

    def test_timeout_is_failure_without_starting_another_build(self):
        client = self.polygon_client()
        client.packages.side_effect = [[], []]
        with mock.patch('judge.management.commands.build_polygon_packages.time.monotonic',
                        side_effect=[0, 0, 2, 2]):
            with self.assertRaises(CommandError):
                self.run_command(client, timeout=1)
        client.call.assert_called_once()

    def test_failed_problem_does_not_stop_inspection_of_other_problems(self):
        client = self.polygon_client()
        second = dict(client.list_problems.return_value[0], id=2, name='beta')
        client.list_problems.return_value.append(second)
        client.packages.side_effect = [PolygonAPIError('no access'), [package(2, 'READY')]]
        output = io.StringIO()
        with mock.patch('judge.management.commands.build_polygon_packages.PolygonClient', return_value=client):
            with self.assertRaises(CommandError):
                call_command('build_polygon_packages', stdout=output)
        self.assertIn('failed=1, ready=1', output.getvalue())
        client.call.assert_not_called()

    def test_read_only_access_and_uncommitted_changes_do_not_start_build(self):
        client = self.polygon_client()
        client.packages.return_value = []
        client.list_problems.return_value[0]['accessType'] = 'READ'
        self.assertIn('skipped=1', self.run_command(client))
        client.list_problems.return_value[0].update(accessType='WRITE', modified=True)
        with self.assertRaises(CommandError):
            self.run_command(client)
        client.call.assert_not_called()

    def test_ambiguous_build_failure_is_not_retried(self):
        client = self.polygon_client()
        client.packages.return_value = []
        retry_limits = []

        def fail(*args, **kwargs):
            retry_limits.append(client.max_retries)
            raise PolygonAPIError('connection lost')

        client.call.side_effect = fail
        with self.assertRaises(CommandError):
            self.run_command(client)
        self.assertEqual(retry_limits, [1])
        self.assertEqual(client.max_retries, 6)
        client.call.assert_called_once()
