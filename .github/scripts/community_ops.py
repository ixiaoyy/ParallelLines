"""圈子首次上线的固定运维事务；只接受已审核应用版本和明确列出的显式操作。"""

import contextlib
import fcntl
import hashlib
import http.client
import importlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import socket
import ssl
import subprocess
import sys
import time
import urllib.request
import urllib.error
import urllib.parse


APP = "93ca819f20f760b142cab9a320110879ff8179df"
BEFORE = "50d893772a9fe451e575b707d6e9a78cd4f4e8a9"
REMOTE = "https://github.com/ixiaoyy/ParallelLines.git"
MAIN = Path("/opt/parallellines")
ROOT = MAIN / ".deployment/community" / APP
SOURCE = ROOT / "source"
PENDING = ROOT / "pending.json"
CURRENT = ROOT / "current.json"
MAIN_CONFIG = MAIN / "deploy/nginx/default.conf"
MARKER = MAIN / ".deployment/forum-enabled"
RENEW_CRON = Path("/etc/cron.d/parallellines-community-renew")
DOMAIN = "forum.pingxingxian.space"
BASE_FILES = (MAIN / "docker-compose.yml", MAIN / "deploy/docker-compose.migration.yml")
TOOLS = Path("/opt/parallellines-tools/ops")
OLD_CONFIG = "222e0e28eb971465498ae464d8b4567fe99b650dcc46b5e0ce229ae9ecbe4ed9"
NEW_CONFIG = "39e83980ff071194e2e0711111bc4e09be28f1cd64c9197b4c13209623f308cf"
TAG = "community-" + APP
FORUM_IMAGE = "parallellines-forum-web:" + TAG
API_IMAGE = "parallellines-community-api:" + APP
API_BASE_IMAGE = "parallellines-community-api-base:" + APP
BASE_API_TREE = "593a6c62df1fe2b104468ccdbe2caa86a2d273603fa79d2f2d424555fa8d8ee7"
API_CHANGED_FILES = ("apps/api/app/api/seo.py", "apps/api/app/core/config.py",
                     "apps/api/app/services/seo.py", "apps/api/app/services/seo_renderer.py")
OPERATIONS = ("inventory", "prepare", "probe", "prepare-tls", "deploy", "health", "rollback")
BODY_LIMIT = 2 * 1024 * 1024
# 按阶段交付；准备与真实切换分别完成现场及恢复审查后才能加入此列表。
READY_OPERATIONS = ("inventory", "health", "prepare", "probe", "prepare-tls")


class OperationError(Exception):
    """只携带稳定错误码，不下发环境、配置原文、命令 stderr 或响应正文。"""


class ProbeError(OperationError):
    """保留有界 HTTP 状态/同域跳转诊断，不携带完整 URL、查询串或响应正文。"""

    def __init__(self, code, checks):
        super().__init__(code)
        self.checks = checks


class Runner:
    """固定 argv 执行器；总时限、单项时限和输出均有上限，不使用 shell。"""

    def __init__(self, seconds=150):
        self.end = time.monotonic() + seconds

    def run(self, label, args, timeout=15, accepted=(0,), binary=False, cwd=None):
        remaining = self.end - time.monotonic()
        if remaining <= 0:
            raise OperationError("operation_deadline_reached")
        try:
            result = subprocess.run(args, cwd=cwd, capture_output=True, text=not binary,
                                    timeout=min(timeout, remaining), check=False,
                                    env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
        except subprocess.TimeoutExpired:
            raise OperationError(label + ":timeout") from None
        except OSError as error:
            raise OperationError(label + ":" + type(error).__name__) from None
        if result.returncode not in accepted:
            raise OperationError(label + ":exit_" + str(result.returncode))
        if len(result.stdout) + len(result.stderr) > BODY_LIMIT:
            raise OperationError(label + ":output_limit")
        return result


def digest(value):
    """返回公开前像或受限元数据的完整摘要，用于并发校验，不用于隐藏敏感值。"""
    if not isinstance(value, bytes):
        value = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(value).hexdigest()


def safe_path(path, *, root=None):
    """限定本次固定目录并拒绝任一级符号链接；不创建或读取目录外对象。"""
    root = MAIN if root is None else Path(root)
    path = Path(path)
    if path != root and root not in path.parents:
        raise OperationError("path_outside_owned_root")
    for item in (path, *path.parents):
        if item == root or root in item.parents:
            if item.is_symlink():
                raise OperationError("owned_path_symlink")
    return path


def atomic(path, data):
    """只写本任务文件；主 Nginx 配置由同 inode 的独立写入方法处理。"""
    path = safe_path(path)
    path.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".new-" + secrets.token_hex(4))
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def save(path, value):
    """保存私有恢复记录，不向日志展开记录内容或真实配置。"""
    atomic(path, (json.dumps(value, sort_keys=True, indent=2) + "\n").encode())


def read(path):
    """读取固定小型事务记录；缺失返回 None，损坏明确失败。"""
    path = safe_path(path)
    if not path.exists():
        return None
    if not path.is_file() or path.stat().st_size > BODY_LIMIT:
        raise OperationError("transaction_record_invalid")
    return json.loads(path.read_text(encoding="utf-8"))


def git(runner, args, *, repository=None, binary=False, accepted=(0,)):
    """只在固定主仓库或本任务源码副本执行 Git，禁用交互和外部 diff。"""
    repository = MAIN if repository is None else repository
    return runner.run("git_" + args[0], ["git", "--no-optional-locks", "-c", "core.fsmonitor=false",
                      "-c", "credential.helper=", "-C", str(repository), *args],
                      timeout=120 if args[0] == "fetch" else 15, binary=binary, accepted=accepted)


def git_state(runner):
    """核全局 tracked/index 与非本任务未跟踪文件；不读取 .env 或工作区文件正文。"""
    head = git(runner, ["rev-parse", "--verify", "HEAD"]).stdout.strip()
    branch = git(runner, ["symbolic-ref", "--quiet", "HEAD"]).stdout.strip()
    status = git(runner, ["status", "--porcelain=v1", "--untracked-files=no", "--", ".",
                         ":(exclude).deployment/community/**", ":(exclude).deployment/forum-enabled"]).stdout
    untracked = git(runner, ["ls-files", "--others", "--exclude-standard", "--directory", "--", ".",
                            ":(exclude).deployment/community/**", ":(exclude).deployment/forum-enabled"]).stdout
    if not re.fullmatch(r"[0-9a-f]{40}", head) or branch != "refs/heads/main":
        raise OperationError("main_git_identity_invalid")
    return {"head": head, "branch": branch, "clean": not status,
            "tracked_dirty_paths": [line[3:] for line in status.splitlines()][:64],
            "untracked_directory_entries": len(untracked.splitlines())}


def compose(runner, args, override=None):
    """只用现场固定 base+migration 及本任务镜像覆盖；不展开真实环境。"""
    command = ["docker", "compose", "--project-name", "parallellines", "--project-directory", str(MAIN)]
    for file in BASE_FILES:
        if not safe_path(file).is_file():
            raise OperationError("baseline_compose_file_missing")
        command += ["--file", str(file)]
    if override:
        command += ["--file", str(safe_path(override))]
    return runner.run("compose_" + args[0], command + args, timeout=120)


def compose_hash(runner, service, override=None):
    """仅读取 Compose 原生服务摘要，不打印完整 model、env 或密钥。"""
    value = compose(runner, ["config", "--hash", service], override).stdout.strip()
    match = re.fullmatch(r"(?:[a-z-]+\s+)?([0-9a-f]{64})", value)
    if not match:
        raise OperationError("compose_hash_invalid")
    return match[1]


def containers(runner):
    """读取容器身份白名单及固定规格，不读取 Config.Env 或完整 inspect/labels。"""
    ids = runner.run("docker_ps", ["docker", "ps", "--all", "--no-trunc", "--format", "{{.ID}}"] ).stdout.split()
    if len(ids) > 64 or not ids or any(not re.fullmatch(r"[0-9a-f]{64}", item) for item in ids):
        raise OperationError("container_inventory_bounds")
    fields = {"id": ".Id", "image_id": ".Image", "image": ".Config.Image", "running": ".State.Running",
              "project": '(index .Config.Labels "com.docker.compose.project")',
              "service": '(index .Config.Labels "com.docker.compose.service")',
              "hash": '(index .Config.Labels "com.docker.compose.config-hash")',
              "working_directory": '(index .Config.Labels "com.docker.compose.project.working_dir")',
              "compose_files": '(index .Config.Labels "com.docker.compose.project.config_files")',
              "mounts": ".Mounts", "restart": ".HostConfig.RestartPolicy",
              "entrypoint": ".Config.Entrypoint", "command": ".Config.Cmd",
              "port_bindings": ".HostConfig.PortBindings", "privileged": ".HostConfig.Privileged",
              "network_mode": ".HostConfig.NetworkMode", "memory": ".HostConfig.Memory",
              "nano_cpus": ".HostConfig.NanoCpus", "read_only": ".HostConfig.ReadonlyRootfs",
              "user": ".Config.User", "workdir": ".Config.WorkingDir"}
    # 非目标服务只取 ID/名称/镜像/运行状态，避免把任意其他容器的命令参数带进状态。
    basic = '{"id":{{json .Id}},"name":{{json .Name}},"image_id":{{json .Image}},"running":{{json .State.Running}},"service":{{json (index .Config.Labels "com.docker.compose.service")}},"project":{{json (index .Config.Labels "com.docker.compose.project")}}}'
    records = [json.loads(line) for line in runner.run("docker_identities", ["docker", "inspect", "--format", basic, *ids]).stdout.splitlines()]
    for item in records:
        if item["project"] != "parallellines" or item["service"] not in ("api", "nginx", "forum-web"):
            continue
        template = "{" + ",".join(json.dumps(key) + ":{{json " + value + "}}" for key, value in fields.items()) + "}"
        item.update(json.loads(runner.run("service_public_spec", ["docker", "inspect", "--format", template, item["id"]]).stdout))
        item["networks"] = sorted(runner.run("service_networks", ["docker", "inspect", "--format", "{{range $name, $network := .NetworkSettings.Networks}}{{$name}} {{end}}", item["id"]]).stdout.split())
        if item["service"] == "api" and item["command"] != ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]:
            # 命令的额外空白由 Compose 折叠方式决定；只接受同一已知词序，不回显未知参数。
            command = item["command"]
            if not (isinstance(command, list) and len(command) == 3 and command[:2] == ["sh", "-c"]
                    and " ".join(command[2].split()) == "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"):
                raise OperationError("api_command_requires_review")
    return records


def service(records, name, *, optional=False):
    """从已核 project 定位唯一服务，不猜容器名，也不接管外部同名服务。"""
    selected = [item for item in records if item.get("project") == "parallellines" and item.get("service") == name]
    if optional and not selected:
        return None
    if len(selected) != 1:
        raise OperationError("service_not_unique:" + name)
    return selected[0]


def current_revision(runner, api):
    """仅用 Alembic current 读取现有版本表，不升级或创建迁移。"""
    output = runner.run("alembic_current", ["docker", "exec", api["id"], "alembic", "current"], timeout=20).stdout
    revisions = re.findall(r"^([a-zA-Z0-9_]+)(?:\s+\(head\))?\s*$", output, flags=re.MULTILINE)
    if len(revisions) != 1:
        raise OperationError("database_revision_not_unique")
    return revisions[0]


def ownership_metadata():
    """只取固定部署/Git目标的数字属主和权限，不解析用户名、不改权限或读取文件内容。"""
    paths = {"main_directory": MAIN, "git_directory": MAIN / ".git", "git_index": MAIN / ".git/index",
             "main_ref": MAIN / ".git/refs/heads/main", "default_conf": MAIN_CONFIG,
             "fetch_head": MAIN / ".git/FETCH_HEAD", "packed_refs": MAIN / ".git/packed-refs"}
    value = {}
    for label, path in paths.items():
        try:
            metadata = path.lstat()
        except FileNotFoundError:
            value[label] = {"exists": False}
            continue
        value[label] = {"exists": True, "uid": metadata.st_uid, "gid": metadata.st_gid,
                        "mode": metadata.st_mode & 0o7777, "symlink": path.is_symlink()}
    return value


def inventory(runner):
    """独立只读盘点：当前身份、Git、挂载、迁移版本及配置完整前像，不建目录。"""
    records = containers(runner)
    api, gateway = service(records, "api"), service(records, "nginx")
    config = safe_path(MAIN_CONFIG).read_bytes()
    if len(config) > BODY_LIMIT:
        raise OperationError("main_config_size_limit")
    stat = MAIN_CONFIG.stat()
    inode = runner.run("gateway_configuration_inode", ["docker", "exec", gateway["id"], "stat", "-c", "%d:%i", "/etc/nginx/conf.d/default.conf"]).stdout.strip()
    if inode != f"{stat.st_dev}:{stat.st_ino}":
        raise OperationError("gateway_configuration_inode_mismatch")
    if not any(m.get("Source") == str(MAIN_CONFIG) and m.get("Destination") == "/etc/nginx/conf.d/default.conf" and m.get("RW") is False for m in gateway["mounts"]):
        raise OperationError("gateway_configuration_mount_mismatch")
    # 资源与源码完整性只收集非敏感元数据；不执行构建或读取真实环境值。
    memory = {}
    for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
        key, _, text = line.partition(":")
        if key in ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree"):
            memory[key] = int(text.split()[0]) * 1024
    disk = shutil.disk_usage(MAIN)
    integrity_script = ("import hashlib,json;from pathlib import Path;"
                        "r=Path('/app');p=[r/'uv.lock',r/'pyproject.toml',r/'alembic.ini']+sorted((r/'app').rglob('*.py'))+sorted((r/'alembic').rglob('*.py'));"
                        "assert len(p)<=2048 and sum(x.stat().st_size for x in p)<=67108864;"
                        "h={str(x.relative_to(r)):hashlib.sha256(x.read_bytes()).hexdigest() for x in p};"
                        "print(json.dumps({'file_count':len(h),'tree_sha256':hashlib.sha256(json.dumps(h,sort_keys=True,separators=(',',':')).encode()).hexdigest(),'uv_lock_sha256':h['uv.lock'],'pyproject_sha256':h['pyproject.toml']}))")
    integrity = json.loads(runner.run("api_public_source_integrity", ["docker", "exec", api["id"], "python", "-c", integrity_script], timeout=20).stdout) if api["running"] else None
    git_value = git_state(runner)
    untracked_count = git_value.pop("untracked_directory_entries")
    value = {"git": git_value, "config_sha256": digest(config),
             "config_identity": {"device": stat.st_dev, "inode": stat.st_ino},
             "api": api, "gateway": gateway,
             "forum": service(records, "forum-web", optional=True),
             "other_container_ids": sorted(item["id"] for item in records if item["id"] != api["id"]
                                           and item is not service(records, "forum-web", optional=True)),
             "api_compose_hash": compose_hash(runner, "api"),
             "gateway_compose_hash": compose_hash(runner, "nginx"),
             "database_revision": current_revision(runner, api) if api["running"] else None,
             "forum_certificate_present": (MAIN / "var/letsencrypt/live" / DOMAIN / "fullchain.pem").is_file(),
             "api_public_source_integrity": integrity, "ownership": ownership_metadata()}
    value["approval_identity"] = approval_identity(value)
    value["approval_sha256"] = digest(value["approval_identity"])
    value["state_sha256"] = digest(value)
    # 容量和负载会自然变化，不把它们混入身份前像；每次只读盘点仍返回最新值供审批。
    value["resources"] = {"cpu_count": os.cpu_count(), "load_average": os.getloadavg(),
                          "memory": memory, "disk": {"path": str(MAIN), "total": disk.total, "free": disk.free}}
    value["worktree_boundaries"] = {"untracked_directory_entries": untracked_count,
                                   "historical_untracked_not_read_or_modified": True}
    return value


def approval_identity(actual):
    """外部授权仅使用已独立核实的公开任务身份；完整运行状态另作服务端并发守卫。"""
    return {"schema": 1, "application_revision": APP,
            "git": {"head": actual["git"]["head"], "tracked_index_clean": actual["git"]["clean"]},
            "configuration": {"sha256": actual["config_sha256"], "identity": actual["config_identity"]},
            "api": {"id": actual["api"]["id"], "image_id": actual["api"]["image_id"],
                    "compose_hash": actual["api_compose_hash"]},
            "gateway": {"id": actual["gateway"]["id"], "compose_hash": actual["gateway_compose_hash"]},
            "database_revision": actual["database_revision"],
            "api_public_source_tree_sha256": actual["api_public_source_integrity"]["tree_sha256"]}


def expect_snapshot(actual, expected):
    """只接受新协议的透明授权身份摘要；不猜补或换通道获取被遮蔽的完整状态摘要。"""
    if not re.fullmatch(r"[0-9a-f]{64}", expected) or digest(approval_identity(actual)) != expected:
        raise OperationError("fresh_approval_identity_mismatch")


def baseline(actual):
    """本次首次激活仅接受已核原站版本；未知规格或既有圈子服务一律停止。"""
    if (actual["git"]["head"] != BEFORE or not actual["git"]["clean"]
            or actual["config_sha256"] != OLD_CONFIG or actual["forum"] is not None):
        raise OperationError("initial_application_baseline_mismatch")
    for key in ("api", "gateway"):
        item = actual[key]
        if (not item["running"] or item["working_directory"] != str(MAIN)
                or item["compose_files"] != ",".join(map(str, BASE_FILES))
                or item["hash"] != actual[key + "_compose_hash"]):
            raise OperationError("runtime_compose_or_environment_drift:" + key)
    if "parallellines_default" not in actual["api"]["networks"] or "parallellines_default" not in actual["gateway"]["networks"]:
        raise OperationError("baseline_network_missing")
    if not actual.get("api_public_source_integrity") or actual["api_public_source_integrity"]["tree_sha256"] != BASE_API_TREE:
        raise OperationError("running_api_public_source_differs_from_reviewed_base")


def source_prepare(runner):
    """只在独立目录取得固定公开提交，不切换或覆盖正在服务的主工作树。"""
    safe_path(ROOT).mkdir(mode=0o750, parents=True, exist_ok=True)
    if not SOURCE.exists():
        SOURCE.mkdir(mode=0o750)
        runner.run("source_init", ["git", "init", str(SOURCE)])
    head = git(runner, ["rev-parse", "--verify", "HEAD"], repository=SOURCE, accepted=(0, 128))
    if head.returncode == 128:
        if git(runner, ["status", "--porcelain=v1", "--untracked-files=all"], repository=SOURCE).stdout:
            raise OperationError("unfinished_source_contains_unowned_files")
        git(runner, ["fetch", "--no-tags", "--depth=1", REMOTE, APP], repository=SOURCE)
        git(runner, ["checkout", "--detach", "FETCH_HEAD"], repository=SOURCE)
    if git(runner, ["rev-parse", "HEAD"], repository=SOURCE).stdout.strip() != APP:
        raise OperationError("prepared_source_identity_mismatch")
    if git(runner, ["status", "--porcelain=v1", "--untracked-files=all"], repository=SOURCE).stdout:
        raise OperationError("prepared_source_dirty")
    if digest((SOURCE / "deploy/nginx/default.conf").read_bytes()) != NEW_CONFIG:
        raise OperationError("candidate_configuration_mismatch")


def image_id(runner, name):
    """仅返回 Docker 原生镜像 ID，不展开镜像环境或历史层。"""
    value = runner.run("image_identity", ["docker", "image", "inspect", "--format", "{{.Id}}", name]).stdout.strip()
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
        raise OperationError("image_identity_invalid")
    return value


def prepare(runner, expected):
    """盘点一致后离线构建独立候选镜像，保留旧镜像和原服务不变。"""
    before = inventory(runner)
    expect_snapshot(before, expected)
    baseline(before)
    if (before["resources"]["memory"].get("MemAvailable", 0) < 2500 * 1024 * 1024
            or before["resources"]["disk"]["free"] < 8 * 1024 * 1024 * 1024):
        raise OperationError("insufficient_headroom_for_bounded_serial_prepare")
    if PENDING.exists() or CURRENT.exists() or MARKER.exists():
        raise OperationError("existing_community_state_requires_review")
    source_prepare(runner)
    target_preimages(runner)
    forum_recipe = (SOURCE / "apps/web/Dockerfile.forum").read_bytes()
    old_build = b"RUN pnpm --dir apps/web build:forum"
    if forum_recipe.count(old_build) != 1:
        raise OperationError("forum_build_resource_limit_anchor_changed")
    atomic(ROOT / "forum.build.Dockerfile", forum_recipe.replace(old_build,
           b"RUN NODE_OPTIONS=--max-old-space-size=1536 pnpm --dir apps/web build:forum", 1))
    runner.run("build_forum", ["docker", "build", "--build-arg", "SOURCE_REVISION=" + APP,
               "--file", str(ROOT / "forum.build.Dockerfile"), "--tag", FORUM_IMAGE, str(SOURCE)], timeout=1200)
    # 已核旧镜像与公开基线完全一致，只覆本次四个 app 文件；不重装依赖、不公开旧镜像。
    runner.run("pin_unchanged_api_base", ["docker", "image", "tag", before["api"]["image_id"], API_BASE_IMAGE])
    recipe = "FROM " + API_BASE_IMAGE + "\nLABEL org.opencontainers.image.revision=" + APP + "\n"
    recipe += "".join("COPY " + name + " /app/" + name[len("apps/api/"):] + "\n" for name in API_CHANGED_FILES)
    atomic(ROOT / "api.build.Dockerfile", recipe.encode())
    runner.run("build_api", ["docker", "build", "--pull=false", "--network", "none", "--file", str(ROOT / "api.build.Dockerfile"), "--tag", API_IMAGE, str(SOURCE)], timeout=120)
    heads = runner.run("candidate_migration_heads", ["docker", "run", "--rm", "--network", "none", "--entrypoint", "alembic", API_IMAGE, "heads"], timeout=30).stdout
    values = re.findall(r"^([a-zA-Z0-9_]+)\s+\(head\)\s*$", heads, flags=re.MULTILINE)
    if values != [before["database_revision"]]:
        raise OperationError("candidate_has_pending_or_divergent_database_migration")
    after = inventory(runner)
    if after["state_sha256"] != before["state_sha256"]:
        raise OperationError("runtime_changed_during_prepare")
    value = {"source_revision": APP, "baseline": before, "forum_image_id": image_id(runner, FORUM_IMAGE),
             "api_image_id": image_id(runner, API_IMAGE), "candidate_database_revision": values[0]}
    save(ROOT / "prepared.json", value)
    return {"complete": True, "source_revision": APP, "images_prepared": True,
            "old_services_unchanged": True, "database_migration_required": False}


@contextlib.contextmanager
def tools_lock():
    """与已安装工具续期/发布共用锁；不改变其 hook、源文件或事务锚点。"""
    if TOOLS.is_symlink() or not (TOOLS / "tls.py").is_file():
        raise OperationError("installed_tls_recovery_unavailable")
    sys.path.insert(0, str(TOOLS))
    tls = importlib.import_module("tls")
    with tls.tls_lock():
        yield tls


@contextlib.contextmanager
def request_deadline(seconds):
    """在已知 Linux 上给 DNS、连接及完整读取加总时限，不给服务或容器发信号。"""
    def expired(_number, _frame):
        raise OperationError("public_request_total_timeout")
    previous = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """首期验证要求固定目标直接返回，拒绝跳到其它域名掩盖错误入口。"""

    def redirect_request(self, _request, _fp, _code, _message, _headers, _new_url):
        return None


def forum_document_valid(body):
    """只认可论坛页面自己的规范链接和标题，导航里出现圈子链接不算论坛首屏。"""
    return (len(body) <= BODY_LIMIT
            and re.search(rb'<link\s+[^>]*rel=["\']canonical["\'][^>]*href=["\']https://forum\.pingxingxian\.space/["\']', body) is not None
            and re.search(rb"<title[^>]*>[^<]*" + "圈子".encode() + rb"[^<]*</title>", body) is not None)


def verify_forum_probe(url, expected):
    """固定 HTTP01 路径最多接受三次同域 HTTP/HTTPS 跳转，总时限内直接核对一次性正文。"""
    initial = urllib.parse.urlsplit(url)
    if (initial.scheme != "http" or initial.hostname != DOMAIN or initial.query or initial.fragment
            or not re.fullmatch(r"/\.well-known/acme-challenge/tools-probe-[0-9a-f]{32}", initial.path)):
        raise ProbeError("forum_http01_initial_probe_contract", [])
    checks = []
    opener = urllib.request.build_opener(NoRedirect())
    with request_deadline(18):
        for step in range(4):
            current = urllib.parse.urlsplit(url)
            request = urllib.request.Request(url, headers={"User-Agent": "ParallelLinesCommunityHTTP01/1", "Cache-Control": "no-cache"})
            try:
                response = opener.open(request, timeout=6)
            except urllib.error.HTTPError as error:
                status, location = error.code, error.headers.get("Location")
                error.close()
                entry = {"step": step, "scheme": current.scheme, "status": status}
                checks.append(entry)
                if status not in (301, 302, 303, 307, 308):
                    raise ProbeError("forum_http01_status_" + str(status), checks) from None
                if not location or step == 3:
                    raise ProbeError("forum_http01_redirect_missing_or_limit", checks) from None
                destination = urllib.parse.urlsplit(urllib.parse.urljoin(url, location))
                entry.update(same_host=destination.hostname == DOMAIN, scheme_allowed=destination.scheme in ("http", "https"),
                             same_probe_path=destination.path == initial.path, has_query=bool(destination.query),
                             has_fragment=bool(destination.fragment), has_userinfo=destination.username is not None)
                try:
                    port_allowed = destination.port in (None, 443 if destination.scheme == "https" else 80)
                except ValueError:
                    raise ProbeError("forum_http01_redirect_invalid_port", checks) from None
                entry["port_allowed"] = port_allowed
                if (destination.hostname != DOMAIN or destination.scheme not in ("http", "https")
                        or destination.username is not None or destination.password is not None
                        or destination.query or destination.fragment or destination.path != initial.path
                        or not port_allowed):
                    raise ProbeError("forum_http01_redirect_outside_fixed_contract", checks) from None
                url = urllib.parse.urlunsplit(destination)
                continue
            except urllib.error.URLError as error:
                raise ProbeError("forum_http01_transport_" + type(error.reason).__name__, checks) from None
            except OSError as error:
                raise ProbeError("forum_http01_transport_" + type(error).__name__, checks) from None
            with response:
                checks.append({"step": step, "scheme": current.scheme, "status": response.status})
                if response.status != 200:
                    raise ProbeError("forum_http01_status_" + str(response.status), checks)
                if response.read(len(expected) + 1) != expected:
                    raise ProbeError("community_http01_probe_mismatch", checks)
            return checks
    raise ProbeError("forum_http01_redirect_limit", checks)


def owned_forum_probe(tls):
    """复用成熟探针文件的排他创建/精确清理，仅把公开请求落点限定为圈子域。"""
    with tls.owned_probe() as (url, body):
        probe = url.replace("http://tools.pingxingxian.space/", "http://" + DOMAIN + "/", 1)
        if probe == url:
            raise ProbeError("reviewed_probe_domain_contract_changed", [])
        return verify_forum_probe(probe, body)


def probe_only(runner, expected):
    """只创建并清理自己的唯一 HTTP01 探针，输出 HTTP 层诊断，不请求证书或改服务。"""
    actual = inventory(runner)
    expect_snapshot(actual, expected)
    baseline(actual)
    with tools_lock() as tls:
        if not tls.configuration_may_reload():
            raise OperationError("installed_configuration_ownership_guard_rejected")
        tls.context_preflight()
        checks = owned_forum_probe(tls)
    return {"complete": True, "probe_only": True, "certificate_requested": False,
            "services_changed": False, "probe_checks": checks}


def prepare_tls(runner, expected):
    """仅新圈子证书：先验证公网 HTTP01 探针，再用既有 Certbot/webroot 签发。"""
    actual = inventory(runner)
    expect_snapshot(actual, expected)
    baseline(actual)
    with tools_lock() as tls:
        if not tls.configuration_may_reload():
            raise OperationError("installed_configuration_ownership_guard_rejected")
        context = tls.context_preflight()
        checks = owned_forum_probe(tls)
        guard = "import subprocess,sys;p=subprocess.Popen(sys.argv[1:]);\ntry: code=p.wait(timeout=300)\nexcept subprocess.TimeoutExpired:\n p.terminate();\n try: p.wait(timeout=10)\n except subprocess.TimeoutExpired: p.kill();p.wait()\n code=124\nsys.exit(code)"
        runner.run("community_certificate", ["docker", "exec", context["certbot"], "python3", "-c", guard,
                   "certbot", "certonly", "--webroot", "-w", "/var/www/certbot", "--cert-name", DOMAIN,
                   "--keep-until-expiring", "--non-interactive", "--agree-tos", "--register-unsafely-without-email",
                   "--no-directory-hooks", "-d", DOMAIN], timeout=330)
    cert = MAIN / "var/letsencrypt/live" / DOMAIN / "fullchain.pem"
    output = runner.run("public_community_certificate", ["openssl", "x509", "-in", str(cert), "-noout", "-ext", "subjectAltName", "-checkend", "86400"]).stdout
    if DOMAIN not in re.findall(r"DNS:([A-Za-z0-9*_.-]+)", output):
        raise OperationError("community_certificate_domain_mismatch")
    return {"complete": True, "new_domain_certificate_ready": True, "gateway_reloaded": False,
            "old_certificates_and_hooks_unchanged": True, "probe_checks": checks}


def same_spec(before, after):
    """API 切换只允许镜像、实例身份及 Compose 接线改变，其他公开运行规格必须相同。"""
    skip = {"id", "name", "image_id", "image", "hash", "compose_files", "running"}
    return {key: value for key, value in before.items() if key not in skip} == {
        key: value for key, value in after.items() if key not in skip}


def configuration_write(runner, gateway, expected, replacement, identity):
    """在已核原 inode 写入唯一候选前像，保持现有 bind 和工具恢复锚点。"""
    with safe_path(MAIN_CONFIG).open("r+b") as stream:
        stat = os.fstat(stream.fileno())
        if {"device": stat.st_dev, "inode": stat.st_ino} != identity or stream.read() != expected:
            raise OperationError("configuration_preimage_or_inode_changed")
        # 写前保留完整过渡两端和阶段；进程若在 write/truncate 之间退出，可识别自己的半写。
        token = secrets.token_hex(8)
        atomic(ROOT / "config-writes" / (token + ".before"), expected)
        atomic(ROOT / "config-writes" / (token + ".after"), replacement)
        save(ROOT / "config-write.json", {"schema": 1, "phase": "writing", "token": token,
             "gateway_id": gateway["id"], "identity": identity,
             "before_sha256": digest(expected), "after_sha256": digest(replacement)})
        stream.seek(0)
        stream.write(replacement)
        stream.truncate()
        stream.flush()
        os.fsync(stream.fileno())
    observed = runner.run("bound_configuration_digest", ["docker", "exec", gateway["id"], "sha256sum", "/etc/nginx/conf.d/default.conf"]).stdout.split()[0]
    if observed != digest(replacement):
        raise OperationError("bound_configuration_digest_mismatch")
    (ROOT / "config-write.json").unlink()


def known_write_transition(current, before, after):
    """只接受顺序前缀写入及未截断尾部；任一不属于两端的字节均视为外部变化。"""
    if current in (before, after):
        return True
    if len(before) < len(current) <= len(after):
        return current == after[:len(current)]
    if len(current) != len(before):
        return False
    limit = min(len(before), len(after))
    # 前缀第一次偏离 after 之后必须完整等于原尾部，避免枚举无界位置或宽泛接受未知内容。
    first = next((i for i in range(limit) if current[i] != after[i]), limit)
    return current[first:] == before[first:]


def interrupted_configuration_owned(current, state):
    """读取固定写意图及备份，要求同网关/inode且当前字节为严格已知过渡，才允许恢复。"""
    intent = read(ROOT / "config-write.json")
    if not intent:
        return False
    if (intent.get("schema") != 1 or intent.get("phase") != "writing"
            or intent.get("gateway_id") != state["before"]["gateway"]["id"]
            or intent.get("identity") != state["before"]["config_identity"]
            or not re.fullmatch(r"[0-9a-f]{16}", str(intent.get("token", "")))):
        return False
    stat = MAIN_CONFIG.stat()
    if {"device": stat.st_dev, "inode": stat.st_ino} != intent["identity"]:
        return False
    prefix = ROOT / "config-writes" / intent["token"]
    before, after = safe_path(prefix.with_suffix(".before")).read_bytes(), safe_path(prefix.with_suffix(".after")).read_bytes()
    if (len(before) > BODY_LIMIT or len(after) > BODY_LIMIT
            or digest(before) != intent["before_sha256"] or digest(after) != intent["after_sha256"]):
        return False
    return known_write_transition(current, before, after)


def alignment_preflight(runner, state):
    """任何源码/配置突变前一次核全 HEAD、索引及全部目标；半恢复只认精确旧/新或写意图。"""
    head = git(runner, ["rev-parse", "HEAD"]).stdout.strip()
    branch = git(runner, ["symbolic-ref", "--quiet", "HEAD"]).stdout.strip()
    if head not in (BEFORE, APP) or branch != "refs/heads/main":
        raise OperationError("main_branch_changed_outside_attempt")
    if all(git(runner, ["diff", "--cached", "--quiet", revision], accepted=(0, 1)).returncode
           for revision in (BEFORE, APP)):
        raise OperationError("main_index_changed_outside_attempt")
    outside = git(runner, ["diff", "--name-only", "HEAD", "--"]).stdout.splitlines()
    if set(outside) - set(state["paths"]):
        raise OperationError("tracked_files_changed_outside_application_delta")
    observed = {}
    for name in state["paths"]:
        path = safe_path(MAIN / name)
        backup = ROOT / "before" / name
        before = safe_path(backup).read_bytes() if backup.exists() else None
        after = safe_path(SOURCE / name).read_bytes()
        actual = path.read_bytes() if path.exists() else None
        if actual not in (before, after):
            if name != "deploy/nginx/default.conf" or actual is None or not interrupted_configuration_owned(actual, state):
                raise OperationError("application_file_changed_outside_attempt:" + name)
        observed[name] = actual
    return head, observed


def changed_paths(runner):
    """本次只部署固定应用版本相对已核基线的 39 个普通文件，拒绝迁移和私有路径。"""
    # 只从已核本地副本取得公开 Git 对象，不改变 origin 或重取任何运行凭据。
    git(runner, ["fetch", "--no-tags", str(SOURCE), APP])
    paths = git(runner, ["diff", "--name-only", BEFORE, APP]).stdout.splitlines()
    if len(paths) != 39 or "deploy/nginx/default.conf" not in paths:
        raise OperationError("reviewed_application_delta_changed")
    for name in paths:
        if (not re.fullmatch(r"[A-Za-z0-9_./-]+", name) or ".." in name.split("/")
                or name.startswith((".deployment/", "apps/api/alembic/"))
                or Path(name).name == ".env"):
            raise OperationError("application_delta_path_not_approved")
    return paths


def target_preimages(runner):
    """逐项验证 39 个目标的原字节/新增碰撞，不读取或清理任何历史未跟踪数据。"""
    paths = changed_paths(runner)
    for name in paths:
        path = safe_path(MAIN / name)
        previous = git(runner, ["show", BEFORE + ":" + name], binary=True, accepted=(0, 128))
        if previous.returncode == 128:
            if path.exists():
                raise OperationError("new_application_path_collision:" + name)
        elif not path.is_file() or path.read_bytes() != previous.stdout:
            raise OperationError("tracked_application_preimage_changed:" + name)
        if not (SOURCE / name).is_file() or (SOURCE / name).is_symlink():
            raise OperationError("candidate_application_file_not_regular")
    return paths


def align_source(runner, state, *, restore=False):
    """逐文件校验并切换固定公开差异，最后 CAS 更新索引和分支，不用整树 reset。"""
    origin, target = (APP, BEFORE) if restore else (BEFORE, APP)
    _head, observed = alignment_preflight(runner, state)
    for name in state["paths"]:
        path = safe_path(MAIN / name)
        before = ROOT / "before" / name
        wanted = before.read_bytes() if restore and before.exists() else (
            None if restore else (SOURCE / name).read_bytes())
        old = before.read_bytes() if before.exists() else None
        new = (SOURCE / name).read_bytes()
        current = path.read_bytes() if path.exists() else None
        if current != observed[name]:
            raise OperationError("application_file_changed_outside_attempt:" + name)
        if current == wanted:
            continue
        if name == "deploy/nginx/default.conf":
            configuration_write(runner, state["before"]["gateway"], current, wanted,
                                state["before"]["config_identity"])
        elif wanted is None:
            path.unlink()
        else:
            atomic(path, wanted)
            path.chmod((SOURCE / name).stat().st_mode & 0o777)
    head = git(runner, ["rev-parse", "HEAD"]).stdout.strip()
    if head not in (origin, target):
        raise OperationError("main_branch_changed_outside_attempt")
    git(runner, ["read-tree", target])
    if head != target:
        git(runner, ["update-ref", "refs/heads/main", target, origin])
    if not git_state(runner)["clean"]:
        raise OperationError("application_alignment_not_clean")


def internal_forum(runner, api):
    """切网关前经同一 API 读取论坛首屏和公开 API；仅输出布尔结果，不记录内容。"""
    script = ("import json,re,urllib.request;"
              "u='http://127.0.0.1:8000';h={'Host':'forum.pingxingxian.space'};"
              "r=urllib.request.urlopen(urllib.request.Request(u+'/',headers=h),timeout=4);b=r.read(2097153);"
              "a=urllib.request.urlopen(urllib.request.Request(u+'/api/v1/boards',headers=h),timeout=4);"
              "v=json.loads(a.read(2097153));"
              "ok=r.status==200 and len(b)<=2097152 and re.search(b'<link[^>]+rel=\"canonical\"[^>]+href=\"https://forum[.]pingxingxian[.]space/\"',b) and re.search(b'<title[^>]*>[^<]*'+'圈子'.encode()+b'[^<]*</title>',b) and a.status==200 and 'data' in v;"
              "print(json.dumps({'forum_root_and_same_origin_api':bool(ok)}));raise SystemExit(0 if ok else 2)")
    result = runner.run("internal_forum_before_gateway", ["docker", "exec", api["id"], "python", "-c", script], timeout=15)
    return json.loads(result.stdout)


def wait_api(runner, expected):
    """只轮询本次 API，最多等待 75 秒，不触发其它服务的修复或重启。"""
    end = min(runner.end, time.monotonic() + 75)
    while time.monotonic() < end:
        item = service(containers(runner), "api")
        if item["running"] and item["image_id"] == expected:
            result = runner.run("api_health", ["docker", "exec", item["id"], "python", "-c",
                     "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/healthz',timeout=2).read(1024)"], accepted=(0, 1), timeout=4)
            if result.returncode == 0:
                return item
        time.sleep(2)
    raise OperationError("api_health_deadline")


def layer_files(runner, gateway, *, remove=False):
    """只管理两份已审核容器层配置；未来重建必须由论坛 Compose 挂载同内容接续。"""
    pairs = (("deploy/nginx/forum.conf", "/etc/nginx/conf.d/forum.conf"),
             ("deploy/nginx/forum-main-redirects.conf", "/etc/nginx/forum-main/redirects.conf"))
    for path in ("/etc/nginx/forum-main", "/etc/nginx/conf.d/forum.conf", "/etc/nginx/forum-main/redirects.conf"):
        if runner.run("layer_symlink_guard", ["docker", "exec", gateway["id"], "test", "-L", path], accepted=(0, 1)).returncode == 0:
            raise OperationError("community_layer_path_symlink")
    entries = []
    for name, destination in pairs:
        exists = runner.run("layer_file_presence", ["docker", "exec", gateway["id"], "test", "-e", destination], accepted=(0, 1)).returncode == 0
        if exists:
            actual = runner.run("layer_file_digest", ["docker", "exec", gateway["id"], "sha256sum", destination]).stdout.split()[0]
            if actual != digest((SOURCE / name).read_bytes()):
                raise OperationError("community_layer_file_changed_outside_attempt")
        entries.append((name, destination, exists))
    # 全部前像先通过，再改第一份文件，不能先删一份才发现另一份属于他人。
    for name, destination, exists in entries:
        if remove:
            if exists:
                runner.run("remove_owned_layer_file", ["docker", "exec", gateway["id"], "rm", "--", destination])
        elif not exists:
            runner.run("community_layer_directory", ["docker", "exec", gateway["id"], "mkdir", "-p", "/etc/nginx/forum-main"])
            runner.run("install_owned_layer_file", ["docker", "cp", str(SOURCE / name), gateway["id"] + ":" + destination])


def guard_gateway(runner, state):
    """每次 reload/恢复前保持同一网关、同一网络与全部既有挂载，不接管新实例。"""
    live = service(containers(runner), "nginx")
    if live != state["before"]["gateway"]:
        raise OperationError("gateway_changed_outside_attempt")


RENEW_BODY = r'''
import hashlib,json,os,re,signal,socket,ssl,subprocess,sys,time
from pathlib import Path
class RenewalError(Exception): pass
def command(label,args):
    try:
        p=subprocess.run(args,capture_output=True,timeout=8,check=False)
    except (OSError,subprocess.TimeoutExpired): raise RenewalError(label+':execution_failed') from None
    if p.returncode or len(p.stdout)+len(p.stderr)>1048576: raise RenewalError(label+':failed')
    return p.stdout
def sha(data): return hashlib.sha256(data).hexdigest()
def owned(path):
    p=Path(path)
    for item in (p,*p.parents):
        if item==ROOT or ROOT in item.parents:
            if item.is_symlink(): raise RenewalError('renewal_owned_path_symlink')
    return p
def record():
    p=owned(ROOT/'current.json')
    if not p.is_file() or p.stat().st_size>2097152: raise RenewalError('community_current_missing')
    s=json.loads(p.read_text())
    if s.get('source_revision')!=APP or s.get('status')!='committed': raise RenewalError('community_not_committed')
    return s
def file_certificate():
    cert=MAIN/'var/letsencrypt/live'/DOMAIN/'fullchain.pem'
    meta=command('public_certificate',['openssl','x509','-in',str(cert),'-noout','-ext','subjectAltName','-checkend','86400'])
    if DOMAIN.encode() not in re.findall(rb'DNS:([A-Za-z0-9*_.-]+)',meta): raise RenewalError('public_certificate_domain')
    return sha(command('public_certificate_der',['openssl','x509','-in',str(cert),'-outform','DER']))
def loaded_certificate():
    with socket.create_connection(('127.0.0.1',443),timeout=5) as raw:
        with ssl.create_default_context().wrap_socket(raw,server_hostname=DOMAIN) as stream:
            return sha(stream.getpeercert(binary_form=True))
def guard(s,tls):
    before=s['before']; old=before['gateway']; cid=old['id']
    if not re.fullmatch(r'[0-9a-f]{64}',cid): raise RenewalError('gateway_identity_invalid')
    raw=command('gateway',['docker','inspect','--format','{"id":{{json .Id}},"image_id":{{json .Image}},"running":{{json .State.Running}},"mounts":{{json .Mounts}}}',cid])
    live=json.loads(raw)
    if live['id']!=cid or live['image_id']!=old['image_id'] or live['running'] is not True or live['mounts']!=old['mounts']: raise RenewalError('gateway_identity_or_mounts_changed')
    networks=command('gateway_networks',['docker','inspect','--format','{{range $n,$v:=.NetworkSettings.Networks}}{{$n}} {{end}}',cid]).decode().split()
    if sorted(networks)!=old['networks']: raise RenewalError('gateway_networks_changed')
    st=CONFIG.stat()
    if CONFIG.is_symlink() or {'device':st.st_dev,'inode':st.st_ino}!=before['config_identity']: raise RenewalError('configuration_inode_changed')
    inode=command('bound_inode',['docker','exec',cid,'stat','-c','%d:%i','/etc/nginx/conf.d/default.conf']).decode().strip()
    if inode!=str(st.st_dev)+':'+str(st.st_ino): raise RenewalError('configuration_bind_changed')
    if sha(CONFIG.read_bytes())!=CONFIG_SHA or not tls.configuration_may_reload(): raise RenewalError('configuration_ownership_changed')
    renewal=s['renewal']
    for path,key in ((ROOT/'renew-community.py','script_sha256'),(CRON,'cron_sha256')):
        if path.is_symlink() or sha(path.read_bytes())!=renewal[key]: raise RenewalError('renewal_consumer_changed')
    cron_stat=CRON.stat()
    if cron_stat.st_nlink!=1 or cron_stat.st_uid!=0 or cron_stat.st_mode&0o022: raise RenewalError('renewal_cron_permissions_or_links')
    if {'device':cron_stat.st_dev,'inode':cron_stat.st_ino}!=renewal['cron_identity']: raise RenewalError('renewal_cron_identity_changed')
    for path,key in (('/etc/nginx/conf.d/forum.conf','forum_sha256'),('/etc/nginx/forum-main/redirects.conf','redirects_sha256')):
        if command('owned_forum_configuration',['docker','exec',cid,'sha256sum',path]).decode().split()[0]!=renewal[key]: raise RenewalError('forum_configuration_changed')
    return cid
def save_report(value):
    path=owned(ROOT/'renewal-last.json'); temp=owned(ROOT/'renewal-last.json.new')
    if temp.exists(): raise RenewalError('renewal_report_temporary_exists')
    fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as stream:
        json.dump(value,stream,sort_keys=True);stream.flush();os.fsync(stream.fileno())
    os.replace(temp,path)
def main(args):
    report={'complete':False,'reloaded':False,'errors':[]}
    if args not in (['check'],['renew']): return 2
    def expired(_signum,_frame): raise RenewalError('renewal_total_timeout')
    signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,75)
    try:
        state=record(); public=file_certificate(); loaded=loaded_certificate()
        sys.path.insert(0,'/opt/parallellines-tools/ops');import tls
        # check 永不 reload；首次安装也核全部所有权，不能仅以证书一致作为消费者就绪。
        with tls.tls_lock():
            cid=guard(state,tls)
            if public!=file_certificate(): raise RenewalError('public_certificate_changed_during_check')
            if public!=loaded_certificate():
                if args==['check']: raise RenewalError('new_certificate_not_loaded')
                command('nginx_test',['docker','exec',cid,'nginx','-t'])
                guard(state,tls)
                command('nginx_reload',['docker','exec',cid,'nginx','-s','reload'])
                # reload 只投递信号；允许旧 worker 正常退出，最多15秒确认，不重复 reload。
                until=time.monotonic()+15; matched=False
                for attempt in range(30):
                    if time.monotonic()>=until: break
                    if loaded_certificate()==public:
                        matched=True;break
                    time.sleep(0.5)
                if not matched: raise RenewalError('reloaded_certificate_mismatch')
                report['reloaded']=True
            report['complete']=True
    except Exception as error:
        report['errors'].append(str(error) if isinstance(error,RenewalError) else type(error).__name__)
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
    try: save_report(report)
    except Exception as error:
        report['complete']=False;report['errors'].append('report:'+type(error).__name__)
    print(json.dumps(report,sort_keys=True))
    return 0 if report['complete'] else 2
if __name__=='__main__': sys.exit(main(sys.argv[1:]))
'''


def renewal_program():
    """生成固定圈子域证书消费者；没有通用命令、域名、凭据或路径输入。"""
    prefix = ("APP=" + repr(APP) + "\nfrom pathlib import Path\nROOT=Path(" + repr(str(ROOT))
              + ")\nMAIN=Path(" + repr(str(MAIN)) + ")\nDOMAIN=" + repr(DOMAIN)
              + "\nCONFIG=Path(" + repr(str(MAIN_CONFIG)) + ")\nCONFIG_SHA=" + repr(NEW_CONFIG)
              + "\nCRON=Path(" + repr(str(RENEW_CRON)) + ")\n")
    return (prefix + RENEW_BODY).encode()


def renewal_preflight(state):
    """安装/恢复只接受本任务新脚本与 cron 的精确前像，不覆盖未知已有消费者。"""
    paths = ((ROOT / "renew-community.py", "script_sha256"),
             (RENEW_CRON, "cron_sha256"))
    if RENEW_CRON.parent.is_symlink() or not RENEW_CRON.parent.is_dir():
        raise OperationError("renewal_cron_directory_not_regular")
    if ROOT.stat().st_dev != RENEW_CRON.parent.stat().st_dev:
        raise OperationError("renewal_atomic_publication_requires_same_filesystem")
    snapshot = ROOT / "renew-community.cron"
    if snapshot.exists() and (not state.get("renewal") or digest(safe_path(snapshot).read_bytes()) != state["renewal"]["cron_sha256"]):
        raise OperationError("renewal_cron_snapshot_preimage_changed")
    for path, key in paths:
        if path.is_symlink():
            raise OperationError("renewal_consumer_symlink")
        if path.exists():
            if not state.get("renewal") or digest(path.read_bytes()) != state["renewal"][key]:
                raise OperationError("renewal_consumer_preimage_changed")
            if path == RENEW_CRON:
                stat = path.stat()
                if {"device": stat.st_dev, "inode": stat.st_ino} != state["renewal"].get("cron_identity"):
                    raise OperationError("renewal_cron_identity_changed")


def install_renewal(state, tls):
    """仅新增本任务消费者和六小时调度；保留父 Certbot loop、旧 hooks 与 tools cron。"""
    scheduler = tls.renewal_environment()
    if not scheduler["cron_active"] or not scheduler["cron_directory_available"]:
        raise OperationError("community_renewal_scheduler_not_available")
    renewal_preflight(state)
    program = renewal_program()
    cron = ("# parallellines-community-owned " + APP + "\n17 */6 * * * root /usr/bin/python3 -B "
            + str(ROOT / "renew-community.py") + " renew >/dev/null 2>&1\n").encode()
    state["renewal"] = {"script_sha256": digest(program), "cron_sha256": digest(cron),
                        "forum_sha256": digest((SOURCE / "deploy/nginx/forum.conf").read_bytes()),
                        "redirects_sha256": digest((SOURCE / "deploy/nginx/forum-main-redirects.conf").read_bytes())}
    save(PENDING, state)
    # 完整内容先在任务目录原子落盘，再排他发布并去掉临时链接；最终 cron 不会半写且单链接。
    atomic(ROOT / "renew-community.cron", cron)
    atomic(ROOT / "renew-community.py", program)
    snapshot = (ROOT / "renew-community.cron").stat()
    state["renewal"]["cron_identity"] = {"device": snapshot.st_dev, "inode": snapshot.st_ino}
    save(PENDING, state)
    os.link(ROOT / "renew-community.cron", RENEW_CRON)
    (ROOT / "renew-community.cron").unlink()


def remove_renewal(state):
    """只清理匹配前像的消费者及发布临时文件，证书和恢复报告保留。"""
    renewal_preflight(state)
    if state.get("renewal"):
        for path in (RENEW_CRON, ROOT / "renew-community.py", ROOT / "renew-community.cron"):
            if path.exists():
                path.unlink()


def deploy(runner, expected):
    """完整前像及恢复快照先落盘，仅替换 API、增加论坛并原位接入配置，不重建网关。"""
    before = inventory(runner)
    expect_snapshot(before, expected)
    baseline(before)
    prepared = read(ROOT / "prepared.json")
    if (not prepared or prepared["source_revision"] != APP or prepared["candidate_database_revision"] != before["database_revision"]
            or image_id(runner, FORUM_IMAGE) != prepared["forum_image_id"]
            or image_id(runner, API_IMAGE) != prepared["api_image_id"]):
        raise OperationError("prepared_candidates_or_migration_identity_changed")
    if not before["forum_certificate_present"] or PENDING.exists() or CURRENT.exists() or MARKER.exists():
        raise OperationError("community_activation_prerequisite_or_transaction_exists")
    source_prepare(runner)
    paths = target_preimages(runner)
    state = {"schema": 1, "source_revision": APP, "status": "snapshotted", "before": before,
             "paths": paths, "prepared": prepared, "after_api": None, "forum_id": None}
    for name in paths:
        path = safe_path(MAIN / name)
        if path.exists():
            atomic(ROOT / "before" / name, path.read_bytes())
    save(ROOT / "api.override.json", {"services": {"api": {"image": prepared["api_image_id"], "environment": {
         "PUBLIC_FORUM_URL": "https://" + DOMAIN, "FORUM_WEB_APP_SHELL_URL": "http://forum-web/index.html"}},
         "forum-web": {"image": prepared["forum_image_id"], "restart": "unless-stopped", "expose": ["80"],
                       "networks": ["default"], "healthcheck": {"test": ["CMD-SHELL", "wget -qO- http://127.0.0.1/ >/dev/null || exit 1"], "interval": "10s", "timeout": "3s", "retries": 20}}}})
    save(ROOT / "restore.override.json", {"services": {"api": {"image": before["api"]["image_id"]}}})
    state["after_api_hash"] = compose_hash(runner, "api", ROOT / "api.override.json")
    state["forum_hash"] = compose_hash(runner, "forum-web", ROOT / "api.override.json")
    state["restore_api_hash"] = compose_hash(runner, "api", ROOT / "restore.override.json")
    save(PENDING, state)
    with tools_lock() as tls:
        if not tls.configuration_may_reload():
            raise OperationError("installed_configuration_ownership_guard_rejected")
        guard_gateway(runner, state)
        if inventory(runner)["state_sha256"] != before["state_sha256"]:
            raise OperationError("activation_state_changed_before_switch")
        alignment_preflight(runner, state)
        renewal_preflight(state)
        scheduler = tls.renewal_environment()
        if not scheduler["cron_active"] or not scheduler["cron_directory_available"]:
            raise OperationError("community_renewal_scheduler_not_available")
        # 容器层文件在首次启用前必须不存在，避免把他人的文件当成本事务拥有。
        for destination in ("/etc/nginx/conf.d/forum.conf", "/etc/nginx/forum-main/redirects.conf"):
            if runner.run("layer_file_absent", ["docker", "exec", before["gateway"]["id"], "test", "-e", destination], accepted=(0, 1)).returncode == 0:
                raise OperationError("community_layer_file_already_exists")
        align_source(runner, state)
        state["status"] = "source_aligned"
        save(PENDING, state)
        compose(runner, ["up", "-d", "--no-deps", "--no-build", "forum-web"], ROOT / "api.override.json")
        state["forum_id"] = service(containers(runner), "forum-web")["id"]
        save(PENDING, state)
        if current_revision(runner, service(containers(runner), "api")) != prepared["candidate_database_revision"]:
            raise OperationError("database_revision_changed_before_api_switch")
        compose(runner, ["up", "-d", "--no-deps", "--no-build", "api"], ROOT / "api.override.json")
        after_api = wait_api(runner, prepared["api_image_id"])
        if not same_spec(before["api"], after_api):
            raise OperationError("replacement_api_public_spec_changed")
        state["after_api"] = after_api
        state["status"] = "api_ready"
        save(PENDING, state)
        internal_forum(runner, after_api)
        guard_gateway(runner, state)
        layer_files(runner, before["gateway"])
        runner.run("community_nginx_test", ["docker", "exec", before["gateway"]["id"], "nginx", "-t"])
        if not tls.configuration_may_reload():
            raise OperationError("installed_consumer_rejected_aligned_source")
        guard_gateway(runner, state)
        runner.run("community_nginx_reload", ["docker", "exec", before["gateway"]["id"], "nginx", "-s", "reload"])
        health_report = health(runner)
        if not health_report["complete"]:
            raise OperationError("community_independent_health_failed")
        records = containers(runner)
        unaffected = sorted(item["id"] for item in records if item["id"] not in (after_api["id"], state["forum_id"]))
        if unaffected != before["other_container_ids"]:
            raise OperationError("unrelated_container_identity_changed")
        install_renewal(state, tls)
        atomic(MARKER, (TAG + "\n").encode())
        state["status"] = "committed"
        save(CURRENT, state)
        PENDING.unlink()
    runner.run("installed_community_renewal_consumer", ["/usr/bin/python3", "-B", str(ROOT / "renew-community.py"), "check"], timeout=90)
    return {"complete": True, "source_revision": APP, "gateway_not_recreated": True,
            "main_web_not_replaced": True, "shared_data_services_unchanged": True,
            "forum_marker_installed": True, "installed_renewal_consumer_verified": True, "health": health_report}


def restore(runner):
    """只恢复本事务拥有的源文件/API/新服务/两份容器文件；漂移时保留记录并停止。"""
    state = read(PENDING) or read(CURRENT)
    if not state or state.get("source_revision") != APP or state.get("status") == "rolled_back":
        raise OperationError("no_owned_community_transaction_to_restore")
    with tools_lock():
        guard_gateway(runner, state)
        records = containers(runner)
        api = service(records, "api")
        if api["image_id"] not in (state["before"]["api"]["image_id"], state["prepared"]["api_image_id"]):
            raise OperationError("api_changed_outside_community_attempt")
        allowed_api_hashes = (state["before"]["api"]["hash"], state["after_api_hash"], state["restore_api_hash"])
        if api["hash"] not in allowed_api_hashes:
            raise OperationError("api_configuration_changed_outside_attempt")
        forum = service(records, "forum-web", optional=True)
        if forum and (forum["image_id"] != state["prepared"]["forum_image_id"] or forum["hash"] != state["forum_hash"]
                      or (state.get("forum_id") and forum["id"] != state["forum_id"])):
            raise OperationError("forum_changed_outside_community_attempt")
        if not same_spec(state["before"]["api"], api):
            raise OperationError("api_public_spec_changed_outside_attempt")
        alignment_preflight(runner, state)
        renewal_preflight(state)
        if MARKER.exists() and MARKER.read_text(encoding="ascii") != TAG + "\n":
            raise OperationError("forum_marker_changed_outside_attempt")
        remove_renewal(state)
        layer_files(runner, state["before"]["gateway"], remove=True)
        align_source(runner, state, restore=True)
        if api["image_id"] != state["before"]["api"]["image_id"] or not api["running"]:
            compose(runner, ["up", "-d", "--no-deps", "--no-build", "api"], ROOT / "restore.override.json")
        # 即使镜像已是旧版本也必须确认运行及健康，不能将已停或不健康的旧实例当恢复成功。
        restored = wait_api(runner, state["before"]["api"]["image_id"])
        if not same_spec(state["before"]["api"], restored):
            raise OperationError("restored_api_public_spec_mismatch")
        if forum:
            runner.run("remove_owned_forum_instance", ["docker", "rm", "--force", forum["id"]])
        if MARKER.exists():
            if MARKER.read_text(encoding="ascii") != TAG + "\n":
                raise OperationError("forum_marker_changed_outside_attempt")
            MARKER.unlink()
        guard_gateway(runner, state)
        runner.run("restored_nginx_test", ["docker", "exec", state["before"]["gateway"]["id"], "nginx", "-t"])
        runner.run("restored_nginx_reload", ["docker", "exec", state["before"]["gateway"]["id"], "nginx", "-s", "reload"])
        restored_health = health(runner, include_community=False)
        if not restored_health["complete"]:
            raise OperationError("restored_independent_baseline_health_failed")
        state["status"] = "rolled_back"
        save(ROOT / "rolled-back.json", state)
        for record in (PENDING, CURRENT):
            if record.exists():
                record.unlink()
    return {"complete": True, "restored_original_api_and_source": True, "gateway_not_recreated": True,
            "data_and_previous_images_preserved": True}


class OriginHTTPS(http.client.HTTPSConnection):
    """仅连接本机443，以固定圈子域名执行标准 CA/SNI 校验，不绕过 TLS 验证。"""

    def connect(self):
        raw = socket.create_connection(("127.0.0.1", 443), timeout=self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=DOMAIN)
        except Exception:
            raw.close()
            raise


def health(runner, *, include_community=True):
    """独立只读健康矩阵，不依赖部署进程；失败记录错误码，继续其余有限检查。"""
    checks = []
    endpoints = [("main", "https://pingxingxian.space/healthz"),
                 ("tools", "https://tools.pingxingxian.space/healthz"),
                 ("chat", "https://chat.pingxingxian.space/health"),
                 ("oidc", "https://pingxingxian.space/auth/oidc/.well-known/openid-configuration"),
                 ("model_gateway", "https://api.pingxingxian.space/api/status")]
    if include_community:
        endpoints.append(("community", "https://" + DOMAIN + "/"))
    for name, url in endpoints:
        try:
            with request_deadline(8), urllib.request.build_opener(NoRedirect()).open(urllib.request.Request(url, headers={"User-Agent": "ParallelLinesCommunityHealth/1"}), timeout=6) as response:
                body = response.read(BODY_LIMIT + 1)
                if response.status != 200 or len(body) > BODY_LIMIT:
                    raise OperationError("http_status_or_size")
                if name == "community" and not forum_document_valid(body):
                    raise OperationError("community_document_mismatch")
            checks.append({"name": name, "ok": True})
        except (OSError, ValueError, OperationError) as error:
            checks.append({"name": name, "ok": False, "error": str(error) if isinstance(error, OperationError) else type(error).__name__})
    if not include_community:
        return {"complete": all(item["ok"] for item in checks), "read_only": True, "checks": checks}
    try:
        with request_deadline(8):
            connection = OriginHTTPS(DOMAIN, timeout=6, context=ssl.create_default_context())
            try:
                connection.request("GET", "/", headers={"Host": DOMAIN})
                response = connection.getresponse()
                body = response.read(BODY_LIMIT + 1)
            finally:
                connection.close()
        if response.status != 200 or not forum_document_valid(body):
            raise OperationError("community_origin_document_mismatch")
        checks.append({"name": "community_origin_tls", "ok": True, "ca_verified": True})
    except (OSError, ValueError, http.client.HTTPException, OperationError) as error:
        checks.append({"name": "community_origin_tls", "ok": False, "error": str(error) if isinstance(error, OperationError) else type(error).__name__})
    return {"complete": all(item["ok"] for item in checks), "read_only": True, "checks": checks}


def main(arguments):
    """只按固定枚举及应用 SHA 派发；任何失败均非零，不把恢复失败伪装成成功。"""
    report = {"operation": arguments[0] if arguments else "rejected", "complete": False, "errors": []}
    operation = report["operation"]
    if len(arguments) != 3 or operation not in OPERATIONS or arguments[1] != APP:
        report["errors"].append("unsupported_operation_or_application_revision")
        print(json.dumps(report))
        return 2
    if operation not in READY_OPERATIONS:
        report["errors"].append("community_write_operations_pending_review")
        print(json.dumps(report))
        return 2
    runner = Runner(2600 if operation == "prepare" else 420 if operation in ("deploy", "rollback", "prepare-tls") else 150)
    try:
        if operation == "inventory":
            report.update(complete=True, read_only=True, inventory=inventory(runner))
        elif operation == "prepare":
            report.update(prepare(runner, arguments[2]))
        elif operation == "prepare-tls":
            report.update(prepare_tls(runner, arguments[2]))
        elif operation == "probe":
            report.update(probe_only(runner, arguments[2]))
        elif operation == "deploy":
            report.update(deploy(runner, arguments[2]))
        elif operation == "rollback":
            report.update(restore(runner))
        else:
            report.update(health(runner))
    except OperationError as error:
        report["errors"].append(str(error))
        if isinstance(error, ProbeError):
            report["probe_checks"] = error.checks
            report["certificate_requested"] = False
    except Exception as error:
        report["errors"].append("community_operation:" + type(error).__name__)
    # 切换失败后保留独立 rollback 入口与完整状态；不在错误处理里隐藏或反复重试写操作。
    if operation == "deploy" and not report["complete"]:
        report["rollback_available"] = PENDING.exists() or CURRENT.exists()
        report["rollback_operation"] = "rollback"
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report["complete"] else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
