"""独立静态工具站的有前像部署/恢复；只改自有容器、自有运维文件和唯一 vhost 段。"""

import contextlib
from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import secrets
import signal
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import health
import tls
from managed_config import ManagedConfigError, replace as replace_fragment, split, validate_fragment
from release_contract import ContractError, SOURCE_REPOSITORY, safe_extract_bundle, validate_descriptors, validate_receipt


APP = Path("/opt/parallellines-tools")
OPS = APP / "ops"
CURRENT = OPS / "current.json"
PENDING = OPS / "pending.json"
MAIN_CONFIG = Path("/opt/parallellines/deploy/nginx/default.conf")
GATEWAY = "parallellines-nginx-1"
CONTAINER = "parallellines-tools-static"
NETWORK = "parallellines_default"
CRON = Path("/etc/cron.d/parallellines-tools")
TIMEOUT = Path("/usr/bin/timeout")
CRON_TEXT = ("# Managed by parallellines-tools; do not merge into existing crontabs.\n"
             "17 */12 * * * root /usr/bin/timeout --signal=TERM --kill-after=10s 600s /usr/bin/python3 -B "
             "/opt/parallellines-tools/ops/tls.py scheduled-renew "
             ">/opt/parallellines-tools/ops/last-renewal.stdout 2>/opt/parallellines-tools/ops/last-renewal.stderr\n")
SOURCE_NAMES = ("deploy.py", "rollback.py", "release_contract.py", "managed_config.py", "tls.py", "health.py", "vhost.conf")


class DeployError(Exception):
    """只携带稳定错误码，禁止把 HTTP、Docker 或服务器配置原文作为日志。"""


def run(label, arguments, timeout=12, accepted=(0,), cwd=None, env=None, binary=False):
    """固定 argv 执行；显式设置单命令总时限，不使用 shell，不输出原始 stderr。"""
    try:
        result = subprocess.run(arguments, capture_output=True, text=not binary, check=False,
                                timeout=timeout, cwd=cwd, env=env)
    except subprocess.TimeoutExpired:
        raise DeployError(label + ":timeout") from None
    except OSError as error:
        raise DeployError(label + ":" + type(error).__name__) from None
    if result.returncode not in accepted:
        raise DeployError(label + ":exit_" + str(result.returncode))
    if len(result.stdout) + len(result.stderr) > 2 * 1024 * 1024:
        raise DeployError(label + ":output_limit")
    return result


def revision(value):
    """验证公开的应用提交 ID，不能将任意输入拼入路径或命令。"""
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}", value):
        raise DeployError("invalid_application_revision")
    return value


def directory(path):
    """只创建已批准工具目录内的目录，拒绝可写/非本用户拥有的现有路径和符号链接。"""
    path = Path(path)
    if path != APP and APP not in path.parents:
        raise DeployError("path_outside_tools_directory")
    for item in reversed((path, *path.parents)):
        if item == APP or APP in item.parents:
            if item.is_symlink():
                raise DeployError("tools_directory_symlink")
            if item.exists():
                stat = item.stat()
                if not item.is_dir() or stat.st_uid != os.geteuid() or stat.st_mode & 0o022:
                    raise DeployError("tools_directory_not_exclusively_owned")
            else:
                item.mkdir(mode=0o750)
    return path


def owned_path(value):
    """读取恢复路径前核实其仍在本任务目录中，不采用 state 中任意外部路径。"""
    path = Path(value)
    if APP.resolve() not in path.resolve().parents or path.is_symlink():
        raise DeployError("state_path_outside_tools_directory")
    return path


def atomic_bytes(path, content, mode=0o600):
    """原子保存本任务的运维/状态文件；仅 Nginx bind 文件另走 in-place 写入。"""
    path = Path(path)
    if path.is_symlink():
        raise DeployError("owned_file_symlink")
    temporary = path.with_name(path.name + ".new-" + secrets.token_hex(4))
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def save_json(path, value):
    """本地受限状态记录，不把完整状态、配置或内部摘要写到共享日志。"""
    atomic_bytes(path, (json.dumps(value, ensure_ascii=True, indent=2) + "\n").encode())


def read_json(path):
    """仅读本任务已知的小型状态文件，缺失为 None，损坏则停止而非隐式成功。"""
    path = Path(path)
    if not path.exists():
        return None
    if path.is_symlink() or path.stat().st_size > 256 * 1024:
        raise DeployError("invalid_owned_state_file")
    return json.loads(path.read_text(encoding="utf-8"))


@contextlib.contextmanager
def deadline(seconds):
    """已确认 Linux 主机上限制完整下载/解包阶段，包括 DNS 与流式读取。"""
    def expired(_number, _frame):
        raise DeployError("artifact_stage_deadline")

    old = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


class ReleaseRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        """仅允许 GitHub 公共 release 的 HTTPS 资产跳转，不附认证或 Cookie。"""
        parsed = urllib.parse.urlsplit(newurl)
        if parsed.scheme != "https" or parsed.hostname not in (
                "github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com") or parsed.username:
            raise DeployError("release_redirect_outside_github_assets")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url, output, limit, expected_sha, expected_bytes=None):
    """限时流式下载公开资产，完整摘要/大小通过后才交给 JSON 或 tar 解析。"""
    digest, size = hashlib.sha256(), 0
    request = urllib.request.Request(url, headers={"User-Agent": "ParallelLinesToolsDeploy/1"})
    try:
        with deadline(120), urllib.request.build_opener(ReleaseRedirect()).open(request, timeout=15) as response:
            if response.status != 200:
                raise DeployError("release_download_status")
            with Path(output).open("xb") as handle:
                while True:
                    chunk = response.read(128 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > limit:
                        raise DeployError("release_download_size_limit")
                    digest.update(chunk)
                    handle.write(chunk)
    except (OSError, urllib.error.URLError) as error:
        raise DeployError("release_download:" + type(error).__name__) from None
    if digest.hexdigest() != expected_sha or (expected_bytes is not None and size != expected_bytes):
        raise DeployError("release_download_integrity_mismatch")
    return size


def tools_metadata():
    """按精确名称查询存在性，再只读身份/能力字段；不把 inspect 失败误当容器不存在。"""
    ids = run("tools_lookup", ["docker", "ps", "--all", "--no-trunc", "--filter", "name=^/" + CONTAINER + "$", "--format", "{{.ID}}"] ).stdout.split()
    if not ids:
        return None
    if len(ids) != 1 or not re.fullmatch(r"[0-9a-f]{64}", ids[0]):
        raise DeployError("tools_container_not_unique")
    template = ('{"id":{{json .Id}},"image":{{json .Image}},"running":{{json .State.Running}},'
                '"status":{{json .State.Status}},"health":{{if .State.Health}}{{json .State.Health.Status}}{{else}}null{{end}},'
                '"source":{{json (index .Config.Labels "org.opencontainers.image.source")}},'
                '"revision":{{json (index .Config.Labels "org.opencontainers.image.revision")}},'
                '"memory":{{json .HostConfig.Memory}},"cpu":{{json .HostConfig.NanoCpus}},'
                '"pids":{{json .HostConfig.PidsLimit}},"read_only":{{json .HostConfig.ReadonlyRootfs}},'
                '"privileged":{{json .HostConfig.Privileged}},"ports":{{json .HostConfig.PortBindings}}}')
    record = json.loads(run("tools_metadata", ["docker", "inspect", "--format", template, ids[0]]).stdout)
    if record["source"] != SOURCE_REPOSITORY:
        raise DeployError("tools_name_owned_by_another_source")
    revision(record.get("revision"))
    return record


def gateway_binding(expected_id=None, expected_identity=None):
    """捕获或复核固定 gateway 的真实 ID/只读 bind/同一宿主 inode；恢复不能改用新实例。"""
    template = '{"id":{{json .Id}},"mounts":{{json .Mounts}},"networks":"{{range $name,$network := .NetworkSettings.Networks}}{{$name}} {{end}}"}'
    metadata = json.loads(run("gateway_binding_snapshot", ["docker", "inspect", "--format", template, GATEWAY]).stdout)
    identifier = metadata.get("id", "")
    if not re.fullmatch(r"[0-9a-f]{64}", identifier):
        raise DeployError("gateway_identity_invalid")
    if expected_id is not None and identifier != expected_id:
        raise DeployError("gateway_instance_changed_realign_transaction")
    if not any(item.get("Type") == "bind" and item.get("Source") == str(MAIN_CONFIG)
               and item.get("Destination") == "/etc/nginx/conf.d/default.conf" and item.get("RW") is False
               for item in metadata.get("mounts", [])):
        raise DeployError("gateway_bind_changed_realign_transaction")
    if NETWORK not in metadata.get("networks", "").split():
        raise DeployError("gateway_network_changed_realign_transaction")
    if MAIN_CONFIG.is_symlink() or not MAIN_CONFIG.is_file():
        raise DeployError("gateway_host_configuration_not_regular")
    stat = MAIN_CONFIG.stat()
    identity = {"device": stat.st_dev, "inode": stat.st_ino}
    if expected_identity is not None and identity != expected_identity:
        raise DeployError("gateway_host_inode_changed_realign_transaction")
    actual = run("gateway_binding_inode", ["docker", "exec", GATEWAY, "stat", "-c", "%d:%i", "/etc/nginx/conf.d/default.conf"]).stdout.strip()
    if actual != str(stat.st_dev) + ":" + str(stat.st_ino):
        raise DeployError("gateway_bound_inode_changed_realign_transaction")
    return {"id": identifier, "config_identity": identity}


def gateway_guard(expected, report=None):
    """只回前像/挂载匹配布尔；不恢复被屏蔽的摘要，不改 Git 或 gateway。"""
    binding = gateway_binding()
    matches, source = tls.expected_preimage(expected)
    if report is not None:
        report["expectedPreimage"] = matches
    if not matches or not tls.configuration_may_reload():
        raise DeployError("main_configuration_not_approved_preimage")
    tls.context_preflight()
    actual = run("gateway_bound_preimage", ["docker", "exec", GATEWAY, "sha256sum", "/etc/nginx/conf.d/default.conf"]).stdout.split()[0]
    if actual != hashlib.sha256(source).hexdigest():
        raise DeployError("gateway_bind_does_not_match_host_file")
    return source, binding


def known_configuration(source, fragment):
    """事务恢复可核自己的新/旧段；只允许外围与当前 Git HEAD 完全一致且索引未改。"""
    from managed_config import owned_delta_allowed
    base = ["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-C", "/opt/parallellines"]
    if run("main_index_clean", base + ["diff", "--no-ext-diff", "--cached", "--quiet", "--", "deploy/nginx/default.conf"], accepted=(0, 1)).returncode:
        return False
    head = run("main_configuration_head", base + ["show", "HEAD:deploy/nginx/default.conf"], binary=True).stdout
    return owned_delta_allowed(source, head, fragment)


def inplace_configuration(expected, replacement):
    """仅在完整前像与 inode 未变时原位写唯一文件，保留 Docker file-bind 及其它配置字节。"""
    flags = os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(MAIN_CONFIG, flags)
    with os.fdopen(descriptor, "r+b") as handle:
        before = os.fstat(handle.fileno())
        if handle.read() != expected or (MAIN_CONFIG.stat().st_dev, MAIN_CONFIG.stat().st_ino) != (before.st_dev, before.st_ino):
            raise DeployError("main_configuration_changed_before_inplace_write")
        if replacement == expected:
            pass
        elif replacement.startswith(expected):
            # 首次追加只写本任务尾部，原主站前像从未被覆写；中断时可严格识别部分尾部。
            handle.seek(len(expected))
            handle.write(replacement[len(expected):])
        elif expected.startswith(replacement):
            # 恢复首次追加只截掉已证明属于本任务的尾部，不截断保留的主站原像。
            handle.truncate(len(replacement))
        else:
            handle.seek(0)
            handle.write(replacement)
            handle.flush()
            os.fsync(handle.fileno())
            # 替换新内容完整落盘以后才截尾，不能先 truncate(0) 破坏恢复前像。
            handle.truncate(len(replacement))
        handle.flush()
        os.fsync(handle.fileno())
        after = MAIN_CONFIG.stat()
        if (after.st_dev, after.st_ino) != (before.st_dev, before.st_ino):
            raise DeployError("main_configuration_inode_changed_during_write")
    actual = run("gateway_bound_postimage", ["docker", "exec", GATEWAY, "sha256sum", "/etc/nginx/conf.d/default.conf"]).stdout.split()[0]
    if actual != hashlib.sha256(replacement).hexdigest():
        raise DeployError("gateway_bind_postimage_mismatch")


def compose_spec():
    """固定 schema1 独立运行能力，JSON 是 Compose 原生格式，不展开包内未知 env_file。"""
    return {"name": "parallellines-tools", "services": {"tools-static": {
        "image": "${TOOLS_IMAGE:?verified_image_required}", "container_name": CONTAINER,
        "restart": "unless-stopped", "init": True, "cpus": 0.5, "mem_limit": "256m", "pids_limit": 64,
        "read_only": True, "security_opt": ["no-new-privileges:true"],
        "logging": {"driver": "json-file", "options": {"max-size": "10m", "max-file": "2"}},
        "tmpfs": ["/var/cache/nginx:rw,nosuid,noexec,size=32m", "/var/run:rw,nosuid,noexec,size=1m"],
        "expose": ["80"], "networks": {"gateway": {"aliases": [CONTAINER]}},
        "healthcheck": {"test": ["CMD", "wget", "-q", "-O", "/dev/null", "http://127.0.0.1/healthz"],
                        "interval": "10s", "timeout": "3s", "start_period": "5s", "retries": 3}}},
        "networks": {"gateway": {"external": True, "name": "${TOOLS_PROXY_NETWORK:?verified_network_required}"}}}


def compose_environment(image):
    """只传正常 Docker 客户端所需的非凭据路径/上下文及两个 TOOL 参数，不读取 .env。"""
    allowed = ("PATH", "HOME", "LANG", "LC_ALL", "XDG_CONFIG_HOME", "DOCKER_CONFIG", "DOCKER_HOST",
               "DOCKER_CONTEXT", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH")
    environment = {key: os.environ[key] for key in allowed if key in os.environ}
    environment.update(TOOLS_IMAGE=image, TOOLS_PROXY_NETWORK=NETWORK, DOCKER_BUILDKIT="1")
    return environment


def up_application(compose_path, image):
    """只启动 tools-static，不构建、不拉可变镜像、不启动依赖或其它项目服务。"""
    run("tools_compose_up", ["docker", "compose", "--project-name", "parallellines-tools", "--env-file", "/dev/null",
        "--file", str(compose_path), "up", "--detach", "--no-deps", "--no-build", "--pull", "never", "tools-static"],
        timeout=90, env=compose_environment(image))


def wait_application(image):
    """最多20次、单次4秒和间隔2秒，总计不超120秒；只重试明确的 starting HTTP 未就绪。"""
    for attempt in range(20):
        current = tools_metadata()
        if current is None or current["image"] != image:
            raise DeployError("tools_image_identity_mismatch")
        if (current["memory"], current["cpu"], current["pids"], current["read_only"], current["privileged"], current["ports"] or {}) != (268435456, 500000000, 64, True, False, {}):
            raise DeployError("tools_runtime_capabilities_mismatch")
        if not current["running"] or current["health"] == "unhealthy":
            raise DeployError("tools_container_unhealthy")
        probe = run("tools_http_probe", ["docker", "exec", CONTAINER, "wget", "-q", "-O", "-", "http://127.0.0.1/healthz"], timeout=4, accepted=(0, 1))
        if probe.returncode == 0 and probe.stdout.strip() == "ok":
            return
        if current["health"] not in (None, "starting"):
            raise DeployError("tools_http_health_failed")
        if attempt < 19:
            time.sleep(2)
    raise DeployError("tools_startup_deadline")


def source_bundle():
    """支持受审 workflow 静态 source 包与已安装的独立恢复入口；不在生产下载执行脚本。"""
    bundle = globals().get("OPS_SOURCES")
    if bundle is None:
        base = Path(__file__).resolve().parent
        bundle = {name: (base / name).read_text(encoding="utf-8") for name in SOURCE_NAMES}
    if set(bundle) != set(SOURCE_NAMES) or any(not isinstance(value, str) or len(value) > 256 * 1024 for value in bundle.values()):
        raise DeployError("invalid_reviewed_ops_source_bundle")
    return bundle


def install_sources(bundle, attempt):
    """先持久保存完整独立恢复代码，再切换自有服务；文件均在任务目录并原子保存。"""
    versioned = directory(attempt / "ops")
    for name, value in bundle.items():
        atomic_bytes(versioned / name, value.encode("utf-8"))
    for name, value in bundle.items():
        if name != "vhost.conf":
            atomic_bytes(OPS / name, value.encode("utf-8"))
    return versioned


def verify_image(image, application):
    """真实本地 imageID 及不可变版本/来源标签同时匹配，才允许启动或恢复。"""
    template = '{"id":{{json .Id}},"source":{{json (index .Config.Labels "org.opencontainers.image.source")}},"revision":{{json (index .Config.Labels "org.opencontainers.image.revision")}}}'
    record = json.loads(run("image_identity", ["docker", "image", "inspect", "--format", template, image]).stdout)
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", record["id"]) or record["source"] != SOURCE_REPOSITORY or record["revision"] != application:
        raise DeployError("built_image_provenance_mismatch")
    return record["id"]


def cron_before(current):
    """只接受本任务已记录的调度入口，不读取或覆盖其它 cron。"""
    if not CRON.exists():
        return None
    if current is None or CRON.is_symlink():
        raise DeployError("existing_cron_not_proven_owned")
    data = CRON.read_bytes()
    if hashlib.sha256(data).hexdigest() != current.get("cron_sha256"):
        raise DeployError("owned_cron_changed_outside_deployment")
    return data


def perform_deploy(tag, receipt_sha, expected, report):
    """验证发行物、完整备份和独立恢复路线后，只部署本工具并应用唯一 vhost 段。"""
    if not re.fullmatch(r"site-[0-9a-f]{40}", tag) or not re.fullmatch(r"[0-9a-f]{64}", receipt_sha):
        raise DeployError("invalid_release_inputs")
    application = tag[5:]
    bundle = source_bundle()
    fragment = validate_fragment(bundle["vhost.conf"].encode("utf-8"))
    source, gateway = gateway_guard(expected, report)
    if not tls.certificate_status().get("valid_more_than_30_days"):
        raise DeployError("tools_certificate_not_prepared")
    environment = tls.renewal_environment()
    if not environment["cron_active"] or not environment["cron_directory_available"] or not TIMEOUT.is_file():
        raise DeployError("dedicated_renewal_consumer_unavailable")
    directory(OPS)
    with tls.tls_lock():
        if PENDING.exists():
            raise DeployError("unfinished_deployment_requires_rollback")
        current = read_json(CURRENT)
        before_container = tools_metadata()
        if before_container is not None and (current is None or current.get("source") != SOURCE_REPOSITORY or current.get("image_id") != before_container["image"]):
            raise DeployError("existing_tools_image_has_no_verified_restore_record")
        before_cron = cron_before(current)
        release = directory(APP / "releases" / application)
        attempt = directory(release / "attempts" / secrets.token_hex(8))
        receipt_file = attempt / "deployment-receipt.json"
        download(SOURCE_REPOSITORY + "/releases/download/" + tag + "/deployment-receipt.json", receipt_file, 256 * 1024, receipt_sha)
        receipt = validate_receipt(json.loads(receipt_file.read_text(encoding="utf-8")), tag)
        archive = attempt / "toolbox-dist.tar.gz"
        item = receipt["bundle"]
        download(item["url"], archive, item["bytes"], item["sha256"], item["bytes"])
        with deadline(120):
            safe_extract_bundle(archive, attempt / "payload")
        payload = attempt / "payload"
        validate_descriptors(payload)
        report["release_integrity_verified"] = True
        image_tag = "parallellines-tools:" + application
        verified = release / "verified-image.json"
        if run("immutable_tag_lookup", ["docker", "image", "ls", "--quiet", "--no-trunc", image_tag]).stdout.strip():
            previous_image = read_json(verified)
            if (previous_image is None or previous_image.get("receipt_sha256") != receipt_sha
                    or previous_image.get("bundle_sha256") != item["sha256"]
                    or previous_image.get("nginxImage") != receipt["nginxImage"]):
                raise DeployError("immutable_revision_tag_exists_without_matching_receipt")
            image = verify_image(image_tag, application)
            if previous_image.get("image_id") != image:
                raise DeployError("immutable_revision_tag_image_changed")
            report["verified_image_reused"] = True
        else:
            run("pull_official_nginx", ["docker", "pull", receipt["nginxImage"]], timeout=120)
            iid = attempt / "image.iid"
            run("copy_only_build", ["docker", "build", "--network", "none", "--pull=false", "--build-arg", "NGINX_IMAGE=" + receipt["nginxImage"],
                "--build-arg", "APP_REVISION=" + application, "--tag", image_tag, "--iidfile", str(iid),
                "--file", "deploy/Dockerfile.prebuilt", "."], timeout=180, cwd=payload, env=compose_environment(image_tag))
            image = verify_image(image_tag, application)
            if iid.read_text().strip() != image:
                raise DeployError("iidfile_image_identity_mismatch")
            save_json(verified, {"receipt_sha256": receipt_sha, "bundle_sha256": item["sha256"],
                                 "nginxImage": receipt["nginxImage"], "image_id": image})
        compose_file = attempt / "compose.json"
        save_json(compose_file, compose_spec())
        versioned = install_sources(bundle, attempt)
        backup = attempt / "gateway-default.conf.before"
        atomic_bytes(backup, source)
        saved_old = OPS / "managed-vhost.conf"
        old_saved = saved_old.read_bytes() if saved_old.exists() else None
        if before_cron is not None:
            atomic_bytes(attempt / "cron.before", before_cron)
        state = {"schema": 1, "source": SOURCE_REPOSITORY, "applicationRevision": application,
                 "attempt": str(attempt), "image_id": image, "image_tag": image_tag,
                 "compose": str(compose_file), "receipt_sha256": receipt_sha,
                 "before_current": current, "before_container": before_container,
                 "before_config": str(backup), "before_saved_fragment": old_saved.decode("utf-8") if old_saved is not None else None,
                 "before_cron_present": before_cron is not None, "gateway_id": gateway["id"],
                 "config_identity": gateway["config_identity"],
                 "new_fragment": fragment.decode("utf-8"), "status": "prepared"}
        save_json(attempt / "transaction.json", state)
        save_json(PENDING, state)
        try:
            # 构建耗时后重核真实前像与实例，不能覆盖期间出现的主站或工具更新。
            if gateway_guard(expected)[1] != gateway or tools_metadata() != before_container:
                raise DeployError("deployment_state_changed_before_service_switch")
            up_application(compose_file, image_tag)
            wait_application(image)
            if gateway_guard(expected)[1] != gateway:
                raise DeployError("gateway_recreated_outside_tools_operation")
            _, prior_fragment = split(source)
            if prior_fragment is not None and prior_fragment != fragment and old_saved != prior_fragment:
                raise DeployError("existing_vhost_not_proven_owned")
            target = replace_fragment(source, prior_fragment, fragment)
            inplace_configuration(source, target)
            atomic_bytes(saved_old, fragment)
            gateway_binding(state["gateway_id"], state["config_identity"])
            run("nginx_test", ["docker", "exec", GATEWAY, "nginx", "-t"])
            gateway_binding(state["gateway_id"], state["config_identity"])
            run("nginx_reload", ["docker", "exec", GATEWAY, "nginx", "-s", "reload"])
            after = health.run_health()
            report["health"] = after
            if not after["healthy"]:
                raise DeployError("post_deploy_health_failed")
            tls.confirm_loaded_certificate()
            gateway_binding(state["gateway_id"], state["config_identity"])
            # 新的 cron 是本任务独有入口；只复制自有源，不改变任何旧 cron/cert/hooks。
            atomic_bytes(OPS / "renew.cron", CRON_TEXT.encode(), mode=0o600)
            atomic_bytes(CRON, CRON_TEXT.encode(), mode=0o644)
            tls.request_certificate("renew", dry_run=True)
            committed = {"schema": 1, "source": SOURCE_REPOSITORY, "applicationRevision": application,
                         "image_id": image, "image_tag": image_tag, "compose": str(compose_file),
                         "attempt": str(attempt), "cron_sha256": hashlib.sha256(CRON_TEXT.encode()).hexdigest(),
                         "receipt_sha256": receipt_sha, "renewal_verified_at": datetime.now(timezone.utc).isoformat()}
            save_json(CURRENT, committed)
            state["status"] = "awaiting_independent_consumer_check"
            save_json(attempt / "transaction.json", state)
            save_json(PENDING, state)
        except Exception:
            # 补偿只使用这笔已完整落盘的事务；补偿失败保留 pending 和独立恢复入口，不伪装成功。
            try:
                restore_state(state, report)
            except Exception as restoration:
                report["recovery"] = {"complete": False, "error": type(restoration).__name__,
                                      "operation": "rollback", "revision": application}
            raise
    # 独立进程必须自行取得同一把锁；不能在父进程持锁时调用而让消费者永远锁失败。
    try:
        run("installed_renewal_consumer_check", ["/usr/bin/timeout", "--signal=TERM", "--kill-after=10s", "600s",
            "/usr/bin/python3", "-B", str(OPS / "tls.py"), "scheduled-renew"], timeout=620)
        consumer = read_json(OPS / "last-renewal.json")
        if consumer is None or consumer.get("operation") != "scheduled-renew" or consumer.get("complete") is not True:
            raise DeployError("installed_consumer_receipt_not_successful")
        with tls.tls_lock():
            observed = read_json(PENDING)
            if observed is None or observed["attempt"] != str(attempt) or tools_metadata()["image"] != image:
                raise DeployError("deployment_changed_during_consumer_check")
            gateway_binding(state["gateway_id"], state["config_identity"])
            state["status"] = "committed"
            save_json(attempt / "transaction.json", state)
            PENDING.unlink()
            report.update(applicationRevision=application, image_identity_verified=True,
                          copy_only_build_verified=True, renewal_dry_run_verified=True,
                          installed_consumer_invoked=True, gateway_not_recreated=True,
                          rollback_revision=application, complete=True)
    except Exception:
        try:
            with tls.tls_lock():
                restore_state(state, report)
        except Exception as restoration:
            report["recovery"] = {"complete": False, "error": type(restoration).__name__,
                                  "operation": "rollback", "revision": application}
        raise


def assert_attempt_owner(state):
    """恢复只属于完整 attempt，不因同 SHA/同镜像而接管另一个更新事务。"""
    attempt = str(owned_path(state["attempt"]))
    pending = read_json(PENDING)
    current = read_json(CURRENT)
    if pending is not None:
        if pending.get("attempt") != attempt or pending.get("applicationRevision") != state["applicationRevision"]:
            raise DeployError("recovery_attempt_replaced_realign_transaction")
        before = state.get("before_current")
        if current is not None and current.get("attempt") not in (attempt, before.get("attempt") if before else None):
            raise DeployError("recovery_current_attempt_replaced")
        return False
    transaction = read_json(owned_path(attempt) / "transaction.json")
    if transaction is not None and transaction.get("status") == "rolled_back" and current == state.get("before_current"):
        return True
    if current is None or current.get("attempt") != attempt:
        raise DeployError("recovery_attempt_is_not_current")
    return False


def restore_state(state, report):
    """只恢复已记录的自有容器与唯一 vhost 段；外部修改或未知容器绝不整文件覆盖。"""
    application = revision(state["applicationRevision"])
    if state.get("source") != SOURCE_REPOSITORY or state.get("schema") != 1:
        raise DeployError("rollback_state_not_owned")
    if assert_attempt_owner(state):
        report["recovery"] = {"complete": True, "already_restored": True, "no_mutation": True}
        return
    identifier, identity = state.get("gateway_id"), state.get("config_identity")
    if not isinstance(identifier, str) or not re.fullmatch(r"[0-9a-f]{64}", identifier) or not isinstance(identity, dict):
        raise DeployError("rollback_gateway_anchor_missing_realign_transaction")
    # 任何服务/config突变前，必须仍是这笔事务捕获的实例和相同物理 bind 文件。
    gateway_binding(identifier, identity)
    attempt = owned_path(state["attempt"])
    prior_source = owned_path(state["before_config"]).read_bytes()
    _, before_fragment = split(prior_source)
    current_source = MAIN_CONFIG.read_bytes()
    new_fragment = validate_fragment(state["new_fragment"].encode("utf-8"))
    # 只识别首次 append 的已证明部分尾部，不接受替换旧段中断或任意 foreign 字节。
    partial_append = (before_fragment is None and len(prior_source) < len(current_source) < len(prior_source) + len(new_fragment)
                      and current_source.startswith(prior_source)
                      and new_fragment.startswith(current_source[len(prior_source):]))
    if partial_append:
        if not known_configuration(prior_source, None):
            raise DeployError("rollback_partial_append_base_changed")
        restored = prior_source
    else:
        _, current_fragment = split(current_source)
        if current_fragment not in (before_fragment, new_fragment) or not known_configuration(current_source, current_fragment):
            raise DeployError("rollback_gateway_changed_outside_owned_delta")
        restored = replace_fragment(current_source, current_fragment, before_fragment)
    current = tools_metadata()
    before = state.get("before_container")
    if current is not None and current["image"] not in ({state["image_id"]} | ({before["image"]} if before else set())):
        raise DeployError("rollback_container_changed_outside_transaction")
    old_record = state.get("before_current")
    if before is not None:
        if old_record is None:
            raise DeployError("rollback_previous_receipt_missing")
        old_revision = revision(old_record["applicationRevision"])
        old_tag = old_record["image_tag"]
        if verify_image(old_tag, old_revision) != before["image"]:
            raise DeployError("rollback_previous_image_missing")
        up_application(owned_path(old_record["compose"]), old_tag)
        wait_application(before["image"])
    elif current is not None:
        run("remove_only_new_owned_tools_container", ["docker", "rm", "--force", CONTAINER], timeout=30)
    if restored != current_source:
        inplace_configuration(current_source, restored)
    saved = state.get("before_saved_fragment")
    atomic_bytes(OPS / "managed-vhost.conf", saved.encode("utf-8") if saved is not None else b"")
    gateway_binding(identifier, identity)
    run("rollback_nginx_test", ["docker", "exec", GATEWAY, "nginx", "-t"])
    gateway_binding(identifier, identity)
    run("rollback_nginx_reload", ["docker", "exec", GATEWAY, "nginx", "-s", "reload"])
    if CRON.exists():
        if CRON.is_symlink() or CRON.read_bytes() not in (CRON_TEXT.encode(), (attempt / "cron.before").read_bytes() if state["before_cron_present"] else b""):
            raise DeployError("rollback_cron_changed_outside_owned_entry")
        if not state["before_cron_present"]:
            CRON.unlink()
    if state["before_cron_present"]:
        atomic_bytes(CRON, (attempt / "cron.before").read_bytes(), mode=0o644)
    gateway_binding(identifier, identity)
    assert_attempt_owner(state)
    if old_record is None:
        if CURRENT.exists():
            CURRENT.unlink()
    else:
        save_json(CURRENT, old_record)
    state["status"] = "rolled_back"
    save_json(attempt / "transaction.json", state)
    save_json(OPS / "last-rollback.json", {"applicationRevision": application, "attempt": str(attempt)})
    if PENDING.exists():
        pending = read_json(PENDING)
        if pending["applicationRevision"] != application or pending.get("attempt") != str(attempt):
            raise DeployError("rollback_pending_revision_changed")
        PENDING.unlink()
    report["recovery"] = {"complete": True, "application_restored_to_previous_presence": before is not None,
                          "gateway_not_recreated": True, "only_owned_configuration_changed": True}


def rollback_application(application, report):
    """独立恢复入口：先恢复未完成事务，否则只允许撤销当前版本这一笔已记录部署。"""
    application = revision(application)
    with tls.tls_lock():
        state = read_json(PENDING)
        if state is None:
            current = read_json(CURRENT)
            if current is not None and current["applicationRevision"] == application:
                state = read_json(owned_path(current["attempt"]) / "transaction.json")
            else:
                last = read_json(OPS / "last-rollback.json")
                if last is None or last["applicationRevision"] != application:
                    raise DeployError("rollback_revision_is_not_current")
                state = read_json(owned_path(last["attempt"]) / "transaction.json")
        if state is None or state["applicationRevision"] != application:
            raise DeployError("rollback_transaction_not_found")
        restore_state(state, report)
        report["complete"] = True


def main(arguments):
    """仅接受 deploy tag/receipt摘要/配置前像；rollback 由独立入口选择已记录版本。"""
    if len(arguments) != 4 or arguments[0] != "deploy":
        print(json.dumps({"operation": "rejected", "complete": False, "errors": ["invalid_deploy_arguments"]}))
        return 2
    report = {"operation": "deploy", "complete": False, "errors": []}
    try:
        perform_deploy(arguments[1], arguments[2], arguments[3], report)
    except (DeployError, ContractError, ManagedConfigError, tls.OperationError) as error:
        report["errors"].append(str(error))
    except (OSError, ValueError, KeyError, TypeError) as error:
        report["errors"].append("tools_deploy:" + type(error).__name__)
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report["complete"] and not report["errors"] else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
