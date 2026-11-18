"""Tavern 主站登录的固定配置操作；复用原部署守卫，不修改续期消费者。"""
import contextlib
import fcntl
import json
import os
from pathlib import Path
import re
import secrets
import stat
import sys
import tempfile
import time

import entertainment_ops as native


OPERATIONS = ('enable-main-login', 'restore-main-login', 'main-login-status')
STATE = native.ROOT / 'main-login.json'
BACKUP = native.ROOT / 'runtime/main-login-backup'
PROGRAM = native.ROOT / 'sso-operations.py'
# 固定识别这次已写完配置但未结案的首版，保留原独立程序供审计。
LEGACY_REVISION = '7d3ab51cff65e239e17c945a87950cbb6df8ab85'
LEGACY_EXTENSION = '8e9e34b40ac822f2a53ec7612101c4cd8d749805f2bae67fd1de63f5cf77d178'
LEGACY_PROGRAM_SHA = '168ad90981a394c14ef35a006a33597640819f2a55e92bb0ea6c975d95c74fee'
LEGACY_PROGRAM = native.ROOT / 'sso-operations.before-element-sync-7d3ab51c.py'
CANDIDATE = native.ROOT / 'data/synapse/tavern-sso-candidate.yaml'
SECRET = native.ROOT / 'data/synapse/tavern-oidc-client-secret'
LOCK = native.ROOT / 'runtime/main-login.lock'
TARGETS = {
    'synapse': native.ROOT / 'data/synapse/homeserver.yaml',
    'element': native.ROOT / 'config/element.json',
    'prepared': native.PREPARED,
}
ELEMENT_BASE = {'default_server_config': {'m.homeserver': {
    'base_url': 'https://matrix.pingxingxian.space',
    'server_name': 'matrix.pingxingxian.space',
}}}
ELEMENT_SSO = {**ELEMENT_BASE, 'disable_custom_urls': True,
               'sso_redirect_options': {'immediate': True}}
OIDC_PROVIDER = {
    'idp_id': 'parallellines', 'idp_name': '平行线',
    'issuer': 'https://pingxingxian.space/auth/oidc',
    'client_id': 'parallellines-tavern',
    'client_secret_path': '/data/tavern-oidc-client-secret',
    'client_auth_method': 'client_secret_basic', 'pkce_method': 'always',
    'scopes': ['openid', 'profile'], 'user_profile_method': 'userinfo_endpoint',
    'allow_existing_users': False, 'enable_registration': True,
    'user_mapping_provider': {'config': {
        'localpart_template': 'pl_{{ user.sub }}',
        'display_name_template': '{{ user.name }}',
    }},
}

ELEMENT_SYNC = r'''
set -eu
src=/app/config.json
dir=/tmp/element-web-config
dst=$dir/config.json
[ ! -L "$dir" ] && [ -d "$dir" ] && [ ! -L "$dst" ] && [ -f "$dst" ] && [ ! -L "$src" ] && [ -f "$src" ] || exit 1
[ "$(stat -c %u:%a "$dst")" = "$(id -u):644" ]
source_sha=$(sha256sum "$src"); [ "${source_sha%% *}" = "$2" ]
live_sha=$(sha256sum "$dst"); live_sha=${live_sha%% *}
[ "$live_sha" = "$2" ] && exit 0
[ "$live_sha" = "$1" ]
tmp=$(mktemp "$dir/.tavern-config.XXXXXXXX")
trap 'rm -f "$tmp"' EXIT
cp "$src" "$tmp"
chmod 644 "$tmp"
tmp_sha=$(sha256sum "$tmp"); [ "${tmp_sha%% *}" = "$2" ]
live_sha=$(sha256sum "$dst"); [ "${live_sha%% *}" = "$1" ]
mv -f "$tmp" "$dst"
'''

# 只在既有官方容器内解析 YAML。候选文件不激活服务，也不输出任何私有配置。
PREPARE_PROGRAM = r'''
import json,os,sys
from pathlib import Path
import yaml
source=Path('/data/homeserver.yaml')
target=Path('/data/tavern-sso-candidate.yaml')
actual=yaml.safe_load(source.read_text())
assert isinstance(actual,dict) and actual['server_name']=='matrix.pingxingxian.space'
assert actual.get('enable_registration') is True and actual.get('registration_requires_token') is True
assert not actual.get('oidc_providers') and not actual.get('oidc_config')
assert not actual.get('sso')
password=actual.get('password_config') or {}
assert isinstance(password,dict) and password.get('enabled',True) is True
actual['enable_registration']=False
actual.pop('registration_requires_token',None)
actual['password_config']={**password,'enabled':'only_for_reauth'}
actual['oidc_providers']=[json.loads(sys.argv[1])]
actual['sso']={'client_whitelist':['https://tavern.pingxingxian.space/']}
content=yaml.safe_dump(actual,sort_keys=False,allow_unicode=True).encode()
assert 0<len(content)<=131072
if target.exists() or target.is_symlink():
    assert target.is_file() and not target.is_symlink() and target.read_bytes()==content
    info=target.stat()
    assert info.st_uid==991 and info.st_gid==991 and info.st_mode&0o777==0o600
else:
    fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as stream:
        stream.write(content);stream.flush();os.fsync(stream.fileno())
    os.chown(target,991,991)
print(json.dumps({'complete':True}))
'''


def file_snapshot(path):
    """读取本模块有界常规文件及权限/归属，返回私有前像，不输出正文。"""
    path = native.owned(path)
    info = path.stat()
    limit = 240 * 1024 if path in (PROGRAM, LEGACY_PROGRAM) else 128 * 1024
    native.check(stat.S_ISREG(info.st_mode) and 0 < info.st_size <= limit,
                 'main_login_file_missing_or_out_of_bound')
    content = path.read_bytes()
    return content, {'sha256': native.digest(content), 'uid': info.st_uid,
                     'gid': info.st_gid, 'mode': stat.S_IMODE(info.st_mode),
                     'device': info.st_dev, 'inode': info.st_ino}


def secret_identity():
    """仅核本次专用秘密文件；它须先由另行授权的配置渠道与身份桥同步。"""
    native.check(native.owned(SECRET).is_file(), 'private_tavern_oidc_secret_required')
    content, info = file_snapshot(SECRET)
    native.check(info['uid'] == 991 and info['gid'] == 991 and info['mode'] == 0o600 and
                 32 <= len(content.strip()) <= 4096, 'private_tavern_oidc_secret_required')
    return info['sha256']


def is_legacy_record(value):
    """仅兼容已核首次生产切换的精确版本，不接受其他历史消费者。"""
    return (value.get('operation_revision'), value.get('extension_sha256'), value.get('program_sha256')) == (
        LEGACY_REVISION, LEGACY_EXTENSION, LEGACY_PROGRAM_SHA)


def load_record():
    """校验本次叠加配置回执，不将其它版本或目录当成本次恢复对象。"""
    value = native.read_record(STATE)
    native.check(value.get('schema') == 1 and value.get('project') == native.PROJECT and
                 value.get('baseline_source_revision') == native.SOURCE_REVISION,
                 'main_login_record_identity_changed')
    native.check(value.get('status') in ('pending', 'enabled', 'restoring', 'restored'),
                 'main_login_record_status_invalid')
    current = native.digest(globals().get('SSO_SOURCE', '').encode())
    native.check((value.get('extension_sha256') == current or is_legacy_record(value)) and
                 value.get('native_source_sha256') == native.digest(native.OPS_SOURCE.encode()),
                 'main_login_recovery_source_changed')
    return value


def verify_recovery(value):
    """原位恢复入口须为已登记的 root 私有程序；只识别自身原子升级的中间态。"""
    _, info = file_snapshot(PROGRAM)
    native.check(info['uid'] == 0 and info['mode'] == 0o600, 'main_login_recovery_program_changed')
    if info['sha256'] == value.get('program_sha256'):
        return
    source = globals().get('SSO_PROGRAM_SOURCE', '')
    native.check(is_legacy_record(value) and source and info['sha256'] == native.digest(source.encode()),
                 'main_login_recovery_program_changed')
    _, old = file_snapshot(LEGACY_PROGRAM)
    native.check(old['uid'] == 0 and old['mode'] == 0o600 and old['sha256'] == LEGACY_PROGRAM_SHA,
                 'main_login_legacy_recovery_program_changed')


def save_private_snapshot(path, content):
    """排他保存本次备份/恢复程序；中断重试仅复用完全相同的 root 私有文件。"""
    path = native.owned(path)
    if path.exists() or path.is_symlink():
        actual, info = file_snapshot(path)
        native.check(actual == content and info['uid'] == 0 and info['mode'] == 0o600,
                     'unknown_main_login_backup_or_program')
        return
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def upgrade_recovery(value):
    """保留原备份及独立入口路径，原子换程序；调用方再持久化新回执。"""
    if not is_legacy_record(value):
        return
    verify_recovery(value)
    for name in TARGETS:
        for side in ('before', 'after'):
            backup_content(value, name, side)
    source = globals().get('SSO_PROGRAM_SOURCE', '')
    native.check(isinstance(source, str) and source, 'main_login_reviewed_source_required')
    compile(source, '<tavern-recovery>', 'exec')
    current, info = file_snapshot(PROGRAM)
    if info['sha256'] == LEGACY_PROGRAM_SHA:
        save_private_snapshot(LEGACY_PROGRAM, current)
        target = native.owned(PROGRAM)
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.tavern-recovery-', delete=False) as stream:
            tmp = Path(stream.name)
            stream.write(source.encode())
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.replace(tmp, target)
            directory = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if tmp.exists():
                tmp.unlink()
    value.update(extension_sha256=native.digest(globals()['SSO_SOURCE'].encode()),
                 program_sha256=native.digest(source.encode()),
                 recovery_operation_revision=globals()['OPS_REVISION'])
    verify_recovery(value)


def intermediate_content_matches(content, source, target):
    """识别从 source 顺序覆盖 target 后尚未完成 truncate 的精确中间像。"""
    if content == target:
        return True
    if len(content) > len(source):
        return len(content) <= len(target) and content == target[:len(content)]
    if len(content) != len(source):
        return False
    prefix = 0
    while prefix < min(len(content), len(target)) and content[prefix] == target[prefix]:
        prefix += 1
    difference = max((index + 1 for index, pair in enumerate(zip(content, source))
                      if pair[0] != pair[1]), default=0)
    return difference <= prefix


def interrupted_write_matches(value, name, content):
    """只为回执中当前写意图核私有精确前像；其它文件或陌生内容不放行。"""
    intent = value.get('write_intent', {})
    if value['status'] not in ('pending', 'restoring') or intent.get('target') != name:
        return False
    filename = intent.get('snapshot', '')
    if intent.get('side') not in ('before', 'after') or not re.fullmatch(
            re.escape(name) + r'\.write-[0-9a-f]{16}\.before', filename):
        return False
    source, info = file_snapshot(BACKUP / filename)
    native.check(info['uid'] == 0 and info['mode'] == 0o600 and
                 info['sha256'] == intent.get('sha256'), 'main_login_write_intent_snapshot_changed')
    target = backup_content(value, name, intent['side'])
    return intermediate_content_matches(content, source, target)


def assert_targets(value, *, side=None, allow_interrupted=False):
    """只接受同 inode 的精确前/后像；恢复可另核本次持久写意图的精确中间像。"""
    for name, path in TARGETS.items():
        content, actual = file_snapshot(path)
        before = value['before'][name]
        native.check(all(actual[key] == before[key] for key in ('uid', 'gid', 'mode', 'device', 'inode')),
                     'main_login_target_identity_changed')
        allowed = [value[side][name]['sha256']] if side else [
            before['sha256'], value['after'][name]['sha256']]
        native.check(actual['sha256'] in allowed or
                     (side is None and allow_interrupted and interrupted_write_matches(value, name, content)),
                     'main_login_unknown_configuration_preimage')


def backup_content(value, name, side):
    """读取本次固定备份并核完整性；完整 Synapse 配置始终只留服务器私有目录。"""
    path = native.owned(BACKUP / (name + '.' + side))
    content, info = file_snapshot(path)
    native.check(info['uid'] == 0 and info['mode'] == 0o600 and
                 info['sha256'] == value[side][name]['sha256'], 'main_login_backup_changed')
    return content


def write_target(value, name, side):
    """先持久化精确写意图再原地覆盖；中断可验证恢复，保留 bind mount inode。"""
    content = backup_content(value, name, side)
    assert_targets(value, allow_interrupted=side == 'before')
    path = native.owned(TARGETS[name])
    fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW)
    with os.fdopen(fd, 'r+b') as stream:
        info = os.fstat(stream.fileno())
        before = value['before'][name]
        native.check((info.st_dev, info.st_ino) == (before['device'], before['inode']),
                     'main_login_target_inode_raced')
        current = stream.read()
        native.check(native.digest(current) in (before['sha256'], value['after'][name]['sha256']) or
                     (side == 'before' and interrupted_write_matches(value, name, current)),
                     'main_login_target_content_raced')
        if current == content:
            if value.get('write_intent', {}).get('target') == name:
                value.pop('write_intent')
                native.private_record(STATE, value)
            return
        # 每次写都留下不可变前像；恢复自身再次中断也沿同一精确关系恢复，不放宽其它漂移。
        native.check(len(list(BACKUP.glob('*.write-*.before'))) < 32, 'main_login_write_journal_bound')
        snapshot = name + '.write-' + secrets.token_hex(8) + '.before'
        save_private_snapshot(BACKUP / snapshot, current)
        value['write_intent'] = {'target': name, 'side': side, 'snapshot': snapshot,
                                 'sha256': native.digest(current)}
        native.private_record(STATE, value)
        stream.seek(0)
        stream.write(content)
        stream.truncate()
        stream.flush()
        os.fsync(stream.fileno())
    native.check(file_snapshot(path)[1]['sha256'] == value[side][name]['sha256'],
                 'main_login_configuration_write_incomplete')
    value.pop('write_intent')
    native.private_record(STATE, value)


def synapse_container(runner, value=None):
    """返回现有同一 Synapse 容器，调用方可在配置失败后恢复而不要求它健康。"""
    saved, items = native.live_module_record(runner)
    if value is not None:
        native.check(saved['container_ids'] == value['container_ids'],
                     'main_login_module_container_changed')
    return native.select(items, native.PROJECT, 'synapse')


def login_flows():
    """只读本机 Matrix 原生登录能力，不交换授权码或创建用户/设备。"""
    return native.request_status('http://127.0.0.1:13102/_matrix/client/v3/login', expected_json=True)


def verify_sso_flows():
    """普通用户仅用 SSO/token；保留原生服务账号 API 能力，并核固定身份提供者。"""
    flows = login_flows().get('flows')
    native.check(isinstance(flows, list) and flows and
                 {item.get('type') for item in flows} <=
                 {'m.login.sso', 'm.login.token', 'm.login.application_service'},
                 'main_login_native_password_flow_still_enabled')
    sso = [item for item in flows if item.get('type') == 'm.login.sso']
    native.check(len(sso) == 1 and [item.get('id') for item in sso[0].get('identity_providers', [])] ==
                 ['oidc-parallellines'], 'main_login_native_provider_missing_or_changed')


def sync_element_config(runner, value, side):
    """Element 将挂载文件复制后对外提供；原子更新已登记容器里的实际网页副本。"""
    saved, items = native.live_module_record(runner)
    native.check(saved['container_ids'] == value['container_ids'], 'main_login_module_container_changed')
    element = native.select(items, native.PROJECT, 'element')
    expected = backup_content(value, 'element', side)
    desired = native.digest(expected)
    other = 'before' if side == 'after' else 'after'
    previous = native.digest(backup_content(value, 'element', other))
    runner.run('main_login_sync_element_served_config', [
        'docker', 'exec', element['id'], 'sh', '-c', ELEMENT_SYNC, 'tavern-element-sync', previous, desired])
    seen = native.request_status('http://127.0.0.1:13101/config.json', expected_json=True)
    native.check(seen == json.loads(expected), 'main_login_element_served_configuration_changed')


def verify_bridge_client(runner, containers):
    """只读现有健康发行方的客户端布尔结果；未配置前不关闭 Tavern 原生登录。"""
    bridge = native.select(containers, 'parallellines-chat', 'chat-oidc')
    native.check(bridge['running'] and bridge['health'] == 'healthy', 'tavern_bridge_not_healthy')
    program = ('import("./config.mjs").then(({loadConfiguration})=>'
               'process.exit(loadConfiguration().clients.some(c=>c.clientId==="parallellines-tavern"'
               '&&c.callbackUri==="https://matrix.pingxingxian.space/_synapse/client/oidc/callback"'
               '&&!c.refreshEnabled&&!c.profileSyncEnabled)?0:1))')
    runner.run('tavern_bridge_client_not_configured', [
        'docker', 'exec', '--workdir', '/app', bridge['id'], 'node', '-e', program])


def prepare_snapshots(runner, synapse):
    """生成并校验原生候选，保存前后像与独立恢复入口，再允许激活。"""
    secret_sha = secret_identity()
    native.check(json.loads(TARGETS['element'].read_text()) == ELEMENT_BASE,
                 'main_login_element_baseline_changed')
    source = globals().get('SSO_PROGRAM_SOURCE')
    revision = globals().get('OPS_REVISION')
    native.check(isinstance(source, str) and 0 < len(source.encode()) <= 240 * 1024 and
                 isinstance(revision, str) and re.fullmatch('[0-9a-f]{40}', revision),
                 'reviewed_main_login_bundle_required')
    result = runner.run('prepare_native_main_login_candidate', [
        'docker', 'exec', '--user', '0:0', synapse['id'], 'python', '-c', PREPARE_PROGRAM,
        json.dumps(OIDC_PROVIDER, ensure_ascii=True)], timeout=30)
    native.check(native.response_json(result.stdout).get('complete') is True,
                 'main_login_candidate_not_prepared')
    runner.run('validate_native_main_login_candidate', [
        'docker', 'exec', '--user', '991:991', synapse['id'], 'python', '-m', 'synapse.config',
        '-c', '/data/tavern-sso-candidate.yaml'], timeout=45)
    before = {name: file_snapshot(path) for name, path in TARGETS.items()}
    after_synapse = file_snapshot(CANDIDATE)[0]
    after_element = (json.dumps(ELEMENT_SSO, ensure_ascii=False, indent=2) + '\n').encode()
    prepared = json.loads(before['prepared'][0])
    prepared['files']['config/element.json'] = native.digest(after_element)
    prepared['private_files']['data/synapse/homeserver.yaml'] = native.digest(after_synapse)
    prepared['main_login_overlay'] = {'operation_revision': revision,
                                     'client_id': 'parallellines-tavern'}
    after = {'synapse': after_synapse, 'element': after_element,
             'prepared': (json.dumps(prepared, sort_keys=True, indent=2) + '\n').encode()}
    native.owned(BACKUP).mkdir(mode=0o700, exist_ok=True)
    directory = BACKUP.stat()
    allowed = {name + '.' + side for name in TARGETS for side in ('before', 'after')}
    native.check(directory.st_uid == 0 and stat.S_IMODE(directory.st_mode) == 0o700 and
                 {path.name for path in BACKUP.iterdir()} <= allowed, 'unknown_main_login_backup_directory')
    for name in TARGETS:
        for side, content in (('before', before[name][0]), ('after', after[name])):
            save_private_snapshot(BACKUP / (name + '.' + side), content)
    save_private_snapshot(PROGRAM, source.encode())
    saved, _ = native.live_module_record(runner)
    value = {'schema': 1, 'project': native.PROJECT, 'baseline_source_revision': native.SOURCE_REVISION,
             'operation_revision': revision, 'status': 'pending', 'stage': 'backed_up',
             'extension_sha256': native.digest(globals()['SSO_SOURCE'].encode()),
             'native_source_sha256': native.digest(native.OPS_SOURCE.encode()),
             'program_sha256': native.digest(source.encode()), 'secret_sha256': secret_sha,
             'container_ids': saved['container_ids'], 'login_flows_before': login_flows(),
             'before': {name: item[1] for name, item in before.items()},
             'after': {name: {'sha256': native.digest(content)} for name, content in after.items()}}
    native.private_record(STATE, value)
    native.check(file_snapshot(CANDIDATE)[1]['sha256'] == value['after']['synapse']['sha256'],
                 'main_login_staged_candidate_changed')
    native.owned(CANDIDATE).unlink()
    verify_recovery(value)
    # 真实走已保存程序的只读分发，确认恢复入口不依赖 GitHub 注入或身份桥登录。
    probe = runner.run('verify_independent_main_login_recovery', [
        '/usr/bin/python3', '-B', str(PROGRAM), 'main-login-status'], timeout=90)
    observed = native.response_json(probe.stdout)
    native.check(observed.get('complete') is True and observed.get('main_login_status') == 'pending',
                 'independent_main_login_recovery_not_verified')
    return value


def restart_synapse(runner, value):
    """只重启回执中同一 Synapse，保留 Element/Postgres/网关与其它系统身份。"""
    synapse = synapse_container(runner, value)
    runner.run('restart_same_synapse_for_main_login', [
        'docker', 'restart', '--time', '20', synapse['id']], timeout=55)
    native.wait_native_health(runner, seconds=150)


@contextlib.contextmanager
def write_operation_lock():
    """串行化 Actions 与独立恢复程序的写动作；只读状态不创建锁文件。"""
    fd = os.open(native.owned(LOCK), os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        native.check(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and
                     stat.S_IMODE(info.st_mode) == 0o600, 'unsafe_main_login_operation_lock')
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise native.OperationError('main_login_write_operation_running') from None
        yield
    finally:
        os.close(fd)


def main_login_status(runner):
    """报告配置/原生能力与健康，不把这些探针当作真实主站登录验收。"""
    native.verify_renewal_installation()
    result = native.health(runner)
    if not STATE.exists():
        return {**result, 'main_login_enabled': False, 'main_login_record_present': False,
                'authenticated_main_login_verified': False}
    value = load_record()
    verify_recovery(value)
    synapse_container(runner, value)
    assert_targets(value, side='after' if value['status'] == 'enabled' else
                   'before' if value['status'] == 'restored' else None,
                   allow_interrupted=value['status'] in ('pending', 'restoring'))
    if value['status'] == 'enabled':
        native.preparation_record()
        native.check(secret_identity() == value['secret_sha256'], 'main_login_secret_changed')
        verify_sso_flows()
    return {**result, 'main_login_enabled': value['status'] == 'enabled',
            'main_login_status': value['status'], 'recovery_program_private': True,
            'authenticated_main_login_verified': False, 'account_or_message_data_changed': False}


def enable_main_login(runner):
    """在已审核独立客户端秘密就绪后启用本次原生配置；不写身份桥或业务数据。"""
    native.verify_renewal_installation()
    native.preparation_record()
    synapse = synapse_container(runner)
    containers = native.containers(runner)
    verify_bridge_client(runner, containers)
    protected = native.protected_snapshot(containers)
    if STATE.exists():
        value = load_record()
        verify_recovery(value)
        if value['status'] == 'enabled':
            return {**main_login_status(runner), 'already_enabled': True}
        if value['status'] == 'pending':
            # 仅已完成三项原地写入的后像可续结；未完成或不明中间写仍按现有规则回退。
            native.check(value.get('stage') == 'synapse_configuration_written' and not value.get('write_intent'),
                         'main_login_pending_requires_restore')
            synapse_container(runner, value)
            assert_targets(value, side='after')
            verify_sso_flows()
            return finish_enable(runner, value, protected, resumed=True)
        native.check(value['status'] == 'restored', 'main_login_pending_requires_restore')
        assert_targets(value, side='before')
        native.check(secret_identity() == value['secret_sha256'], 'main_login_secret_changed')
        native.health(runner)
        upgrade_recovery(value)
        value.update(status='pending', stage='backed_up')
        native.private_record(STATE, value)
    else:
        native.health(runner)
        value = prepare_snapshots(runner, synapse)
    # 先启用服务端能力，再开启前端自动跳转，避免把访客送入尚未就绪的登录链。
    write_target(value, 'synapse', 'after')
    value['stage'] = 'synapse_configuration_written'
    native.private_record(STATE, value)
    restart_synapse(runner, value)
    verify_sso_flows()
    write_target(value, 'element', 'after')
    write_target(value, 'prepared', 'after')
    return finish_enable(runner, value, protected)


def finish_enable(runner, value, protected, *, resumed=False):
    """重核三项目标和网页实际配置后结案；续跑不再次重启 Synapse。"""
    assert_targets(value, side='after')
    native.check(secret_identity() == value['secret_sha256'], 'main_login_secret_changed')
    sync_element_config(runner, value, 'after')
    native.preparation_record()
    native.health(runner)
    native.assert_protected(runner, protected)
    upgrade_recovery(value)
    value.update(status='enabled', stage='configuration_and_native_flows_verified',
                 finished_at=int(time.time()))
    native.private_record(STATE, value)
    return {'complete': True, 'read_only': False, 'main_login_enabled': True,
            'authenticated_main_login_verified': False, 'only_synapse_restarted': not resumed,
            'resumed_pending': resumed, 'element_restarted': False,
            'other_services_changed': False, 'account_or_message_data_changed': False,
            'recovery_program': str(PROGRAM)}


def restore_main_login(runner):
    """仅恢复本次配置前像；不回灌数据库、不删除后续账号/消息、不改专用秘密。"""
    native.verify_renewal_installation()
    value = load_record()
    verify_recovery(value)
    synapse_container(runner, value)
    assert_targets(value, allow_interrupted=True)
    containers = native.containers(runner)
    protected = native.protected_snapshot(containers)
    if value['status'] == 'restored':
        return {**main_login_status(runner), 'already_restored': True}
    # 先撤公网再恢复旧密码能力；不要让应急回退重新公开第二套登录。
    published = native.read_record(native.STATE)
    gateway = native.select(containers, 'parallellines', 'nginx')
    public = native.public_record() if native.PUBLIC_STATE.exists() else None
    native.check(published.get('public_entry') is not True and
                 native.gateway_layer_digest(runner, gateway) is None and
                 (public is None or (public.get('status') == 'retracted' and
                  public.get('loaded_state_uncertain') is not True)),
                 'retract_tavern_public_entry_before_restore')
    upgrade_recovery(value)
    value.update(status='restoring', stage='restoring_configuration')
    native.private_record(STATE, value)
    # 必须先修复当前中断目标，避免下一次写意图覆盖仍需恢复的中间像证明。
    interrupted = value.get('write_intent', {}).get('target')
    order = ([interrupted] if interrupted in TARGETS else []) + [
        name for name in TARGETS if name != interrupted]
    for name in order:
        write_target(value, name, 'before')
    sync_element_config(runner, value, 'before')
    restart_synapse(runner, value)
    native.check(login_flows() == value['login_flows_before'], 'restored_native_login_flows_changed')
    native.preparation_record()
    native.health(runner)
    native.assert_protected(runner, protected)
    value.update(status='restored', stage='original_configuration_and_native_flows_verified',
                 finished_at=int(time.time()))
    native.private_record(STATE, value)
    return {'complete': True, 'read_only': False, 'main_login_enabled': False,
            'configuration_restored': True, 'only_synapse_restarted': True,
            'account_or_message_data_changed': False, 'other_services_changed': False}


def main(arguments):
    """只分发三个固定动作；失败保留回执和独立恢复入口，不伪装成功或展开错误正文。"""
    report = {'operation': arguments[0] if arguments else 'rejected', 'complete': False, 'errors': []}
    try:
        native.check(len(arguments) == 1 and arguments[0] in OPERATIONS, 'unsupported_main_login_operation')
        if Path(globals().get('__file__', '')).absolute() == PROGRAM:
            verify_recovery(load_record())
        runner = native.Runner(360 if arguments[0] != 'main-login-status' else 180)
        lock = write_operation_lock() if arguments[0] != 'main-login-status' else contextlib.nullcontext()
        edge = native.approved_reload_scope() if arguments[0] == 'restore-main-login' else contextlib.nullcontext()
        with lock, edge:
            report.update({'enable-main-login': enable_main_login, 'restore-main-login': restore_main_login,
                           'main-login-status': main_login_status}[arguments[0]](runner))
    except native.OperationError as error:
        report['errors'].append(str(error))
    except Exception as error:
        report['errors'].append('main_login_operation:' + type(error).__name__)
    if not report['complete']:
        report.update(recovery_operation='restore-main-login', recovery_program=str(PROGRAM),
                      configuration_may_be_pending=STATE.exists())
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    return 0 if report['complete'] else 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
