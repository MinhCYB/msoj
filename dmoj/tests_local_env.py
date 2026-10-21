import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase

from dmoj.local_env import load_local_env


class LocalEnvTests(SimpleTestCase):
    def test_process_environment_wins(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / '.env'
            path.write_text('AI_9ROUTER_API_KEY=file-value\n', encoding='utf-8')
            with patch.dict(os.environ, {'AI_9ROUTER_API_KEY': 'process-value'}):
                load_local_env(path)
                self.assertEqual(os.environ['AI_9ROUTER_API_KEY'], 'process-value')

    def test_missing_file_does_not_fail(self):
        with TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            load_local_env(Path(directory) / '.env')
            self.assertNotIn('AI_9ROUTER_API_KEY', os.environ)

    def test_only_allowlisted_key_is_loaded(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / '.env'
            path.write_text('# comment\n\nUNRELATED_SECRET=ignore\n AI_9ROUTER_API_KEY =value=part\n', encoding='utf-8')
            with patch.dict(os.environ, {}, clear=True):
                load_local_env(path)
                self.assertNotIn('UNRELATED_SECRET', os.environ)
                self.assertEqual(os.environ['AI_9ROUTER_API_KEY'], 'value=part')

    def test_placeholder_is_not_a_credential(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / '.env'
            path.write_text('AI_9ROUTER_API_KEY=<PLACEHOLDER>\n', encoding='utf-8')
            with patch.dict(os.environ, {}, clear=True):
                load_local_env(path)
                self.assertNotIn('AI_9ROUTER_API_KEY', os.environ)
