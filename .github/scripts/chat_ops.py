"""固定 Chat 个人连接发布通道；无任意脚本、目标地址或凭据输入。"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tarfile
import time
import urllib.request

ROOT = Path('/data/deployment/parallellines-chat-personal')
PROJECT = 'pl-official-candidate-20261030'
SERVICE = 'openwebui'
CONTAINER = '/pl-official-candidate-20261030-openwebui-1'
MAX_ARCHIVE = 256 * 1024 * 1024
MAX_EXPANDED = 512 * 1024 * 1024
MAX_FILES = 12000
ALLOWED_DOWNLOAD_HOSTS = {'github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com'}


class OperationError(RuntimeError):
    """稳定错误码，不在共享日志展开命令输出、配置或用户数据。"""


def check(value, code):
    if not value:
        raise OperationError(code)


def run(args, timeout=30):
    """固定 argv 有界执行；调用者只输出明确白名单字段。"""
    try:
        result = subprocess.run([str(value) for value in args], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        raise OperationError('command_unavailable_or_timeout') from None
    check(result.returncode == 0, 'command_failed')
    check(len(result.stdout) + len(result.stderr) <= 4 * 1024 * 1024, 'command_output_limit')
    return result.stdout.strip()


def safe_path(value):
    """明确绝对目录，拒绝软链和父级逃逸；不读取 env_file 指向的内容。"""
    path = Path(value)
    check(path.is_absolute() and '..' not in path.parts, 'unsafe_path')
    check(not any(item.is_symlink() for item in (path, *path.parents)), 'symlink_path_rejected')
    return path


def target():
    """锁定实际单 Chat Compose 服务；不检查其他产品的环境或凭据。"""
    ids = run(['docker', 'ps', '-aq', '--filter', 'label=com.docker.compose.project=' + PROJECT,
               '--filter', 'label=com.docker.compose.service=' + SERVICE]).split()
    check(len(ids) == 1 and re.fullmatch(r'[a-f0-9]{12,64}', ids[0]), 'unique_chat_container_required')
    template = '{"name":{{json .Name}},"image_id":{{json .Image}},"image":{{json .Config.Image}},"running":{{json .State.Running}},"health":{{json .State.Health.Status}},"config_files":{{json (index .Config.Labels "com.docker.compose.project.config_files")}},"working_dir":{{json (index .Config.Labels "com.docker.compose.project.working_dir")}},"env_files":{{json (index .Config.Labels "com.docker.compose.project.environment_file")}}}'
    value = json.loads(run(['docker', 'inspect', '--format', template, ids[0]]))
    check(value['name'] == CONTAINER and value['running'] and value['health'] == 'healthy', 'chat_identity_or_health_changed')
    check(re.fullmatch(r'sha256:[a-f0-9]{64}', value['image_id']), 'chat_image_identity_invalid')
    for name in ('config_files', 'working_dir'):
        check(isinstance(value.get(name), str) and value[name], 'chat_compose_metadata_missing')
    value['config_files'] = [str(safe_path(path)) for path in value['config_files'].split(',') if path]
    value['env_files'] = [str(safe_path(path)) for path in (value['env_files'] or '').split(',') if path]
    safe_path(value['working_dir'])
    check(0 < len(value['config_files']) <= 8 and len(value['env_files']) <= 8, 'chat_compose_metadata_limit')
    return value


def read_json(path, limit=2 * 1024 * 1024):
    path = safe_path(path)
    check(path.is_file() and path.stat().st_size <= limit, 'record_file_invalid')
    return json.loads(path.read_text(encoding='utf-8'))


def load_deployer(source):
    """只加载已校验发布包内的既有 Chat 发布能力。"""
    path = source / 'deploy/deploy-personal-connections.py'
    check(path.is_file() and not path.is_symlink(), 'chat_deployer_missing')
    spec = importlib.util.spec_from_file_location('chat_personal_deployer', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def source_hashes(container, names):
    """只检查公开应用文件；所有比较在服务器内部，不输出被遮蔽的摘要。"""
    program = 'import hashlib,json;from pathlib import Path;r=Path("/app");names=' + repr(names) + ';print(json.dumps({p:hashlib.sha256((r/p).read_bytes()).hexdigest() for p in names}))'
    return json.loads(run(['docker', 'exec', container, 'python', '-B', '-c', program], timeout=45))


class RestrictedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        """只允许 GitHub 官方发布资产 HTTPS 重定向，不把下载变成任意地址请求。"""
        from urllib.parse import urlsplit
        parsed = urlsplit(new_url)
        check(parsed.scheme == 'https' and parsed.hostname in ALLOWED_DOWNLOAD_HOSTS and not parsed.username and not parsed.password, 'artifact_redirect_denied')
        return super().redirect_request(request, fp, code, message, headers, new_url)


def download(revision, expected, destination):
    """下载固定仓库/名称的公开资产，校验输入哈希和体积；失败不执行任何包内代码。"""
    tag = 'personal-connections-' + revision
    name = 'parallellines-chat-personal-connections-' + revision + '.tar.gz'
    url = 'https://github.com/ixiaoyy/parallellines-chat/releases/download/' + tag + '/' + name
    check(not destination.exists(), 'artifact_destination_exists')
    opener = urllib.request.build_opener(RestrictedRedirect())
    deadline = time.monotonic() + 300
    digest = hashlib.sha256(); size = 0
    with opener.open(urllib.request.Request(url, headers={'User-Agent': 'ParallelLines-Chat-Release'}), timeout=30) as response:
        declared = response.headers.get('Content-Length')
        check(declared is None or int(declared) <= MAX_ARCHIVE, 'artifact_too_large')
        with destination.open('xb') as stream:
            os.chmod(destination, 0o600)
            while True:
                check(time.monotonic() < deadline, 'artifact_download_timeout')
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk); check(size <= MAX_ARCHIVE, 'artifact_too_large')
                digest.update(chunk); stream.write(chunk)
    check(size > 0 and digest.hexdigest() == expected, 'artifact_integrity_failed')


def extract(archive, destination):
    """先验证全部条目，再手动展开普通公开文件；禁止链接、设备及资源爆炸。"""
    with tarfile.open(archive, 'r:gz') as tar:
        members = tar.getmembers()
        check(0 < len(members) <= MAX_FILES, 'artifact_file_count_limit')
        total = 0; seen = set()
        for item in members:
            path = PurePosixPath(item.name)
            check(item.name and path.parts and '\\' not in item.name and not path.is_absolute() and '..' not in path.parts, 'artifact_path_denied')
            check(path.parts[0] in ('source', 'context', 'release-input-manifest.json'), 'artifact_root_denied')
            check(path.as_posix() not in seen, 'artifact_duplicate_path'); seen.add(path.as_posix())
            check(item.isdir() or item.isfile(), 'artifact_special_file_denied')
            check(not any(part in ('.git', 'node_modules', 'frontend-debug', '__pycache__') for part in path.parts), 'artifact_private_directory_denied')
            check(path.name not in ('.env', '.env.local') and not path.name.endswith(('.key', '.pem', '.map')), 'artifact_private_file_denied')
            check(0 <= item.size <= 128 * 1024 * 1024, 'artifact_member_limit')
            total += item.size; check(total <= MAX_EXPANDED, 'artifact_expansion_limit')
        for item in members:
            path = destination / item.name
            check(path.resolve().is_relative_to(destination.resolve()), 'artifact_path_escape')
            if item.isdir():
                path.mkdir(parents=True, exist_ok=True, mode=0o755)
            else:
                path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
                check(not path.exists(), 'artifact_file_collision')
                with tar.extractfile(item) as reader, path.open('xb') as stream:
                    while True:
                        chunk = reader.read(1024 * 1024)
                        if not chunk: break
                        stream.write(chunk)
                os.chmod(path, 0o644)


def make_scope(root, revision, observed):
    """使用当前服务内部前像生成私有 scope，镜像 ID 和配置内容从不经过共享日志。"""
    source = root / 'source'; context = root / 'context'
    record = read_json(root / 'release-input-manifest.json')
    check(record.get('schema') == 1 and record.get('chat_revision') == revision, 'release_input_identity_changed')
    feature_bytes = (source / 'openwebui-profile-overlay/personal-connections/manifest.json').read_bytes()
    public_bytes = (context / 'frontend-build-manifest.json').read_bytes()
    check(hashlib.sha256(feature_bytes).hexdigest() == record.get('backend_overlay_manifest_sha256'), 'release_backend_manifest_changed')
    check(hashlib.sha256(public_bytes).hexdigest() == record.get('frontend_manifest_sha256'), 'release_frontend_manifest_changed')
    feature = json.loads(feature_bytes)
    expected = {p: value['before_sha256'] for p, value in feature['files'].items() if p.startswith('backend/') and value['before_sha256'] is not None}
    protected = ['backend/open_webui/main.py', 'backend/open_webui/utils/auth.py', 'backend/open_webui/utils/oauth.py', 'backend/open_webui/utils/main_unified_login.py', 'build/index.html']
    names = list(dict.fromkeys([*expected, *protected]))
    actual = source_hashes(observed['name'].lstrip('/'), names)
    check(all(actual.get(p) == value for p, value in expected.items()), 'live_backend_before_changed')
    module = load_deployer(source)
    selected = None
    for filename in observed['config_files']:
        service = module.base.utils.load_yaml(safe_path(filename).read_text(encoding='utf-8')).get('services', {}).get(SERVICE, {})
        if 'image' in service:
            selected = filename, service['image']
    check(selected is not None, 'chat_compose_image_definition_missing')
    return {'source': str(source), 'receipts': str(root / 'receipts'), 'chat': {
        'container': observed['name'].lstrip('/'), 'project': PROJECT, 'service': SERVICE,
        'new_image': 'parallellines-chat:personal-' + revision[:12], 'expected_image_id': observed['image_id'],
        'expected_compose_image': selected[1], 'target_compose': selected[0], 'working_dir': observed['working_dir'],
        'env_files': observed['env_files'], 'compose_files': observed['config_files'], 'source_root': '/app', 'interpreter': 'python',
        'expected_source': actual, 'frontend_context': str(context), 'frontend_manifest_sha256': record['frontend_manifest_sha256']}}


def write_record(path, value):
    """事务记录仅位于本次私有发布目录，保留源和备份，不覆盖其他发布。"""
    check(path.is_relative_to(ROOT) and not path.exists(), 'private_record_collision')
    with path.open('x', encoding='utf-8') as stream:
        os.chmod(path, 0o600); json.dump(value, stream, indent=2)


def payload_files(root):
    """准备后固定公开包内每个文件，后续操作拒绝源码/上下文漂移；不遍历私有备份。"""
    files = [root / 'release-input-manifest.json']
    for name in ('source', 'context'):
        for path in (root / name).rglob('*'):
            check(not path.is_symlink(), 'prepared_payload_symlink')
            if path.is_file(): files.append(path)
    check(len(files) <= MAX_FILES, 'prepared_payload_limit')
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(files)}


def main(operation, revision='', artifact_sha256=''):
    """固定四种操作；写操作依赖已确认的 revision 和公开资产完整哈希。"""
    check(operation in ('inventory', 'preflight', 'prepare', 'deploy'), 'unsupported_operation')
    observed = target()
    summary = {'container': observed['name'], 'project': PROJECT, 'service': SERVICE, 'image': observed['image'], 'health': observed['health']}
    if operation == 'inventory':
        return {'complete': True, 'read_only': True, **summary}
    check(re.fullmatch('[a-f0-9]{40}', revision or ''), 'chat_revision_required')
    root = safe_path(ROOT / revision)
    if operation == 'preflight' and not (root / 'scope.json').is_file():
        return {'complete': True, 'read_only': True, 'payload_prepared': False, **summary}
    if operation == 'prepare':
        check(re.fullmatch('[a-f0-9]{64}', artifact_sha256 or ''), 'artifact_digest_required')
        safe_path(ROOT).mkdir(parents=True, exist_ok=True, mode=0o700)
        check(ROOT.stat().st_mode & 0o077 == 0, 'unsafe_release_parent')
        check(not root.exists(), 'release_directory_exists')
        root.mkdir(mode=0o700)
        archive = root / 'payload.tar.gz'
        download(revision, artifact_sha256, archive)
        extract(archive, root)
        scope = make_scope(root, revision, observed)
        release = load_deployer(root / 'source').PersonalConnectionsRelease(scope, 'chat')
        release.preflight()
        write_record(root / 'scope.json', scope)
        write_record(root / 'prepared.json', {'schema': 1, 'chat_revision': revision, 'artifact_sha256': artifact_sha256,
                                              'scope_sha256': hashlib.sha256((root / 'scope.json').read_bytes()).hexdigest(), 'files': payload_files(root)})
        return {'complete': True, 'prepared': True, 'configuration_changed': False, 'data_changed': False, **summary}
    prepared = read_json(root / 'prepared.json')
    check(prepared.get('chat_revision') == revision, 'prepared_revision_changed')
    check(prepared.get('files') == payload_files(root), 'prepared_payload_changed')
    check(prepared.get('scope_sha256') == hashlib.sha256((root / 'scope.json').read_bytes()).hexdigest(), 'prepared_scope_changed')
    scope = read_json(root / 'scope.json')
    check(scope.get('source') == str(root / 'source') and scope['chat']['container'] == CONTAINER.lstrip('/'), 'prepared_target_changed')
    release = load_deployer(root / 'source').PersonalConnectionsRelease(scope, 'chat')
    if operation == 'preflight':
        release.preflight()
        return {'complete': True, 'read_only': True, 'payload_prepared': True, 'stable_key_confirmed': True, 'native_direct_connections': release.database_snapshot['direct_connections_persisted'], **summary}
    check(re.fullmatch('[a-f0-9]{64}', artifact_sha256 or '') and artifact_sha256 == prepared.get('artifact_sha256'), 'prepared_artifact_digest_changed')
    release.deploy()
    return {'complete': True, 'deployed': True, 'configuration_changed': False, 'data_changed_by_operator': False, 'model_requests': 0, **summary}


if __name__ == '__main__':
    os.umask(0o077)
    try:
        check(2 <= len(sys.argv) <= 4, 'invalid_arguments')
        print(json.dumps(main(*sys.argv[1:]), sort_keys=True))
    except Exception as error:
        code = str(error) if isinstance(error, OperationError) and re.fullmatch(r'[a-z0-9_]{1,120}', str(error)) else type(error).__name__
        print(json.dumps({'complete': False, 'error': code}))
        raise SystemExit(1) from None
