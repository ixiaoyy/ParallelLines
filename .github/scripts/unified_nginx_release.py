"""统一登录 Nginx 同 inode 事务；复用真实消费者所有权，仅由受控 orchestrator 激活/恢复。"""

from __future__ import annotations

import ast
import difflib
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys
import time
from collections.abc import Callable


TOOLS = Path("/opt/parallellines-tools/ops")
MODULES = (
    "tls.py", "managed_config.py", "release_contract.py", "main_web.py",
    "deploy.py", "rollback.py", "health.py",
)
SOURCE_LIMIT = 256 * 1024
FUNCTION_LIMIT = 128
BASE_REVISION = "93ca819f20f760b142cab9a320110879ff8179df"
APP_REVISION = "a2cfeddeec01ca0d5def4b3308103f3d85cc3861"
MAIN = Path("/opt/parallellines")
TRANSACTION = MAIN / ".deployment/unified-login" / APP_REVISION / "nginx"
ARTIFACTS = Path("/data/deployment/parallellines-unified") / APP_REVISION
MAIN_CONFIG = MAIN / "deploy/nginx/default.conf"
FORUM_CONFIG = MAIN / "deploy/nginx/forum.conf"
COMMUNITY = MAIN / ".deployment/community" / BASE_REVISION
COMMUNITY_PROGRAM = COMMUNITY / "renew-community.py"
COMMUNITY_CURRENT = COMMUNITY / "current.json"
COMMUNITY_CRON = Path("/etc/cron.d/parallellines-community-renew")
FORUM_REDIRECTS = MAIN / "deploy/nginx/forum-main-redirects.conf"
BASE_MAIN_SHA = "39e83980ff071194e2e0711111bc4e09be28f1cd64c9197b4c13209623f308cf"
BASE_FORUM_SHA = "c04886b77ccd21381f12f8bb71696ea875ea5dd9d0dcef8c9c0cf8a26b1a2621"
MAIN_IDENTITY = {"device": 64769, "inode": 1049133}
FILE_LIMIT = 2 * 1024 * 1024
LABELS = ("main", "forum_host", "forum_layer", "community_program", "community_current")
SOURCE_CONTRACTS = {
    "tls.py": (
        "clean_main_configuration", "main_web_redirect_record", "configuration_may_reload",
        "context_preflight", "tls_lock",
    ),
    "managed_config.py": ("span", "split", "replace", "replace_tool_entries", "owned_delta_allowed"),
    "main_web.py": ("modules", "anchor", "guard", "install_sources", "restore", "deploy"),
    "deploy.py": (
        "gateway_binding", "gateway_guard", "known_configuration", "inplace_configuration",
        "assert_attempt_owner", "restore_state",
    ),
}
DIGEST_LITERAL = re.compile(r"(?<![A-Za-z0-9])[0-9a-fA-F]{32,128}(?![A-Za-z0-9])")
SENSITIVE_NAME = re.compile(
    r"secret|password|(?:access|refresh|id)[_-]?token|authorization|credential|private[_-]?key",
    re.IGNORECASE,
)


class OperationError(Exception):
    """仅携带稳定错误标识；不输出配置、源码正文、默认参数值或异常上下文。"""


class Commands:
    """固定参数执行器；每次命令和整个事务均有上限，不回显 stderr、环境或配置正文。"""

    def __init__(self, seconds: int = 150):
        self.deadline = time.monotonic() + seconds

    def run(self, label: str, arguments: list[str], *, timeout: int = 15, data: bytes | None = None) -> bytes:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise OperationError("nginx_transaction_deadline")
        try:
            result = subprocess.run(
                arguments, input=data, capture_output=True, timeout=min(timeout, remaining), check=False,
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "PYTHONDONTWRITEBYTECODE": "1"},
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise OperationError(label + ":" + type(error).__name__) from None
        if len(result.stdout) + len(result.stderr) > FILE_LIMIT:
            raise OperationError(label + ":output_limit")
        if result.returncode:
            raise OperationError(label + ":exit_" + str(result.returncode))
        return result.stdout


def sha(value: bytes) -> str:
    """只用于本事务的精确前后像与并发守卫；不向回执输出先前遮蔽的摘要。"""
    return hashlib.sha256(value).hexdigest()


def regular(path: Path) -> bytes:
    """读取固定小型普通文件；不跟随叶子符号链接，不递归或读取私钥/环境文件。"""
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as stream:
        metadata = os.fstat(stream.fileno())
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > FILE_LIMIT:
            raise OperationError("nginx_file_not_regular_or_large")
        value = stream.read(FILE_LIMIT + 1)
        if len(value) > FILE_LIMIT:
            raise OperationError("nginx_file_grew_beyond_limit")
        return value


def identity(path: Path) -> dict:
    """记录普通文件 inode 和权限，更新和恢复均不得换对象或改权限。"""
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode):
        raise OperationError("nginx_file_not_regular")
    return {
        "device": metadata.st_dev, "inode": metadata.st_ino,
        "mode": stat.S_IMODE(metadata.st_mode), "uid": metadata.st_uid, "gid": metadata.st_gid,
    }


def transaction_path(value: str | Path) -> Path:
    """只接受本次固定事务目录，且所有已经存在的父级都不得为链接。"""
    path = Path(value)
    if path != TRANSACTION:
        raise OperationError("nginx_transaction_path_not_allowed")
    for part in (path, *path.parents):
        if part.is_symlink():
            raise OperationError("nginx_transaction_path_symlink")
    return path


def atomic(path: Path, value: bytes) -> None:
    """仅原子发布本任务私有快照/状态，不用于 bind 配置或既有消费者文件。"""
    if TRANSACTION not in path.parents or path.is_symlink():
        raise OperationError("nginx_snapshot_path_not_owned")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".new-" + secrets.token_hex(8))
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(value)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def save_state(state: dict) -> None:
    atomic(TRANSACTION / "state.json", (json.dumps(state, sort_keys=True, indent=2) + "\n").encode())


def read_state(value: str | Path) -> dict:
    transaction_path(value)
    state = json.loads(regular(TRANSACTION / "state.json"))
    if state.get("schema") != 1 or state.get("revision") != APP_REVISION:
        raise OperationError("nginx_transaction_not_owned")
    return state


def git(commands: Commands, *arguments: str) -> bytes:
    return commands.run("nginx_source_identity", [
        "git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-C", str(MAIN), *arguments,
    ])


def source_guard(commands: Commands, revisions: tuple[str, ...]) -> None:
    """源对齐只接受已审核事务两端和原 main 分支，拒绝接管第三方 Git 变化。"""
    if git(commands, "symbolic-ref", "--quiet", "HEAD").decode().strip() != "refs/heads/main":
        raise OperationError("nginx_source_branch_changed")
    if git(commands, "rev-parse", "HEAD").decode().strip() not in revisions:
        raise OperationError("nginx_source_revision_changed")


def tools_modules():
    """复用已经审阅的真实接口，不改工具源码/JSON锚点，也不增加 ownership 白名单。"""
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(TOOLS))
    result = []
    for name in ("tls", "managed_config", "main_web", "deploy"):
        owned_source(name + ".py")
        module = importlib.import_module(name)
        if Path(module.__file__) != TOOLS / (name + ".py"):
            raise OperationError("nginx_consumer_module_collision")
        result.append(module)
    tls, managed, main_web, deploy = result
    if Path(tls.MAIN_CONFIG) != MAIN_CONFIG or Path(deploy.MAIN_CONFIG) != MAIN_CONFIG:
        raise OperationError("nginx_consumer_configuration_path_changed")
    return tls, managed, main_web, deploy


def gateway(commands: Commands) -> dict:
    """只读固定网关身份、挂载、网络和宿主PID，不输出 Env 或完整 labels。"""
    template = (
        '{"id":{{json .Id}},"image":{{json .Image}},"running":{{json .State.Running}},'
        '"pid":{{json .State.Pid}},"mounts":{{json .Mounts}},'
        '"networks":"{{range $name,$network := .NetworkSettings.Networks}}{{$name}} {{end}}"}'
    )
    value = json.loads(commands.run("nginx_gateway", [
        "docker", "inspect", "--format", template, "parallellines-nginx-1",
    ]))
    if not re.fullmatch(r"[0-9a-f]{64}", value.get("id", "")) or value.get("running") is not True:
        raise OperationError("nginx_gateway_not_running")
    if not isinstance(value.get("pid"), int) or value["pid"] <= 1:
        raise OperationError("nginx_gateway_pid_invalid")
    value["networks"] = sorted(value["networks"].split())
    return value


def gateway_guard(commands: Commands, state: dict, deploy) -> None:
    """保持同容器、PID、镜像、全部挂载与网络；调用成熟 bind guard 复核同 inode。"""
    if gateway(commands) != state["gateway"]:
        raise OperationError("nginx_gateway_changed")
    deploy.gateway_binding(state["gateway"]["id"], MAIN_IDENTITY)


def forum_layer_path(commands: Commands, live: dict) -> Path:
    """现网论坛配置在容器层：通过已核PID的namespace路径原位写，拒绝未知新挂载。"""
    destination = "/etc/nginx/conf.d/forum.conf"
    for mount in live["mounts"]:
        target = mount.get("Destination", "").rstrip("/")
        if target and (destination == target or destination.startswith(target + "/")):
            raise OperationError("nginx_forum_layer_now_mounted_requires_review")
    path = Path("/proc") / str(live["pid"]) / "root/etc/nginx/conf.d/forum.conf"
    host_value = regular(path)
    container_value = commands.run("nginx_forum_layer_bytes", ["docker", "exec", live["id"], "cat", destination])
    observed = commands.run("nginx_forum_layer_inode", ["docker", "exec", live["id"], "stat", "-c", "%d:%i", destination]).decode().strip()
    metadata = identity(path)
    if host_value != container_value or observed != str(metadata["device"]) + ":" + str(metadata["inode"]):
        raise OperationError("nginx_forum_layer_namespace_mismatch")
    return path


def consumer_snapshot(tls, main_web) -> dict:
    """只钉本事务实际依赖的策略/工具锚点；不读取密钥，也不假造 Main Web 发布记录。"""
    paths = [TOOLS / name for name in ("tls.py", "managed_config.py", "main_web.py", "deploy.py")]
    paths += [TOOLS / "managed-vhost.conf", TOOLS / "current.json", TOOLS / "main-web/redirects.json"]
    files = {str(path): sha(regular(path)) if path.exists() else None for path in paths}
    anchor, attempt = main_web.anchor()
    return {"files": files, "main_web_anchor": anchor, "tool_attempt": str(attempt),
            "redirect_record": tls.main_web_redirect_record()}


def owner_guard(tls, main_web, state: dict) -> None:
    """同一工具策略与原 MainWeb bind 锚点必须继续接受现场；不手改其元数据。"""
    if consumer_snapshot(tls, main_web) != state["consumers"]:
        raise OperationError("nginx_consumer_changed")
    if not tls.configuration_may_reload():
        raise OperationError("nginx_existing_ownership_denied")
    tls.context_preflight()


def candidate(commands: Commands, value: str | Path, name: str, before: bytes) -> bytes:
    """候选必须来自本次固定产物根且逐字等于已授权应用 Git blob；仅允许已审增量插入。"""
    path = Path(value)
    if ARTIFACTS not in path.parents:
        raise OperationError("nginx_candidate_outside_release")
    for part in (path, *path.parents):
        if part.is_symlink():
            raise OperationError("nginx_candidate_symlink")
    content = regular(path)
    if content != git(commands, "show", APP_REVISION + ":" + name):
        raise OperationError("nginx_candidate_not_application_blob")
    if before != git(commands, "show", BASE_REVISION + ":" + name):
        raise OperationError("nginx_baseline_not_application_blob")
    changes = difflib.SequenceMatcher(None, before.splitlines(keepends=True), content.splitlines(keepends=True), autojunk=False)
    if any(kind not in ("equal", "insert") for kind, *_ in changes.get_opcodes()):
        raise OperationError("nginx_delta_not_insert_only")
    return content


def snapshots(state: dict, direction: str) -> dict[str, bytes]:
    """仅从本任务快照读取精确端点，读取时核内部摘要，防止恢复源漂移。"""
    result = {}
    for label in LABELS:
        value = regular(TRANSACTION / direction / label)
        if sha(value) != state["files"][label][direction]:
            raise OperationError("nginx_snapshot_changed:" + label)
        result[label] = value
    return result


def targets(commands: Commands, state: dict) -> dict[str, Path]:
    return {
        "main": MAIN_CONFIG, "forum_host": FORUM_CONFIG,
        "forum_layer": forum_layer_path(commands, state["gateway"]),
        "community_program": COMMUNITY_PROGRAM, "community_current": COMMUNITY_CURRENT,
    }


def known_transition(current: bytes, before: bytes, after: bytes) -> bool:
    """只认前缀顺序写入/截断形成的自有中间态；任意第三方字节都拒绝。"""
    if current in (before, after):
        return True
    if len(before) < len(current) <= len(after):
        return current == after[:len(current)]
    if len(current) != len(before):
        return False
    limit = min(len(before), len(after))
    first = next((index for index in range(limit) if current[index] != after[index]), limit)
    return current[first:] == before[first:]


def interrupted_write(state: dict, label: str, actual: bytes) -> bool:
    """根据持久写意图的真实起止字节识别半写，包含恢复自身再次中断的情况。"""
    intent = state.get("writing")
    if not intent or intent.get("label") != label:
        return False
    token = intent.get("token", "")
    if not isinstance(token, str) or not re.fullmatch(r"[0-9a-f]{16}", token):
        raise OperationError("nginx_write_intent_invalid")
    before = regular(TRANSACTION / "writes" / (token + ".before"))
    after = regular(TRANSACTION / "writes" / (token + ".after"))
    if sha(before) != intent.get("before") or sha(after) != intent.get("after"):
        raise OperationError("nginx_write_intent_snapshot_changed")
    return known_transition(actual, before, after)


def file_guard(commands: Commands, state: dict, *, recovery: bool = False) -> dict[str, Path]:
    """写前一次核全部受影响文件；恢复仅多认持久写意图所证明的单文件自有中间态。"""
    before, after = snapshots(state, "before"), snapshots(state, "after")
    paths = targets(commands, state)
    for label, path in paths.items():
        if identity(path) != state["files"][label]["identity"]:
            raise OperationError("nginx_file_identity_changed:" + label)
        actual = regular(path)
        accepted = actual in (before[label], after[label]) if recovery else actual == before[label]
        if accepted:
            continue
        if recovery and interrupted_write(state, label, actual):
            continue
        raise OperationError("nginx_file_changed_outside_transaction:" + label)
    if regular(COMMUNITY_CRON) != regular(TRANSACTION / "community-cron.before") or identity(COMMUNITY_CRON) != state["cron_identity"]:
        raise OperationError("nginx_community_cron_changed")
    redirects = commands.run("nginx_forum_redirects", ["docker", "exec", state["gateway"]["id"], "cat", "/etc/nginx/forum-main/redirects.conf"])
    if sha(redirects) != state["redirects_sha256"] or regular(FORUM_REDIRECTS) != redirects:
        raise OperationError("nginx_forum_redirects_changed")
    return paths


def endpoint_guard(commands: Commands, state: dict, direction: str) -> None:
    """真实测试/reload 前要求全部文件处于同一个完整端点，不能以混合前后像代替完成。"""
    paths = file_guard(commands, state, recovery=True)
    expected = snapshots(state, direction)
    if any(regular(path) != expected[label] for label, path in paths.items()):
        raise OperationError("nginx_transaction_endpoint_incomplete")


def inplace(path: Path, expected: bytes, replacement: bytes, expected_identity: dict) -> None:
    """只更新已核普通文件原 inode，保留权限和属主；绑定配置绝不用 rename 替换。"""
    descriptor = os.open(path, os.O_RDWR | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "r+b") as stream:
        opened = os.fstat(stream.fileno())
        if identity(path) != expected_identity or (opened.st_dev, opened.st_ino) != (expected_identity["device"], expected_identity["inode"]) or stream.read() != expected:
            raise OperationError("nginx_inplace_preimage_changed")
        stream.seek(0)
        stream.write(replacement)
        stream.flush()
        os.fsync(stream.fileno())
        stream.truncate()
        stream.flush()
        os.fsync(stream.fileno())
    if identity(path) != expected_identity or regular(path) != replacement:
        raise OperationError("nginx_inplace_postimage_mismatch")


def write_endpoint(state: dict, label: str, path: Path, value: bytes, deploy, direction: str) -> None:
    """先落持久写意图再改唯一目标；中断后独立 rollback 可识别自己的半写。"""
    current = regular(path)
    if current == value:
        return
    source = regular(TRANSACTION / ("before" if direction == "after" else "after") / label)
    if current != source and not (direction == "before" and interrupted_write(state, label, current)):
        raise OperationError("nginx_target_preimage_changed:" + label)
    if identity(path) != state["files"][label]["identity"]:
        raise OperationError("nginx_target_identity_changed:" + label)
    token = secrets.token_hex(8)
    atomic(TRANSACTION / "writes" / (token + ".before"), current)
    atomic(TRANSACTION / "writes" / (token + ".after"), value)
    state["writing"] = {"label": label, "token": token, "before": sha(current), "after": sha(value)}
    save_state(state)
    if label == "main":
        deploy.inplace_configuration(current, value)
    else:
        inplace(path, current, value, state["files"][label]["identity"])
    state["writing"] = None
    save_state(state)


def prepare(transaction_dir: str | Path, candidate_main: str | Path, candidate_forum: str | Path) -> dict:
    """捕获可独立恢复的前像及候选；只写本事务目录，不改运行配置或消费者。"""
    root = transaction_path(transaction_dir)
    commands = Commands()
    tls, managed, main_web, deploy = tools_modules()
    with tls.tls_lock():
        if (root / "state.json").exists():
            state = read_state(root)
            if state.get("status") != "prepared":
                raise OperationError("nginx_transaction_already_started")
            gateway_guard(commands, state, deploy)
            owner_guard(tls, main_web, state)
            file_guard(commands, state)
            return {"complete": True, "operation": "prepare", "already_prepared": True, "runtime_unchanged": True}
        if root.exists() and any(root.iterdir()):
            raise OperationError("nginx_transaction_directory_not_empty")
        source_guard(commands, (BASE_REVISION,))
        git(commands, "diff", "--cached", "--quiet")
        if not tls.configuration_may_reload():
            raise OperationError("nginx_existing_ownership_denied")
        tls.context_preflight()
        live = gateway(commands)
        deploy.gateway_binding(live["id"], MAIN_IDENTITY)
        layer = forum_layer_path(commands, live)
        paths = {"main": MAIN_CONFIG, "forum_host": FORUM_CONFIG, "forum_layer": layer,
                 "community_program": COMMUNITY_PROGRAM, "community_current": COMMUNITY_CURRENT}
        before = {label: regular(path) for label, path in paths.items()}
        if sha(before["main"]) != BASE_MAIN_SHA or sha(before["forum_host"]) != BASE_FORUM_SHA or before["forum_layer"] != before["forum_host"]:
            raise OperationError("nginx_reviewed_baseline_changed")
        after = dict(before)
        after["main"] = candidate(commands, candidate_main, "deploy/nginx/default.conf", before["main"])
        after["forum_host"] = candidate(commands, candidate_forum, "deploy/nginx/forum.conf", before["forum_host"])
        after["forum_layer"] = after["forum_host"]
        saved = regular(TOOLS / "managed-vhost.conf") or None
        redirects = tls.main_web_redirect_record()
        if managed.split(before["main"])[1] != managed.split(after["main"])[1] or not managed.owned_delta_allowed(after["main"], after["main"], saved, redirects):
            raise OperationError("nginx_candidate_tools_fragment_changed")
        community = json.loads(before["community_current"])
        renewal = community.get("renewal", {})
        cron = regular(COMMUNITY_CRON)
        if community.get("source_revision") != BASE_REVISION or community.get("status") != "committed" or renewal.get("script_sha256") != sha(before["community_program"]) or renewal.get("forum_sha256") != sha(before["forum_layer"]) or renewal.get("cron_sha256") != sha(cron):
            raise OperationError("nginx_community_consumer_preimage_changed")
        cron_identity = identity(COMMUNITY_CRON)
        original_gateway = community.get("before", {}).get("gateway", {})
        if renewal.get("cron_identity") != {key: cron_identity[key] for key in ("device", "inode")} or community.get("before", {}).get("config_identity") != MAIN_IDENTITY or original_gateway.get("id") != live["id"] or original_gateway.get("image_id") != live["image"] or original_gateway.get("mounts") != live["mounts"] or original_gateway.get("networks") != live["networks"]:
            raise OperationError("nginx_community_runtime_anchor_changed")
        redirects_value = commands.run("nginx_original_forum_redirects", ["docker", "exec", live["id"], "cat", "/etc/nginx/forum-main/redirects.conf"])
        if sha(redirects_value) != renewal.get("redirects_sha256") or regular(FORUM_REDIRECTS) != redirects_value:
            raise OperationError("nginx_original_forum_redirects_changed")
        expression = re.compile(rb"(?m)^CONFIG_SHA=([\"'])" + BASE_MAIN_SHA.encode() + rb"\1$")
        if len(expression.findall(before["community_program"])) != 1:
            raise OperationError("nginx_community_config_anchor_not_unique")
        after["community_program"] = expression.sub(b"CONFIG_SHA='" + sha(after["main"]).encode() + b"'", before["community_program"])
        renewal["script_sha256"] = sha(after["community_program"])
        renewal["forum_sha256"] = sha(after["forum_layer"])
        after["community_current"] = (json.dumps(community, sort_keys=True, indent=2) + "\n").encode()
        state = {"schema": 1, "revision": APP_REVISION, "status": "prepared", "writing": None,
                 "gateway": live, "consumers": consumer_snapshot(tls, main_web), "cron_identity": identity(COMMUNITY_CRON),
                 "redirects_sha256": sha(redirects_value),
                 "files": {label: {"before": sha(before[label]), "after": sha(after[label]), "identity": identity(path)} for label, path in paths.items()}}
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        for direction, values in (("before", before), ("after", after)):
            for label, value in values.items():
                atomic(root / direction / label, value)
        atomic(root / "community-cron.before", cron)
        save_state(state)
        gateway_guard(commands, state, deploy)
        owner_guard(tls, main_web, state)
        file_guard(commands, state)
        return {"complete": True, "operation": "prepare", "runtime_unchanged": True, "recovery_captured": True}


def activate(transaction_dir: str | Path, *, source_align: Callable[[], None]) -> dict:
    """同锁激活；source_align 必须是 root 自行限时、排除两配置写入的已审 Git 对齐回调。"""
    if not callable(source_align):
        raise OperationError("nginx_controlled_source_align_required")
    state = read_state(transaction_dir)
    if state.get("status") != "prepared":
        raise OperationError("nginx_transaction_requires_recovery")
    commands = Commands()
    tls, _managed, main_web, deploy = tools_modules()
    with tls.tls_lock():
        source_guard(commands, (BASE_REVISION,))
        gateway_guard(commands, state, deploy)
        owner_guard(tls, main_web, state)
        paths = file_guard(commands, state)
        after = snapshots(state, "after")
        state["status"] = "activating"
        save_state(state)
        for label in ("main", "forum_host", "forum_layer"):
            write_endpoint(state, label, paths[label], after[label], deploy, "after")
        # 旧 ownership 已在写前确认；仅本锁内短暂存在新配置/旧 Git，绝不以放宽策略处理。
        source_align()
        if git(commands, "rev-parse", "HEAD").decode().strip() != APP_REVISION:
            raise OperationError("nginx_controlled_source_align_incomplete")
        state["status"] = "source_aligned"
        save_state(state)
        for label in ("community_program", "community_current"):
            write_endpoint(state, label, paths[label], after[label], deploy, "after")
        owner_guard(tls, main_web, state)
        gateway_guard(commands, state, deploy)
        endpoint_guard(commands, state, "after")
        commands.run("unified_nginx_test", ["docker", "exec", state["gateway"]["id"], "nginx", "-t"])
        gateway_guard(commands, state, deploy)
        commands.run("unified_nginx_reload", ["docker", "exec", state["gateway"]["id"], "nginx", "-s", "reload"])
        state["status"] = "reloaded"
        save_state(state)
        commands.run("unified_community_consumer_check", ["/usr/bin/python3", "-B", str(COMMUNITY_PROGRAM), "check"], timeout=90)
        gateway_guard(commands, state, deploy)
        owner_guard(tls, main_web, state)
        state["status"] = "activated"
        save_state(state)
        return {"complete": True, "operation": "activate", "gateway_not_recreated": True,
                "same_inode": True, "existing_ownership_verified": True, "community_consumer_verified": True,
                "nginx_test_passed": True}


def rollback(transaction_dir: str | Path, *, source_restore: Callable[[], None]) -> dict:
    """只恢复自有前像；source_restore 须自行限时并幂等恢复原 Git 基线，不能调用旧圈子回滚。"""
    if not callable(source_restore):
        raise OperationError("nginx_controlled_source_restore_required")
    state = read_state(transaction_dir)
    commands = Commands()
    tls, _managed, main_web, deploy = tools_modules()
    with tls.tls_lock():
        source_guard(commands, (BASE_REVISION, APP_REVISION))
        gateway_guard(commands, state, deploy)
        # 部分写入时策略可以暂不承认现场，但消费者自身不能被他人替换；恢复只认自有精确端点。
        if consumer_snapshot(tls, main_web) != state["consumers"]:
            raise OperationError("nginx_consumer_changed")
        paths = file_guard(commands, state, recovery=state.get("status") != "prepared")
        before = snapshots(state, "before")
        if state.get("status") == "rolled_back":
            if any(regular(path) != before[label] for label, path in paths.items()):
                raise OperationError("nginx_restored_files_changed")
            owner_guard(tls, main_web, state)
            return {"complete": True, "operation": "rollback", "already_restored": True}
        if state.get("status") == "prepared":
            # 尚未激活的 Nginx 不需要 reload；仍让全局事务幂等恢复其已预写的其他应用源码。
            source_restore()
            source_guard(commands, (BASE_REVISION,))
            owner_guard(tls, main_web, state)
            state["status"] = "rolled_back"
            save_state(state)
            return {"complete": True, "operation": "rollback", "runtime_configuration_unchanged": True}
        state["status"] = "restoring"
        save_state(state)
        # 先完成当前半写文件的恢复，避免后续文件写意图覆盖其恢复依据。
        pending = state.get("writing", {}).get("label") if state.get("writing") else None
        order = ([pending] if pending in LABELS else []) + [label for label in reversed(LABELS) if label != pending]
        for label in order:
            write_endpoint(state, label, paths[label], before[label], deploy, "before")
        source_restore()
        if git(commands, "rev-parse", "HEAD").decode().strip() != BASE_REVISION:
            raise OperationError("nginx_controlled_source_restore_incomplete")
        owner_guard(tls, main_web, state)
        gateway_guard(commands, state, deploy)
        endpoint_guard(commands, state, "before")
        commands.run("unified_restored_nginx_test", ["docker", "exec", state["gateway"]["id"], "nginx", "-t"])
        commands.run("unified_restored_nginx_reload", ["docker", "exec", state["gateway"]["id"], "nginx", "-s", "reload"])
        commands.run("unified_restored_community_check", ["/usr/bin/python3", "-B", str(COMMUNITY_PROGRAM), "check"], timeout=90)
        gateway_guard(commands, state, deploy)
        state["status"] = "rolled_back"
        state["writing"] = None
        save_state(state)
        return {"complete": True, "operation": "rollback", "gateway_not_recreated": True,
                "same_inode": True, "community_consumer_verified": True}


def owned_source(name: str) -> Path:
    """限定已经盘点的 tools 公开模块；拒绝符号链接、特殊文件和任意路径输入。"""
    if name not in MODULES:
        raise OperationError("module_not_allowed")
    path = TOOLS / name
    for part in (TOOLS, TOOLS.parent, path):
        if part.is_symlink():
            raise OperationError("consumer_module_symlink")
    if not path.is_file() or path.stat().st_size > SOURCE_LIMIT:
        raise OperationError("consumer_module_missing_or_large:" + name)
    return path


def reference(node: ast.AST) -> str | None:
    """只提取调用目标的标识符，不求值属性、参数或默认值。"""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = reference(node.value)
        return prefix + "." + node.attr if prefix else None
    return None


def signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """展示参数名和参数种类；所有默认值统一隐藏，注解也不回显字符串内容。"""
    args = node.args
    positional = [*args.posonlyargs, *args.args]
    required = len(positional) - len(args.defaults)
    parts = []
    for index, argument in enumerate(positional):
        parts.append(argument.arg + ("=<default>" if index >= required else ""))
        if args.posonlyargs and index + 1 == len(args.posonlyargs):
            parts.append("/")
    if args.vararg:
        parts.append("*" + args.vararg.arg)
    elif args.kwonlyargs:
        parts.append("*")
    for argument, default in zip(args.kwonlyargs, args.kw_defaults, strict=True):
        parts.append(argument.arg + ("=<default>" if default is not None else ""))
    if args.kwarg:
        parts.append("**" + args.kwarg.arg)
    return "(" + ", ".join(parts) + ")"


def function_interface(node: ast.FunctionDef | ast.AsyncFunctionDef, *, owner: str = "") -> dict:
    """返回公开函数的签名、位置和调用名；不给出函数正文、实参或状态文件内容。"""
    calls = sorted({
        name for item in ast.walk(node) if isinstance(item, ast.Call)
        if (name := reference(item.func)) is not None
    })
    if len(calls) > FUNCTION_LIMIT:
        raise OperationError("consumer_call_inventory_limit")
    return {
        "name": owner + node.name,
        "signature": signature(node),
        "async": isinstance(node, ast.AsyncFunctionDef),
        "line": node.lineno,
        "end_line": node.end_lineno,
        "calls": calls,
    }


def module_interface(name: str) -> dict:
    """AST 解析现场文件而不 import；模块顶层写入、动态导入和默认值表达式均不会运行。"""
    path = owned_source(name)
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=name)
    except (UnicodeError, SyntaxError):
        raise OperationError("consumer_module_not_parseable:" + name) from None
    functions = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
            functions.append(function_interface(node))
        elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            for member in node.body:
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)) and not member.name.startswith("_"):
                    functions.append(function_interface(member, owner=node.name + "."))
    if len(functions) > FUNCTION_LIMIT:
        raise OperationError("consumer_interface_inventory_limit")
    return {"path": str(path), "public_functions": functions}


def describe() -> dict:
    """只读列出真实 tools 接口，供集成人员核对接续和恢复合同；不申请锁或读取凭据。"""
    return {
        "complete": True,
        "operation": "describe",
        "read_only": True,
        "transaction_ready": False,
        "transaction_implemented": True,
        "write_interface": "same_process_orchestrator_callbacks_only",
        "modules": {name: module_interface(name) for name in MODULES},
        "known_required_interfaces": {
            "tls.py": ["tls_lock", "configuration_may_reload"],
            "managed_config.py": ["split", "owned_delta_allowed"],
            "main_web.py": ["anchor"],
            "deploy.py": ["gateway_binding", "inplace_configuration"],
        },
        "next_evidence": [
            "固定事务 prepare 尚须在服务器捕获当前前像与恢复快照；describe 不代表现场已就绪",
            "activate/rollback 只接受受控同进程源对齐回调，必须与主站 Git 对齐共用真实 tls_lock",
            "源对齐后重新调用现有 ownership；不手改 tools/MainWeb 元数据或增加白名单",
        ],
        "unknown_values": "既有回执中遮蔽的摘要保持未知，不从其他通道猜补或恢复",
    }


class SourceRedactor(ast.NodeTransformer):
    """仅为语义审阅生成脱敏 AST 文本；不执行源码，也不用源码恢复此前遮蔽摘要。"""

    def visit_Constant(self, node: ast.Constant):
        if not isinstance(node.value, str):
            return node
        value = node.value
        if "\n" in value or len(value) > 1024:
            value = "<multiline-or-long-literal-omitted>"
        elif "-----BEGIN" in value or "Bearer " in value:
            value = "<sensitive-literal-omitted>"
        else:
            value = DIGEST_LITERAL.sub("<digest-redacted>", value)
        return ast.copy_location(ast.Constant(value=value), node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.generic_visit(node)
        # 默认参数可能含凭据或配置内容；签名已由 describe 给出，仅保留有无默认值。
        node.args.defaults = [ast.Constant(value="<default>") for _ in node.args.defaults]
        node.args.kw_defaults = [
            ast.Constant(value="<default>") if value is not None else None
            for value in node.args.kw_defaults
        ]
        for argument in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]:
            argument.annotation = None
        node.returns = None
        return node

    def visit_Assign(self, node: ast.Assign):
        self.generic_visit(node)
        names = [part.id for target in node.targets for part in ast.walk(target) if isinstance(part, ast.Name)]
        if any(SENSITIVE_NAME.search(name) for name in names) and isinstance(node.value, ast.Constant):
            node.value = ast.Constant(value="<sensitive-assignment-omitted>")
        return node

    def visit_Dict(self, node: ast.Dict):
        self.generic_visit(node)
        for index, key in enumerate(node.keys):
            if isinstance(key, ast.Constant) and isinstance(key.value, str) and SENSITIVE_NAME.search(key.value):
                node.values[index] = ast.Constant(value="<sensitive-dict-value-omitted>")
        return node


def public_constant(value: object) -> object:
    """只公开确切函数引用的固定部署路径、工具路径与 marker；不输出摘要或任意配置字面量。"""
    if isinstance(value, str):
        if "\n" not in value and len(value) <= 512 and not DIGEST_LITERAL.search(value):
            if value.startswith(("/opt/parallellines", "/etc/nginx", "/etc/cron.d/parallellines", "/tools")):
                return value
            if value.startswith(("# BEGIN parallellines-tools", "# END parallellines-tools")):
                return value
            if re.fullmatch(r"https://(?:tools\.)?pingxingxian[.]space/?", value):
                return value
        return "<nonpublic-literal-omitted>"
    if isinstance(value, (tuple, list)) and len(value) <= 16:
        return [public_constant(item) for item in value]
    return "<nonpublic-literal-omitted>"


def describe_source() -> dict:
    """仅读固定模块的固定公开函数 AST 段；所有输出仅供审阅，禁止作为运行源码复用。"""
    modules = {}
    for module, requested in SOURCE_CONTRACTS.items():
        path = owned_source(module)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=module)
        except (UnicodeError, SyntaxError):
            raise OperationError("consumer_module_not_parseable:" + module) from None
        available = {
            node.name: node for node in tree.body
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
        }
        if any(name not in available for name in requested):
            raise OperationError("consumer_public_contract_changed:" + module)
        referenced = {
            node.id for name in requested for node in ast.walk(available[name])
            if isinstance(node, ast.Name) and node.id.isupper()
        }
        constants = {}
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in referenced:
                    try:
                        literal = ast.literal_eval(node.value)
                    except (ValueError, TypeError):
                        constants[target.id] = "<nonliteral-value-omitted>"
                    else:
                        constants[target.id] = public_constant(literal)
        sources = {}
        for name in requested:
            redacted = SourceRedactor().visit(available[name])
            ast.fix_missing_locations(redacted)
            sources[name] = ast.unparse(redacted)
        modules[module] = {
            "path": str(path), "referenced_public_constants": constants, "public_functions": sources,
        }
    result = {
        "complete": True, "operation": "describe-source", "read_only": True,
        "transaction_ready": False, "redacted_source_not_executable": True, "modules": modules,
        "unknown_values": "默认值、摘要及敏感字面量不输出；此前遮蔽内容保持未知",
    }
    if len(json.dumps(result, ensure_ascii=True).encode()) > 192 * 1024:
        raise OperationError("consumer_source_output_limit")
    return result


def main(arguments: list[str]) -> dict:
    """CLI 仅开放固定只读审阅；写阶段必须由同进程 orchestrator 提供受控回调。"""
    if arguments == ["describe"]:
        return describe()
    if arguments == ["describe-source"]:
        return describe_source()
    raise OperationError("nginx_write_operation_requires_orchestrator_callback")


if __name__ == "__main__":
    try:
        print(json.dumps(main(sys.argv[1:]), ensure_ascii=True, sort_keys=True, indent=2))
    except Exception as error:
        print(json.dumps({
            "complete": False,
            "error": str(error) if isinstance(error, OperationError) else type(error).__name__,
        }))
        raise SystemExit(1) from None
