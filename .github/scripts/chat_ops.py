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

# 只导入原生配置模型，不导入 main/config 的启动迁移、默认值播种或修复入口。
ENABLE_PERSONAL_PROGRAM = r'''
import asyncio,json,os,sys
from pathlib import Path
mode=sys.argv[1]
if mode not in ('read','enable'): raise RuntimeError('unsupported_flag_operation')
for item in Path('/proc/1/environ').read_bytes().split(b'\0'):
 name,sep,value=item.partition(b'=')
 name=name.decode(errors='ignore')
 if sep and (name.startswith('DATABASE_') or name in {'WEBUI_SECRET_KEY','WEBUI_JWT_SECRET_KEY','DATA_DIR','ENABLE_PERSISTENT_CONFIG'}):
  os.environ[name]=value.decode()
os.environ['ENABLE_DB_MIGRATIONS']='false'
os.environ['FROM_INIT_PY']='false'
os.environ['DATABASE_SQLITE_PRAGMA_BUSY_TIMEOUT']='5000'
if os.environ.get('ENABLE_PERSISTENT_CONFIG','true').lower()!='true': raise RuntimeError('persistent_config_required')
data=Path(os.environ.get('DATA_DIR') or '/app/backend/data')
if (data/'ollama.db').exists(): raise RuntimeError('legacy_database_rename_path_present')
if not os.environ.get('DATABASE_URL','sqlite:///').startswith('sqlite:///'): raise RuntimeError('sqlite_config_required')
from open_webui.models.config import Config
from open_webui.internal.db import get_async_db,async_engine,engine
KEY='direct.enable'
async def action():
 try:
  if mode=='read':
   value=await Config.get(KEY)
   if type(value) is not bool: raise RuntimeError('native_direct_flag_not_boolean')
   return {'value':value}
  async with get_async_db() as db:
   row=await db.get(Config,KEY)
   if row is None or type(row.value) is not bool: raise RuntimeError('native_direct_flag_not_boolean')
   before=row.value
   if before is False:
    await Config.upsert({KEY:True},db=db)
    await db.commit()
  after=await Config.get(KEY)
  if after is not True: raise RuntimeError('native_direct_flag_readback_failed')
  return {'before':before,'after':after,'changed':before is False}
 finally:
  await async_engine.dispose()
  engine.dispose()
print(json.dumps(asyncio.run(asyncio.wait_for(action(),timeout=20))))
'''


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
    template = '{"id":{{json .Id}},"name":{{json .Name}},"image_id":{{json .Image}},"image":{{json .Config.Image}},"running":{{json .State.Running}},"health":{{json .State.Health.Status}},"config_files":{{json (index .Config.Labels "com.docker.compose.project.config_files")}},"working_dir":{{json (index .Config.Labels "com.docker.compose.project.working_dir")}},"env_files":{{json (index .Config.Labels "com.docker.compose.project.environment_file")}}}'
    value = json.loads(run(['docker', 'inspect', '--format', template, ids[0]]))
    check(value['name'] == CONTAINER and value['running'] and value['health'] == 'healthy', 'chat_identity_or_health_changed')
    check(re.fullmatch(r'[a-f0-9]{64}', value.get('id', '')), 'chat_container_identity_invalid')
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
        stream.flush(); os.fsync(stream.fileno())


def payload_files(root):
    """准备后固定公开包内每个文件，后续操作拒绝源码/上下文漂移；不遍历私有备份。"""
    files = [root / 'release-input-manifest.json']
    for name in ('source', 'context'):
        for path in (root / name).rglob('*'):
            check(not path.is_symlink(), 'prepared_payload_symlink')
            if path.is_file(): files.append(path)
    check(len(files) <= MAX_FILES, 'prepared_payload_limit')
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(files)}


def native_personal_flag(container_id, mode):
    """固定模型 API 只读/启用 direct.enable；仅接收布尔元数据，不返回任何配置对象。"""
    check(re.fullmatch('[a-f0-9]{64}', container_id or '') and mode in ('read', 'enable'), 'native_flag_scope_invalid')
    output = run(['docker', 'exec', '-e', 'ENABLE_DB_MIGRATIONS=false', '-e', 'FROM_INIT_PY=false',
                  container_id, 'python', '-B', '-c', ENABLE_PERSONAL_PROGRAM, mode], timeout=45)
    result = json.loads(output.splitlines()[-1])
    expected = {'value'} if mode == 'read' else {'before', 'after', 'changed'}
    check(set(result) == expected and all(type(value) is bool for value in result.values()), 'native_flag_metadata_invalid')
    return result


def enable_personal(root, revision, observed, scope):
    """仅成功发布的当前候选可开启唯一原生开关；已为 true 时完全只读。"""
    records = sorted((root / 'receipts').glob('chat-*/receipt.json'))
    check(0 < len(records) <= 64, 'successful_chat_receipt_required')
    successful = [read_json(path) for path in records]
    successful = [record for record in successful if record.get('success') is True
                  and record.get('image') == scope['chat']['new_image'] and record.get('image_id') == observed['image_id']]
    check(successful and observed['image'] == scope['chat']['new_image'], 'deployed_chat_image_required')
    receipt = successful[-1]
    expected = receipt.get('source_sha256')
    check(isinstance(expected, dict) and 0 < len(expected) <= 64
          and all(isinstance(path, str) and not Path(path).is_absolute() and '..' not in Path(path).parts for path in expected), 'successful_chat_source_required')
    check(source_hashes(observed['id'], list(expected)) == expected, 'deployed_chat_source_changed')
    before = native_personal_flag(observed['id'], 'read')['value']
    if before is True:
        return {'complete': True, 'enabled': True, 'changed': False, 'previous': True}
    backup = root / 'enable-personal-before.json'
    value = {'schema': 1, 'chat_revision': revision, 'key': 'direct.enable', 'before': False}
    if backup.exists(): check(read_json(backup) == value, 'native_flag_backup_changed')
    else: write_record(backup, value)
    # 副本/备份完成后重核实际容器和源，exec 绑定不可变 ID，不能误写后来的替代服务。
    current = target()
    check(current['id'] == observed['id'] and current['image_id'] == observed['image_id'], 'chat_changed_before_flag_write')
    check(source_hashes(current['id'], list(expected)) == expected, 'chat_source_changed_before_flag_write')
    result = native_personal_flag(current['id'], 'enable')
    check(result['after'] is True, 'native_flag_enable_failed')
    return {'complete': True, 'enabled': True, 'changed': result['changed'], 'previous': result['before']}


def main(operation, revision='', artifact_sha256=''):
    """固定发布/单字段启用操作；写操作依赖已确认的 revision 和公开资产完整哈希。"""
    check(operation in ('inventory', 'preflight', 'prepare', 'deploy', 'enable-personal'), 'unsupported_operation')
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
    if operation == 'enable-personal':
        check(re.fullmatch('[a-f0-9]{64}', artifact_sha256 or '') and artifact_sha256 == prepared.get('artifact_sha256'), 'prepared_artifact_digest_changed')
        return enable_personal(root, revision, observed, scope)
    release = load_deployer(root / 'source').PersonalConnectionsRelease(scope, 'chat')
    if operation == 'preflight':
        release.preflight()
        return {'complete': True, 'read_only': True, 'payload_prepared': True, 'stable_key_confirmed': True, 'native_direct_connections': release.database_snapshot['direct_connections_persisted'], **summary}
    check(re.fullmatch('[a-f0-9]{64}', artifact_sha256 or '') and artifact_sha256 == prepared.get('artifact_sha256'), 'prepared_artifact_digest_changed')
    release.deploy()
    return {'complete': True, 'deployed': True, 'configuration_changed': False, 'data_changed_by_operator': False, 'model_requests': 0, **{**summary, 'image': scope['chat']['new_image']}}


if __name__ == '__main__':
    os.umask(0o077)
    try:
        check(2 <= len(sys.argv) <= 4, 'invalid_arguments')
        print(json.dumps(main(*sys.argv[1:]), sort_keys=True))
    except Exception as error:
        code = str(error) if isinstance(error, OperationError) and re.fullmatch(r'[a-z0-9_]{1,120}', str(error)) else type(error).__name__
        print(json.dumps({'complete': False, 'error': code}))
        raise SystemExit(1) from None
