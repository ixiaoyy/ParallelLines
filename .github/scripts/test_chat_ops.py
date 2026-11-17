"""固定 Chat 发布通道测试；不连网络、Docker 或生产服务器。"""
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
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
        self.assertIn('options: [inventory, preflight, prepare, deploy]', source)
        self.assertIn("format('chat-read-{0}', inputs.operation)", source)
        self.assertIn("'deploy-production'", source)
        self.assertIn('fingerprint: SHA256:3XgT+rjG+BpWEyVWUwI2p2SVojjzHpSxrbUFhLj15Ws', source)
        self.assertNotIn('push:', source)
        self.assertNotIn('script_b64', source)


if __name__ == '__main__': unittest.main()
