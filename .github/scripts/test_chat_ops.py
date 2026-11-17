"""固定 Chat 发布通道测试；不连网络、Docker 或生产服务器。"""
import importlib.util
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location('chat_ops', Path(__file__).with_name('chat_ops.py'))
ops = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ops)


def archive(path, entries):
    with tarfile.open(path, 'w:gz') as tar:
        for name, data, kind in entries:
            info = tarfile.TarInfo(name)
            if kind == 'symlink':
                info.type = tarfile.SYMTYPE; info.linkname = '/etc/passwd'; tar.addfile(info)
            elif kind == 'directory':
                info.type = tarfile.DIRTYPE; tar.addfile(info)
            else:
                info.size = len(data); tar.addfile(info, io.BytesIO(data))


class ChatOpsTests(unittest.TestCase):
    def test_safe_archive_and_payload_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); target = root / 'out'; target.mkdir()
            bundle = root / 'bundle.tar.gz'
            archive(bundle, [('source/deploy/entry.py', b'public source', 'file'), ('context/frontend-build/index.html', b'public web', 'file'), ('release-input-manifest.json', b'{}', 'file')])
            ops.extract(bundle, target)
            before = ops.payload_files(target)
            self.assertEqual(len(before), 3)
            (target / 'source/deploy/entry.py').write_bytes(b'changed')
            self.assertNotEqual(before, ops.payload_files(target))

    def test_archive_rejects_traversal_links_private_and_duplicate_before_extract(self):
        cases = [('../escape', 'file'), ('context/../../escape', 'file'), ('context/link', 'symlink'),
                 ('context/frontend-debug/a.map', 'file'), ('source/.env', 'file'), ('context/secret.pem', 'file'), ('/tmp/escape', 'file')]
        for name, kind in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); out = root / 'out'; out.mkdir()
                bundle = root / 'bundle.tar.gz'
                archive(bundle, [('context/normal', b'ok', 'file'), (name, b'bad', kind)])
                with self.assertRaises(ops.OperationError): ops.extract(bundle, out)
                self.assertEqual(list(out.iterdir()), [])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); out = root / 'out'; out.mkdir()
            archive(root / 'a.tar.gz', [('source/x', b'x', 'file'), ('source/x', b'y', 'file')])
            with self.assertRaisesRegex(ops.OperationError, 'duplicate'): ops.extract(root / 'a.tar.gz', out)

    def test_archive_resource_limit_is_checked_before_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); out = root / 'out'; out.mkdir()
            archive(root / 'a.tar.gz', [('context/a', b'123', 'file')])
            with mock.patch.object(ops, 'MAX_EXPANDED', 2):
                with self.assertRaisesRegex(ops.OperationError, 'expansion'): ops.extract(root / 'a.tar.gz', out)
            self.assertEqual(list(out.iterdir()), [])

    def test_fixed_download_url_and_integrity(self):
        with tempfile.TemporaryDirectory() as directory:
            body = b'reviewed public archive'; response = io.BytesIO(body); response.headers = {'Content-Length': str(len(body))}
            opener = mock.Mock(); opener.open.return_value = response
            with mock.patch.object(ops.urllib.request, 'build_opener', return_value=opener):
                ops.download('a' * 40, ops.hashlib.sha256(body).hexdigest(), Path(directory) / 'payload')
            url = opener.open.call_args.args[0].full_url
            self.assertEqual(url, 'https://github.com/ixiaoyy/parallellines-chat/releases/download/personal-connections-' + 'a' * 40 + '/parallellines-chat-personal-connections-' + 'a' * 40 + '.tar.gz')

    def test_redirect_cannot_escape_official_github_hosts(self):
        handler = ops.RestrictedRedirect()
        request = ops.urllib.request.Request('https://github.com/ixiaoyy/parallellines-chat')
        for url in ('http://github.com/file', 'https://127.0.0.1/file', 'https://example.invalid/file', 'https://user:pass@github.com/file'):
            with self.subTest(url=url), self.assertRaises(ops.OperationError):
                handler.redirect_request(request, None, 302, '', {}, url)

    def test_inventory_does_not_write_or_expose_image_identity(self):
        observed = {'name': ops.CONTAINER, 'image': 'chat:live', 'image_id': 'secretly-masked-id', 'health': 'healthy'}
        with mock.patch.object(ops, 'target', return_value=observed), mock.patch.object(ops, 'write_record') as write:
            result = ops.main('inventory')
        self.assertTrue(result['read_only']); write.assert_not_called()
        self.assertNotIn('image_id', result)

    def test_invalid_operation_and_revision_cannot_reach_package_code(self):
        with mock.patch.object(ops, 'target', return_value={'name': ops.CONTAINER, 'image': 'chat:live', 'health': 'healthy'}):
            for operation, revision in [('shell', ''), ('prepare', '../bad'), ('deploy', 'main')]:
                with self.subTest(operation=operation), self.assertRaises(ops.OperationError): ops.main(operation, revision)

    def test_workflow_is_chat_only_and_keeps_independent_read_channel(self):
        source = (Path(__file__).parents[1] / 'workflows/chat-ops.yml').read_text(encoding='utf-8')
        self.assertIn('options: [inventory, preflight, prepare, deploy, enable-personal]', source)
        self.assertIn("format('chat-read-{0}', inputs.operation)", source)
        self.assertIn("'deploy-production'", source)
        self.assertIn('fingerprint: SHA256:3XgT+rjG+BpWEyVWUwI2p2SVojjzHpSxrbUFhLj15Ws', source)
        self.assertNotIn('push:', source)
        self.assertNotIn('script_b64', source)

    def enable_fixture(self, root):
        receipts = root / 'receipts/chat-fixed'; receipts.mkdir(parents=True)
        expected = {'backend/open_webui/main.py': 'public-source-digest'}
        observed = {'id': 'c' * 64, 'name': ops.CONTAINER, 'image': 'chat:personal', 'image_id': 'sha256:' + 'a' * 64, 'health': 'healthy'}
        scope = {'chat': {'new_image': observed['image']}}
        (receipts / 'receipt.json').write_text(json.dumps({'success': True, 'image': observed['image'], 'image_id': observed['image_id'], 'source_sha256': expected}))
        return observed, scope, expected

    def test_enable_requires_success_image_source_and_only_backs_up_false_bool(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); observed, scope, expected = self.enable_fixture(root)
            with mock.patch.object(ops, 'ROOT', root), mock.patch.object(ops, 'target', return_value=observed), mock.patch.object(ops, 'source_hashes', return_value=expected), mock.patch.object(ops, 'native_personal_flag', side_effect=[{'value': False}, {'before': False, 'after': True, 'changed': True}]) as native:
                result = ops.enable_personal(root, 'a' * 40, observed, scope)
            self.assertTrue(result['changed']); self.assertTrue(result['enabled'])
            self.assertEqual(native.call_args_list, [mock.call(observed['id'], 'read'), mock.call(observed['id'], 'enable')])
            backup = json.loads((root / 'enable-personal-before.json').read_text())
            self.assertEqual(backup, {'schema': 1, 'chat_revision': 'a' * 40, 'key': 'direct.enable', 'before': False})

    def test_enable_already_true_is_read_only_and_drift_never_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); observed, scope, expected = self.enable_fixture(root)
            with mock.patch.object(ops, 'source_hashes', return_value=expected), mock.patch.object(ops, 'native_personal_flag', return_value={'value': True}) as native, mock.patch.object(ops, 'write_record') as write:
                result = ops.enable_personal(root, 'a' * 40, observed, scope)
            self.assertFalse(result['changed']); write.assert_not_called()
            native.assert_called_once_with(observed['id'], 'read')
            drift = {**observed, 'image_id': 'sha256:' + 'b' * 64}
            with mock.patch.object(ops, 'native_personal_flag') as native, self.assertRaisesRegex(ops.OperationError, 'deployed_chat_image'):
                ops.enable_personal(root, 'a' * 40, drift, scope)
            native.assert_not_called()

    def test_enable_rechecks_source_after_backup_before_native_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); observed, scope, expected = self.enable_fixture(root)
            with mock.patch.object(ops, 'ROOT', root), mock.patch.object(ops, 'target', return_value=observed), mock.patch.object(ops, 'source_hashes', side_effect=[expected, {}]), mock.patch.object(ops, 'native_personal_flag', return_value={'value': False}) as native:
                with self.assertRaisesRegex(ops.OperationError, 'source_changed_before_flag_write'):
                    ops.enable_personal(root, 'a' * 40, observed, scope)
            native.assert_called_once_with(observed['id'], 'read')

    def native_program(self, mode, before=False, legacy_database=False):
        state = {'direct.enable': before, 'unrelated': {'secret': 'synthetic-not-a-real-key'}}
        original = copy.deepcopy(state); calls = []
        class Session:
            async def get(self, cls, key):
                calls.append(('session_get', key)); return SimpleNamespace(value=state[key])
            async def commit(self): calls.append(('commit',))
        @contextlib.asynccontextmanager
        async def session(): yield Session()
        class Config:
            @staticmethod
            async def get(key):
                calls.append(('get', key, os.environ.get('ENABLE_DB_MIGRATIONS'), os.environ.get('FROM_INIT_PY')))
                return state[key]
            @staticmethod
            async def upsert(updates, *, db):
                calls.append(('upsert', copy.deepcopy(updates)))
                self.assertIsInstance(db, Session)
                self.assertEqual(updates, {'direct.enable': True})
                state.update(updates)
        class AsyncEngine:
            async def dispose(self): pass
        native = ModuleType('open_webui.models.config'); native.Config = Config
        internal = ModuleType('open_webui.internal.db')
        internal.get_async_db = session; internal.async_engine = AsyncEngine(); internal.engine = SimpleNamespace(dispose=lambda: None)
        modules = {'open_webui.models.config': native, 'open_webui.internal.db': internal}
        output = io.StringIO()
        env = b'DATA_DIR=/synthetic-data\0DATABASE_URL=sqlite:////synthetic-data/webui.db\0'
        with mock.patch.dict(sys.modules, modules), mock.patch.object(sys, 'argv', ['fixed-code', mode]), mock.patch('pathlib.Path.read_bytes', return_value=env), mock.patch('pathlib.Path.exists', return_value=legacy_database), mock.patch.dict(os.environ, {}, clear=True), contextlib.redirect_stdout(output):
            exec(compile(ops.ENABLE_PERSONAL_PROGRAM, '<fixed native flag code>', 'exec'), {})
        self.assertEqual(state['unrelated'], original['unrelated'])
        self.assertNotIn('synthetic-not-a-real-key', output.getvalue())
        return json.loads(output.getvalue()), calls

    def test_fixed_native_program_uses_only_single_key_upsert_and_true_is_noop(self):
        result, calls = self.native_program('enable')
        self.assertEqual(result, {'before': False, 'after': True, 'changed': True})
        self.assertEqual([value for value in calls if value[0] == 'upsert'], [('upsert', {'direct.enable': True})])
        self.assertIn(('commit',), calls)
        self.assertTrue(all(value[2:] == ('false', 'false') for value in calls if value[0] == 'get'))
        result, calls = self.native_program('enable', before=True)
        self.assertFalse(result['changed'])
        self.assertFalse(any(value[0] in ('upsert', 'commit') for value in calls))
        result, calls = self.native_program('read')
        self.assertEqual(result, {'value': False})
        self.assertFalse(any(value[0] in ('upsert', 'commit') for value in calls))

    def test_fixed_native_program_rejects_legacy_import_migration_path(self):
        with self.assertRaisesRegex(RuntimeError, 'legacy_database_rename_path_present'):
            self.native_program('enable', legacy_database=True)

    def test_deploy_summary_reports_verified_new_image_not_preflight_image(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); revision = 'a' * 40; release = root / revision
            release.mkdir(); (release / 'source').mkdir(); (release / 'context').mkdir()
            (release / 'release-input-manifest.json').write_text('{}')
            scope = {'source': str(release / 'source'), 'chat': {'container': ops.CONTAINER.lstrip('/'), 'new_image': 'chat:verified-new'}}
            (release / 'scope.json').write_text(json.dumps(scope))
            prepared = {'chat_revision': revision, 'artifact_sha256': 'b' * 64, 'files': ops.payload_files(release), 'scope_sha256': ops.hashlib.sha256((release / 'scope.json').read_bytes()).hexdigest()}
            (release / 'prepared.json').write_text(json.dumps(prepared))
            deployed = mock.Mock()
            module = SimpleNamespace(PersonalConnectionsRelease=lambda *_: SimpleNamespace(deploy=deployed))
            observed = {'name': ops.CONTAINER, 'image': 'chat:old', 'health': 'healthy'}
            with mock.patch.object(ops, 'ROOT', root), mock.patch.object(ops, 'target', return_value=observed), mock.patch.object(ops, 'load_deployer', return_value=module):
                result = ops.main('deploy', revision, 'b' * 64)
            self.assertEqual(result['image'], 'chat:verified-new'); deployed.assert_called_once_with()


if __name__ == '__main__': unittest.main()
