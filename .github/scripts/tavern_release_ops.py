"""固定交付 Tavern 的共享身份桥与 Chat 前端；不修改账号或业务数据。"""

import argparse
import contextlib
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import time


ROOT = Path('/data/deployment/parallellines-tavern-login')
MATRIX = Path('/data/services/parallellines-entertainment')
MATRIX_BASE = '5b96163a00f7c4877150cd5185fc510436ed6697'
MATRIX_SECRET = MATRIX / 'data/synapse/tavern-oidc-client-secret'
SOURCE_REPO = 'https://github.com/ixiaoyy/parallellines-chat.git'
OVERLAYS = ('frontend-performance', 'frontend-bootstrap', 'frontend-auth-recovery',
            'frontend-silent-recovery', 'unified-login', 'personal-connections',
            'frontend-i18n', 'frontend-chat-rooms')
TARGETS = {
    'bridge': ('parallellines-chat', 'chat-oidc', 'parallellines-identity',
               'Dockerfile', 'BRIDGE_BASE_IMAGE', 120),
    'frontend': ('pl-official-candidate-20261030', 'openwebui', 'parallellines-chat',
                 'Dockerfile.frontend-i18n', 'CHAT_BASE_IMAGE', 240),
}
ACTIONS = ('publish-tavern-bridge', 'rollback-tavern-bridge',
           'publish-tavern-frontend', 'rollback-tavern-frontend', 'tavern-release-status')
# 用户仅批准这份侧栏产物在人工验收未完成时发布；其他版本仍须人工验收。
FRONTEND_ACCEPTANCE_WAIVER = (
    '6578349bd3594245b06d3854896eef54bf4f7082',
    '4877a9e5c829dc0d1cd1fc835b104a412d779bbc972cfa90f366a89a82109fcc',
)
BRIDGE_BEFORE = {
    # i18n 已发布的三个被覆盖文件；其他桥代码全部继承运行镜像。
    'config.mjs': '760eb10c7c69ce68d6dbfff942ce3729ca6126f34038a0dc552590074c1afeda',
    'identity-provider.mjs': '7ff3d896a8d0de9276cf80cad240a39f1a000ddb832369fbc78e90391355aab0',
    'error-page.mjs': '69cd5c18c65fdb0430ac6288200a4e147036c05f2972d5359a2db935b3fd069e',
}
I18N_BEFORE = {
    'manifest_sha256': 'f9f8656c2ab85631b40cfe1628c1deec9f58b773aa777069735bfb54ed811d0f',
    'index_sha256': '3290e82e6595681ceb8f4971712723ca8feb911d14314d98037b8eecf3056a1e',
}
BRIDGE_CLIENT = ('import("./config.mjs").then(({loadConfiguration})=>{'
                 'const c=loadConfiguration().clients.find(x=>x.clientId==="parallellines-tavern");'
                 'process.exit(c&&c.callbackUri==="https://matrix.pingxingxian.space/'
                 '_synapse/client/oidc/callback"&&!c.refreshEnabled&&!c.profileSyncEnabled?0:1);})')


class OperationError(RuntimeError):
    pass


def require(value, code):
    if not value:
        raise OperationError(code)


def run(args, code, *, timeout=30, binary=False, cwd=None, stdin_data=None):
    """执行有界的固定命令；私有配置、容器环境和命令输出不进入 Actions 日志。"""
    result = subprocess.run([str(x) for x in args], capture_output=True, cwd=cwd,
                            timeout=timeout, input=stdin_data, env={**os.environ, 'GIT_TERMINAL_PROMPT': '0'})
    require(result.returncode == 0, code)
    return result.stdout if binary else result.stdout.decode().strip()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def valid_image(value):
    return re.fullmatch(r'sha256:[0-9a-f]{64}', value or '') is not None


def safe_path(value):
    """仅使用已登记服务器绝对路径，不跟随软链或接受路径逃逸。"""
    path = Path(value)
    require(path.is_absolute() and '..' not in path.parts and
            any(path.is_relative_to(root) for root in (Path('/data'), Path('/opt'))) and
            not any(p.is_symlink() for p in (path, *path.parents)), 'unsafe_release_path')
    return path


def private_dir(path, *, create=False):
    path = safe_path(path)
    if create:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
    meta = path.stat()
    require(stat.S_ISDIR(meta.st_mode) and meta.st_uid == 0 and not meta.st_mode & 0o077,
            'unsafe_release_directory')
    return path


def read_private(path, limit=2 * 1024 * 1024):
    path = safe_path(path)
    meta = path.stat()
    require(stat.S_ISREG(meta.st_mode) and meta.st_uid == 0 and not meta.st_mode & 0o077
            and meta.st_size <= limit, 'unsafe_release_record')
    return path.read_bytes()


def save(path, data):
    """持久化运行/写入意图；中断后的恢复以完整记录为准。"""
    safe_path(path)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    fd = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def save_record(path, value):
    save(path, json.dumps(value, sort_keys=True).encode())


@contextlib.contextmanager
def operation_lock(path):
    """复用 Tavern 配置操作的写锁，覆盖 Actions 及独立服务器恢复命令。"""
    fd = os.open(safe_path(path), os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        meta = os.fstat(fd)
        require(stat.S_ISREG(meta.st_mode) and meta.st_uid == 0 and
                stat.S_IMODE(meta.st_mode) == 0o600, 'unsafe_tavern_lock')
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise OperationError('tavern_write_operation_already_running') from None
        yield
    finally:
        os.close(fd)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, safe_path(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def checkout_inputs(role_dir, revision):
    """只从官方 Chat main 取审核提交中的固定公开输入，不执行 checkout hook。"""
    source = private_dir(role_dir / 'source', create=True)
    git_dir = private_dir(role_dir / 'git', create=True)
    git = ['git', '--git-dir=' + str(git_dir), '-c', 'credential.helper=']
    if not (git_dir / 'HEAD').exists():
        run([*git, 'init', '--bare', '--template='], 'chat_git_init_failed')
    run([*git, 'fetch', '--no-tags', SOURCE_REPO, '+refs/heads/main:refs/heads/main'],
        'chat_source_fetch_failed', timeout=180)
    run([*git, 'merge-base', '--is-ancestor', revision, 'refs/heads/main'],
        'chat_revision_not_on_main')
    names = ['deploy/profile-deploy-utils.py', 'deploy/tavern-release-inputs.py',
             'openwebui-profile-overlay/Dockerfile.frontend-i18n']
    names.extend('identity-bridge/' + name for name in (*BRIDGE_BEFORE, 'package.json', 'package-lock.json'))
    names.extend('openwebui-profile-overlay/' + name + '/manifest.json' for name in OVERLAYS)
    for name in names:
        path = safe_path(source / name)
        path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        data = run([*git, 'show', revision + ':' + name], 'chat_release_file_missing', binary=True)
        save(path, data)
    return source


def inspect(role):
    """只读定位当前固定服务；重建失败时允许调用方辨别无容器，不选其他实例。"""
    project, service, *_ = TARGETS[role]
    ids = run(['docker', 'ps', '-aq', '--filter', 'label=com.docker.compose.project=' + project,
               '--filter', 'label=com.docker.compose.service=' + service], 'docker_list_failed').split()
    if not ids:
        return None
    require(len(ids) == 1 and re.fullmatch(r'[a-f0-9]{12,64}', ids[0]), 'release_service_not_unique')
    fmt = ('{"name":{{json .Name}},"id":{{json .Id}},"image":{{json .Image}},'
           '"reference":{{json .Config.Image}},"running":{{json .State.Running}},'
           '"health":{{if .State.Health}}{{json .State.Health.Status}}{{else}}"none"{{end}},'
           '"working":{{json (index .Config.Labels "com.docker.compose.project.working_dir")}},'
           '"files":{{json (index .Config.Labels "com.docker.compose.project.config_files")}},'
           '"env":{{json (index .Config.Labels "com.docker.compose.project.environment_file")}}}')
    value = json.loads(run(['docker', 'inspect', '--format', fmt, ids[0]], 'docker_inspect_failed'))
    require(value['name'] == f'/{project}-{service}-1' and valid_image(value['image'])
            and re.fullmatch(r'[a-f0-9]{64}', value['id']), 'release_service_identity_changed')
    require(value['working'] and value['files'], 'release_compose_labels_missing')
    for key in ('files', 'env'):
        value[key] = [str(safe_path(p)) for p in (value[key] or '').split(',') if p]
    require(0 < len(value['files']) <= 8 and len(value['env']) <= 8, 'release_compose_labels_limit')
    safe_path(value['working'])
    return value


def compose(role, scope, *args, override=None, failure='target_compose_command_failed', stdin_data=None):
    project, service, *_ = TARGETS[role]
    command = ['docker', 'compose', '--project-name', project, '--project-directory', safe_path(scope['working'])]
    for key, flag in (('env', '--env-file'), ('files', '-f')):
        for name in scope[key]:
            command.extend((flag, safe_path(name)))
    if override is not None:
        command.extend(('-f', safe_path(override)))
    if args == ('replace',):
        args = ('up', '-d', '--no-deps', '--no-build', '--pull', 'never', service)
    return run([*command, *args], failure, timeout=180, cwd=scope['working'], stdin_data=stdin_data)


def image_id(reference):
    return run(['docker', 'image', 'inspect', '--format', '{{.Id}}', reference], 'release_image_missing')


def local_json(url):
    return json.loads(run(['curl', '--silent', '--show-error', '--fail', '--connect-timeout', '3',
                           '--max-time', '6', url], 'local_release_probe_failed', timeout=9))


def tavern_gate():
    """前端上线要求生效的单一入口；人工确认仍是独立前置。"""
    state = safe_path(MATRIX / 'main-login.json')
    status = json.loads(read_private(state))['status']
    flows = local_json('http://127.0.0.1:13102/_matrix/client/v3/login')['flows']
    options = local_json('http://127.0.0.1:13101/config.json')
    automatic = options.get('sso_redirect_options', {}).get('immediate') is True
    types = {flow['type'] for flow in flows}
    ids = [p['id'] for f in flows if f['type'] == 'm.login.sso' for p in f.get('identity_providers', [])]
    require(status == 'enabled' and automatic and ids == ['oidc-parallellines'] and
            types <= {'m.login.sso', 'm.login.token', 'm.login.application_service'},
            'tavern_main_login_not_active')


def tavern_detached():
    """证明 Tavern 从未切换或已精确恢复；认证故障时不依赖 Tavern HTTP 探针。"""
    state = safe_path(MATRIX / 'main-login.json')
    prepared = json.loads(read_private(MATRIX / 'prepared.json'))
    require(prepared.get('project') == MATRIX.name and prepared.get('source_revision') == MATRIX_BASE
            and 'main_login_overlay' not in prepared, 'tavern_still_depends_on_bridge_restore_first')
    if state.exists():
        value = json.loads(read_private(state))
        require(value.get('project') == MATRIX.name and value.get('baseline_source_revision') == MATRIX_BASE
                and value.get('status') == 'restored', 'tavern_still_depends_on_bridge_restore_first')
    for name, expected in (
        ('config/element.json', prepared['files']['config/element.json']),
        ('data/synapse/homeserver.yaml', prepared['private_files']['data/synapse/homeserver.yaml']),
    ):
        path = safe_path(MATRIX / name)
        require(path.is_file() and path.stat().st_size <= 128 * 1024
                and digest(path.read_bytes()) == expected, 'tavern_original_configuration_drift')


def bridge_registered(current):
    run(['docker', 'exec', '--workdir', '/app', current['id'], 'node', '-e', BRIDGE_CLIENT],
        'tavern_client_not_configured')


def preflight_bridge(scope, attempt, image):
    """以候选和原 Compose 环境比较私有客户端配置；仅运行校验，不启动第二个发行方。"""
    secret = safe_path(MATRIX_SECRET)
    require(secret.is_file(), 'private_tavern_client_secret_required')
    with os.fdopen(os.open(secret, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        meta = os.fstat(stream.fileno())
        require(stat.S_ISREG(meta.st_mode) and (meta.st_uid, meta.st_gid) == (991, 991)
                and stat.S_IMODE(meta.st_mode) == 0o600 and 32 <= meta.st_size <= 4096,
                'private_tavern_client_secret_required')
        credential = stream.read(4097)
        require(len(credential) == meta.st_size, 'private_tavern_client_secret_changed')
    override = attempt / 'bridge-preflight.json'
    save_record(override, {'services': {'chat-oidc': {'image': image}}})
    check = ('import("./config.mjs").then(async ({loadConfiguration})=>{'
             'const clients=loadConfiguration().clients;'
             'const c=clients.find(x=>x.clientId==="parallellines-tavern");'
             'const {readFileSync}=await import("node:fs");'
             'const match=c&&c.clientSecret===readFileSync(0,"utf8").trim();'
             'process.exit(match&&["parallellines-openwebui","parallellines-newapi"]'
             '.every(id=>clients.some(client=>client.clientId===id))?0:1);})')
    # 保留容器实际用户和权限；专用秘密只经主机本地标准输入比较，不挂载或放到参数里。
    compose('bridge', scope, 'run', '--rm', '--no-deps', '--pull', 'never', '-T',
            '--entrypoint', 'node', '--workdir', '/app', 'chat-oidc', '-e', check,
            override=override, failure='tavern_candidate_client_configuration_invalid', stdin_data=credential)


def wait_ready(role, expected):
    """检查目标镜像容器与实际服务入口；不用真实账号请求，也不调用模型。"""
    deadline = time.monotonic() + TARGETS[role][-1]
    while time.monotonic() < deadline:
        current = inspect(role)
        if current and current['image'] == expected and current['running'] and current['health'] == 'healthy':
            if role == 'bridge':
                issuer = 'https://pingxingxian.space/auth/oidc'
                try:
                    data = run(['curl', '--silent', '--show-error', '--fail', '--connect-timeout', '3',
                                '--max-time', '6', '--resolve', 'pingxingxian.space:443:127.0.0.1',
                                issuer + '/.well-known/openid-configuration'],
                               'issuer_origin_not_ready', timeout=9)
                except OperationError:
                    time.sleep(2)
                    continue
                require(json.loads(data).get('issuer') == issuer, 'issuer_identity_changed')
            else:
                try:
                    local_json('http://127.0.0.1:18080/health')
                except OperationError:
                    time.sleep(2)
                    continue
            return current
        time.sleep(2)
    raise OperationError('service_readiness_timeout')


def bridge_hashes(current, files):
    code = ('const fs=require("node:fs"),c=require("node:crypto"),n=' + json.dumps(sorted(files)) +
            ';console.log(JSON.stringify(Object.fromEntries(n.map(x=>[x,c.createHash("sha256")'
            '.update(fs.readFileSync("/app/"+x)).digest("hex")]))))')
    return json.loads(run(['docker', 'exec', current['id'], 'node', '-e', code], 'bridge_source_probe_failed'))


def frontend_matches(current, expected, *, full=False):
    """核实际中英发布清单及首页；激活后再从容器读回完整公开构建。"""
    code = ('import hashlib,json;from pathlib import Path\n'
            'raw=Path("/app/frontend-i18n-manifest.json").read_bytes()\n'
            'root=Path("/app/build"); digest=lambda path: hashlib.sha256(path.read_bytes()).hexdigest()\n'
            'if hashlib.sha256(raw).hexdigest()!=' + repr(expected['manifest_sha256']) + ': raise SystemExit(1)\n'
            'if digest(root/"index.html")!=' + repr(expected['index_sha256']) + ': raise SystemExit(1)\n')
    if full:
        code += ('for name,value in json.loads(raw)["files"].items():\n'
                 ' path=root/name\n'
                 ' if not path.resolve().is_relative_to(root) or digest(path)!=value: raise SystemExit(1)\n')
    run(['docker', 'exec', current['id'], 'python', '-B', '-c', code],
        'frontend_runtime_manifest_or_assets_changed', timeout=90)


def scope_for(role, current, utils):
    """选取唯一生效的目标服务定义；不推断其他 overlay 对 build 的用途。"""
    service = TARGETS[role][1]
    images, builds = [], []
    for path in current['files']:
        doc = utils.load_yaml(safe_path(path).read_text(encoding='utf-8'))
        item = doc.get('services', {}).get(service, {})
        if 'image' in item:
            images.append((path, item))
        if 'build' in item:
            builds.append(path)
    require(images and (not builds or builds == [images[-1][0]]), 'release_compose_definition_ambiguous')
    target, item = images[-1]
    require(item['image'] == current['reference'] and image_id(current['reference']) == current['image'],
            'release_baseline_reference_changed')
    return target


def compose_identity(path):
    meta = safe_path(path).stat()
    return [meta.st_dev, meta.st_ino]


def read_record(role_dir, role, revision):
    value = json.loads(read_private(role_dir / 'release.json'))
    require(value.get('role') == role and value.get('revision') == revision and value.get('schema') == 1,
            'release_record_identity_changed')
    return value


def guard(role, record, utils):
    """仅接受本次前像、后像和规范化恢复形态；其他服务的独立写入不阻断。"""
    target, scope = safe_path(record['target']), record['scope']
    service = TARGETS[role][1]
    require(compose_identity(target) == record['compose_identity'], 'release_compose_inode_changed')
    value = utils.service_hash(target.read_bytes().decode('utf-8'), service)
    require(value in (record['before_hash'], record['after_hash'], record['restored_hash']),
            'release_target_service_drift')
    current = inspect(role)
    if current:
        require(current['image'] in (record['before_image'], record['after_image']) and
                all(current[key] == scope[key] for key in ('working', 'files', 'env')),
                'release_runtime_drift')
    else:
        require(record['restart_intent'] and record['status'] in ('switching', 'restoring'),
                'release_service_missing_without_owned_restart')
    return value, current


def restoring_service(record, utils):
    before = utils.load_yaml(record['old_service'])['services'][TARGETS[record['role']][1]]

    def restore(service):
        service.clear()
        service.update(before)

    return restore


def publish(role, revision, directory, args):
    """从已审当前镜像做薄派生；先保存可离线恢复的 intent，再替换唯一服务。"""
    role_dir = private_dir(directory / role, create=True)
    receipt = role_dir / 'release.json'
    if safe_path(receipt).exists():
        previous = read_record(role_dir, role, revision)
        require(previous['status'] == 'rolled_back', 'active_or_pending_release_already_recorded')
    else:
        previous = None
    current = inspect(role)
    require(current and current['image'] == args.expected_image_id and current['running']
            and current['health'] == 'healthy', 'release_expected_healthy_baseline_changed')
    acceptance = {'manual_tavern_login_accepted': False}
    if role == 'frontend':
        acceptance = {'manual_tavern_login_accepted': args.login_verified,
                      'manual_tavern_login_waived': args.login_waived}
        # 豁免只影响人工登录项；上线前仍严格核对 Tavern、身份桥和候选产物。
        tavern_gate()
        bridge = inspect('bridge')
        require(bridge and bridge['running'] and bridge['health'] == 'healthy', 'tavern_bridge_not_healthy')
        bridge_registered(bridge)
    source = checkout_inputs(role_dir, revision)
    utility = role_dir / 'profile-deploy-utils.py'
    utility_bytes = (source / 'deploy/profile-deploy-utils.py').read_bytes()
    save(utility, utility_bytes)
    utils = load_module('tavern_compose_cas', utility)
    inputs = load_module('tavern_release_inputs', source / 'deploy/tavern-release-inputs.py')
    target = safe_path(scope_for(role, current, utils))
    _project, service, image_prefix, dockerfile, argument, _budget = TARGETS[role]
    scope = {key: current[key] for key in ('working', 'files', 'env')}
    compose(role, scope, 'config', '--quiet')
    raw = target.read_bytes().decode('utf-8')
    identity = compose_identity(target)
    old_service = utils.load_yaml(raw)['services'][service]
    old_yaml = utils.yaml.dump({'services': {service: old_service}}, Dumper=utils.ComposeDumper,
                               sort_keys=False, allow_unicode=True)
    # 每次尝试保留独立镜像/上下文；中断准备或已回退后可重试而不覆盖旧产物。
    attempt = Path(tempfile.mkdtemp(prefix='attempt-', dir=role_dir))
    base = f'{image_prefix}:tavern-{revision}-{role}-{attempt.name.removeprefix("attempt-")}'
    base_alias = base + '-base'
    context = safe_path(attempt / 'build' if role == 'bridge' else directory / 'frontend-input')
    if role == 'bridge':
        prepared = inputs.prepare_bridge(source, context)
        require(bridge_hashes(current, BRIDGE_BEFORE) == BRIDGE_BEFORE and
                bridge_hashes(current, prepared['dependencies']) == prepared['dependencies'],
                'bridge_runtime_not_reviewed_i18n_baseline')
    else:
        prepared = inputs.verify_frontend(source, private_dir(context))
        require(prepared['manifest_sha256'] == args.frontend_manifest_sha256,
                'frontend_manifest_not_approved')
        frontend_matches(current, I18N_BEFORE)

    require(not any(run(['docker', 'image', 'ls', '-q', reference], 'release_tag_probe_failed')
                    for reference in (base, base_alias)), 'release_tag_exists')
    run(['docker', 'tag', current['image'], base_alias], 'retain_old_image_failed')
    run(['docker', 'build', '--pull=false', '--network=none', '--build-arg', f'{argument}={base_alias}',
         '--label', 'org.opencontainers.image.revision=' + revision,
         '-f', context / dockerfile, '-t', base, context], 'tavern_image_build_failed', timeout=300)
    after_image = image_id(base)
    require(valid_image(after_image) and image_id(base_alias) == current['image'] and inspect(role) == current,
            'release_baseline_changed_during_build')
    if role == 'bridge':
        preflight_bridge(scope, attempt, base)
        require(inspect(role) == current, 'release_baseline_changed_during_client_check')

    def change(item):
        item['image'] = base
        if 'build' in item:
            item['build'] = {'context': str(context), 'dockerfile': dockerfile, 'args': {argument: base_alias}}

    projected = utils.patch_service(raw, service, change)
    record = {'schema': 1, 'role': role, 'revision': revision, 'target': str(target), 'scope': scope,
              'before_hash': utils.service_hash(raw, service), 'after_hash': utils.service_hash(projected, service),
              'before_image': current['image'], 'before_reference': current['reference'], 'after_image': after_image,
              'after_reference': base, 'old_service': old_yaml, 'compose_identity': identity,
              'utility_sha256': digest(utility_bytes), 'status': 'switching', 'restart_intent': False,
              **acceptance}
    restored = utils.patch_service(projected, service, restoring_service(record, utils))
    record['restored_hash'] = utils.service_hash(restored, service)
    # 备妥当前操作器字节；回退不依赖 GitHub、候选上下文或登录。
    require(compose_identity(target) == identity, 'release_compose_inode_changed')
    if previous is not None:
        save_record(attempt / 'previous-release.json', previous)
    save(role_dir / 'operator.py', OPERATOR_SOURCE.encode())
    save_record(receipt, record)
    utils.cas_service_update(target, service, record['before_hash'], change, role_dir / 'backup')
    compose(role, scope, 'config', '--quiet')
    require(guard(role, record, utils)[0] == record['after_hash'] and image_id(base) == after_image,
            'release_candidate_configuration_changed')
    record['restart_intent'] = True
    save_record(receipt, record)
    compose(role, scope, 'replace')
    candidate = wait_ready(role, after_image)
    if role == 'bridge':
        require(bridge_hashes(candidate, prepared['files']) == prepared['files'], 'bridge_candidate_source_changed')
        bridge_registered(candidate)
    else:
        frontend_matches(candidate, prepared, full=True)
    require(guard(role, record, utils)[0] == record['after_hash'], 'release_candidate_drift')
    record['status'] = 'active'
    save_record(receipt, record)
    return {'status': 'active', 'role': role, 'image_id': after_image,
            'recovery_program': str(role_dir / 'operator.py'), **acceptance}


def rollback(role, revision, directory):
    """仅按私有前像恢复本次一个服务；不下载、不重构建、不回灌数据。"""
    role_dir = private_dir(directory / role)
    receipt = role_dir / 'release.json'
    record = read_record(role_dir, role, revision)
    if role == 'bridge':
        tavern_detached()
    utility = role_dir / 'profile-deploy-utils.py'
    require(digest(read_private(utility)) == record['utility_sha256'], 'release_recovery_helper_changed')
    utils = load_module('tavern_compose_cas', utility)
    target = safe_path(record['target'])
    value, current = guard(role, record, utils)
    report = {'status': 'rolled_back', 'role': role, 'image_id': record['before_image']}
    require(image_id(record['before_reference']) == record['before_image'], 'old_image_reference_changed')
    if record['status'] == 'rolled_back':
        require(value in (record['before_hash'], record['restored_hash']) and current and
                current['image'] == record['before_image'] and current['running'] and
                current['health'] == 'healthy', 'rolled_back_runtime_changed')
        return report
    record['status'] = 'restoring'
    save_record(receipt, record)
    if value == record['after_hash']:
        value = utils.cas_service_update(target, TARGETS[role][1], value, restoring_service(record, utils),
                                         role_dir / 'rollback-backup')['after_service_sha256']
    require(value in (record['before_hash'], record['restored_hash']), 'restored_compose_mismatch')
    compose(role, record['scope'], 'config', '--quiet')
    value, current = guard(role, record, utils)
    if not current or current['image'] != record['before_image'] or not current['running']:
        require(record['restart_intent'] and image_id(record['before_reference']) == record['before_image'],
                'release_original_runtime_or_restart_intent_changed')
        compose(role, record['scope'], 'replace')
    wait_ready(role, record['before_image'])
    require(guard(role, record, utils)[0] in (record['before_hash'], record['restored_hash']),
            'release_rollback_drift')
    record['status'] = 'rolled_back'
    save_record(receipt, record)
    return report


def status(revision, directory):
    """只读盘点运行容器和本次恢复入口；不把 HTTP 健康当成实际账号登录。"""
    result = {}
    for role in TARGETS:
        current = inspect(role)
        role_dir = directory / role
        exists = safe_path(role_dir / 'release.json').exists()
        record = read_record(role_dir, role, revision) if exists else {}
        result[role] = {'image_id': current['image'] if current else None,
                        'health': current['health'] if current else None, 'recorded_status': record.get('status'),
                        'image_matches_record': (
                            current['image'] == record['after_image' if record['status'] == 'active' else 'before_image']
                            if current and record.get('status') in ('active', 'rolled_back') else None),
                        'recovery_program': str(role_dir / 'operator.py') if exists else None}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=ACTIONS)
    parser.add_argument('revision')
    parser.add_argument('--expected-image-id')
    parser.add_argument('--frontend-manifest-sha256')
    acceptance = parser.add_mutually_exclusive_group()
    acceptance.add_argument('--login-verified', action='store_true')
    acceptance.add_argument('--login-waived', action='store_true')
    args = parser.parse_args()
    operation, revision = args.operation, args.revision
    require(re.fullmatch(r'[0-9a-f]{40}', revision), 'reviewed_chat_revision_required')
    require(not args.login_waived or operation == 'publish-tavern-frontend', 'frontend_acceptance_waiver_only')
    if operation == 'publish-tavern-frontend':
        require(args.login_verified or args.login_waived, 'manual_tavern_login_acceptance_required')
        if args.login_waived:
            require((revision, args.frontend_manifest_sha256) == FRONTEND_ACCEPTANCE_WAIVER,
                    'frontend_acceptance_waiver_not_approved_for_release')
    directory = safe_path(ROOT / revision)
    if operation == 'tavern-release-status':
        return status(revision, directory)
    require(os.geteuid() == 0 and run(['findmnt', '-n', '-o', 'TARGET', '/data'], 'no_data_mount') == '/data',
            'root_and_data_mount_required')
    role = operation.rsplit('-', 1)[1]
    with operation_lock(MATRIX / 'runtime/main-login.lock'):
        if operation.startswith('rollback-'):
            return rollback(role, revision, directory)
        require(OPERATOR_SOURCE and valid_image(args.expected_image_id), 'reviewed_expected_image_required')
        if role == 'frontend':
            require(re.fullmatch(r'[0-9a-f]{64}', args.frontend_manifest_sha256 or ''),
                    'reviewed_frontend_manifest_required')
        private_dir(ROOT, create=True)
        private_dir(directory, create=True)
        return publish(role, revision, directory, args)


if __name__ == '__main__':
    os.umask(0o077)
    # Workflow 注入已审源码；服务器副本只执行显式回退/状态，避免变成另一个发布入口。
    OPERATOR_SOURCE = globals().get('OPERATOR_SOURCE')
    try:
        result = main()
        print(json.dumps({'complete': True, 'result': result}, sort_keys=True))
    except Exception as error:
        reason = str(error) if isinstance(error, RuntimeError) and re.fullmatch(r'[a-z0-9_]{1,120}', str(error)) else type(error).__name__
        print(json.dumps({'complete': False, 'error': reason}, sort_keys=True))
        raise SystemExit(1) from None
