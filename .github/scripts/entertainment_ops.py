"""固定 Matrix 娱乐模块运维；无任意命令、域名、路径或版本输入。"""
import contextlib
import hashlib
import http.client
import json
import os
from pathlib import Path
import platform
import re
import secrets
import shutil
import signal
import socket
import ssl
import subprocess
import sys
import time
import types
import urllib.error
import urllib.parse
import urllib.request


PROJECT = 'parallellines-entertainment'
ROOT = Path('/data/services/parallellines-entertainment')
STATE = ROOT / 'deployment.json'
MAIN_CONFIG = Path('/opt/parallellines/deploy/nginx/default.conf')
DOMAINS = ('tavern.pingxingxian.space', 'matrix.pingxingxian.space')
SERVICES = ('element', 'synapse', 'postgres')
PORTS = (13101, 13102)
MAX_OUTPUT = 4 * 1024 * 1024
OPERATIONS = ('inventory', 'prepare', 'deploy', 'bootstrap', 'prepare-tls', 'publish', 'retract',
              'install-renewal', 'renew', 'renewal-status', 'scheduled-renew', 'health', 'stop')
SOURCE_REVISION = '5b96163a00f7c4877150cd5185fc510436ed6697'
SOURCE_BASE = 'https://raw.githubusercontent.com/ixiaoyy/parallellines-entertainment/' + SOURCE_REVISION + '/'
PREPARED = ROOT / 'prepared.json'
SOURCE_FILES = ('compose.yaml', 'upstream.lock.json', 'config/element.json', 'config/synapse-public.yaml')
CERTIFICATE_ROOT = Path('/opt/parallellines/var/letsencrypt')
HTTP01_ROOT = Path('/opt/parallellines/var/certbot')
CERTIFICATE_NAME = 'parallellines-entertainment'
TLS_PREPARED = ROOT / 'tls-prepared.json'
PUBLIC_STATE = ROOT / 'public-entry.json'
RENEWAL_STATE = ROOT / 'renewal.json'
RENEWAL_LAST = ROOT / 'renewal-last.json'
RUNTIME_PROGRAM = ROOT / 'operations.py'
RENEWAL_CRON = Path('/etc/cron.d/parallellines-entertainment-renew')
EDGE_NETWORK = 'pl-official-candidate-20261030_default'
GATEWAY_CONF_NAME = 'parallellines-entertainment.conf'
GATEWAY_LAYER = '/etc/nginx/conf.d/' + GATEWAY_CONF_NAME
GATEWAY_SITES_DIR = Path('/opt/parallellines/nginx/sites.d')
GATEWAY_PERSISTENT_CONF = GATEWAY_SITES_DIR / GATEWAY_CONF_NAME
GATEWAY_CONTAINER_CONF = '/etc/nginx/sites.d/' + GATEWAY_CONF_NAME
GATEWAY_INCLUDE_SOURCE = Path('/opt/parallellines/deploy/nginx/sites.d/00-include-sites.conf')
GATEWAY_INCLUDE_CONTAINER = '/etc/nginx/conf.d/zz-gateway-sites.conf'
GATEWAY_SITES_VERIFY = Path('/opt/parallellines/deploy/nginx/sites.d/verify-gateway-sites.mjs')
GATEWAY_SITES_MARKER = Path('/opt/parallellines/.deployment/gateway-sites-enabled')
GATEWAY_REQUIRED_ROUTE = GATEWAY_CONF_NAME + '=' + ','.join(DOMAINS)
LEGACY_NATIVE_SOURCE_SHA = '005694547821f42e5778ab7819970e3f113599d3c57cd47e6bcb4732f8184335'
LEGACY_RUNTIME_BACKUP = ROOT / 'runtime/operations.before-persistent-sites-1abefac5.py'
TOOLS_DIRECTORY = Path('/opt/parallellines-tools/ops')
TOOLS_SOURCE_DIGESTS = {
    'tls.py': '844134baef2d45170db29dd1d9504b1e3e51c2a2545129d0ac3b13d58c019142',
    'managed_config.py': '7a4ed86ebb241261029c11becbd40cfad37ca0cdc9e3226fb352b80ebd4d1807',
}
_TOOLS_MODULE = None
CERTBOT_PROCESS_GUARD = ("import subprocess,sys;p=subprocess.Popen(sys.argv[1:]);\n"
                        "try: code=p.wait(timeout=240)\n"
                        "except subprocess.TimeoutExpired:\n"
                        " p.terminate()\n"
                        " try: p.wait(timeout=10)\n"
                        " except subprocess.TimeoutExpired: p.kill();p.wait(timeout=5)\n"
                        " code=124\n"
                        "sys.exit(code)")
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


class TLSPreparationError(OperationError):
    """携带非秘密 HTTP01 结果和是否已调用 Certbot，不包含验证值或原始日志。"""

    def __init__(self, code, checks, command_invoked=False):
        super().__init__(code)
        self.checks = checks
        self.command_invoked = command_invoked


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
        # 这是可执行 Compose 输入，存在不代表获准；每次使用都绑定固定本模块字节。
        check(edge.is_file() and edge.stat().st_size == len(EDGE_CONFIGURATION) and
              edge.read_bytes() == EDGE_CONFIGURATION, 'owned_edge_overlay_changed')
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
            return {**result, 'deployed': True, 'already_running': True,
                    'public_entry': saved.get('public_entry') is True}
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
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *arguments):
            return None
    request = urllib.request.Request(url, headers={'User-Agent': 'ParallelLines-Entertainment-Health'})
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=5) as response:
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


def native_health(runner):
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


def certificate_metadata(runner):
    """只读取本次固定证书的公开 SAN/期限；不读取或输出私钥。缺失返回 None。"""
    path = CERTIFICATE_ROOT / 'live' / CERTIFICATE_NAME / 'fullchain.pem'
    if not path.exists():
        check(not path.is_symlink(), 'new_certificate_dangling_link')
        return None
    check(path.is_file() and CERTIFICATE_ROOT.resolve() in path.resolve().parents,
          'new_certificate_outside_expected_storage')
    result = runner.run('new_certificate_public_metadata', [
        'openssl', 'x509', '-in', str(path), '-noout', '-enddate', '-ext', 'subjectAltName',
        '-checkend', '86400'], accepted=(0, 1))
    names = sorted(set(re.findall(r'DNS:([A-Za-z0-9*_.-]+)', result.stdout)))
    check(names == sorted(DOMAINS), 'new_certificate_san_not_exact_module_domains')
    match = re.search(r'^notAfter=(.+)$', result.stdout, re.M)
    check(match is not None, 'new_certificate_expiry_missing')
    try:
        expiry = int(ssl.cert_time_to_seconds(match.group(1).strip()))
    except ValueError:
        raise OperationError('new_certificate_expiry_invalid') from None
    return {'certificate_name': CERTIFICATE_NAME, 'domains': names,
            'not_after': match.group(1).strip(),
            'expiry_time': expiry,
            'valid_for_at_least_one_day': result.returncode == 0}


def http01_roundtrip(domain, filename, expected):
    """只请求固定域名/新验证路径；最多两次同域重定向，18 秒总时限，不返回正文。"""
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *arguments):
            return None
    def timeout(*arguments):
        raise OperationError('http01_total_timeout')
    previous = signal.signal(signal.SIGALRM, timeout)
    signal.alarm(18)
    trace = []
    target = 'http://' + domain + '/.well-known/acme-challenge/' + filename
    opener = urllib.request.build_opener(NoRedirect())
    try:
        for _ in range(3):
            request = urllib.request.Request(target, headers={
                'User-Agent': 'ParallelLines-Matrix-HTTP01', 'Cache-Control': 'no-cache'})
            try:
                response = opener.open(request, timeout=6)
            except urllib.error.HTTPError as error:
                response = error
            except (OSError, urllib.error.URLError) as error:
                return {'domain': domain, 'matched': False, 'statuses': trace,
                        'failure': 'http01_transport:' + type(error).__name__}
            with response:
                trace.append(response.code)
                if response.code in (301, 302, 303, 307, 308):
                    try:
                        next_url = urllib.parse.urljoin(target, response.headers.get('Location', ''))
                        parsed = urllib.parse.urlsplit(next_url)
                        port = parsed.port
                    except ValueError:
                        return {'domain': domain, 'matched': False, 'statuses': trace,
                                'failure': 'http01_invalid_redirect'}
                    safe = (parsed.scheme in ('http', 'https') and parsed.hostname == domain and
                            parsed.path == '/.well-known/acme-challenge/' + filename and
                            not parsed.query and not parsed.fragment and not parsed.username and
                            not parsed.password and port in (None, 80, 443))
                    if not safe:
                        return {'domain': domain, 'matched': False, 'statuses': trace,
                                'failure': 'http01_redirect_outside_contract'}
                    target = next_url
                    continue
                body = response.read(1025)
                matched = response.code == 200 and body == expected
                return {'domain': domain, 'matched': matched, 'statuses': trace,
                        'failure': None if matched else 'http01_status_or_body_mismatch'}
        return {'domain': domain, 'matched': False, 'statuses': trace,
                'failure': 'http01_redirect_limit'}
    except OperationError as error:
        return {'domain': domain, 'matched': False, 'statuses': trace, 'failure': str(error)}
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


def prepare_tls(runner):
    """先证明两域 HTTP01 到既有 webroot，再只申请本模块新证书；不改配置或 reload。"""
    preparation_record()
    health(runner)
    values = containers(runner)
    gateway = select(values, 'parallellines', 'nginx')
    certbot = select(values, 'parallellines', 'certbot')
    check(gateway['running'] and certbot['running'], 'existing_gateway_and_certbot_required')
    for item in (gateway, certbot):
        mounted = {(mount.get('Source'), mount.get('Destination')) for mount in item['mounts']}
        check((str(CERTIFICATE_ROOT), '/etc/letsencrypt') in mounted and
              (str(HTTP01_ROOT), '/var/www/certbot') in mounted,
              'existing_certbot_webroot_mounts_changed')
    check(MAIN_CONFIG.is_file() and not MAIN_CONFIG.is_symlink(), 'gateway_default_not_regular')
    default_identity = (MAIN_CONFIG.stat().st_dev, MAIN_CONFIG.stat().st_ino, digest(MAIN_CONFIG.read_bytes()))
    before = protected_snapshot(values)
    accounts = CERTIFICATE_ROOT / 'accounts/acme-v02.api.letsencrypt.org/directory'
    check(accounts.is_dir() and not accounts.is_symlink(), 'existing_production_acme_account_required')
    account_dirs = [path for path in accounts.iterdir() if path.is_dir() and not path.is_symlink()]
    check(len(account_dirs) == 1, 'single_existing_acme_account_required')
    previous = read_record(TLS_PREPARED) if TLS_PREPARED.exists() else None
    if previous is not None:
        check(previous.get('project') == PROJECT and previous.get('source_revision') == SOURCE_REVISION and
              previous.get('certificate_name') == CERTIFICATE_NAME and previous.get('domains') == list(DOMAINS),
              'tls_receipt_identity_changed')
    live = CERTIFICATE_ROOT / 'live' / CERTIFICATE_NAME
    renewal = CERTIFICATE_ROOT / 'renewal' / (CERTIFICATE_NAME + '.conf')
    if live.exists() or renewal.exists():
        check(previous is not None and previous.get('certificate_command_invoked') is True,
              'new_certificate_name_already_present_not_owned')
    check(HTTP01_ROOT.is_dir() and not HTTP01_ROOT.is_symlink(), 'existing_http01_webroot_required')
    directory = HTTP01_ROOT / '.well-known/acme-challenge'
    for path in (directory, *directory.parents):
        check(not path.is_symlink(), 'http01_path_symlink')
    directory.mkdir(mode=0o755, parents=True, exist_ok=True)
    check(directory.is_dir(), 'http01_directory_not_regular')
    filename = 'pl-entertainment-http01-' + secrets.token_hex(16)
    probe = directory / filename
    expected = secrets.token_urlsafe(32).encode()
    fd = os.open(probe, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(expected)
    os.chmod(probe, 0o644)
    identity = (probe.stat().st_dev, probe.stat().st_ino)
    checks = []
    prior_invocation = bool(previous and previous.get('certificate_command_invoked'))
    invoked = False
    receipt = {'schema': 1, 'project': PROJECT, 'source_revision': SOURCE_REVISION,
               'certificate_name': CERTIFICATE_NAME, 'domains': list(DOMAINS),
               'status': 'probing', 'certificate_command_invoked': prior_invocation,
               'last_attempt_certificate_command_invoked': False}
    failure = None
    try:
        private_record(TLS_PREPARED, receipt)
        checks = [http01_roundtrip(domain, filename, expected) for domain in DOMAINS]
        check(all(item['matched'] for item in checks), 'public_http01_roundtrip_failed')
        assert_protected(runner, before)
        meta = certificate_metadata(runner)
        if meta is None or not meta['valid_for_at_least_one_day']:
            # 进程终止在容器内完成，避免仅杀 Docker CLI 而遗留后台发证进程。
            invoked = True
            receipt.update(status='certificate_command_started', certificate_command_invoked=True,
                           last_attempt_certificate_command_invoked=True, http01_checks=checks)
            private_record(TLS_PREPARED, receipt)
            result = runner.run('new_module_certificate', [
                'docker', 'exec', certbot['id'], 'python3', '-c', CERTBOT_PROCESS_GUARD,
                'certbot', 'certonly', '--webroot', '-w', '/var/www/certbot',
                '--cert-name', CERTIFICATE_NAME, '--non-interactive', '--keep-until-expiring',
                '--no-directory-hooks', '--preferred-challenges', 'http',
                '--pre-hook', '', '--post-hook', '', '--deploy-hook', '',
                '--server', 'https://acme-v02.api.letsencrypt.org/directory',
                '-d', DOMAINS[0], '-d', DOMAINS[1]], timeout=275, accepted=(0, 1, 2, 124))
            if result.returncode:
                reason = 'native_certbot_exit_' + str(result.returncode)
                diagnostic = result.stderr.lower()
                if 'another instance of certbot is already running' in diagnostic:
                    reason = 'native_certbot_busy_no_automatic_retry'
                elif 'rate limit' in diagnostic or 'ratelimited' in diagnostic:
                    reason = 'native_acme_rate_limited_no_automatic_retry'
                raise OperationError(reason)
            meta = certificate_metadata(runner)
        check(meta is not None and meta['valid_for_at_least_one_day'], 'module_certificate_not_ready')
        assert_protected(runner, before)
        current_identity = (MAIN_CONFIG.stat().st_dev, MAIN_CONFIG.stat().st_ino,
                            digest(MAIN_CONFIG.read_bytes()))
        check(current_identity == default_identity, 'gateway_default_changed_during_tls')
        receipt.update(status='prepared', http01_checks=checks, certificate=meta,
                       certificate_command_invoked=prior_invocation or invoked,
                       last_attempt_certificate_command_invoked=invoked, gateway_unchanged=True)
        private_record(TLS_PREPARED, receipt)
    except OperationError as error:
        failure = str(error)
        receipt.update(status='pending', http01_checks=checks,
                       certificate_command_invoked=prior_invocation or invoked,
                       last_attempt_certificate_command_invoked=invoked, error=failure)
        private_record(TLS_PREPARED, receipt)
    finally:
        if probe.exists():
            check(not probe.is_symlink() and probe.is_file() and
                  (probe.stat().st_dev, probe.stat().st_ino) == identity and
                  probe.stat().st_size == len(expected) and probe.read_bytes() == expected,
                  'http01_owned_probe_changed_before_cleanup')
            probe.unlink()
    if failure:
        raise TLSPreparationError(failure, checks, invoked)
    return {'complete': True, 'read_only': False, 'tls_prepared': True, 'http01_checks': checks,
            'certificate': meta, 'certificate_command_invoked': invoked,
            'gateway_configuration_changed': False, 'gateway_reloaded': False,
            'other_services_changed': False, 'public_entry': False}


def approved_tools_module():
    """只加载逐字节匹配已审公开源码的两个现有模块，不执行未知 installed 代码。"""
    global _TOOLS_MODULE
    sources = {}
    for name, expected in TOOLS_SOURCE_DIGESTS.items():
        path = TOOLS_DIRECTORY / name
        check(path.is_file() and not path.is_symlink() and path.stat().st_size <= 128 * 1024,
              'approved_tools_reload_source_missing')
        source = path.read_bytes()
        check(digest(source) == expected, 'approved_tools_reload_source_identity_mismatch')
        sources[name] = source.decode('utf-8')
    if _TOOLS_MODULE is None:
        managed = types.ModuleType('managed_config')
        managed.__file__ = str(TOOLS_DIRECTORY / 'managed_config.py')
        exec(compile(sources['managed_config.py'], managed.__file__, 'exec'), managed.__dict__)
        previous = sys.modules.get('managed_config')
        sys.modules['managed_config'] = managed
        try:
            module = types.ModuleType('pl_entertainment_approved_tools_tls')
            module.__file__ = str(TOOLS_DIRECTORY / 'tls.py')
            exec(compile(sources['tls.py'], module.__file__, 'exec'), module.__dict__)
        finally:
            if previous is None:
                sys.modules.pop('managed_config', None)
            else:
                sys.modules['managed_config'] = previous
        _TOOLS_MODULE = module
    return _TOOLS_MODULE


def require_approved_reload():
    """复核既有 Main/Tools 认可的配置归属，不能用本次操作前像给未知改动背书。"""
    module = approved_tools_module()
    try:
        allowed = module.configuration_may_reload()
    except module.OperationError as error:
        code = str(error)
        check(False, 'existing_reload_guard:' +
              (code if re.fullmatch('[A-Za-z0-9_:]{1,160}', code) else type(error).__name__))
    check(allowed is True, 'gateway_configuration_not_owned_for_reload')
    return module


@contextlib.contextmanager
def approved_reload_scope():
    """复用既有非阻塞 TLS 锁，与旧 reload 消费者串行；不改它们的配置或状态。"""
    module = require_approved_reload()
    try:
        with module.tls_lock():
            require_approved_reload()
            yield
    except module.OperationError as error:
        code = str(error)
        raise OperationError('existing_tls_lock:' +
                             (code if re.fullmatch('[A-Za-z0-9_:]{1,160}', code) else type(error).__name__)) from None


def public_record():
    """读取本模块入口回执；没有回执不能覆盖同名网关文件。"""
    value = read_record(PUBLIC_STATE)
    check(value.get('project') == PROJECT and value.get('source_revision') == SOURCE_REVISION,
          'public_entry_receipt_identity_changed')
    return value


def default_identity(runner, gateway):
    """绑定 default.conf 原字节、inode 与原只读挂载，不更改任何旧配置。"""
    check(MAIN_CONFIG.is_file() and not MAIN_CONFIG.is_symlink(), 'gateway_default_not_regular')
    check(any(item.get('Source') == str(MAIN_CONFIG) and
              item.get('Destination') == '/etc/nginx/conf.d/default.conf' and item.get('RW') is False
              for item in gateway['mounts']), 'gateway_default_mount_changed')
    stat = MAIN_CONFIG.stat()
    observed = runner.run('gateway_default_bound_inode', [
        'docker', 'exec', gateway['id'], 'stat', '-c', '%d:%i', '/etc/nginx/conf.d/default.conf']).stdout.strip()
    check(observed == str(stat.st_dev) + ':' + str(stat.st_ino), 'gateway_default_inode_changed')
    return {'device': stat.st_dev, 'inode': stat.st_ino, 'sha256': digest(MAIN_CONFIG.read_bytes())}


def gateway_layer_digest(runner, gateway):
    """只对本模块固定文件取前像；拒绝软链、目录或未知文件覆盖。"""
    check(runner.run('owned_gateway_layer_symlink', ['docker', 'exec', gateway['id'], 'test', '-L', GATEWAY_LAYER],
                     accepted=(0, 1)).returncode != 0, 'owned_gateway_layer_symlink')
    exists = runner.run('owned_gateway_layer_present', ['docker', 'exec', gateway['id'], 'test', '-e', GATEWAY_LAYER],
                        accepted=(0, 1)).returncode == 0
    if not exists:
        return None
    check(runner.run('owned_gateway_layer_regular', ['docker', 'exec', gateway['id'], 'test', '-f', GATEWAY_LAYER],
                     accepted=(0, 1)).returncode == 0, 'owned_gateway_layer_not_regular')
    value = runner.run('owned_gateway_layer_identity', ['docker', 'exec', gateway['id'], 'sha256sum', GATEWAY_LAYER]).stdout.split()[0]
    check(re.fullmatch('[0-9a-f]{64}', value), 'owned_gateway_layer_identity_invalid')
    return value


def ensure_gateway_sites_directory():
    """验证或初始化共享网关宿主机持久站点目录，拒绝任一级软链。"""
    for item in (GATEWAY_SITES_DIR, *GATEWAY_SITES_DIR.parents):
        check(not item.is_symlink(), 'gateway_sites_path_symlink')
    if not GATEWAY_SITES_DIR.exists():
        GATEWAY_SITES_DIR.mkdir(parents=True, mode=0o755)
    check(GATEWAY_SITES_DIR.is_dir(), 'gateway_sites_dir_not_regular')
    return GATEWAY_SITES_DIR


def gateway_sites_mount_active(runner, gateway):
    """检查当前网关容器是否已只读挂载 sites.d 与引导 include 文件，并核对宿主机 inode。"""
    mounts = {(item.get('Source'), item.get('Destination'), item.get('RW')) for item in gateway['mounts']}
    has_dir = (str(GATEWAY_SITES_DIR), '/etc/nginx/sites.d', False) in mounts
    has_inc = (str(GATEWAY_INCLUDE_SOURCE), GATEWAY_INCLUDE_CONTAINER, False) in mounts
    check(has_dir == has_inc, 'gateway_sites_partial_mount_invalid')
    if not has_dir:
        return False
    check(GATEWAY_INCLUDE_SOURCE.is_file() and not GATEWAY_INCLUDE_SOURCE.is_symlink(),
          'gateway_sites_include_source_not_regular')
    inc_stat = GATEWAY_INCLUDE_SOURCE.stat()
    observed_inc = runner.run('gateway_sites_include_bound_inode', [
        'docker', 'exec', gateway['id'], 'stat', '-c', '%d:%i', GATEWAY_INCLUDE_CONTAINER]).stdout.strip()
    check(observed_inc == f'{inc_stat.st_dev}:{inc_stat.st_ino}', 'gateway_sites_include_inode_changed')
    return True


def gateway_persistent_digest(runner, gateway=None):
    """只对宿主机持久 sites.d 内本模块文件取摘要；网关已挂载时同步核对容器只读绑定 inode。"""
    if not GATEWAY_SITES_DIR.exists():
        check(not GATEWAY_SITES_DIR.is_symlink(), 'gateway_sites_path_symlink')
        return None
    ensure_gateway_sites_directory()
    check(not GATEWAY_PERSISTENT_CONF.is_symlink(), 'owned_gateway_persistent_symlink')
    if not GATEWAY_PERSISTENT_CONF.exists():
        if gateway is not None and gateway_sites_mount_active(runner, gateway):
            absent = runner.run('owned_gateway_persistent_container_absent', [
                'docker', 'exec', gateway['id'], 'test', '!', '-e', GATEWAY_CONTAINER_CONF], accepted=(0, 1))
            check(absent.returncode == 0, 'owned_gateway_persistent_mount_desync')
        return None
    check(GATEWAY_PERSISTENT_CONF.is_file() and 0 < GATEWAY_PERSISTENT_CONF.stat().st_size <= 64 * 1024,
          'owned_gateway_persistent_not_regular')
    value = digest(GATEWAY_PERSISTENT_CONF.read_bytes())
    if gateway is not None and gateway_sites_mount_active(runner, gateway):
        st = GATEWAY_PERSISTENT_CONF.stat()
        observed = runner.run('owned_gateway_persistent_bound_inode', [
            'docker', 'exec', gateway['id'], 'stat', '-c', '%d:%i', GATEWAY_CONTAINER_CONF]).stdout.strip()
        check(observed == f'{st.st_dev}:{st.st_ino}', 'owned_gateway_persistent_inode_mismatch')
    return value


def verify_gateway_sites_host(runner, *, require_published=False):
    """纯 Python 3 静态校验宿主机 sites.d（不依赖宿主机安装 Node），发布态强制验证两域唯一归属。"""
    ensure_gateway_sites_directory()
    if GATEWAY_INCLUDE_SOURCE.exists() or GATEWAY_INCLUDE_SOURCE.is_symlink():
        check(GATEWAY_INCLUDE_SOURCE.is_file() and not GATEWAY_INCLUDE_SOURCE.is_symlink(),
              'gateway_sites_include_source_missing')
        non_comment = [line.strip() for line in GATEWAY_INCLUDE_SOURCE.read_text(encoding='utf-8').splitlines()
                       if line.strip() and not line.strip().startswith('#')]
        check(non_comment == ['include /etc/nginx/sites.d/*.conf;'],
              'gateway_include_file_unexpected_content')
    protected_domains = {'pingxingxian.space', 'www.pingxingxian.space', '_'}
    safe_name_re = re.compile(r'^[a-z0-9][a-z0-9._-]*\.conf$')
    server_name_re = re.compile(r'\bserver_name\s+([^;]+);')
    domain_owners = {}
    file_domain_sets = {}
    checked_files = []
    for entry in sorted(GATEWAY_SITES_DIR.iterdir(), key=lambda item: item.name):
        name = entry.name
        if not name.endswith('.conf') or name == '00-include-sites.conf':
            continue
        check(safe_name_re.fullmatch(name) is not None, 'unsafe_site_filename:' + name)
        check(not entry.is_symlink() and entry.is_file(), 'site_file_must_be_regular:' + name)
        cleaned = re.sub(r'#[^\n]*', '', entry.read_text(encoding='utf-8'))
        names = [token.lower() for match in server_name_re.finditer(cleaned)
                 for token in match.group(1).strip().split() if token]
        check(bool(names), 'site_file_missing_server_name:' + name)
        for domain in names:
            check(domain not in protected_domains, 'site_file_hijacks_core_domain:' + name)
            existing = domain_owners.get(domain)
            check(not existing or existing == name, 'duplicate_server_name:' + domain)
            domain_owners[domain] = name
        unique = list(dict.fromkeys(names))
        file_domain_sets[name] = set(unique)
        checked_files.append({'file': name, 'server_names': unique})
    if require_published:
        check(bool(domain_owners), 'gateway_sites_no_active_routes')
        actual_set = file_domain_sets.get(GATEWAY_CONF_NAME)
        check(actual_set is not None, 'required_route_file_missing:' + GATEWAY_CONF_NAME)
        expected_set = {d.lower() for d in DOMAINS}
        for domain in expected_set:
            check(domain_owners.get(domain) == GATEWAY_CONF_NAME,
                  'required_route_domain_not_owned:' + domain)
        check(actual_set == expected_set, 'required_route_unexpected_domain:' + GATEWAY_CONF_NAME)
    return {'ok': True, 'site_files': checked_files, 'domain_count': len(domain_owners)}


def snapshot_gateway_sites_marker():
    """读取启用标记前像，供写失败时精确回滚，不篡改其他站点契约。"""
    for item in (GATEWAY_SITES_MARKER, *GATEWAY_SITES_MARKER.parents):
        check(not item.is_symlink(), 'gateway_sites_marker_symlink')
    if not GATEWAY_SITES_MARKER.exists():
        return None
    check(GATEWAY_SITES_MARKER.is_file() and GATEWAY_SITES_MARKER.stat().st_size <= 16 * 1024,
          'gateway_sites_marker_invalid')
    return GATEWAY_SITES_MARKER.read_bytes()


def restore_gateway_sites_marker(previous):
    """将 gateway-sites-enabled 精确恢复为操作前状态。"""
    for item in (GATEWAY_SITES_MARKER, *GATEWAY_SITES_MARKER.parents):
        check(not item.is_symlink(), 'gateway_sites_marker_symlink')
    if previous is None:
        if GATEWAY_SITES_MARKER.exists():
            GATEWAY_SITES_MARKER.unlink()
        return
    GATEWAY_SITES_MARKER.parent.mkdir(parents=True, exist_ok=True)
    temporary = GATEWAY_SITES_MARKER.with_name(GATEWAY_SITES_MARKER.name + '.restore-' + secrets.token_hex(8))
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(previous)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, GATEWAY_SITES_MARKER)


def sync_gateway_sites_marker(runner, *, published):
    """同步 .deployment/gateway-sites-enabled；撤回最后一个站点时移除标记，有其他站点时保留标记。"""
    previous = snapshot_gateway_sites_marker()
    lines = []
    if previous is not None:
        for raw in previous.decode('utf-8').splitlines():
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            if line.split('=', 1)[0].strip() == GATEWAY_CONF_NAME:
                continue
            lines.append(line)
    if published:
        lines.append(GATEWAY_REQUIRED_ROUTE)
    summary = verify_gateway_sites_host(runner, require_published=published)
    if not published and summary.get('domain_count', 0) == 0 and not lines:
        if GATEWAY_SITES_MARKER.exists():
            GATEWAY_SITES_MARKER.unlink()
        return
    GATEWAY_SITES_MARKER.parent.mkdir(parents=True, exist_ok=True)
    payload = ('\n'.join(lines) + ('\n' if lines else '')).encode('utf-8')
    temporary = GATEWAY_SITES_MARKER.with_name(GATEWAY_SITES_MARKER.name + '.new-' + secrets.token_hex(8))
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, GATEWAY_SITES_MARKER)


def gateway_effective_digest(runner, gateway):
    """返回当前网关实际生效的 Tavern/Matrix 配置摘要；禁止容器层与持久层同时存留两份配置。"""
    persistent_mounted = gateway_sites_mount_active(runner, gateway)
    persistent_hash = gateway_persistent_digest(runner, gateway)
    layer_hash = gateway_layer_digest(runner, gateway)
    if persistent_mounted:
        check(layer_hash is None, 'duplicate_gateway_container_and_persistent_layer')
        return persistent_hash
    if persistent_hash is not None and layer_hash is not None:
        check(persistent_hash == layer_hash, 'divergent_gateway_container_and_persistent_layer')
    return layer_hash


def gateway_public_context(runner, values):
    """核当前网关和已有 edge，不改变网关网络，拒绝其它配置已占用两个域名。"""
    gateway = select(values, 'parallellines', 'nginx')
    chat = select(values, 'pl-official-candidate-20261030', 'openwebui')
    check(gateway['running'] and EDGE_NETWORK in gateway['networks'] and EDGE_NETWORK in chat['networks'],
          'approved_shared_edge_changed')
    persistent_mounted = gateway_sites_mount_active(runner, gateway)
    allowed_files = {GATEWAY_CONTAINER_CONF} if persistent_mounted else {GATEWAY_LAYER}
    raw = runner.run('gateway_http_include_and_domain_ownership', ['docker', 'exec', gateway['id'], 'nginx', '-T']).stdout
    check(re.search(r'^\s*include\s+/etc/nginx/conf\.d/\*\.conf;', raw, re.M), 'gateway_conf_d_include_missing')
    if persistent_mounted:
        check(re.search(r'^\s*include\s+/etc/nginx/sites\.d/\*\.conf;', raw, re.M), 'gateway_sites_d_include_missing')
    current_file = ''
    for line in raw.splitlines():
        header = re.match(r'^# configuration file ([^:]+):$', line)
        if header:
            current_file = header.group(1)
        match = re.match(r'^\s*server_name\s+([^;]+);', line)
        if match and current_file not in allowed_files:
            names = {name.strip('"\'') for name in match.group(1).split()}
            check(not names.intersection(DOMAINS), 'module_domain_already_owned_by_other_configuration')
    return gateway


def gateway_fragment():
    """只生成两个域的原生代理；Matrix 原始 URI、查询串、认证与长轮询均透传。"""
    return ('''# parallellines-entertainment-owned matrix-element
map $http_upgrade $pl_entertainment_connection {
    default upgrade;
    '' close;
}
server {
    listen 80;
    server_name tavern.pingxingxian.space matrix.pingxingxian.space;
    location ^~ /.well-known/acme-challenge/ {
        root /var/www/certbot;
        default_type text/plain;
        try_files $uri =404;
    }
    location / { return 301 https://$host$request_uri; }
}
server {
    listen 443 ssl;
    http2 on;
    server_name tavern.pingxingxian.space;
    ssl_certificate /etc/letsencrypt/live/parallellines-entertainment/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/parallellines-entertainment/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    resolver 127.0.0.11 valid=10s ipv6=off;
    set $pl_entertainment_element pl-entertainment-element:80;
    access_log off;
    location / {
        proxy_pass http://$pl_entertainment_element$request_uri;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $pl_entertainment_connection;
    }
}
server {
    listen 443 ssl;
    http2 on;
    server_name matrix.pingxingxian.space;
    ssl_certificate /etc/letsencrypt/live/parallellines-entertainment/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/parallellines-entertainment/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    resolver 127.0.0.11 valid=10s ipv6=off;
    set $pl_entertainment_synapse pl-entertainment-synapse:8008;
    client_max_body_size 50M;
    access_log off;
    location = /.well-known/matrix/client {
        default_type application/json;
        add_header Access-Control-Allow-Origin "*" always;
        return 200 '{"m.homeserver":{"base_url":"https://matrix.pingxingxian.space"}}';
    }
    location = /.well-known/matrix/server {
        default_type application/json;
        return 200 '{"m.server":"matrix.pingxingxian.space:443"}';
    }
    location ~ ^/_synapse/admin(?:/|$) { return 404; }
    location ~ ^/(?:_matrix|_synapse/client)(?:/|$) {
        proxy_pass http://$pl_entertainment_synapse$request_uri;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $pl_entertainment_connection;
        proxy_buffering off;
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
    }
    location / { return 404; }
}
''').encode()


EDGE_CONFIGURATION = b'''services:
  element:
    networks:
      edge:
        aliases: [pl-entertainment-element]
  synapse:
    networks:
      edge:
        aliases: [pl-entertainment-synapse]
networks:
  edge:
    external: true
    name: pl-official-candidate-20261030_default
'''


def write_gateway_artifact(path, content):
    """将已审核的公开代理/edge 材料保留在本项目私有目录，不写旧配置。"""
    path = owned(path)
    temporary = owned(path.with_name(path.name + '.new-' + secrets.token_hex(8)))
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def gateway_source_for(expected):
    """只在已登记的 active/candidate/前像三类自有材料中寻找匹配源，支持中断后恢复。"""
    check(re.fullmatch('[0-9a-f]{64}', expected or ''), 'owned_gateway_source_identity_invalid')
    for name in ('active.conf', 'candidate.conf', 'before-' + expected + '.conf'):
        path = owned(ROOT / 'gateway' / name)
        if path.is_file() and path.stat().st_size <= 64 * 1024 and digest(path.read_bytes()) == expected:
            return path
    raise OperationError('owned_gateway_source_preimage_missing')


def certificate_leaf_identity(runner):
    """只取本模块公开叶证书身份，与实际源站 SNI 握手比较，不读取私钥。"""
    path = CERTIFICATE_ROOT / 'live' / CERTIFICATE_NAME / 'fullchain.pem'
    value = runner.run('module_public_leaf_identity', ['openssl', 'x509', '-in', str(path),
                       '-noout', '-fingerprint', '-sha256']).stdout.partition('=')[2].strip().replace(':', '').lower()
    check(re.fullmatch('[0-9a-f]{64}', value), 'module_public_leaf_identity_invalid')
    return value


class OriginHTTPS(http.client.HTTPSConnection):
    """对本机源站做真实 SNI/CA 验证，不把 Cloudflare 边缘证书误认为源站证书。"""

    def connect(self):
        with socket.create_connection(('127.0.0.1', 443), timeout=self.timeout) as raw:
            self.sock = ssl.create_default_context().wrap_socket(raw, server_hostname=self.host)


def origin_response(domain, path, expected_leaf):
    """只读两个固定域的有限源站响应；保留真实证书验证，不输出响应正文。"""
    check(domain in DOMAINS and path.startswith('/'), 'origin_probe_outside_scope')
    connection = OriginHTTPS(domain, timeout=6)
    try:
        connection.connect()
        check(digest(connection.sock.getpeercert(binary_form=True)) == expected_leaf, 'origin_certificate_not_loaded')
        connection.request('GET', path, headers={'Host': domain, 'User-Agent': 'ParallelLines-Matrix-Origin'})
        response = connection.getresponse()
        body = response.read(65537)
        check(len(body) <= 65536, 'origin_response_bound')
        return response.status, body, dict(response.getheaders())
    except (OSError, http.client.HTTPException) as error:
        raise OperationError('module_origin_probe:' + type(error).__name__) from None
    finally:
        connection.close()


def public_health(runner):
    """核源站已加载新证书/路由，再核两个公网 HTTPS 入口；不登录或发送聊天。"""
    meta = certificate_metadata(runner)
    check(meta is not None and meta['valid_for_at_least_one_day'], 'public_module_certificate_not_ready')
    leaf = certificate_leaf_identity(runner)
    expected = json.loads(owned(ROOT / 'config/element.json').read_text())
    status, body, _ = origin_response(DOMAINS[0], '/config.json', leaf)
    check(status == 200 and response_json(body) == expected, 'origin_element_homeserver_mismatch')
    status, body, headers = origin_response(DOMAINS[1], '/_matrix/client/versions', leaf)
    check(status == 200 and response_json(body).get('versions'), 'origin_matrix_client_versions_failed')
    check(any(key.lower() == 'access-control-allow-origin' and value == '*'
              for key, value in headers.items()), 'origin_native_matrix_cors_missing')
    status, _, _ = origin_response(DOMAINS[1], '/_synapse/admin/v1/server_version', leaf)
    check(status == 404, 'origin_admin_api_not_blocked')
    remote_element = request_status('https://' + DOMAINS[0] + '/config.json', expected_json=True)
    check(remote_element == expected, 'public_element_homeserver_mismatch')
    remote_matrix = request_status('https://' + DOMAINS[1] + '/_matrix/client/versions', expected_json=True)
    check(remote_matrix.get('versions'), 'public_matrix_client_versions_failed')
    check(certificate_leaf_identity(runner) == leaf, 'module_certificate_changed_during_public_probe')
    return {'origin_certificate_loaded': True, 'public_element_https': True,
            'public_matrix_https': True, 'native_matrix_cors': True, 'admin_api_blocked': True}


def response_json(body):
    """把固定原生探针的非 JSON/非对象响应转为明确失败，不把 HTML 回退当成功。"""
    try:
        value = json.loads(body)
    except (ValueError, UnicodeError):
        raise OperationError('public_native_response_not_json') from None
    check(isinstance(value, dict), 'public_native_response_not_object')
    return value


def health(runner):
    """原生健康与已登记公网入口一起核对；没有公网发布记录时只读内部服务。"""
    result = native_health(runner)
    if STATE.exists() and read_record(STATE).get('public_entry') is True:
        values = containers(runner)
        gateway = select(values, 'parallellines', 'nginx')
        persistent_mounted = gateway_sites_mount_active(runner, gateway)
        result.update(public_health(runner), public_entry=True,
                      temporary_conf_layer=not persistent_mounted,
                      persistent_gateway_sites_mounted=persistent_mounted)
    else:
        result['public_entry'] = False
    return result


def live_module_record(runner):
    """绑定原生部署记录与当前三个官方容器，不接管换镜像或换身份的新实例。"""
    saved = read_record(STATE)
    check(saved.get('project') == PROJECT and saved.get('stack') == 'matrix' and
          saved.get('source_revision') == SOURCE_REVISION, 'live_module_record_identity_changed')
    values = module_containers(runner)
    check(len(values) == 3, 'live_module_service_count_changed')
    check(all(saved.get('container_ids', {}).get(item['service']) == item['id'] and
              item['image'] == IMAGES[item['service']] for item in values),
          'live_module_container_or_image_changed')
    return saved, values


def assert_gateway_unchanged(runner, gateway, baseline, protected):
    """每次 reload 前后重核旧配置/容器身份；旧站的陌生变化不能由本任务接管。"""
    assert_protected(runner, protected)
    current = select(containers(runner), 'parallellines', 'nginx')
    check(current['id'] == gateway['id'] and default_identity(runner, current) == baseline,
          'gateway_identity_or_default_changed_outside_module')


def replace_gateway_persistent_conf(source, expected, replacement):
    """CAS 原子替换或撤回宿主机 sites.d 内本模块路由文件，严禁向只读挂载执行 docker cp。"""
    ensure_gateway_sites_directory()
    actual = gateway_persistent_digest(None)
    check(actual in (expected, None) if replacement is not None else actual == expected,
          'owned_gateway_persistent_preimage_changed')
    if replacement is None:
        if GATEWAY_PERSISTENT_CONF.exists():
            GATEWAY_PERSISTENT_CONF.unlink()
    else:
        check(source is not None and source.is_file() and digest(source.read_bytes()) == replacement,
              'owned_gateway_source_changed')
        temporary = GATEWAY_PERSISTENT_CONF.with_name(GATEWAY_CONF_NAME + '.new-' + secrets.token_hex(8))
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(source.read_bytes())
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, GATEWAY_PERSISTENT_CONF)
    check(gateway_persistent_digest(None) == replacement, 'owned_gateway_persistent_write_not_confirmed')


def replace_gateway_layer(runner, gateway, source, expected, replacement):
    """写宿主机持久 sites.d 并按当前网关挂载状态处理；已挂载 sites.d 时绝不写容器层。"""
    persistent_mounted = gateway_sites_mount_active(runner, gateway)
    layer_actual = gateway_layer_digest(runner, gateway)
    if persistent_mounted:
        check(layer_actual is None, 'duplicate_gateway_container_and_persistent_layer')
        replace_gateway_persistent_conf(source, expected, replacement)
        check(gateway_persistent_digest(runner, gateway) == replacement,
              'owned_gateway_persistent_mount_write_not_confirmed')
        return
    check(layer_actual == expected, 'owned_gateway_layer_preimage_changed')
    replace_gateway_persistent_conf(source, expected, replacement)
    if replacement is None:
        if expected is not None:
            runner.run('remove_only_owned_gateway_layer', ['docker', 'exec', gateway['id'], 'rm', '--', GATEWAY_LAYER])
    else:
        check(source.is_file() and digest(source.read_bytes()) == replacement, 'owned_gateway_source_changed')
        runner.run('copy_only_owned_gateway_layer', ['docker', 'cp', str(source), gateway['id'] + ':' + GATEWAY_LAYER])
    check(gateway_layer_digest(runner, gateway) == replacement, 'owned_gateway_layer_write_not_confirmed')


def approved_gateway_reload(runner, gateway, baseline, protected):
    """仅在旧配置仍获既有 owner 批准且全局 nginx-t 通过时，向同一网关发送 reload。"""
    assert_gateway_unchanged(runner, gateway, baseline, protected)
    require_approved_reload()
    runner.run('gateway_configuration_test', ['docker', 'exec', gateway['id'], 'nginx', '-t'])
    require_approved_reload()
    assert_gateway_unchanged(runner, gateway, baseline, protected)
    runner.run('reload_same_approved_gateway', ['docker', 'exec', gateway['id'], 'nginx', '-s', 'reload'])


def wait_native_health(runner, seconds=150):
    """只等待本次两个新服务接 edge 后恢复，不重启或轮询修复其它系统。"""
    deadline = min(runner.end - 30, time.monotonic() + seconds)
    while time.monotonic() < deadline:
        try:
            return native_health(runner)
        except OperationError as error:
            transient = str(error) in ('module_not_fully_running', 'module_container_unhealthy')
            check(transient or str(error).startswith('health_transport:'), str(error))
            time.sleep(3)
    raise OperationError('native_edge_startup_health_deadline')


def publish(runner):
    """发布两域独立配置；仅首次可组网，恢复已有入口不重建服务。"""
    preparation_record()
    native_health(runner)
    tls = read_record(TLS_PREPARED)
    check(tls.get('status') == 'prepared' and tls.get('source_revision') == SOURCE_REVISION and
          tls.get('certificate_name') == CERTIFICATE_NAME, 'module_tls_not_prepared')
    meta = certificate_metadata(runner)
    check(meta is not None and meta['valid_for_at_least_one_day'], 'module_certificate_not_ready')
    with approved_reload_scope():
        saved, own = live_module_record(runner)
        values = containers(runner)
        gateway = gateway_public_context(runner, values)
        persistent_mounted = gateway_sites_mount_active(runner, gateway)
        baseline = default_identity(runner, gateway)
        protected = protected_snapshot(values)
        previous = public_record() if owned(PUBLIC_STATE).exists() else None
        before_conf = gateway_effective_digest(runner, gateway)
        before_persistent = gateway_persistent_digest(runner, gateway)
        before_marker = snapshot_gateway_sites_marker()
        if before_conf is not None:
            check(previous is not None and before_conf in
                  (previous.get('conf_sha256'), previous.get('pending_conf_sha256')),
                  'unknown_existing_module_gateway_layer')
        if before_persistent is not None:
            check(previous is not None and before_persistent in
                  (previous.get('conf_sha256'), previous.get('pending_conf_sha256')),
                  'unknown_existing_module_persistent_gateway_conf')
        desired = {'element': 'pl-entertainment-element', 'synapse': 'pl-entertainment-synapse'}
        ready = all(EDGE_NETWORK in item['networks'] and desired[item['service']] in
                    (item['networks'][EDGE_NETWORK].get('Aliases') or [])
                    for item in own if item['service'] in desired)
        # 已撤回或失败的回执也属于恢复；缺别名时在写文件前停止，不重建容器。
        check(ready or (previous is None and saved.get('public_entry') is False),
              'module_edge_alias_missing_for_public_recovery')
        directory = owned(ROOT / 'gateway')
        directory.mkdir(mode=0o700, exist_ok=True)
        active = owned(directory / 'active.conf')
        before_source = None
        if before_conf is not None:
            previous_source = gateway_source_for(before_conf)
            before_source = owned(directory / ('before-' + before_conf + '.conf'))
            if before_source.exists():
                check(digest(before_source.read_bytes()) == before_conf, 'owned_gateway_backup_changed')
            else:
                write_gateway_artifact(before_source, previous_source.read_bytes())
        content = gateway_fragment()
        next_conf = digest(content)
        next_source = owned(directory / 'candidate.conf')
        write_gateway_artifact(next_source, content)
        edge = owned(ROOT / 'compose.edge.yaml')
        if edge.exists():
            check(edge.is_file() and edge.read_bytes() == EDGE_CONFIGURATION, 'owned_edge_overlay_changed')
        else:
            write_gateway_artifact(edge, EDGE_CONFIGURATION)
        # STATE 可能尚未跟上已经 HUP 的 publishing 回执，不能把旧入口误判为未激活。
        prior_uncertain = bool(previous and (previous.get('status') == 'publishing' or
                                            previous.get('loaded_state_uncertain') is True))
        old_public = (saved.get('public_entry') is True or bool(previous and (
            previous.get('status') in ('publishing', 'published') or
            previous.get('public_entry') is True or previous.get('loaded_state_uncertain') is True)))
        receipt = {'schema': 1, 'project': PROJECT, 'source_revision': SOURCE_REVISION,
                   'status': 'publishing', 'gateway_id': gateway['id'],
                   'gateway_image_id': gateway['image_id'], 'default_identity': baseline,
                   'conf_sha256': before_conf, 'pending_conf_sha256': next_conf,
                   'edge_sha256': digest(EDGE_CONFIGURATION),
                   'temporary_conf_layer': not persistent_mounted,
                   'persistent_gateway_sites_mounted': persistent_mounted,
                   'persistent_conf_path': str(GATEWAY_PERSISTENT_CONF),
                   'public_entry': old_public, 'loaded_state_uncertain': prior_uncertain}
        private_record(PUBLIC_STATE, receipt)
        reload_attempted = False
        web_recreated = False
        failure = None
        result = None
        try:
            if not ready:
                compose(runner, 'native_edge_configuration', ['config', '--quiet'])
                # 只重建新项目的两个 Web 服务；PG、稳定密钥和所有旧站容器均保留。
                compose(runner, 'attach_only_new_web_services_to_edge', [
                    'up', '-d', '--no-deps', '--no-build', '--pull', 'never', '--force-recreate',
                    'element', 'synapse'], timeout=90)
                web_recreated = True
            current = module_containers(runner)
            saved['container_ids'] = {item['service']: item['id'] for item in current}
            private_record(STATE, saved)
            wait_native_health(runner)
            preparation_record()
            assert_gateway_unchanged(runner, gateway, baseline, protected)
            replace_gateway_layer(runner, gateway, next_source, before_conf, next_conf)
            sync_gateway_sites_marker(runner, published=True)
            approved_gateway_reload(runner, gateway, baseline, protected)
            reload_attempted = True
            # HUP 后新 worker 可稍后开始接受连接，只重试明确的旧证书/连接过渡。
            for attempt in range(5):
                try:
                    result = public_health(runner)
                    break
                except OperationError as error:
                    transition = str(error) == 'origin_certificate_not_loaded' or str(error).startswith('module_origin_probe:')
                    check(transition and attempt < 4, str(error))
                    time.sleep(0.4)
            check(result is not None, 'module_public_health_not_confirmed')
            assert_gateway_unchanged(runner, gateway, baseline, protected)
            write_gateway_artifact(active, content)
            receipt.update(status='published', conf_sha256=next_conf, public_entry=True,
                           loaded_certificate_identity=certificate_leaf_identity(runner),
                           gateway_recreate_requires_publish=not persistent_mounted,
                           temporary_conf_layer=not persistent_mounted,
                           persistent_gateway_sites_mounted=persistent_mounted,
                           renewal_ready=False, loaded_state_uncertain=False)
            receipt.pop('error', None)
            receipt.pop('recovery_error', None)
            private_record(PUBLIC_STATE, receipt)
            saved.update(public_entry=True, status='running')
            private_record(STATE, saved)
        except (OperationError, OSError) as error:
            failure = str(error) if isinstance(error, OperationError) else 'public_io:' + type(error).__name__
            reload_attempted = reload_attempted or failure.startswith('reload_same_approved_gateway:')
        if failure:
            recovery = None
            try:
                current = module_containers(runner)
                check(all(item['image'] == IMAGES[item['service']] for item in current),
                      'new_module_image_changed_during_public_recovery')
                saved['container_ids'] = {item['service']: item['id'] for item in current}
                private_record(STATE, saved)
                current_hash = gateway_effective_digest(runner, gateway)
                if current_hash == next_conf:
                    replace_gateway_layer(runner, gateway, before_source, next_conf, before_conf)
                else:
                    check(current_hash == before_conf, 'owned_gateway_layer_changed_during_recovery')
                if not persistent_mounted and gateway_persistent_digest(None) != before_persistent:
                    replace_gateway_persistent_conf(
                        gateway_source_for(before_persistent) if before_persistent is not None else None,
                        gateway_persistent_digest(None), before_persistent)
                restore_gateway_sites_marker(before_marker)
                if reload_attempted:
                    approved_gateway_reload(runner, gateway, baseline, protected)
                saved['public_entry'] = old_public
                private_record(STATE, saved)
            except (OperationError, OSError) as error:
                recovery = str(error) if isinstance(error, OperationError) else 'public_recovery_io:' + type(error).__name__
                saved['public_entry'] = old_public or reload_attempted
                private_record(STATE, saved)
            receipt.update(status='pending', public_entry=saved.get('public_entry') is True,
                           error=failure, recovery_error=recovery,
                           loaded_state_uncertain=prior_uncertain or recovery is not None)
            private_record(PUBLIC_STATE, receipt)
            raise OperationError('public_activation:' + failure +
                                 (':recovery:' + recovery if recovery else ':owned_layer_restored'))
    return {'complete': True, 'read_only': False, 'public_entry': True, **result,
            'temporary_conf_layer': not persistent_mounted,
            'persistent_gateway_sites_mounted': persistent_mounted,
            'gateway_recreated': False,
            'gateway_recreate_requires_publish': not persistent_mounted,
            'new_web_services_recreated': web_recreated,
            'default_configuration_changed': False, 'other_services_changed': False,
            'renewal_ready': False, 'native_account_and_message_flow_verified': False}


def retract(runner):
    """仅撤回本模块已登记独立 conf；重新加载仍须旧 owner 批准，不停止旧站。"""
    saved = read_record(STATE)
    check(saved.get('project') == PROJECT and saved.get('stack') == 'matrix' and
          saved.get('source_revision') == SOURCE_REVISION, 'retract_module_record_identity_changed')
    own = module_containers(runner)
    check(all(saved.get('container_ids', {}).get(item['service']) == item['id'] and
              item['image'] == IMAGES[item['service']] for item in own),
          'retract_module_container_or_image_changed')
    with approved_reload_scope():
        values = containers(runner)
        gateway = select(values, 'parallellines', 'nginx')
        persistent_mounted = gateway_sites_mount_active(runner, gateway)
        baseline = default_identity(runner, gateway)
        protected = protected_snapshot(values)
        actual = gateway_effective_digest(runner, gateway)
        before_persistent = gateway_persistent_digest(runner, gateway)
        before_marker = snapshot_gateway_sites_marker()
        if not PUBLIC_STATE.exists():
            check(actual is None and before_persistent is None and saved.get('public_entry') is not True,
                  'unknown_module_public_entry_without_receipt')
            return {'complete': True, 'read_only': True, 'entry_retracted': True, 'already_absent': True}
        receipt = public_record()
        check(gateway['id'] == receipt.get('gateway_id') or persistent_mounted,
              'gateway_recreated_requires_publish_review')
        check(actual is None or actual in (receipt.get('conf_sha256'), receipt.get('pending_conf_sha256')),
              'owned_gateway_layer_changed_before_retract')
        check(before_persistent is None or before_persistent in (receipt.get('conf_sha256'), receipt.get('pending_conf_sha256')),
              'owned_gateway_persistent_changed_before_retract')
        if (actual is None and before_persistent is None and receipt.get('status') == 'retracted' and
                saved.get('public_entry') is not True and receipt.get('loaded_state_uncertain') is not True):
            return {'complete': True, 'read_only': True, 'entry_retracted': True, 'already_absent': True}
        active = None
        if actual is not None:
            active = gateway_source_for(actual)
        elif before_persistent is not None:
            active = gateway_source_for(before_persistent)
        prior_receipt = dict(receipt)
        prior_uncertain = receipt.get('status') == 'publishing' or receipt.get('loaded_state_uncertain') is True
        prior_public = (saved.get('public_entry') is True or actual is not None or
                        receipt.get('status') in ('publishing', 'published') or
                        receipt.get('public_entry') is True or receipt.get('loaded_state_uncertain') is True)
        failure = None
        reloaded = False
        try:
            if actual is not None:
                replace_gateway_layer(runner, gateway, None, actual, None)
            elif before_persistent is not None:
                replace_gateway_persistent_conf(None, before_persistent, None)
            sync_gateway_sites_marker(runner, published=False)
            approved_gateway_reload(runner, gateway, baseline, protected)
            reloaded = True
            assert_gateway_unchanged(runner, gateway, baseline, protected)
            check(gateway_effective_digest(runner, gateway) is None and
                  gateway_persistent_digest(runner, gateway) is None,
                  'owned_gateway_layer_not_retracted')
            receipt.update(status='retracted', public_entry=False, loaded_state_uncertain=False,
                           temporary_conf_layer=not persistent_mounted,
                           persistent_gateway_sites_mounted=persistent_mounted)
            receipt.pop('error', None)
            receipt.pop('recovery_error', None)
            private_record(PUBLIC_STATE, receipt)
            saved['public_entry'] = False
            private_record(STATE, saved)
        except (OperationError, OSError) as error:
            failure = str(error) if isinstance(error, OperationError) else 'retract_io:' + type(error).__name__
            reloaded = reloaded or failure.startswith('reload_same_approved_gateway:')
        if failure:
            recovery = None
            try:
                if actual is not None:
                    replace_gateway_layer(runner, gateway, active, None, actual)
                elif before_persistent is not None and gateway_persistent_digest(None) is None:
                    replace_gateway_persistent_conf(active, None, before_persistent)
                restore_gateway_sites_marker(before_marker)
                if reloaded:
                    approved_gateway_reload(runner, gateway, baseline, protected)
                saved['public_entry'] = prior_public
                private_record(STATE, saved)
            except (OperationError, OSError) as error:
                recovery = str(error) if isinstance(error, OperationError) else 'retract_recovery_io:' + type(error).__name__
            receipt = prior_receipt
            receipt.update(status='pending', public_entry=prior_public, error=failure, recovery_error=recovery,
                           loaded_state_uncertain=prior_uncertain or recovery is not None)
            private_record(PUBLIC_STATE, receipt)
            raise OperationError('public_retraction:' + failure +
                                 (':recovery:' + recovery if recovery else ':owned_layer_restored'))
    return {'complete': True, 'read_only': False, 'entry_retracted': True,
            'other_services_changed': False, 'data_preserved': True}


def renewal_record():
    """只读本证书消费者私有身份；不接管旧 cron、其它证书或未知脚本。"""
    value = read_record(RENEWAL_STATE)
    check(value.get('schema') == 1 and value.get('project') == PROJECT and
          value.get('source_revision') == SOURCE_REVISION and
          value.get('certificate_name') == CERTIFICATE_NAME and value.get('domains') == list(DOMAINS),
          'renewal_consumer_identity_changed')
    check(value.get('status') in ('installing', 'installed', 'ready'), 'renewal_consumer_status_invalid')
    return value


def renewal_artifact(path, expected, mode):
    """校验仅本项目程序/cron 的常规文件、root 所有权、精确权限和完整来源身份。"""
    check(path in (RUNTIME_PROGRAM, RENEWAL_CRON, LEGACY_RUNTIME_BACKUP), 'renewal_artifact_outside_scope')
    check(not path.is_symlink(), 'renewal_artifact_symlink')
    check(path.is_file(), 'renewal_artifact_missing')
    stat = path.stat()
    check(stat.st_uid == 0 and stat.st_mode & 0o777 == mode, 'renewal_artifact_permissions_changed')
    check(0 < stat.st_size <= 200 * 1024 and digest(path.read_bytes()) == expected,
          'renewal_artifact_source_changed')
    return True


def verify_runtime_program():
    """服务器本地直接运行恢复命令时，先核已审私有程序；不依赖 GitHub 或部署凭据。"""
    record = renewal_record()
    renewal_artifact(RUNTIME_PROGRAM, record.get('program_sha256'), 0o600)
    check(record.get('operation_revision') == globals().get('OPS_REVISION'),
          'runtime_operation_revision_changed')
    return record


def verify_renewal_installation(*, allow_legacy_upgrade=False):
    """核完整消费者与 cron 安装，Actions 调用还要求与当前已审 source 字节一致（或显式升级旧已核基线）。"""
    record = renewal_record()
    renewal_artifact(RUNTIME_PROGRAM, record.get('program_sha256'), 0o600)
    renewal_artifact(RENEWAL_CRON, record.get('cron_sha256'), 0o644)
    source = globals().get('OPS_SOURCE')
    if isinstance(source, str):
        current_sha = digest(source.encode('utf-8'))
        check(current_sha == record.get('source_sha256') or
              (allow_legacy_upgrade and record.get('source_sha256') == LEGACY_NATIVE_SOURCE_SHA),
              'installed_renewal_program_requires_reviewed_update')
    return record


def scheduler_active(runner):
    """只查现有 cron 调度进程是否活跃；不启动服务、不读取旧命令或环境。"""
    if shutil.which('systemctl'):
        for name in ('cron', 'crond'):
            result = runner.run('existing_cron_active', ['systemctl', 'is-active', name],
                                timeout=5, accepted=(0, 1, 3, 4))
            if result.stdout.strip() == 'active':
                return True
    if shutil.which('pgrep'):
        for name in ('cron', 'crond'):
            if runner.run('existing_cron_process', ['pgrep', '-x', name], timeout=5,
                          accepted=(0, 1)).returncode == 0:
                return True
    return False


def renewal_context(runner):
    """消费者识别同一网关，或已挂载持久 sites.d 且唯一归属与证书核验通过的新网关实例。"""
    preparation_record()
    saved, own = live_module_record(runner)
    receipt = public_record()
    check(saved.get('public_entry') is True and receipt.get('status') == 'published' and
          receipt.get('public_entry') is True and receipt.get('loaded_state_uncertain') is not True,
          'published_module_required_for_renewal')
    values = containers(runner)
    gateway = select(values, 'parallellines', 'nginx')
    persistent_mounted = gateway_sites_mount_active(runner, gateway)
    effective_hash = gateway_effective_digest(runner, gateway)
    check(effective_hash == receipt.get('conf_sha256'),
          'owned_gateway_layer_missing_or_changed_requires_publish')
    baseline = default_identity(runner, gateway)
    check(baseline == receipt.get('default_identity'), 'gateway_default_changed_requires_publish')
    if gateway['id'] != receipt.get('gateway_id') or gateway['image_id'] != receipt.get('gateway_image_id'):
        check(persistent_mounted, 'gateway_recreated_requires_publish')
        gateway_public_context(runner, values)
        verify_gateway_sites_host(runner, require_published=True)
    return gateway, baseline, protected_snapshot(values), receipt


def write_renewal_artifact(path, content, expected, mode, *, replace_existing=False):
    """安装或受控原子升级已登记的本项目程序或 cron，不会向定时任务暴露半写文件。"""
    check(path in (RUNTIME_PROGRAM, RENEWAL_CRON, LEGACY_RUNTIME_BACKUP), 'renewal_artifact_outside_scope')
    check(path.parent.is_dir() and not path.parent.is_symlink(), 'renewal_artifact_parent_invalid')
    if (path.exists() or path.is_symlink()) and not replace_existing:
        renewal_artifact(path, expected, mode)
        return
    check(not path.is_symlink(), 'renewal_artifact_symlink')
    temporary = path.with_name(path.name + '.new-' + secrets.token_hex(8))
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, 'wb') as stream:
        os.fchmod(stream.fileno(), mode)
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    if replace_existing:
        os.replace(temporary, path)
    else:
        # 链接排他发布，不覆盖两次检查之间出现的文件，也不会暴露半写 cron。
        try:
            os.link(temporary, path)
        finally:
            temporary.unlink()
    renewal_artifact(path, expected, mode)


def install_renewal(runner):
    """安装或受控升级私有恢复脚本和仅本项目 cron；升级前保存并验证可独立恢复的前像。"""
    source = globals().get('OPS_SOURCE')
    revision = globals().get('OPS_REVISION')
    check(isinstance(source, str) and isinstance(revision, str) and
          re.fullmatch('[0-9a-f]{40}', revision), 'reviewed_runtime_source_required')
    source_sha = digest(source.encode('utf-8'))
    program = ('OPS_REVISION=' + repr(revision) + '\n' + source).encode('utf-8')
    check(len(program) <= 200 * 1024, 'fixed_runtime_program_bound')
    cron = ('# parallellines-entertainment-owned ' + SOURCE_REVISION + '\n'
            '37 */6 * * * root /usr/bin/python3 -B ' + str(RUNTIME_PROGRAM) +
            ' scheduled-renew >/dev/null 2>&1\n').encode()
    with approved_reload_scope():
        gateway, baseline, protected, public = renewal_context(runner)
        check(scheduler_active(runner), 'existing_cron_scheduler_not_active')
        public_health(runner)
        runner.run('renewal_reload_path_configuration_test', ['docker', 'exec', gateway['id'], 'nginx', '-t'])
        require_approved_reload()
        assert_gateway_unchanged(runner, gateway, baseline, protected)
        upgrading_legacy = False
        prior_record = None
        prior_program_bytes = None
        if RENEWAL_STATE.exists():
            record = renewal_record()
            if record.get('source_sha256') == source_sha:
                # 相同 source 的重复调用保留已安装 producer 身份，不因其它 Main commit 漂移而重写。
                if record.get('status') != 'installing' and record.get('runtime_health_verified') is True:
                    verify_renewal_installation()
                    latest = read_record(RENEWAL_LAST) if RENEWAL_LAST.exists() else {}
                    ready = (record.get('status') == 'ready' and latest.get('complete') is True and
                             certificate_leaf_identity(runner) == public.get('loaded_certificate_identity'))
                    return {'complete': True, 'read_only': True, 'already_installed': True,
                            'renewal_ready': ready, 'native_renewal_verification_required': not ready}
                program = ('OPS_REVISION=' + repr(record['operation_revision']) + '\n' + source).encode('utf-8')
            else:
                check(record.get('source_sha256') == LEGACY_NATIVE_SOURCE_SHA,
                      'renewal_program_update_requires_explicit_review')
                verify_renewal_installation(allow_legacy_upgrade=True)
                prior_record = dict(record)
                prior_program_bytes = RUNTIME_PROGRAM.read_bytes()
                write_renewal_artifact(LEGACY_RUNTIME_BACKUP, prior_program_bytes,
                                       prior_record['program_sha256'], 0o600)
                private_record(ROOT / 'runtime/renewal.before-persistent-sites-1abefac5.json', prior_record)
                upgrading_legacy = True
                record = dict(record, operation_revision=revision, source_sha256=source_sha,
                              program_sha256=digest(program), cron_sha256=digest(cron),
                              previous_operation_revision=prior_record.get('operation_revision'),
                              previous_source_sha256=prior_record.get('source_sha256'),
                              previous_program_sha256=prior_record.get('program_sha256'),
                              legacy_backup_program=str(LEGACY_RUNTIME_BACKUP))
        else:
            check(not RUNTIME_PROGRAM.exists() and not RUNTIME_PROGRAM.is_symlink() and
                  not RENEWAL_CRON.exists() and not RENEWAL_CRON.is_symlink(),
                  'unknown_existing_renewal_program_or_cron')
            record = {'schema': 1, 'project': PROJECT, 'source_revision': SOURCE_REVISION,
                      'certificate_name': CERTIFICATE_NAME, 'domains': list(DOMAINS),
                      'operation_revision': revision, 'source_sha256': source_sha,
                      'program_sha256': digest(program), 'cron_sha256': digest(cron),
                      'status': 'installing', 'native_renewal_command_verified': False}
            private_record(RENEWAL_STATE, record)
        check(digest(program) == record.get('program_sha256') and digest(cron) == record.get('cron_sha256'),
              'renewal_install_intent_changed')
        try:
            write_renewal_artifact(RUNTIME_PROGRAM, program, record['program_sha256'], 0o600,
                                   replace_existing=upgrading_legacy)
            write_renewal_artifact(RENEWAL_CRON, cron, record['cron_sha256'], 0o644)
            if not upgrading_legacy:
                record['status'] = 'installed'
            private_record(RENEWAL_STATE, record)
            verify_renewal_installation()
            assert_gateway_unchanged(runner, gateway, baseline, protected)
            # 真正从私有文件走一次独立只读 health，证明恢复入口不依赖 Actions 注入或 Secrets。
            probe = runner.run('installed_manual_health_entrypoint', [
                '/usr/bin/python3', '-B', str(RUNTIME_PROGRAM), 'health'], timeout=80)
            observed = response_json(probe.stdout)
            check(observed.get('complete') is True and observed.get('public_entry') is True,
                  'installed_manual_health_not_verified')
            record['runtime_health_verified'] = True
            private_record(RENEWAL_STATE, record)
            assert_gateway_unchanged(runner, gateway, baseline, protected)
        except Exception:
            if upgrading_legacy and prior_record is not None and prior_program_bytes is not None:
                write_renewal_artifact(RUNTIME_PROGRAM, prior_program_bytes,
                                       prior_record['program_sha256'], 0o600, replace_existing=True)
                private_record(RENEWAL_STATE, prior_record)
            raise
    latest = read_record(RENEWAL_LAST) if RENEWAL_LAST.exists() else {}
    ready = (record.get('status') == 'ready' and latest.get('complete') is True and
             certificate_leaf_identity(runner) == public.get('loaded_certificate_identity'))
    return {'complete': True, 'read_only': False, 'installed': True,
            'upgraded_legacy_runtime': upgrading_legacy, 'renewal_ready': ready,
            'native_renewal_verification_required': not ready, 'scheduler_active': True,
            'manual_runtime_program': str(RUNTIME_PROGRAM), 'runtime_program_private': True,
            'manual_health_entrypoint_verified': True,
            'other_services_changed': False}


def renew(runner, *, scheduled=False):
    """仅 native renew 本证书；变化或旧 loaded 身份落后时才合法 reload，不强制轮换。"""
    record = verify_renewal_installation()
    check(record.get('status') != 'installing', 'renewal_installation_not_complete')
    check(record.get('runtime_health_verified') is True, 'manual_runtime_health_verification_required')
    if scheduled:
        check(record.get('native_renewal_command_verified') is True, 'initial_native_renewal_verification_required')
    with approved_reload_scope():
        gateway, baseline, protected, public = renewal_context(runner)
        check(scheduler_active(runner), 'existing_cron_scheduler_not_active')
        native_health(runner)
        meta = certificate_metadata(runner)
        check(meta is not None, 'owned_certificate_missing')
        before = certificate_leaf_identity(runner)
        values = containers(runner)
        certbot = select(values, 'parallellines', 'certbot')
        check(certbot['running'], 'existing_certbot_not_running')
        mounts = {(item.get('Source'), item.get('Destination')) for item in certbot['mounts']}
        check((str(CERTIFICATE_ROOT), '/etc/letsencrypt') in mounts and
              (str(HTTP01_ROOT), '/var/www/certbot') in mounts, 'existing_certbot_webroot_mounts_changed')
        result = runner.run('renew_only_module_certificate', [
            'docker', 'exec', certbot['id'], 'python3', '-c', CERTBOT_PROCESS_GUARD,
            'certbot', 'renew', '--cert-name', CERTIFICATE_NAME, '--non-interactive',
            '--no-directory-hooks', '--pre-hook', '', '--post-hook', '', '--deploy-hook', '',
            '--webroot', '-w', '/var/www/certbot', '--no-random-sleep-on-renew',
            '--server', 'https://acme-v02.api.letsencrypt.org/directory'],
            timeout=275, accepted=(0, 1, 2, 124))
        latest_meta = certificate_metadata(runner)
        latest = certificate_leaf_identity(runner)
        changed = latest != before
        pending = latest != public.get('loaded_certificate_identity')
        report = {'complete': False, 'read_only': False, 'certificate_changed': changed,
                  'certificate_reload_pending': pending, 'gateway_reloaded': False}
        private_record(RENEWAL_LAST, report)
        if result.returncode:
            reason = 'native_module_renew_exit_' + str(result.returncode)
            diagnostic = (result.stdout + result.stderr).lower()
            if 'another instance of certbot is already running' in diagnostic:
                reason = 'native_certbot_busy_no_automatic_retry'
            raise OperationError(reason)
        check(latest_meta is not None and latest_meta['valid_for_at_least_one_day'], 'renewed_module_certificate_not_ready')
        if pending:
            approved_gateway_reload(runner, gateway, baseline, protected)
        else:
            # 本轮未到期跳过时不无故 HUP，但仍实核未来 reload 的来源、权限与全局配置。
            runner.run('renewal_reload_path_configuration_test', ['docker', 'exec', gateway['id'], 'nginx', '-t'])
            require_approved_reload()
            assert_gateway_unchanged(runner, gateway, baseline, protected)
        effective = None
        for attempt in range(5 if pending else 1):
            try:
                effective = public_health(runner)
                break
            except OperationError as error:
                transition = str(error) == 'origin_certificate_not_loaded' or str(error).startswith('module_origin_probe:')
                check(pending and transition and attempt < 4, str(error))
                time.sleep(0.4)
        check(effective is not None, 'renewal_effective_route_unconfirmed')
        assert_gateway_unchanged(runner, gateway, baseline, protected)
        text = (result.stdout + result.stderr).lower()
        skipped = not changed and ('not due for renewal' in text or 'no renewals were attempted' in text)
        persistent_mounted = gateway_sites_mount_active(runner, gateway)
        public.update(gateway_id=gateway['id'], gateway_image_id=gateway['image_id'],
                      loaded_certificate_identity=latest, renewal_ready=True,
                      temporary_conf_layer=not persistent_mounted,
                      persistent_gateway_sites_mounted=persistent_mounted,
                      gateway_recreate_requires_publish=not persistent_mounted)
        private_record(PUBLIC_STATE, public)
        record.update(status='ready', native_renewal_command_verified=True,
                      last_verified_at=int(time.time()), last_native_result='not_due' if skipped else 'rotated' if changed else 'unchanged')
        private_record(RENEWAL_STATE, record)
        report.update(complete=True, renewal_ready=True, native_renewal_command_verified=True,
                      certificate_reload_pending=False, gateway_reloaded=pending,
                      renewal_not_due=skipped, actual_certificate_rotation_verified=changed,
                      reload_path_validated=True, current_public_route_verified=True,
                      other_services_changed=False, **effective)
        private_record(RENEWAL_LAST, report)
    return report


def renewal_status(runner):
    """只读当前消费者来源/权限/调度与 pending；timer 存在本身不等于 ready。"""
    if not RENEWAL_STATE.exists():
        return {'complete': True, 'read_only': True, 'installed': False, 'renewal_ready': False}
    record = verify_renewal_installation()
    gateway, baseline, protected, public = renewal_context(runner)
    require_approved_reload()
    active = scheduler_active(runner)
    pending = certificate_leaf_identity(runner) != public.get('loaded_certificate_identity')
    latest = read_record(RENEWAL_LAST) if RENEWAL_LAST.exists() else {}
    return {'complete': True, 'read_only': True, 'installed': record.get('status') != 'installing',
            'renewal_ready': record.get('status') == 'ready' and latest.get('complete') is True and active and not pending,
            'scheduler_active': active, 'installed_source_and_permissions_verified': True,
            'certificate_reload_pending': pending, 'last_run_complete': latest.get('complete'),
            'native_renewal_command_verified': record.get('native_renewal_command_verified') is True,
            'last_native_result': record.get('last_native_result'),
            'manual_runtime_program': str(RUNTIME_PROGRAM)}


def stop(runner):
    """先撤回本模块入口，再只停止已登记新容器；保留卷、密钥和所有旧站。"""
    if PUBLIC_STATE.exists():
        public = public_record()
        if public.get('status') in ('publishing', 'published', 'pending') or public.get('public_entry') is True or public.get('loaded_state_uncertain'):
            retract(runner)
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
    renewal_attempt = False
    try:
        check(len(arguments) == 1 and arguments[0] in OPERATIONS, 'unsupported_fixed_operation')
        # 私有本地恢复脚本可独立执行，但须保持安装时已审 source 与 root 权限。
        if Path(globals().get('__file__', '')).absolute() == RUNTIME_PROGRAM:
            verify_runtime_program()
        runner = Runner(850 if arguments[0] == 'prepare' else 420 if arguments[0] in ('deploy', 'prepare-tls', 'publish', 'renew', 'scheduled-renew') else 240 if arguments[0] == 'install-renewal' else 180)
        if arguments[0] in ('renew', 'scheduled-renew'):
            renewal_record()
            private_record(RENEWAL_LAST, {'operation': arguments[0], 'complete': False,
                                         'stage': 'running', 'started_at': int(time.time())})
            renewal_attempt = True
        report.update({'inventory': inventory, 'prepare': prepare, 'deploy': deploy,
                       'bootstrap': bootstrap, 'prepare-tls': prepare_tls,
                       'publish': publish, 'retract': retract, 'install-renewal': install_renewal,
                       'renew': renew, 'scheduled-renew': lambda value: renew(value, scheduled=True),
                       'renewal-status': renewal_status, 'health': health, 'stop': stop}[arguments[0]](runner))
    except OperationError as error:
        report['errors'].append(str(error))
        if isinstance(error, TLSPreparationError):
            report.update(http01_checks=error.checks, certificate_command_invoked=error.command_invoked,
                          gateway_configuration_changed=False, gateway_reloaded=False)
    except Exception as error:
        report['errors'].append('entertainment_operation:' + type(error).__name__)
    if renewal_attempt and not report['complete']:
        # 失败也记录 pending，保留本轮已观察到的证书变更，不把 timer 或旧成功当本轮成功。
        try:
            last = read_record(RENEWAL_LAST)
            last.update(complete=False, pending=True, operation=arguments[0], errors=report['errors'],
                        finished_at=int(time.time()))
            private_record(RENEWAL_LAST, last)
        except (OperationError, OSError, ValueError) as error:
            report['errors'].append('renewal_failure_record:' + type(error).__name__)
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    return 0 if report['complete'] else 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
