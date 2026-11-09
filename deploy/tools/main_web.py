"""主站 Web 窄发布：独立只读规格盘点，以及显式授权的单服务/两处入口事务。"""

import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


WEB = "parallellines-web-1"
GATEWAY = "parallellines-nginx-1"
PROJECT = "parallellines"
NETWORK = "parallellines_default"
MAIN_CONFIG = Path("/opt/parallellines/deploy/nginx/default.conf")
MAX_OUTPUT = 1024 * 1024
APP = Path("/opt/parallellines-tools")
OPS = APP / "ops"
STATE = OPS / "main-web"
PENDING = STATE / "pending.json"
CURRENT = STATE / "current.json"
REDIRECTS = STATE / "redirects.json"
MAIN = Path("/opt/parallellines")
BASE_FILES = (MAIN / "docker-compose.yml", MAIN / "deploy/docker-compose.migration.yml")
REPOSITORY = "https://github.com/ixiaoyy/ParallelLines"


class MainWebError(Exception):
    """稳定错误码，不回显环境、配置正文或命令的原始错误输出。"""


def command(label, arguments, timeout=12, accepted=(0,)):
    """执行固定 argv 并限定时间/结果；不使用 shell，不读取 .env。"""
    try:
        result = subprocess.run(arguments, capture_output=True, text=True, check=False, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise MainWebError(label + ":timeout") from None
    except OSError as error:
        raise MainWebError(label + ":" + type(error).__name__) from None
    if result.returncode not in accepted:
        raise MainWebError(label + ":exit_" + str(result.returncode))
    if len(result.stdout) + len(result.stderr) > MAX_OUTPUT:
        raise MainWebError(label + ":output_limit")
    return result


def inspect_fields(label, fields, optional=False):
    """读取白名单字段组；仅定位不兼容字段名，不回显 Docker 原始错误。"""
    template = "{" + ",".join(json.dumps(key) + ":{{json " + value + "}}" for key, value in fields.items()) + "}"
    result = command(label, ["docker", "inspect", "--format", template, WEB], accepted=(0, 1) if optional else (0,))
    if result.returncode == 0:
        return json.loads(result.stdout), []
    values, unavailable = {}, []
    for name, expression in fields.items():
        single = command("main_web_field_" + name, ["docker", "inspect", "--format", "{{json " + expression + "}}", WEB], accepted=(0, 1))
        if single.returncode:
            unavailable.append(name)
        else:
            values[name] = json.loads(single.stdout)
    return values, unavailable


def web_metadata(require_complete=True, require_running=True):
    """读取 Web 公共规格白名单，不请求 Config.Env、完整 labels 或完整 inspect。"""
    basic = {
        "id": ".Id", "image_id": ".Image", "image": ".Config.Image", "running": ".State.Running",
        "project": '(index .Config.Labels "com.docker.compose.project")',
        "service": '(index .Config.Labels "com.docker.compose.service")',
    }
    value, _ = inspect_fields("main_web_identity", basic)
    fields = {
        "working_directory": '(index .Config.Labels "com.docker.compose.project.working_dir")',
        "compose_files": '(index .Config.Labels "com.docker.compose.project.config_files")',
        "container_number": '(index .Config.Labels "com.docker.compose.container-number")',
        "entrypoint": ".Config.Entrypoint", "command": ".Config.Cmd", "user": ".Config.User",
        "workdir": ".Config.WorkingDir", "exposed_ports": ".Config.ExposedPorts", "healthcheck": ".Config.Healthcheck",
        "mounts": ".Mounts", "restart": ".HostConfig.RestartPolicy", "port_bindings": ".HostConfig.PortBindings",
        "read_only": ".HostConfig.ReadonlyRootfs", "privileged": ".HostConfig.Privileged",
        "network_mode": ".HostConfig.NetworkMode", "memory": ".HostConfig.Memory", "nano_cpus": ".HostConfig.NanoCpus",
        "cpu_shares": ".HostConfig.CpuShares", "pids_limit": ".HostConfig.PidsLimit", "init": ".HostConfig.Init",
        "cap_add": ".HostConfig.CapAdd", "cap_drop": ".HostConfig.CapDrop", "security_opt": ".HostConfig.SecurityOpt",
    }
    value["unavailable_fields"] = []
    entries = list(fields.items())
    for start in range(0, len(entries), 6):
        group, unavailable = inspect_fields("main_web_spec_group_" + str(start // 6), dict(entries[start:start + 6]), optional=True)
        value.update(group)
        value["unavailable_fields"].extend(unavailable)
    networks = command("main_web_networks", ["docker", "inspect", "--format",
                       "{{range $name, $network := .NetworkSettings.Networks}}{{$name}} {{end}}", WEB]).stdout
    value["networks"] = sorted(networks.split())
    if (value.get("project") != PROJECT or value.get("service") != "web"
            or (require_running and value.get("running") is not True)):
        raise MainWebError("main_web_not_running_in_expected_project")
    if not re.fullmatch(r"[0-9a-f]{64}", value.get("id", "")):
        raise MainWebError("main_web_identifier_invalid")
    # 只输出已知静态 Nginx 命令；若被他人改为未知命令，不回显可能夹带的参数。
    if (("entrypoint" in value and value["entrypoint"] != ["/docker-entrypoint.sh"])
            or ("command" in value and value["command"] != ["nginx", "-g", "daemon off;"])):
        raise MainWebError("main_web_command_not_approved")
    check = value.get("healthcheck") or {}
    if "healthcheck" in value and check.get("Test") != ["CMD-SHELL", "wget -qO- http://127.0.0.1/ >/dev/null || exit 1"]:
        raise MainWebError("main_web_healthcheck_not_approved")
    if require_complete and value["unavailable_fields"]:
        raise MainWebError("main_web_spec_fields_unavailable:" + ",".join(value["unavailable_fields"]))
    return value


def gateway_metadata():
    """核固定 gateway 的公开身份、只读配置 bind 和宿主/容器的同一 inode。"""
    template = ('{"id":{{json .Id}},"running":{{json .State.Running}},"mounts":{{json .Mounts}},'
                '"networks":"{{range $name, $network := .NetworkSettings.Networks}}{{$name}} {{end}}"}')
    item = json.loads(command("main_gateway_metadata", ["docker", "inspect", "--format", template, GATEWAY]).stdout)
    if item.get("running") is not True or NETWORK not in item.get("networks", "").split():
        raise MainWebError("main_gateway_not_in_approved_context")
    mount = [value for value in item["mounts"] if value.get("Type") == "bind" and value.get("Source") == str(MAIN_CONFIG)
             and value.get("Destination") == "/etc/nginx/conf.d/default.conf" and value.get("RW") is False]
    if len(mount) != 1 or MAIN_CONFIG.is_symlink() or not MAIN_CONFIG.is_file():
        raise MainWebError("main_gateway_configuration_bind_changed")
    identity = MAIN_CONFIG.stat()
    inode = command("main_gateway_inode", ["docker", "exec", GATEWAY, "stat", "-c", "%d:%i", "/etc/nginx/conf.d/default.conf"]).stdout.strip()
    if inode != str(identity.st_dev) + ":" + str(identity.st_ino):
        raise MainWebError("main_gateway_inode_does_not_match_host")
    return {"id": item["id"], "config_identity": {"device": identity.st_dev, "inode": identity.st_ino},
            "configuration_bind_read_only": True, "network": NETWORK}


def inventory():
    """只读现场规格，用于确定下一次显式 Web 发布的固定配置；不创建状态/目录。"""
    started = time.monotonic()
    web, gateway = web_metadata(require_complete=False), gateway_metadata()
    return {"operation": "main-web-inventory", "read_only": True, "complete": True,
            "web": web, "gateway": gateway, "spec_complete": not web["unavailable_fields"],
            "elapsed_seconds": round(time.monotonic() - started, 3)}


def owned(path):
    """状态和备份只允许位于工具部署目录，拒绝任何路径级符号链接。"""
    path = Path(path)
    if APP not in path.parents and path != APP:
        raise MainWebError("main_web_path_outside_owned_directory")
    for part in (path, *path.parents):
        if part == APP or APP in part.parents:
            if part.is_symlink():
                raise MainWebError("main_web_owned_path_symlink")
    return path


def directory(path):
    """创建本任务私有目录，已有目录必须仍由当前用户独占写入。"""
    path = owned(path)
    path.mkdir(mode=0o750, parents=True, exist_ok=True)
    for part in (path, *path.parents):
        if part == APP or APP in part.parents:
            stat = part.stat()
            if not part.is_dir() or stat.st_uid != os.geteuid() or stat.st_mode & 0o022:
                raise MainWebError("main_web_directory_not_exclusively_owned")
    return path


def atomic(path, data):
    """原子保存本任务文件；Nginx 的同 inode 写入由独立前像函数处理。"""
    path = owned(path)
    temporary = path.with_name(path.name + ".new-" + secrets.token_hex(4))
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def save(path, value):
    """保存有限的本任务事务元数据，不把配置或脚本正文放入共享输出。"""
    atomic(path, (json.dumps(value, ensure_ascii=True, indent=2) + "\n").encode())


def read(path):
    """仅读本工具已有的小型记录；缺失为 None，损坏不降级为成功。"""
    path = owned(path)
    if not path.exists():
        return None
    if not path.is_file() or path.stat().st_size > 256 * 1024:
        raise MainWebError("main_web_state_invalid")
    return json.loads(path.read_text(encoding="utf-8"))


def modules():
    """只在写操作加载随受审提交携带的公开模块，盘点入口保持独立。"""
    import deploy_artifacts
    import health
    import managed_config
    import tls
    return deploy_artifacts, health, managed_config, tls


def anchor():
    """使用已完成工具事务的完整 gateway 锚点，不恢复日志中被屏蔽的 ID。"""
    current = read(OPS / "current.json")
    if current is None or current.get("source") != "https://github.com/ixiaoyy/parallel-lines-tools":
        raise MainWebError("installed_tools_transaction_anchor_missing")
    attempt = owned(current["attempt"])
    transaction = read(attempt / "transaction.json")
    if transaction is None or transaction.get("status") != "committed" or transaction.get("attempt") != str(attempt):
        raise MainWebError("installed_tools_transaction_not_committed")
    gateway = gateway_metadata()
    if gateway["id"] != transaction.get("gateway_id") or gateway["config_identity"] != transaction.get("config_identity"):
        raise MainWebError("main_gateway_changed_since_tools_transaction")
    return gateway, attempt


def guard(gateway):
    """每次突变和 reload 前复核原 gateway、同一物理配置 bind，不接管外部实例。"""
    if gateway_metadata() != gateway:
        raise MainWebError("main_gateway_changed_realign_transaction")


def compose(override=None):
    """只消费现有主站 Compose，正常解析其配置但不读取/输出任何环境值。"""
    arguments = ["docker", "compose", "--project-name", PROJECT, "--project-directory", str(MAIN)]
    for path in BASE_FILES:
        if path.is_symlink() or not path.is_file():
            raise MainWebError("main_compose_source_not_regular")
        arguments += ["--file", str(path)]
    if override is not None:
        arguments += ["--file", str(owned(override))]
    return arguments


def compose_hash(override=None):
    """只取公开服务摘要，不展开可能含凭据的 Compose 配置。"""
    output = command("main_web_compose_hash", compose(override) + ["config", "--hash", "web"]).stdout.strip()
    match = re.fullmatch(r"(?:web\s+)?([0-9a-f]{64})", output)
    if match is None:
        raise MainWebError("main_web_compose_hash_invalid")
    return match.group(1)


def running_hash():
    """读取单个已知 Compose hash label，与原生 Compose 的公开摘要比较。"""
    output = command("main_web_running_hash", ["docker", "inspect", "--format",
                     '{{index .Config.Labels "com.docker.compose.config-hash"}}', WEB]).stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{64}", output):
        raise MainWebError("main_web_running_hash_invalid")
    return output


def approved_web(value):
    """本次现场已核规格；不重造它，不新增端口、挂载、资源限额或环境设置。"""
    expected = {"working_directory": str(MAIN), "compose_files": ",".join(map(str, BASE_FILES)),
                "container_number": "1", "image": "parallellines-web:latest", "user": "", "workdir": "/",
                "exposed_ports": {"80/tcp": {}}, "mounts": [], "port_bindings": {}, "read_only": False,
                "privileged": False, "network_mode": NETWORK, "memory": 0, "nano_cpus": 0, "cpu_shares": 0,
                "pids_limit": None, "init": None, "cap_add": None, "cap_drop": None, "security_opt": None,
                "networks": [NETWORK], "restart": {"Name": "unless-stopped", "MaximumRetryCount": 0}}
    if any(value.get(key) != item for key, item in expected.items()):
        raise MainWebError("main_web_public_spec_drift")
    if compose_hash() != running_hash():
        raise MainWebError("main_web_compose_or_environment_drift")


class ReleaseRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        """仅允许固定 GitHub 公共资产的正常 HTTPS 跳转，不附加身份或 Cookie。"""
        parsed = urllib.parse.urlsplit(newurl)
        if parsed.scheme != "https" or parsed.hostname not in ("github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com") or parsed.username:
            raise MainWebError("main_web_release_redirect_outside_github")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


@contextlib.contextmanager
def deadline(seconds):
    """已确认 Linux 上限定完整下载阶段；镜像 900 秒，元数据使用较短总界。"""
    def expired(_number, _frame):
        raise MainWebError("main_web_download_deadline")
    previous = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def download(url, target, limit, expected=None, seconds=60):
    """公开资产限时限量流式下载，校验通过后才允许解析；不自动重试。"""
    digest, size = hashlib.sha256(), 0
    import github_assets
    opener = urllib.request.build_opener(ReleaseRedirect())
    try:
        with deadline(seconds), opener.open(github_assets.request(url, opener), timeout=30) as response:
            if response.status != 200:
                raise MainWebError("main_web_download_status:" + target.name)
            with owned(target).open("xb") as output:
                while True:
                    chunk = response.read(128 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > limit:
                        raise MainWebError("main_web_download_size:" + target.name)
                    output.write(chunk)
                    digest.update(chunk)
    except urllib.error.HTTPError as error:
        raise MainWebError("main_web_download_http_" + str(error.code) + ":" + target.name) from None
    except (OSError, urllib.error.URLError) as error:
        raise MainWebError("main_web_download_" + type(error).__name__ + ":" + target.name) from None
    if expected is not None and digest.hexdigest() != expected:
        raise MainWebError("main_web_download_integrity:" + target.name)
    return size


def image_id(reference):
    """仅读 native image ID，用于同一服务器上的恢复，不与跨存储 config digest 混比。"""
    value = command("main_web_image_identity", ["docker", "image", "inspect", "--format", "{{.Id}}", reference]).stdout.strip()
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
        raise MainWebError("main_web_image_identity_invalid")
    return value


def up(override=None):
    """只重建现有项目 web 服务，既不启动依赖，也不拉镜像或执行构建。"""
    command("main_web_compose_up", compose(override) + ["up", "--detach", "--no-deps", "--no-build",
            "--pull", "never", "--force-recreate", "web"], timeout=120)


def wait_web(expected):
    """最多 60 次两秒等待，验证同一目标镜像及现有健康检查实际转为 healthy。"""
    for attempt in range(60):
        value = web_metadata()
        if value["image_id"] != expected:
            raise MainWebError("main_web_running_image_mismatch")
        status = command("main_web_health", ["docker", "inspect", "--format", "{{json .State.Health.Status}}", WEB]).stdout.strip()
        if status == '"healthy"':
            return value
        if status != '"starting"':
            raise MainWebError("main_web_health_failed")
        if attempt < 59:
            time.sleep(2)
    raise MainWebError("main_web_health_deadline")


def write_config(expected, replacement, gateway):
    """同 inode 原位更新；不先 truncate 原像，失败保留事务和完整备份。"""
    guard(gateway)
    descriptor = os.open(MAIN_CONFIG, os.O_RDWR | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "r+b") as handle:
        identity = os.fstat(handle.fileno())
        if handle.read() != expected or {"device": identity.st_dev, "inode": identity.st_ino} != gateway["config_identity"]:
            raise MainWebError("main_web_configuration_preimage_changed")
        handle.seek(0)
        handle.write(replacement)
        handle.flush()
        handle.truncate(len(replacement))
        os.fsync(handle.fileno())
    guard(gateway)
    actual = command("main_web_bound_configuration", ["docker", "exec", gateway["id"], "sha256sum", "/etc/nginx/conf.d/default.conf"]).stdout.split()[0]
    if actual != hashlib.sha256(replacement).hexdigest():
        raise MainWebError("main_web_bound_configuration_mismatch")


def lease(state):
    """恢复绑定完整 attempt，旧补偿不能清除同提交的新部署。"""
    active = read(PENDING) or read(CURRENT)
    if active is None or active.get("attempt") != state["attempt"]:
        raise MainWebError("main_web_attempt_replaced_realign_transaction")


def same_public_spec(actual, expected):
    """恢复只容许运行/停止状态变化，其余公开规格及完整 CID 都必须保持。"""
    return ({key: value for key, value in actual.items() if key != "running"}
            == {key: value for key, value in expected.items() if key != "running"})


def new_web_owned(value, state):
    """认领新实例前核本事务独有 override、目标镜像、完整公共规格和 Compose hash。"""
    expected = {**state["before_web"], "id": value["id"], "image_id": state["image_id"],
                "image": "parallellines-web:" + state["revision"],
                "compose_files": state["before_web"]["compose_files"] + "," + state["override"]}
    return (value["id"] != state["before_web"]["id"] and same_public_spec(value, expected)
            and running_hash() == state["after_compose_hash"])


def recovery_web(state):
    """只在本次 recreate 窗口接受缺失；inspect/权限错误绝不当作容器不存在。"""
    identifiers = command("main_web_recovery_presence", ["docker", "ps", "--all", "--no-trunc", "--filter",
                          "name=^/" + WEB + "$", "--format", "{{.ID}}" ]).stdout.split()
    if not identifiers:
        pending = read(PENDING)
        if (state.get("status") != "switching_web" or state.get("image_id") is None or pending is None
                or pending.get("attempt") != state["attempt"] or pending.get("status") != "switching_web"):
            raise MainWebError("main_web_missing_outside_owned_switch")
        return None
    if len(identifiers) != 1 or not re.fullmatch(r"[0-9a-f]{64}", identifiers[0]):
        raise MainWebError("main_web_recovery_presence_not_unique")
    value = web_metadata(require_running=False)
    if value["id"] != identifiers[0]:
        raise MainWebError("main_web_changed_during_recovery_read")
    if same_public_spec(value, state["before_web"]):
        if running_hash() != state["before_compose_hash"]:
            raise MainWebError("main_web_old_spec_changed_before_restore")
        if value["running"] is not True and state.get("status") == "prepared":
            raise MainWebError("main_web_old_stopped_before_owned_switch")
        return value
    if state.get("restored_web") is not None and same_public_spec(value, state["restored_web"]):
        if running_hash() != state["before_compose_hash"]:
            raise MainWebError("main_web_restored_spec_changed")
        return value
    after = state.get("after_web")
    if after is not None:
        if not same_public_spec(value, after) or not new_web_owned(value, state):
            raise MainWebError("main_web_after_instance_or_spec_changed")
        return value
    pending = read(PENDING)
    if (state.get("status") != "switching_web" or pending is None or pending.get("attempt") != state["attempt"]
            or pending.get("status") != "switching_web" or not new_web_owned(value, state)):
        raise MainWebError("main_web_container_changed_outside_attempt")
    return value


def install_sources(attempt, tool_attempt):
    """保留原工具消费者，安装受审兼容代码；旧 deploy 仅改已授权的一个调用点。"""
    bundle = globals().get("OPS_SOURCES")
    required = {"main_web.py", "deploy_artifacts.py", "managed_config.py", "tls.py", "health.py", "github_assets.py"}
    if not isinstance(bundle, dict) or set(bundle) != required:
        raise MainWebError("main_web_reviewed_source_bundle_invalid")
    source_dir = directory(attempt / "ops-before")
    result = {}
    for name in ("tls.py", "managed_config.py", "deploy.py"):
        current = owned(OPS / name).read_bytes()
        original = owned(tool_attempt / "ops" / name).read_bytes()
        if current != original:
            raise MainWebError("main_web_installed_consumer_changed:" + name)
        atomic(source_dir / name, current)
        if name == "deploy.py":
            before = b"owned_delta_allowed(source, head, fragment)"
            after = b"owned_delta_allowed(source, head, fragment, tls.main_web_redirect_record())"
            if current.count(after) == 1 and before not in current:
                replacement = current
            elif current.count(before) == 1 and after not in current:
                replacement = current.replace(before, after, 1)
            else:
                raise MainWebError("main_web_deploy_consumer_patch_preimage")
        else:
            replacement = bundle[name].encode("utf-8")
        result[name] = {"before": hashlib.sha256(current).hexdigest(), "after": hashlib.sha256(replacement).hexdigest()}
        atomic(attempt / (name + ".after"), replacement)
    for name in ("main_web.py", "deploy_artifacts.py", "github_assets.py"):
        atomic(OPS / name, bundle[name].encode("utf-8"))
    return result


def restore(state, report):
    """只恢复原 Web 镜像、两处 exact 与本事务消费者；未知变化保留 pending 停止。"""
    _artifacts, health, managed, _tls = modules()
    lease(state)
    guard(state["gateway"])
    attempt = owned(state["attempt"])
    before = owned(attempt / "gateway.before").read_bytes()
    current = MAIN_CONFIG.read_bytes()
    outside, fragment = managed.split(current)
    before_outside, _ = managed.split(before)
    after_outside = managed.replace_tool_entries(before_outside)
    saved_fragment = owned(OPS / "managed-vhost.conf").read_bytes()
    if outside not in (before_outside, after_outside) or fragment != (saved_fragment or None):
        raise MainWebError("main_web_configuration_changed_outside_two_exact_blocks")
    live = recovery_web(state)
    old = state["before_web"]
    needs_start = live is None or live["image_id"] != old["image_id"] or live.get("running") is not True
    if compose_hash() != state["before_compose_hash"]:
        raise MainWebError("main_web_compose_changed_before_restore")
    latest = image_id("parallellines-web:latest")
    if latest not in (old["image_id"], state.get("image_id")):
        raise MainWebError("main_web_latest_changed_outside_attempt")
    for name, hashes in state["consumer_hashes"].items():
        if hashlib.sha256(owned(OPS / name).read_bytes()).hexdigest() not in hashes.values():
            raise MainWebError("main_web_consumer_changed_outside_attempt:" + name)
    if image_id(old["image_id"]) != old["image_id"]:
        raise MainWebError("main_web_previous_image_unavailable")
    guard(state["gateway"])
    state["status"] = "restoring"
    save(PENDING, state)
    save(attempt / "transaction.json", state)
    command("main_web_restore_latest", ["docker", "image", "tag", old["image_id"], "parallellines-web:latest"])
    if needs_start:
        up()
        restored = web_metadata(require_running=False)
        if not same_public_spec(restored, {**old, "id": restored["id"]}) or running_hash() != state["before_compose_hash"]:
            raise MainWebError("main_web_restored_public_spec_mismatch")
        state["restored_web"] = restored
        save(PENDING, state)
        save(attempt / "transaction.json", state)
        wait_web(old["image_id"])
    if outside == after_outside:
        write_config(current, managed.replace_tool_entries(current, forward=False), state["gateway"])
    if state["before_redirects"] is None:
        if REDIRECTS.exists():
            owned(REDIRECTS).unlink()
    else:
        save(REDIRECTS, state["before_redirects"])
    for name in state["consumer_hashes"]:
        atomic(OPS / name, owned(attempt / "ops-before" / name).read_bytes())
    guard(state["gateway"])
    command("main_web_restore_nginx_test", ["docker", "exec", state["gateway"]["id"], "nginx", "-t"])
    guard(state["gateway"])
    command("main_web_restore_nginx_reload", ["docker", "exec", state["gateway"]["id"], "nginx", "-s", "reload"])
    checked = health.run_health()
    if not checked["healthy"]:
        raise MainWebError("main_web_restore_independent_health_failed")
    lease(state)
    if state["before_current"] is None:
        if CURRENT.exists():
            owned(CURRENT).unlink()
    else:
        save(CURRENT, state["before_current"])
    state["status"] = "rolled_back"
    save(attempt / "transaction.json", state)
    if PENDING.exists():
        if read(PENDING).get("attempt") != state["attempt"]:
            raise MainWebError("main_web_pending_replaced_before_restore_finish")
        owned(PENDING).unlink()
    report["recovery"] = {"complete": True, "only_web_and_two_exact_blocks": True, "gateway_not_recreated": True}


def deploy(tag, receipt_sha, run_id, expected, report):
    """验证同源 schema2 镜像，备份后只更新 web 及工具根入口；失败使用独立恢复事务。"""
    if (not re.fullmatch(r"main-web-[0-9a-f]{40}", tag) or not re.fullmatch(r"[0-9a-f]{64}", receipt_sha)
            or not re.fullmatch(r"[0-9]{1,20}", run_id) or not re.fullmatch(r"[0-9a-f]{64}", expected)):
        raise MainWebError("invalid_main_web_deploy_inputs")
    artifacts, health, managed, tls = modules()
    sha = tag[9:]
    gateway, tool_attempt = anchor()
    before = MAIN_CONFIG.read_bytes()
    if hashlib.sha256(before).hexdigest() != expected or not tls.configuration_may_reload():
        raise MainWebError("main_web_trusted_configuration_preimage_mismatch")
    after = managed.replace_tool_entries(before)
    web = web_metadata()
    approved_web(web)
    if image_id("parallellines-web:latest") != web["image_id"]:
        raise MainWebError("main_web_latest_does_not_match_running_image")
    directory(STATE)
    with tls.tls_lock():
        if PENDING.exists():
            raise MainWebError("unfinished_main_web_deployment_requires_rollback")
        if read(OPS / "pending.json") is not None:
            raise MainWebError("unfinished_tools_deployment_requires_rollback")
        attempt = directory(APP / "main-web" / "releases" / sha / secrets.token_hex(8))
        base = REPOSITORY + "/releases/download/" + tag + "/"
        receipt_file = attempt / "web-image.json"
        download(base + receipt_file.name, receipt_file, 256 * 1024, receipt_sha)
        receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
        identity = artifacts.receipt_identity(receipt, sha, run_id)
        if not re.fullmatch(r"[0-9a-f]{64}", str(receipt.get("archive_sha256", ""))):
            raise MainWebError("main_web_archive_digest_invalid")
        for name in (artifacts.archive_name(sha) + ".sha256", "parallellines-web-" + sha + ".image-id", "parallellines-web-" + sha + ".image-config-digest"):
            download(base + name, attempt / name, 1024)
        archive = attempt / artifacts.archive_name(sha)
        report["archive_bytes"] = download(base + archive.name, archive, 1024 * 1024 * 1024,
                                           receipt["archive_sha256"], seconds=900)
        artifacts.verify_web(attempt, sha, run_id)
        report["schema_2_archive_verified"] = True
        guard(gateway)
        if MAIN_CONFIG.read_bytes() != before or web_metadata() != web:
            raise MainWebError("main_web_state_changed_during_download")
        approved_web(web)
        override = attempt / "image.override.json"
        save(override, {"services": {"web": {"image": "parallellines-web:" + sha}}})
        atomic(attempt / "gateway.before", before)
        consumers = install_sources(attempt, tool_attempt)
        state = {"schema": 1, "operation": "main-web", "revision": sha, "attempt": str(attempt), "gateway": gateway,
                 "before_web": web, "before_compose_hash": compose_hash(), "before_current": read(CURRENT),
                 "before_redirects": read(REDIRECTS), "consumer_hashes": consumers,
                 "override": str(override), "after_compose_hash": compose_hash(override),
                 "receipt_sha256": receipt_sha, "image_id": None, "status": "prepared"}
        save(attempt / "transaction.json", state)
        save(PENDING, state)
        try:
            command("main_web_load", ["docker", "image", "load", "--input", str(archive)], timeout=180)
            state["image_id"] = image_id("parallellines-web:" + sha)
            save(PENDING, state)
            save(attempt / "transaction.json", state)
            loaded = artifacts.verify_loaded(sha, identity["image_config_digest"], identity)
            if loaded["native_image_id"] != state["image_id"]:
                raise MainWebError("main_web_loaded_native_identity_changed")
            report["native_loaded_aliases_verified"] = True
            guard(gateway)
            if web_metadata() != web or MAIN_CONFIG.read_bytes() != before:
                raise MainWebError("main_web_state_changed_before_switch")
            for name in consumers:
                atomic(OPS / name, owned(attempt / (name + ".after")).read_bytes())
            old_outside, _ = managed.split(before)
            new_outside, _ = managed.split(after)
            record = {"schema": 1, "operation": "main-web-redirects", "revision": sha, "attempt": str(attempt),
                      "before_outside_sha256": hashlib.sha256(old_outside).hexdigest(),
                      "after_outside_sha256": hashlib.sha256(new_outside).hexdigest()}
            save(REDIRECTS, record)
            state["status"] = "switching_web"
            save(PENDING, state)
            save(attempt / "transaction.json", state)
            up(override)
            switched = web_metadata(require_running=False)
            if not new_web_owned(switched, state):
                raise MainWebError("main_web_new_instance_not_owned")
            state["after_web"] = switched
            save(PENDING, state)
            save(attempt / "transaction.json", state)
            running = wait_web(state["image_id"])
            for key in set(web) - {"id", "image_id", "image", "compose_files"}:
                if running.get(key) != web[key]:
                    raise MainWebError("main_web_public_runtime_changed:" + key)
            if running_hash() != compose_hash(override):
                raise MainWebError("main_web_new_compose_hash_mismatch")
            guard(gateway)
            write_config(before, after, gateway)
            command("main_web_nginx_test", ["docker", "exec", gateway["id"], "nginx", "-t"])
            guard(gateway)
            command("main_web_nginx_reload", ["docker", "exec", gateway["id"], "nginx", "-s", "reload"])
            checked = health.run_health()
            report["health"] = checked
            if not checked["healthy"]:
                raise MainWebError("main_web_independent_health_failed")
            command("main_web_installed_renewal_policy", ["/usr/bin/python3", "-B", "-c",
                    "import sys;sys.path.insert(0,'/opt/parallellines-tools/ops');import tls;raise SystemExit(0 if tls.configuration_may_reload() else 2)"])
            guard(gateway)
            lease(state)
            state["status"] = "committed"
            save(attempt / "transaction.json", state)
            save(CURRENT, state)
            owned(PENDING).unlink()
            report.update(complete=True, revision=sha, only_web_recreated=True, gateway_not_recreated=True,
                          two_exact_blocks_updated=True, installed_renewal_policy_verified=True)
        except Exception:
            try:
                restore(state, report)
            except Exception as error:
                report["recovery"] = {"complete": False, "error": str(error) if isinstance(error, MainWebError) else type(error).__name__,
                                      "operation": "rollback-main-web", "pending_preserved": True}
            raise


def rollback(sha, report):
    """按本工具已记录的完整 attempt 恢复，不读取任意镜像或复原整个主站工作树。"""
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise MainWebError("main_web_rollback_revision_invalid")
    _artifacts, _health, _managed, tls = modules()
    with tls.tls_lock():
        state = read(PENDING) or read(CURRENT)
        if state is None or state.get("revision") != sha or state.get("operation") != "main-web":
            raise MainWebError("main_web_rollback_not_current_attempt")
        restore(state, report)
        report["complete"] = True


def main(arguments):
    """盘点独立只读；写操作必须传完整显式身份，且受同一部署并发组和 TLS 锁保护。"""
    report = {"operation": arguments[0] if arguments else "rejected", "complete": False, "errors": []}
    try:
        if arguments == ["main-web-inventory"]:
            report = inventory()
        elif len(arguments) == 5 and arguments[0] == "deploy-main-web":
            deploy(*arguments[1:], report)
        elif len(arguments) == 2 and arguments[0] == "rollback-main-web":
            rollback(arguments[1], report)
        else:
            raise MainWebError("unsupported_main_web_operation")
    except MainWebError as error:
        report["errors"].append(str(error))
    except (OSError, ValueError, KeyError, TypeError) as error:
        report["errors"].append("main_web:" + type(error).__name__)
    except Exception as error:
        report["errors"].append("main_web:" + type(error).__name__)
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report["complete"] else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
