"""Restore orchestration and failure checks; all budget/key contents are synthetic."""
from contextlib import ExitStack, nullcontext
from pathlib import Path
from types import SimpleNamespace
import json
import socket
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import budget_recovery as recovery


class TweaksRestoreTests(unittest.TestCase):
    def args(self, target, key, **overrides):
        return SimpleNamespace(target=target,key=key,archive=Path('synthetic.gpg'),release=None,
                               container='restore-test',port=15006,tweaks_port=15005,
                               no_tweaks=False,open_browser=False,**overrides)

    def staged_restore(self, root, *, without_tweaks=False, image_error=False, open_browser=False):
        target=root/'destination';key=root/'test-key.asc';key.write_text('synthetic key')
        args=self.args(target,key);args.no_tweaks=without_tweaks;args.open_browser=open_browser
        manifest={'image':'actualbudget/actual-server@sha256:'+'a'*64,'version':'26.11.0',
                  'checks':{'active_budgets':[{'id':'synthetic','name':'Synthetic'}]}}
        def extract(_archive, destination):
            (destination/'data').mkdir(parents=True)
            (destination/'data'/'synthetic.txt').write_text('synthetic fixture')
        def ensure(image):
            if image_error and image==recovery.TWEAKS_IMAGE:
                raise recovery.RecoveryError('Synthetic registry unavailable')
        with ExitStack() as stack:
            stack.enter_context(patch.object(recovery,'config',return_value={'key_fingerprint':'TEST'}))
            stack.enter_context(patch.object(recovery,'require'))
            command=stack.enter_context(patch.object(recovery,'run',return_value=''))
            stack.enter_context(patch.object(recovery,'check_target'))
            stack.enter_context(patch.object(recovery,'keyring',return_value=nullcontext(['gpg'])))
            stack.enter_context(patch.object(recovery,'import_key'))
            stack.enter_context(patch.object(recovery,'safe_extract',side_effect=extract))
            stack.enter_context(patch.object(recovery,'verify_snapshot',return_value=manifest))
            images=stack.enter_context(patch.object(recovery,'ensure_image',side_effect=ensure))
            ready=stack.enter_context(patch.object(recovery,'verify_restored_services'))
            opened=stack.enter_context(patch('webbrowser.open'))
            if image_error:
                with self.assertRaisesRegex(recovery.RecoveryError,'registry unavailable'):
                    recovery.restore(args)
            else:recovery.restore(args)
            return target,command.call_args_list,images.call_args_list,ready.call_args_list,opened.call_args_list

    def test_default_restore_enables_pinned_tweaks_and_opens_sidecar(self):
        with tempfile.TemporaryDirectory() as folder:
            target,calls,images,ready,opened=self.staged_restore(Path(folder),open_browser=True)
            env=(target/'.env').read_text()
            self.assertIn("COMPOSE_PROFILES='tweaks'",env)
            self.assertIn("ABT_CONTAINER='restore-test-tweaks'",env)
            self.assertIn("ABT_PORT='15005'",env)
            self.assertIn("COMPOSE_PROJECT_NAME='"+recovery.restore_project_name(target)+"'",env)
            self.assertIn(recovery.TWEAKS_IMAGE,env)
            self.assertEqual(len(images),2)
            startup=next(c for c in calls if 'up' in c.args[0])
            self.assertIn('--wait',startup.args[0])
            self.assertEqual(startup.kwargs['env']['ABT_PORT'],'15005')
            self.assertEqual(ready[0].args,(15006,15005))
            self.assertEqual(opened[0].args,('http://localhost:15005',))

    def test_tweaks_image_failure_leaves_destination_unwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            target,*_=self.staged_restore(Path(folder),image_error=True)
            self.assertFalse(target.exists())

    def test_server_only_recovery_skips_tweaks_dependency(self):
        with tempfile.TemporaryDirectory() as folder:
            target,calls,images,ready,opened=self.staged_restore(Path(folder),without_tweaks=True,open_browser=True)
            self.assertIn("COMPOSE_PROFILES=''",(target/'.env').read_text())
            self.assertEqual(len(images),1)
            self.assertEqual(ready[0].args,(15006,None))
            self.assertEqual(opened[0].args,('http://localhost:15006',))

    def test_existing_sidecar_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(recovery,'run',side_effect=['Docker','restore-test-tweaks\n']):
            with self.assertRaisesRegex(recovery.RecoveryError,'already exists'):
                recovery.check_target(Path(folder)/'new','restore-test',15006,15005)

    def test_existing_project_with_other_names_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'new'
            label=recovery.restore_project_name(target)
            with patch.object(recovery,'run',side_effect=['Docker','old-other-container\t'+label+'\n']):
                with self.assertRaisesRegex(recovery.RecoveryError,'Compose project .* already exists'):
                    recovery.check_target(target,'restore-test',15006,15005)

    def test_port_collision_is_rejected_before_docker(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(recovery,'run') as run:
            with self.assertRaisesRegex(recovery.RecoveryError,'different ports'):
                recovery.check_target(Path(folder)/'new','restore-test',15006,15006)
            run.assert_not_called()

    def test_occupied_tweaks_port_is_reported(self):
        with socket.socket() as held,socket.socket() as free,tempfile.TemporaryDirectory() as folder:
            held.bind(('127.0.0.1',0));free.bind(('127.0.0.1',0));actual_port=free.getsockname()[1];free.close()
            with patch.object(recovery,'run',side_effect=['Docker','']):
                with self.assertRaisesRegex(recovery.RecoveryError,'--tweaks-port'):
                    recovery.check_target(Path(folder)/'new','restore-test',actual_port,held.getsockname()[1])

    def response(self, body, content_type='application/json'):
        response=MagicMock();response.__enter__.return_value=response
        response.status=200;response.headers={'Content-Type':content_type};response.read.return_value=body
        return response

    def test_spa_fallback_is_not_mistaken_for_tweaks(self):
        info=json.dumps({'build':{'version':'26.11.0'}}).encode()
        responses=[self.response(info),self.response(info),self.response(b'<html>not javascript</html>','text/html'),self.response(b'/abt/browser-shim.js','text/html')]
        with patch.object(recovery.urllib.request,'urlopen',side_effect=responses):
            with self.assertRaisesRegex(recovery.RecoveryError,'scripts were not loaded'):
                recovery.verify_restored_services(15006,15005)


if __name__=='__main__':unittest.main()
