"""固定 Matrix 娱乐模块运维；无任意命令、域名、路径或版本输入。"""
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import secrets
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
OPERATIONS = ('inventory', 'prepare', 'deploy', 'bootstrap', 'health', 'stop')
SOURCE_REVISION = '5b96163a00f7c4877150cd5185fc510436ed6697'
SOURCE_BASE = 'https://raw.githubusercontent.com/ixiaoyy/parallellines-entertainment/' + SOURCE_REVISION + '/'
PREPARED = ROOT / 'prepared.json'
SOURCE_FILES = ('compose.yaml', 'upstream.lock.json', 'config/element.json', 'config/synapse-public.yaml')
IMAGES = {
    'element': 'ghcr.io/element-hq/element-web:v1.12.35@sha256:406b48b80153818284a235fa3600b2a5b5b6b0aa0e4ef4896b36d8d3461352f3',
    'synapse': 'ghcr.io/element-hq/synapse:v1.165.0@sha256:673b4223c81a7634fd07d832b939a58f97081cfdaae7cdd2d1664cdcf7611b62',
    'postgres': 'postgres:17@sha256:0d938e975177bef9f1f61f3f9dbcf2e0aa0a139568f66d3415ed8892eb97f6ac',
}

# 只在锁定的官方 Synapse 镜像内使用其 PyYAML，避免给共享宿主安装依赖。
MERGE_CONFIG_PROGRAM = r'''
import json,os
from pathlib import Path
import yaml
data=Path('/data')
target=data/'homeserver.yaml'
public=yaml.safe_load(Path('/release-config/synapse-public.yaml').read_text())
actual=yaml.safe_load(target.read_text())
assert actual['server_name']=='matrix.pingxingxian.space'
assert public['server_name']==actual['server_name']
assert public['enable_registration'] is True and public['registration_requires_token'] is True
assert 'password' not in public['database']['args']
assert public['database']['name']=='psycopg2'
secret=Path('/release-private/postgres-password').read_text().strip()
assert len(secret)>=32
for name,value in public.items(): actual[name]=value
actual['database']['args']['password']=secret
assert actual.get('registration_shared_secret') and actual.get('signing_key_path')
assert Path(actual['signing_key_path']).is_file()
target.write_text(yaml.safe_dump(actual,sort_keys=False))
os.chown(target,991,991)
os.chmod(target,0o600)
print(json.dumps({'complete':True,'native_configuration_merged':True}))
'''

# 凭据仅在本模块容器内生成并落私有文件；命令参数和共享报告不携带真实值。
BOOTSTRAP_PROGRAM = r'''
import hashlib,hmac,json,os,re,secrets,signal,time,urllib.error,urllib.request
from pathlib import Path
import yaml
ROOT=Path('/data')
RECORD=ROOT/'bootstrap-private.json'
SOURCE='5b96163a00f7c4877150cd5185fc510436ed6697'
SERVER='matrix.pingxingxian.space'
USER='pl_admin'
BASE='http://127.0.0.1:8008'
class BootstrapError(Exception): pass
def need(value,code):
 if not value: raise BootstrapError(code)
def save(value):
 need(not RECORD.is_symlink(),'bootstrap_record_symlink')
 temp=ROOT/('bootstrap-private.new-'+secrets.token_hex(8))
 fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'w') as stream:
  json.dump(value,stream,sort_keys=True,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
 os.replace(temp,RECORD)
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args): return None
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
def request(method,path,body=None,token=None):
 headers={'Content-Type':'application/json'}
 if token: headers['Authorization']='Bearer '+token
 value=json.dumps(body).encode() if body is not None else None
 req=urllib.request.Request(BASE+path,data=value,headers=headers,method=method)
 try:
  response=opener.open(req,timeout=6)
 except urllib.error.HTTPError as error:
  response=error
 except (OSError,urllib.error.URLError):
  return 0,{'errcode':'BOOTSTRAP_TRANSPORT'}
 with response:
  raw=response.read(65537)
  if len(raw)>65536: return 0,{'errcode':'BOOTSTRAP_RESPONSE_BOUND'}
  try: parsed=json.loads(raw)
  except (ValueError,UnicodeError): return 0,{'errcode':'BOOTSTRAP_RESPONSE_JSON'}
  if not isinstance(parsed,dict): return 0,{'errcode':'BOOTSTRAP_RESPONSE_TYPE'}
  return response.code,parsed
def available():
 status,value=request('GET','/_matrix/client/v3/register/available?username='+USER)
 if status==200 and value.get('available') is True: return True
 if value.get('errcode')=='M_USER_IN_USE': return False
 raise BootstrapError('native_username_availability_unconfirmed')
def login(password):
 return request('POST','/_matrix/client/v3/login',{
  'type':'m.login.password','identifier':{'type':'m.id.user','user':USER},
  'password':password,'device_id':'PL_BOOTSTRAP','initial_device_display_name':'Initial server bootstrap'})
def register(password,shared):
 status,nonce=request('GET','/_synapse/admin/v1/register')
 need(status==200 and isinstance(nonce.get('nonce'),str),'native_registration_nonce_failed')
 mac=hmac.new(shared.encode(),digestmod=hashlib.sha1)
 mac.update(('\0'.join((nonce['nonce'],USER,password,'admin'))).encode())
 status,value=request('POST','/_synapse/admin/v1/register',{
  'nonce':nonce['nonce'],'username':USER,'password':password,'admin':True,
  'mac':mac.hexdigest(),'inhibit_login':True})
 need(status==200 and value.get('user_id')=='@'+USER+':'+SERVER,
      'native_admin_registration_failed_or_existing_user')
def matching_invite(token,access):
 status,value=request('GET','/_synapse/admin/v1/registration_tokens',token=access)
 need(status==200 and isinstance(value.get('registration_tokens'),list),'native_invite_listing_failed')
 need(len(value['registration_tokens'])<=256,'native_invite_listing_bound')
 matches=[item for item in value['registration_tokens'] if item.get('token')==token]
 need(len(matches)<=1,'duplicate_native_invite')
 return matches[0] if matches else None
def deadline(*args): raise BootstrapError('bootstrap_deadline')
report={'complete':False,'errors':[]}
access=None
record=None
owned_record=False
signal.signal(signal.SIGALRM,deadline);signal.alarm(70)
try:
 cfg=yaml.safe_load((ROOT/'homeserver.yaml').read_text())
 need(cfg.get('server_name')==SERVER,'bootstrap_server_name_changed')
 need(cfg.get('enable_registration') is True and cfg.get('registration_requires_token') is True,
      'native_invitation_mode_required')
 shared=cfg.get('registration_shared_secret')
 need(isinstance(shared,str) and len(shared)>=16,'native_registration_secret_missing')
 if RECORD.exists():
  need(not RECORD.is_symlink() and RECORD.is_file() and RECORD.stat().st_size<=16384,
       'bootstrap_record_not_regular')
  need(RECORD.stat().st_uid==0 and RECORD.stat().st_mode&0o077==0,'bootstrap_record_not_private')
  record=json.loads(RECORD.read_text())
  need(record.get('schema')==1 and record.get('source_revision')==SOURCE and
       record.get('server_name')==SERVER and record.get('username')==USER,'bootstrap_record_identity_changed')
  need(isinstance(record.get('password'),str) and len(record['password'])>=48,'bootstrap_password_record_invalid')
  need(isinstance(record.get('invite_token'),str) and
       re.fullmatch('[A-Za-z0-9._~-]{32,64}',record['invite_token']),'bootstrap_invite_record_invalid')
  owned_record=True
 else:
  need(not RECORD.is_symlink(),'bootstrap_record_symlink')
  need(available(),'bootstrap_admin_already_exists_not_owned')
  record={'schema':1,'source_revision':SOURCE,'server_name':SERVER,'username':USER,
          'password':secrets.token_urlsafe(48),'invite_token':secrets.token_urlsafe(32),
          'uses_allowed':10,'expiry_time':int((time.time()+7*86400)*1000),
          'registration_attempted':False,'admin_created':False,'invite_attempted':False,
          'invite_created':False,'status':'pending'}
  owned_record=True
  save(record)
 if not record.get('admin_created'):
  if record.get('registration_attempted'):
   # 上次注册可能已提交而响应丢失；只用本次私有口令复核，不接管或重置未知用户。
   status,value=login(record['password'])
   if status==200:
    need(value.get('user_id')=='@'+USER+':'+SERVER,'bootstrap_login_identity_changed')
    access=value.get('access_token');record['admin_created']=True;save(record)
   else:
    need(available(),'pending_admin_registration_unresolved_no_reset')
  else:
   need(available(),'bootstrap_admin_became_existing_not_owned')
  if not record.get('admin_created'):
   record['registration_attempted']=True;save(record)
   register(record['password'],shared)
   record['admin_created']=True;save(record)
 if access is None:
  status,value=login(record['password'])
  need(status==200 and value.get('user_id')=='@'+USER+':'+SERVER,'native_admin_login_failed_no_reset')
  access=value.get('access_token')
 need(isinstance(access,str) and access,'native_admin_access_missing')
 record['admin_login_verified']=True;save(record)
 need(record.get('uses_allowed')==10 and isinstance(record.get('expiry_time'),int),
      'bootstrap_invite_policy_changed')
 need(record['expiry_time']>int(time.time()*1000),'bootstrap_invite_expired_no_automatic_replacement')
 invite=matching_invite(record['invite_token'],access)
 if invite is None:
  need(not record.get('invite_created'),'bootstrap_invite_missing_no_recreation')
  record['invite_attempted']=True;save(record)
  status,created=request('POST','/_synapse/admin/v1/registration_tokens/new',{
   'token':record['invite_token'],'uses_allowed':10,'expiry_time':record['expiry_time']},token=access)
  if status==200:
   invite=created
  else:
   # 原生 token 唯一约束处理响应丢失后的同码重试，不另发第二个邀请码。
   invite=matching_invite(record['invite_token'],access)
   need(invite is not None,'native_invite_creation_failed')
 else:
  need(record.get('invite_attempted') or record.get('invite_created'),'unexpected_existing_native_invite')
 need(invite.get('token')==record['invite_token'] and invite.get('uses_allowed')==10 and
      invite.get('expiry_time')==record['expiry_time'],'native_invite_policy_mismatch')
 record['invite_created']=True;record['status']='complete';record.pop('last_error_codes',None);save(record)
 report.update(complete=True,native_admin_login_verified=True,native_invite_created=True,
               invite_uses_allowed=10,invite_expiry_time_ms=record['expiry_time'],
               private_handoff_path='/data/services/parallellines-entertainment/data/synapse/bootstrap-private.json')
except BootstrapError as error:
 report['errors'].append(str(error));report['pending']=True
except Exception as error:
 report['errors'].append('native_bootstrap:'+type(error).__name__);report['pending']=True
finally:
 signal.alarm(0)
 if isinstance(access,str) and access:
  status,_=request('POST','/_matrix/client/v3/logout',{},token=access)
  report['bootstrap_session_logged_out']=status==200
  if status!=200:
   report['complete']=False;report['pending']=True;report['errors'].append('bootstrap_session_logout_unconfirmed')
if not report['complete'] and owned_record:
 record['status']='pending';record['last_error_codes']=report['errors']
 try: save(record)
 except Exception as error: report['errors'].append('private_pending_record:'+type(error).__name__)
print(json.dumps(report,sort_keys=True))
raise SystemExit(0 if report['complete'] else 2)
'''


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
        check(not item.is_symlink(), 'module_path_symlink')
    return path


def digest(value):
    """返回文件/元数据摘要，只用于本任务完整性和并发前像，不输出秘密值。"""
    if not isinstance(value, bytes):
        value = json.dumps(value, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(value).hexdigest()


def private_record(path, value):
    """原子保存固定新目录内的私有状态；不覆盖软链，不向日志展开记录。"""
    path = owned(path)
    check(path.parent.is_dir(), 'record_parent_missing')
    temporary = owned(path.with_name(path.name + '.new-' + secrets.token_hex(8)))
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write((json.dumps(value, sort_keys=True, indent=2) + '\n').encode())
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def read_record(path):
    """只读取本项目有限私有状态；不会读取其他系统密钥或数据库。"""
    path = owned(path)
    check(path.is_file() and path.stat().st_size <= 128 * 1024, 'module_record_required')
    return json.loads(path.read_text(encoding='utf-8'))


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


def protected_snapshot(values):
    """只记录其它服务的身份、运行状态、挂载和网络，供写前后比对，不读取环境。"""
    keys = ('id', 'name', 'image_id', 'running', 'health', 'mounts', 'networks', 'ports')
    return {item['id']: {key: item[key] for key in keys}
            for item in values if item['project'] != PROJECT}


def assert_protected(runner, expected):
    """其它容器自然变化也停止接管；本模块不重建、恢复或修复这些服务。"""
    check(protected_snapshot(containers(runner)) == expected, 'other_services_changed_outside_module')


def source_files():
    """仅下载固定公开提交的四个小文件；无任意 URL、重定向或外部脚本输入。"""
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, request, response, code, message, headers, new_url):
            return None
    opener = urllib.request.build_opener(NoRedirect())
    files = {}
    for name in SOURCE_FILES:
        try:
            request = urllib.request.Request(SOURCE_BASE + name,
                                            headers={'User-Agent': 'ParallelLines-Matrix-Deploy'})
            with opener.open(request, timeout=20) as response:
                check(response.status == 200, 'source_http_status')
                value = response.read(128 * 1024 + 1)
        except (OSError, urllib.error.URLError) as error:
            raise OperationError('fixed_source_download:' + type(error).__name__) from None
        check(0 < len(value) <= 128 * 1024, 'source_file_size_bound')
        files[name] = value
    lock = json.loads(files['upstream.lock.json'])
    check(lock.get('schema') == 2 and lock.get('stack') == 'matrix-element', 'matrix_source_lock_required')
    check(lock.get('deployment', {}).get('server_name') == DOMAINS[1], 'immutable_server_name_changed')
    check({name: item['image'] for name, item in lock['components'].items()} == IMAGES,
          'locked_images_changed')
    compose_images = re.findall(r'^\s+image:\s*(\S+)\s*$', files['compose.yaml'].decode(), re.M)
    check(sorted(compose_images) == sorted(IMAGES.values()), 'compose_images_not_locked')
    element = json.loads(files['config/element.json'])
    check(element == {'default_server_config': {'m.homeserver': {
        'base_url': 'https://' + DOMAINS[1], 'server_name': DOMAINS[1]}}},
        'element_non_native_override_rejected')
    return files


def compose(runner, label, arguments, *, timeout=60):
    """只使用固定本项目 Compose 来源；公开阶段的 edge overlay 亦须在同目录。"""
    paths = [owned(ROOT / 'compose.yaml')]
    edge = owned(ROOT / 'compose.edge.yaml')
    if edge.exists():
        paths.append(edge)
    args = ['docker', 'compose', '--project-name', PROJECT, '--project-directory', str(ROOT)]
    for path in paths:
        check(path.is_file(), 'module_compose_file_missing')
        args.extend(['--file', str(path)])
    return runner.run(label, args + arguments, timeout=timeout)


def native_private_integrity():
    """仅在服务器私有回执绑定配置、数据库口令和唯一原生签名文件，不输出内容或摘要。"""
    keys = list(owned(ROOT / 'data/synapse').glob('*.signing.key'))
    check(len(keys) == 1, 'unique_native_signing_key_required')
    paths = [ROOT / 'runtime/postgres-password', ROOT / 'data/synapse/homeserver.yaml', keys[0]]
    values = {}
    for item in paths:
        path = owned(item)
        check(path.is_file() and 0 < path.stat().st_size <= 128 * 1024,
              'native_private_file_missing_or_out_of_bound')
        values[str(path.relative_to(ROOT))] = digest(path.read_bytes())
    return values


def preparation_record():
    """读取固定来源的准备回执并确认公开材料未漂移，不向外暴露摘要或秘密。"""
    prepared = read_record(PREPARED)
    check(prepared.get('project') == PROJECT and prepared.get('stack') == 'matrix',
          'prepared_project_identity_changed')
    check(prepared.get('source_revision') == SOURCE_REVISION, 'prepared_source_changed')
    check(prepared.get('status') == 'prepared', 'module_not_prepared')
    for name in SOURCE_FILES:
        path = owned(ROOT / name)
        check(path.is_file() and digest(path.read_bytes()) == prepared['files'].get(name),
              'prepared_source_file_changed')
    for name in ('runtime/postgres-password', 'data/synapse/homeserver.yaml'):
        path = owned(ROOT / name)
        check(path.is_file() and path.stat().st_mode & 0o077 == 0, 'private_runtime_file_missing_or_public')
    check(prepared.get('private_files') == native_private_integrity(), 'native_private_configuration_changed')
    return prepared


def prepare(runner):
    """生产端拉取官方镜像并原生生成全新私有配置；重试不替换已生成密钥。"""
    if PREPARED.exists():
        preparation_record()
        return {'complete': True, 'prepared': True, 'already_prepared': True,
                'private_keys_preserved': True, 'source_revision': SOURCE_REVISION}
    values = containers(runner)
    check(not any(item['project'] == PROJECT for item in values), 'module_already_present_before_prepare')
    capacity = resources(runner)
    check(capacity['architecture'] in ('x86_64', 'amd64'), 'linux_amd64_host_required')
    # 三容器上限合计 2.125 GiB；此门槛为旧服务留余量，不代表用户容量保证。
    check(capacity['memory'].get('MemAvailable', 0) >= 3 * 1024 ** 3, 'insufficient_available_memory')
    check(all(not item['tcp_listening'] for item in capacity['ports'].values()), 'module_port_already_listening')
    disk = {item['path']: item['free'] for item in capacity['disks']}
    check(disk.get('/', 0) >= 4 * 1024 ** 3 and disk.get('/data', 0) >= 2 * 1024 ** 3,
          'insufficient_disk_space')
    before = protected_snapshot(values)
    files = source_files()
    owner = owned(ROOT / 'owner.json')
    if ROOT.exists():
        actual = read_record(owner)
        check(actual == {'project': PROJECT, 'stack': 'matrix', 'source_revision': SOURCE_REVISION},
              'existing_module_directory_not_owned')
    else:
        owned(ROOT).mkdir(parents=True, mode=0o700)
        private_record(owner, {'project': PROJECT, 'stack': 'matrix', 'source_revision': SOURCE_REVISION})
    for directory in ('config', 'runtime', 'data', 'data/synapse', 'data/postgres'):
        path = owned(ROOT / directory)
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        check(path.is_dir(), 'module_directory_not_regular')
    for name, content in files.items():
        path = owned(ROOT / name)
        if path.exists():
            check(path.is_file() and path.read_bytes() == content, 'partial_source_changed')
        else:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(content)
    # Element 的公开配置由非 root 的原生 nginx 用户读取；host 父目录仍保持私有。
    os.chmod(owned(ROOT / 'config/element.json'), 0o644)
    password = owned(ROOT / 'runtime/postgres-password')
    if password.exists():
        check(password.is_file() and password.stat().st_mode & 0o077 == 0, 'private_password_permissions_changed')
    else:
        fd = os.open(password, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as stream:
            stream.write(secrets.token_urlsafe(48) + '\n')
    for name in SERVICES:
        runner.run('pull_locked_' + name, ['docker', 'pull', '--platform', 'linux/amd64', IMAGES[name]], timeout=220)
    synapse_data = owned(ROOT / 'data/synapse')
    os.chown(synapse_data, 991, 991)
    os.chmod(synapse_data, 0o700)
    native_config = owned(synapse_data / 'homeserver.yaml')
    if not native_config.exists():
        check(not any(synapse_data.iterdir()), 'partial_native_generation_requires_review')
        runner.run('native_synapse_generate', [
            'docker', 'run', '--rm', '--network', 'none',
            '--mount', 'type=bind,src=' + str(synapse_data) + ',dst=/data',
            '--env', 'SYNAPSE_SERVER_NAME=' + DOMAINS[1], '--env', 'SYNAPSE_REPORT_STATS=no',
            IMAGES['synapse'], 'generate'], timeout=90)
    check(native_config.is_file(), 'native_config_generation_missing')
    # 使用官方镜像自带 YAML 解析器，只合并已审核的非秘密字段与本模块新密码。
    result = runner.run('merge_native_configuration', [
        'docker', 'run', '--rm', '--network', 'none', '--user', '0:0', '--entrypoint', 'python',
        '--mount', 'type=bind,src=' + str(synapse_data) + ',dst=/data',
        '--mount', 'type=bind,src=' + str(ROOT / 'config') + ',dst=/release-config,readonly',
        '--mount', 'type=bind,src=' + str(ROOT / 'runtime') + ',dst=/release-private,readonly',
        IMAGES['synapse'], '-c', MERGE_CONFIG_PROGRAM], timeout=45)
    check(json.loads(result.stdout).get('complete') is True, 'native_config_merge_incomplete')
    compose(runner, 'native_compose_configuration', ['config', '--quiet'])
    assert_protected(runner, before)
    private_record(PREPARED, {'schema': 1, 'project': PROJECT, 'stack': 'matrix',
                             'status': 'prepared', 'source_revision': SOURCE_REVISION,
                             'files': {name: digest(content) for name, content in files.items()},
                             'private_files': native_private_integrity()})
    return {'complete': True, 'prepared': True, 'source_revision': SOURCE_REVISION,
            'native_signing_keys_generated': True, 'private_database_password_generated': True,
            'other_services_changed': False, 'public_entry': False}


def deployment_state(runner, *, status):
    """保存本模块容器的不可变身份，供独立停止操作核验；不保存用户凭据。"""
    values = module_containers(runner)
    value = {'schema': 1, 'project': PROJECT, 'stack': 'matrix', 'source_revision': SOURCE_REVISION,
             'status': status, 'public_entry': False,
             'container_ids': {item['service']: item['id'] for item in values}}
    private_record(STATE, value)
    return value


def deploy(runner):
    """只启动三份官方新服务；失败仅停止本项目，保留数据库和原生稳定密钥。"""
    preparation_record()
    current = module_containers(runner)
    if current:
        saved = read_record(STATE)
        check(saved.get('source_revision') == SOURCE_REVISION and saved.get('stack') == 'matrix',
              'existing_module_release_changed')
        check(all(saved.get('container_ids', {}).get(item['service']) == item['id'] for item in current),
              'existing_module_container_changed')
        if len(current) == 3 and all(item['running'] for item in current):
            result = health(runner)
            return {**result, 'deployed': True, 'already_running': True, 'public_entry': False}
    if not any(item['running'] for item in current):
        # 拉取/生成与激活可能间隔较久；首次启动或全停后恢复都重新核资源和端口。
        capacity = resources(runner)
        check(capacity['memory'].get('MemAvailable', 0) >= 3 * 1024 ** 3,
              'insufficient_available_memory_before_start')
        check(all(not item['tcp_listening'] for item in capacity['ports'].values()),
              'module_port_listening_before_start')
    before = protected_snapshot(containers(runner))
    failure = None
    try:
        compose(runner, 'start_only_matrix_module', ['up', '-d', '--no-build', '--pull', 'never'], timeout=90)
        deployment_state(runner, status='starting')
        deadline = min(runner.end - 30, time.monotonic() + 220)
        result = None
        while time.monotonic() < deadline:
            try:
                result = health(runner)
                break
            except OperationError as error:
                # 仅等待原生启动中的连接/健康状态，身份或接线错误立即退出。
                transient = str(error) in ('module_not_fully_running', 'module_container_unhealthy')
                check(transient or str(error).startswith('health_transport:'), str(error))
                time.sleep(4)
        check(result is not None, 'native_startup_health_deadline')
        assert_protected(runner, before)
    except OperationError as error:
        failure = str(error)
    if failure:
        # 先登记此次实际容器，再按独立 stop 的身份守卫回收，绝不删数据。
        deployment_state(runner, status='startup_failed')
        recovery_error = None
        try:
            stop(runner)
        except OperationError as error:
            recovery_error = str(error)
        raise OperationError('matrix_deploy:' + failure +
                             (':stop_failed:' + recovery_error if recovery_error else ':owned_services_stopped'))
    deployment_state(runner, status='running')
    return {**result, 'read_only': False, 'deployed': True, 'source_revision': SOURCE_REVISION,
            'other_services_changed': False, 'public_entry': False,
            'native_admin_and_registration_invite_created': False}


def request_status(url, expected_json=False):
    """只读固定回环健康入口；不登录、不发送聊天或模型请求。"""
    request = urllib.request.Request(url, headers={'User-Agent': 'ParallelLines-Entertainment-Health'})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            body = response.read(65537)
            check(len(body) <= 65536, 'health_response_bound')
            check(response.status == 200, 'health_http_status')
            if expected_json:
                value = json.loads(body)
                check(isinstance(value, dict), 'health_json_object_required')
                return value
            return True
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


def bootstrap(runner):
    """以新实例原生 API 创建初始管理员和有限邀请码；值仅留私有文件，不返回凭据。"""
    preparation_record()
    health(runner)
    saved = read_record(STATE)
    check(saved.get('source_revision') == SOURCE_REVISION and saved.get('stack') == 'matrix',
          'bootstrap_deployment_identity_changed')
    values = module_containers(runner)
    check(all(saved.get('container_ids', {}).get(item['service']) == item['id'] for item in values),
          'bootstrap_container_identity_changed')
    synapse = select(values, PROJECT, 'synapse')
    before = protected_snapshot(containers(runner))
    result = runner.run('native_private_bootstrap', ['docker', 'exec', '--user', '0:0',
                        synapse['id'], 'python', '-c', BOOTSTRAP_PROGRAM], timeout=100, accepted=(0, 2))
    value = json.loads(result.stdout)
    check(isinstance(value, dict), 'native_bootstrap_report_invalid')
    if not value.get('complete'):
        errors = value.get('errors', [])
        safe = [error for error in errors if isinstance(error, str) and
                re.fullmatch('[A-Za-z0-9_:]{1,120}', error)]
        raise OperationError('native_bootstrap_pending:' + (':'.join(safe) if safe else 'report_error'))
    assert_protected(runner, before)
    return {'complete': True, 'read_only': False,
            'native_admin_login_verified': value.get('native_admin_login_verified') is True,
            'native_invite_created': value.get('native_invite_created') is True,
            'invite_uses_allowed': value.get('invite_uses_allowed'),
            'invite_expiry_time_ms': value.get('invite_expiry_time_ms'),
            'private_handoff_path': str(ROOT / 'data/synapse/bootstrap-private.json'),
            'bootstrap_session_logged_out': value.get('bootstrap_session_logged_out') is True,
            'other_services_changed': False}


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
        runner = Runner(850 if arguments[0] == 'prepare' else 420 if arguments[0] == 'deploy' else 180)
        report.update({'inventory': inventory, 'prepare': prepare, 'deploy': deploy,
                       'bootstrap': bootstrap, 'health': health, 'stop': stop}[arguments[0]](runner))
    except OperationError as error:
        report['errors'].append(str(error))
    except Exception as error:
        report['errors'].append('entertainment_operation:' + type(error).__name__)
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    return 0 if report['complete'] else 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
