"""固定 Matrix 娱乐模块运维；无任意命令、域名、路径或版本输入。"""
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request


PROJECT = 'parallellines-entertainment'
ROOT = Path('/data/services/parallellines-entertainment')
STATE = ROOT / 'deployment.json'
MAIN_CONFIG = Path('/opt/parallellines/deploy/nginx/default.conf')
DOMAINS = ('tavern.pingxingxian.space', 'matrix.pingxingxian.space')
SERVICES = ('element', 'synapse', 'postgres')
PORTS = (13101, 13102)
MAX_OUTPUT = 4 * 1024 * 1024
OPERATIONS = ('inventory', 'health', 'stop')


class OperationError(RuntimeError):
    """只输出稳定错误码，不展开命令输出、运行环境或用户数据。"""


def check(value, code):
    if not value:
        raise OperationError(code)


class Runner:
    """固定 argv、单项超时和总时限；不调用 shell 或透传未知参数。"""

    def __init__(self, seconds=180):
        self.end = time.monotonic() + seconds

    def run(self, label, args, timeout=15, accepted=(0,)):
        remaining = self.end - time.monotonic()
        check(remaining > 0, 'operation_deadline_reached')
        try:
            result = subprocess.run(args, capture_output=True, text=True,
                                    timeout=min(timeout, remaining), check=False)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise OperationError(label + ':' + type(error).__name__) from None
        check(len(result.stdout) + len(result.stderr) <= MAX_OUTPUT, label + ':output_limit')
        check(result.returncode in accepted, label + ':exit_' + str(result.returncode))
        return result


def owned(path):
    """仅允许固定新模块目录，拒绝任一级软链；不会创建目录。"""
    path = Path(path)
    check(path == ROOT or ROOT in path.parents, 'path_outside_module')
    for item in (path, *path.parents):
        if item == ROOT or ROOT in item.parents:
            check(not item.is_symlink(), 'module_path_symlink')
    return path


def containers(runner):
    """仅读取白名单容器元数据，明确不读取 Config.Env、Cmd 或日志。"""
    ids = runner.run('container_ids', ['docker', 'ps', '-aq']).stdout.split()
    check(len(ids) <= 256 and all(re.fullmatch('[0-9a-f]{12,64}', x) for x in ids),
          'container_inventory_bound')
    if not ids:
        return []
    template = ('{"id":{{json .Id}},"name":{{json .Name}},"image":{{json .Config.Image}},'
                '"image_id":{{json .Image}},"running":{{json .State.Running}},'
                # 原生非健康检查/非 Compose 容器可缺少这些字段，不能令整机盘点失败。
                '"health":{{with (index .State "Health")}}{{json (index . "Status")}}{{else}}null{{end}},'
                '"project":{{with .Config.Labels}}{{json (index . "com.docker.compose.project")}}{{else}}null{{end}},'
                '"service":{{with .Config.Labels}}{{json (index . "com.docker.compose.service")}}{{else}}null{{end}},'
                '"working_dir":{{with .Config.Labels}}{{json (index . "com.docker.compose.project.working_dir")}}{{else}}null{{end}},'
                '"compose_files":{{with .Config.Labels}}{{json (index . "com.docker.compose.project.config_files")}}{{else}}null{{end}},'
                '"mounts":{{json .Mounts}},"networks":{{json .NetworkSettings.Networks}},'
                '"ports":{{json .HostConfig.PortBindings}}}')
    result = runner.run('container_metadata', ['docker', 'inspect', '--format', template, *ids],
                        accepted=(0, 1))
    if result.returncode:
        # 仅暴露固定模板缺失字段，不将未知 stderr 或 inspect 内容带进公共日志。
        match = re.search(r'map has no entry for key "([A-Za-z_]{1,32})"', result.stderr)
        suffix = ':missing_' + match.group(1) if match else ':template_or_inspect_failed'
        raise OperationError('container_metadata' + suffix)
    raw = result.stdout
    values = [json.loads(line) for line in raw.splitlines() if line.strip()]
    check(len(values) == len(ids), 'container_inventory_incomplete')
    return values


def select(values, project, service, optional=False):
    matches = [item for item in values if item['project'] == project and item['service'] == service]
    check(len(matches) <= 1 and (optional or len(matches) == 1), 'unique_' + service + '_required')
    return matches[0] if matches else None


def public_container(item):
    """对外只返回服务身份和状态，不返回完整 inspect 或挂载内容。"""
    return {key: item[key] for key in ('name', 'project', 'service', 'image', 'running', 'health')}


def consumer_metadata():
    """限定现有公开续期脚本，报告守卫证据；不打印 cron 或程序正文。"""
    entries = []
    paths = [Path('/opt/parallellines-tools/ops/renew-tools.py')]
    community = Path('/opt/parallellines/.deployment/community')
    if community.is_dir() and not community.is_symlink():
        children = list(community.iterdir())
        check(len(children) <= 128, 'renewal_directory_bound')
        paths.extend(child / 'renew-community.py' for child in children
                     if re.fullmatch('[0-9a-f]{40}', child.name) and not child.is_symlink())
    for path in paths:
        value = {'path': str(path), 'present': path.is_file(), 'symlink': path.is_symlink()}
        if path.is_file() and not path.is_symlink():
            check(path.stat().st_size <= 128 * 1024, 'renewal_source_bound')
            text = path.read_text(encoding='utf-8')
            # 仅识别已知整配置摘要比较语句；未识别不等于没有其他所有权检查。
            lines = text.splitlines()
            evidence = [number for number, line in enumerate(lines, 1)
                        if re.search(r'sha\(CONFIG\.read_bytes\(\)\)\s*!=\s*CONFIG_SHA', line)]
            value.update(full_default_conf_digest_guard=bool(evidence), evidence_lines=evidence,
                         conf_d_listing_guard_detected=bool(re.search(r'conf\.d.*(?:glob|listdir)|(?:glob|listdir).*conf\.d', text)))
        entries.append(value)
    for name in ('parallellines-community-renew', 'parallellines-tools-renew',
                 'parallellines-entertainment-renew'):
        path = Path('/etc/cron.d') / name
        entries.append({'path': str(path), 'present': path.is_file(), 'symlink': path.is_symlink()})
    return entries


def gateway_metadata(runner, values):
    """读取实际持久挂载和白名单 Nginx 指令，不读取私钥或真实环境。"""
    gateway = select(values, 'parallellines', 'nginx')
    check(gateway['running'], 'gateway_not_running')
    mounts = [{'type': m.get('Type'), 'source': m.get('Source'),
               'destination': m.get('Destination'), 'writable': m.get('RW')}
              for m in gateway['mounts']
              if m.get('Destination', '').startswith(('/etc/nginx', '/etc/letsencrypt', '/var/www/certbot'))]
    raw = runner.run('nginx_configuration_read', ['docker', 'exec', gateway['id'], 'nginx', '-T']).stdout
    directives = []
    for line in raw.splitlines():
        match = re.match(r'^\s*(server_name|listen|include|ssl_certificate)\s+([^;\r\n]+);', line)
        if match:
            directives.append({'directive': match.group(1), 'value': match.group(2)})
    check(len(directives) <= 512, 'nginx_directive_bound')
    directory_mounts = [m for m in mounts if m['destination'].rstrip('/') in ('/etc/nginx', '/etc/nginx/conf.d')]
    config = {'present': MAIN_CONFIG.is_file(), 'symlink': MAIN_CONFIG.is_symlink()}
    if MAIN_CONFIG.is_file() and not MAIN_CONFIG.is_symlink():
        st = MAIN_CONFIG.stat()
        observed = runner.run('gateway_bound_inode', ['docker', 'exec', gateway['id'], 'stat', '-c',
                              '%d:%i', '/etc/nginx/conf.d/default.conf']).stdout.strip()
        config['host_inode_matches_bound_file'] = observed == str(st.st_dev) + ':' + str(st.st_ino)
    chat = select(values, 'pl-official-candidate-20261030', 'openwebui', optional=True)
    shared = sorted(set(gateway['networks']) & set(chat['networks'])) if chat else []
    return {'service': public_container(gateway), 'mounts': mounts,
            'persistent_conf_d_directory_mounts': directory_mounts,
            'configuration': config, 'directives': directives,
            'gateway_networks': sorted(gateway['networks']),
            'chat_shared_networks': shared, 'renewal_consumers': consumer_metadata()}


def resources(runner):
    """读取本机容量和两个固定端口，不执行任何业务数据库命令。"""
    memory = {}
    for line in Path('/proc/meminfo').read_text(encoding='ascii').splitlines():
        key, _, value = line.partition(':')
        if key in ('MemTotal', 'MemAvailable', 'SwapTotal', 'SwapFree'):
            memory[key] = int(value.split()[0]) * 1024
    disks = []
    for path in (Path('/'), Path('/data')):
        if path.is_dir():
            usage = shutil.disk_usage(path)
            disks.append({'path': str(path), 'total': usage.total, 'free': usage.free})
    ports = {}
    for port in PORTS:
        with socket.socket() as connection:
            connection.settimeout(1)
            ports[str(port)] = {'tcp_listening': connection.connect_ex(('127.0.0.1', port)) == 0}
    return {'architecture': platform.machine(), 'cpu_count': os.cpu_count(),
            'load_average': os.getloadavg(), 'memory': memory, 'disks': disks, 'ports': ports,
            'docker_version': runner.run('docker_server_version', ['docker', 'version', '--format', '{{.Server.Version}}']).stdout.strip(),
            'compose_version': runner.run('compose_version', ['docker', 'compose', 'version', '--short']).stdout.strip()}


def inventory(runner):
    """首次部署前也可独立执行；只读结果不依赖源码下载或项目目录创建。"""
    values = containers(runner)
    own = [item for item in values if item['project'] == PROJECT]
    return {'complete': True, 'read_only': True, 'stack': 'Matrix + Element',
            'domains': list(DOMAINS), 'module_directory_present': ROOT.exists(),
            'module_containers': [public_container(item) for item in own],
            'resources': resources(runner), 'gateway': gateway_metadata(runner, values)}


def request_status(url, expected_json=False):
    """只读固定回环健康入口；不登录、不发送聊天或模型请求。"""
    request = urllib.request.Request(url, headers={'User-Agent': 'ParallelLines-Entertainment-Health'})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            body = response.read(65537)
            check(len(body) <= 65536, 'health_response_bound')
            check(response.status == 200, 'health_http_status')
            return json.loads(body) if expected_json else True
    except (OSError, ValueError, urllib.error.URLError) as error:
        raise OperationError('health_transport:' + type(error).__name__) from None


def module_containers(runner):
    """写操作只接受本项目的三个固定服务，不接管同标签的未知实例。"""
    values = [item for item in containers(runner) if item['project'] == PROJECT]
    check(len(values) <= 3 and all(item['service'] in SERVICES for item in values), 'unknown_module_service')
    check(len({item['service'] for item in values}) == len(values), 'duplicate_module_service')
    for item in values:
        check(item['working_dir'] == str(ROOT), 'module_working_directory_changed')
        sources = (item['compose_files'] or '').split(',')
        check(sources and all(path in (str(ROOT / 'compose.yaml'), str(ROOT / 'compose.edge.yaml'))
                              for path in sources), 'module_compose_origin_changed')
    return values


def health(runner):
    """同时检查原生服务连接和首页；不代表注册、同步、加密或会话验收。"""
    values = module_containers(runner)
    check(len(values) == 3 and all(item['running'] for item in values), 'module_not_fully_running')
    check(all(item['health'] in (None, 'healthy') for item in values), 'module_container_unhealthy')
    element = request_status('http://127.0.0.1:13101/')
    synapse = request_status('http://127.0.0.1:13102/health')
    versions = request_status('http://127.0.0.1:13102/_matrix/client/versions', expected_json=True)
    check(isinstance(versions.get('versions'), list) and versions['versions'], 'matrix_versions_missing')
    return {'complete': True, 'read_only': True, 'healthy': True,
            'element_homepage': element, 'synapse_health': synapse,
            'matrix_client_versions': True,
            'native_account_and_message_flow_verified': False}


def stop(runner):
    """只停止本项目已登记容器，保留卷与密钥；不修改网关或其他服务。"""
    values = module_containers(runner)
    if not values:
        return {'complete': True, 'stopped': True, 'already_absent': True, 'data_preserved': True}
    path = owned(STATE)
    check(path.is_file() and path.stat().st_size <= 128 * 1024, 'module_deployment_record_required')
    state = json.loads(path.read_text(encoding='utf-8'))
    check(state.get('project') == PROJECT and state.get('stack') == 'matrix', 'module_deployment_identity_changed')
    check(state.get('public_entry') is not True, 'owned_public_entry_retraction_required_before_stop')
    recorded = state.get('container_ids', {})
    check(all(recorded.get(item['service']) == item['id'] for item in values), 'module_container_identity_changed')
    running = [item['id'] for item in values if item['running']]
    if running:
        runner.run('stop_owned_module', ['docker', 'stop', '--time', '20', *running], timeout=80)
    check(not any(item['running'] for item in module_containers(runner)), 'module_stop_not_confirmed')
    return {'complete': True, 'stopped': True, 'data_preserved': True, 'other_services_changed': False}


def main(arguments):
    report = {'operation': arguments[0] if arguments else 'rejected', 'complete': False, 'errors': []}
    try:
        check(len(arguments) == 1 and arguments[0] in OPERATIONS, 'unsupported_fixed_operation')
        runner = Runner()
        report.update({'inventory': inventory, 'health': health, 'stop': stop}[arguments[0]](runner))
    except OperationError as error:
        report['errors'].append(str(error))
    except Exception as error:
        report['errors'].append('entertainment_operation:' + type(error).__name__)
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    return 0 if report['complete'] else 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
