import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('updater', Path(__file__).resolve().parents[1] / 'scripts' / 'auto-update.py')
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        updater.ROOT = self.root
        updater.DEPLOY = self.root / '.deploy'
        updater.DEPLOY.mkdir()
        (self.root / '.env').write_text('SALON_PORT=8093\n')
        self.release = updater.DEPLOY / 'releases' / 'newsha'
        self.release.mkdir(parents=True)
    def tearDown(self):
        self.temp.cleanup()
    def fake_run(self, args, **kwargs):
        if args[:2] == ['git', 'rev-parse']:
            return 'newsha\n'
        return ''
    @patch.object(updater, 'compose')
    def test_success_records_healthy_release(self, compose):
        with patch.object(updater, 'run', side_effect=self.fake_run) as run:
            updater.deploy()
        recorded = json.loads((updater.DEPLOY / 'current.json').read_text())
        self.assertEqual(recorded['sha'], 'newsha')
        self.assertTrue(any(call.args[0][:2] == ['docker','run'] for call in run.call_args_list))
        self.assertIn('--wait', compose.call_args.args)
    @patch.object(updater, 'compose')
    def test_failed_build_never_replaces_running_container(self, compose):
        def fail_build(args, **kwargs):
            if args[:2] == ['docker','build']:
                raise subprocess.CalledProcessError(1, args)
            return self.fake_run(args, **kwargs)
        with patch.object(updater, 'run', side_effect=fail_build):
            with self.assertRaises(subprocess.CalledProcessError):
                updater.deploy()
        compose.assert_not_called()
        self.assertFalse((updater.DEPLOY / 'current.json').exists())
    def test_failed_health_restores_previous_image(self):
        previous = {'sha':'oldsha','release':str(self.root/'old')}
        state = updater.DEPLOY / 'current.json'
        state.write_text(json.dumps(previous))
        def fail_new(release, sha, *args, **kwargs):
            if sha == 'newsha' and args[0] == 'up':
                raise subprocess.CalledProcessError(1, ['docker','compose','up'])
        with patch.object(updater,'run',side_effect=self.fake_run), patch.object(updater,'compose',side_effect=fail_new) as compose:
            with self.assertRaises(subprocess.CalledProcessError):
                updater.deploy()
        self.assertEqual(compose.call_args.args[1], 'oldsha')
        self.assertEqual(json.loads(state.read_text()),previous)

    @patch.object(updater, 'compose')
    def test_website_build_failure_preserves_running_services(self, compose):
        website = self.release / 'Website'
        website.mkdir()
        (website / 'Dockerfile').write_text('FROM nginx:stable-alpine\n')
        def fail_website(args, **kwargs):
            if args[:2] == ['docker', 'build'] and args[-1] == str(website):
                raise subprocess.CalledProcessError(1, args)
            return self.fake_run(args, **kwargs)
        with patch.object(updater, 'run', side_effect=fail_website):
            with self.assertRaises(subprocess.CalledProcessError):
                updater.deploy()
        compose.assert_not_called()
        self.assertFalse((updater.DEPLOY / 'current.json').exists())

    def test_website_health_failure_removes_first_rollout_and_restores_dashboard(self):
        website = self.release / 'Website'
        website.mkdir()
        (website / 'Dockerfile').write_text('FROM nginx:stable-alpine\n')
        previous = {'sha': 'oldsha', 'release': str(self.root / 'old')}
        (updater.DEPLOY / 'current.json').write_text(json.dumps(previous))
        def fail_new(release, sha, *args, **kwargs):
            if sha == 'newsha' and args[0] == 'up':
                raise subprocess.CalledProcessError(1, ['docker', 'compose', 'up'])
        with patch.object(updater, 'run', side_effect=self.fake_run), patch.object(updater, 'compose', side_effect=fail_new) as compose:
            with self.assertRaises(subprocess.CalledProcessError):
                updater.deploy()
        self.assertTrue(any(call.args[2:] == ('rm', '--stop', '--force', 'website') for call in compose.call_args_list))
        self.assertEqual(compose.call_args.args[1], 'oldsha')
