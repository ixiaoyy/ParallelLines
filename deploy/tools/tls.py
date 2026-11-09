"""工具域名独立 Certbot 生命周期；仅显式操作可写，不改变既有 Nginx、证书或全局 hooks。"""

import contextlib
from datetime import datetime, timezone
import fcntl
import hashlib
import http.client
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
import urllib.error
import urllib.parse
import urllib.request

from managed_config import ManagedConfigError, owned_delta_allowed


DOMAIN = "tools.pingxingxian.space"
GATEWAY = "parallellines-nginx-1"
CERTBOT = "parallellines-certbot-1"
NETWORK = "parallellines_default"
MAIN_DIRECTORY = Path("/opt/parallellines")
MAIN_CONFIG = MAIN_DIRECTORY / "deploy/nginx/default.conf"
APPLICATION = Path("/opt/parallellines-tools")
PUBLIC_DIRECTORY = Path("/opt/parallellines/var/certbot")
CERTIFICATE_PARENT = Path("/opt/parallellines/var/letsencrypt")
CERTIFICATE_STORE = CERTIFICATE_PARENT / "parallellines-tools"
CONTAINER_STORE = "/etc/letsencrypt/parallellines-tools"
PUBLIC_CERTIFICATE = CERTIFICATE_STORE / "live" / DOMAIN / "fullchain.pem"

# 容器内限定真实 certbot 子进程时间，避免只中止 docker 客户端而让签发无限继续。
CERTBOT_GUARD = """import subprocess, sys
p = subprocess.Popen(sys.argv[1:])
try:
    code = p.wait(timeout=300)
except subprocess.TimeoutExpired:
    p.terminate()
    try:
        p.wait(timeout=10)
    except subprocess.TimeoutExpired:
        p.kill()
        p.wait()
    code = 124
sys.exit(code)
"""


class OperationError(Exception):
    """稳定错误码，不携带 Certbot 输出、配置原文、密钥或环境。"""


def command(label, arguments, timeout=12, accepted=(0,), binary=False):
    """执行固定 argv；binary 用于逐字节核对 Git 配置，不变更旧调用的文本返回约定。"""
    try:
        result = subprocess.run(arguments, capture_output=True, text=not binary, check=False, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise OperationError(label + ":timeout") from None
    except OSError as error:
        raise OperationError(label + ":" + type(error).__name__) from None
    if result.returncode not in accepted:
        raise OperationError(label + ":exit_" + str(result.returncode))
    if len(result.stdout) + len(result.stderr) > 1024 * 1024:
        raise OperationError(label + ":output_limit")
    return result


def expected_preimage(value):
    """与调用方已知的完整前像比较，只返回匹配与否，绝不输出现场摘要或恢复被屏蔽字符。"""
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise OperationError("expected_preimage_must_be_64_hex")
    source = MAIN_CONFIG.read_bytes()
    if len(source) > 2 * 1024 * 1024:
        raise OperationError("main_config_size_limit")
    return hashlib.sha256(source).hexdigest() == value, source


def clean_main_configuration():
    """只检查主站配置这一文件的索引和工作区，不读取其他文件内容、不更新索引。"""
    base = ["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-C", str(MAIN_DIRECTORY)]
    name = "deploy/nginx/default.conf"
    for options in (["diff", "--no-ext-diff", "--quiet"],
                    ["diff", "--no-ext-diff", "--cached", "--quiet"]):
        if command("main_config_clean", base + options + ["--", name], accepted=(0, 1)).returncode:
            return False
    return True


def main_web_redirect_record():
    """仅读本次主站 Web 发布保存的两处 exact 授权记录，不接受任意配置片段。"""
    path = APPLICATION / "ops/main-web/redirects.json"
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 32768:
        raise OperationError("main_web_redirect_record_invalid")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise OperationError("main_web_redirect_record_invalid")
    return value


def configuration_may_reload():
    """接受整体 clean 或仅本工具已记录的 owned delta；外部未提交/已暂存变化仍停止。"""
    if clean_main_configuration():
        return True
    recorded = APPLICATION / "ops/managed-vhost.conf"
    if not recorded.is_file() or recorded.is_symlink():
        return False
    base = ["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-C", str(MAIN_DIRECTORY)]
    name = "deploy/nginx/default.conf"
    if command("main_config_index", base + ["diff", "--no-ext-diff", "--cached", "--quiet", "--", name], accepted=(0, 1)).returncode:
        return False
    head = command("main_config_head_bytes", base + ["show", "HEAD:" + name], binary=True).stdout
    saved = recorded.read_bytes()
    try:
        return owned_delta_allowed(MAIN_CONFIG.read_bytes(), head, saved or None, main_web_redirect_record())
    except ManagedConfigError:
        return False


def context_preflight():
    """确认固定容器、既有挂载和网络仍是已批准现场，不读取 Env、私钥或完整 labels。"""
    if CERTIFICATE_STORE.is_symlink():
        raise OperationError("dedicated_certificate_directory_symlink")
    gateway_networks = command("gateway_network", ["docker", "inspect", "--format",
        "{{range $name, $network := .NetworkSettings.Networks}}{{$name}} {{end}}", GATEWAY]).stdout.split()
    if NETWORK not in gateway_networks:
        raise OperationError("gateway_network_changed")
    expected = {"/etc/letsencrypt": str(CERTIFICATE_PARENT), "/var/www/certbot": str(PUBLIC_DIRECTORY)}
    for container in (GATEWAY, CERTBOT):
        if command("container_running", ["docker", "inspect", "--format", "{{json .State.Running}}", container]).stdout.strip() != "true":
            raise OperationError("required_container_not_running")
        mounts = json.loads(command("container_mounts", ["docker", "inspect", "--format", "{{json .Mounts}}", container]).stdout)
        for destination, source in expected.items():
            if not any(item.get("Source") == source and item.get("Destination") == destination for item in mounts):
                raise OperationError("approved_mount_changed")
    version = command("certbot_version", ["docker", "exec", CERTBOT, "certbot", "--version"], timeout=5).stdout.strip()
    if not version.startswith("certbot 5.8."):
        raise OperationError("certbot_version_requires_review")
    return {"gateway": GATEWAY, "certbot": CERTBOT, "network_confirmed": True, "certbot_version": version}


def renewal_environment():
    """仅识别调度能力和旧续期命令特征，不执行或输出旧 hooks/命令内容。"""
    active = False
    if shutil.which("systemctl"):
        for service in ("cron", "crond"):
            result = command("cron_active", ["systemctl", "is-active", service], timeout=5, accepted=(0, 1, 3, 4))
            active = active or result.stdout.strip() == "active"
    if not active and shutil.which("pgrep"):
        for name in ("cron", "crond"):
            active = active or command("cron_process", ["pgrep", "-x", name], timeout=5, accepted=(0, 1)).returncode == 0
    original_command = json.loads(command("certbot_schedule_metadata", ["docker", "inspect", "--format", "{{json .Config.Cmd}}", CERTBOT]).stdout)
    text = " ".join(original_command or [])
    return {"cron_active": active, "cron_directory_available": Path("/etc/cron.d").is_dir(),
            "existing_parent_renew_loop_detected": bool(re.search(r"\bcertbot\s+renew\b", text)),
            "existing_directory_hooks_disabled": "--no-directory-hooks" in text,
            "tools_config_isolated_from_parent_renewal": True,
            "tools_consumer_installation": "pending_deploy"}


def private_directory(path, mode=0o750):
    """只在已批准工具目录内创建本任务路径，不跟随已有的目录符号链接。"""
    if APPLICATION.is_symlink() or path.is_symlink():
        raise OperationError("application_directory_symlink")
    path.mkdir(mode=mode, parents=True, exist_ok=True)
    if not path.is_dir() or APPLICATION.resolve() not in (path.resolve(), *path.resolve().parents):
        raise OperationError("application_directory_outside_target")


def backup_preimage(source):
    """以独立受限文件保留已匹配的配置前像，不复制证书私钥或真实环境文件。"""
    private_directory(APPLICATION)
    destination = APPLICATION / "releases" / ("tls-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(4))
    private_directory(destination)
    file = destination / "gateway-default.conf.before"
    descriptor = os.open(file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(source)
        handle.flush()
        os.fsync(handle.fileno())
    return str(file)


@contextlib.contextmanager
def tls_lock():
    """本任务 TLS 操作互斥，不锁主站 Git、数据库或旧 Certbot 配置。"""
    private_directory(APPLICATION / "ops")
    path = APPLICATION / "ops/tls.lock"
    if path.is_symlink():
        raise OperationError("tls_lock_symlink")
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    with os.fdopen(descriptor, "a") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise OperationError("tools_tls_operation_already_running") from None
        yield


@contextlib.contextmanager
def owned_probe():
    """创建一次性公开 HTTP01 探针，只清理本次排他创建且 inode 未被替换的文件。"""
    base = PUBLIC_DIRECTORY.resolve(strict=True)
    directory = PUBLIC_DIRECTORY
    for component in (".well-known", "acme-challenge"):
        directory = directory / component
        if not directory.exists():
            directory.mkdir(mode=0o755)
            directory.chmod(0o755)
        if base not in (directory.resolve(), *directory.resolve().parents):
            raise OperationError("acme_directory_outside_fixed_webroot")
    name = "tools-probe-" + secrets.token_hex(16)
    file = directory / name
    body = ("parallellines-tools-http01-" + secrets.token_hex(16)).encode("ascii")
    descriptor = os.open(file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    os.fchmod(descriptor, 0o644)
    identity = os.fstat(descriptor)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(body)
    try:
        yield "http://" + DOMAIN + "/.well-known/acme-challenge/" + name, body
    finally:
        if file.exists():
            current = file.lstat()
            if file.is_symlink() or (current.st_dev, current.st_ino) != (identity.st_dev, identity.st_ino):
                raise OperationError("probe_file_ownership_changed")
            file.unlink()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        """交由调用方限定同域跳转和次数，不使用默认任意跳转策略。"""
        return None


@contextlib.contextmanager
def probe_deadline():
    """已确认 Linux 主机上给完整公网探针设 22 秒上限，覆盖 DNS、跳转与正文读取。"""
    def expired(_number, _frame):
        raise OperationError("http01_probe_deadline")

    previous = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, 22)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def verify_public_probe(url, expected):
    """验证真实公网 HTTP01 路径；最多跟随三次同域 HTTP/HTTPS 跳转，不关闭证书验证。"""
    opener = urllib.request.build_opener(NoRedirect())
    for redirects in range(4):
        parsed = urllib.parse.urlsplit(url)
        if parsed.hostname != DOMAIN or parsed.scheme not in ("http", "https") or parsed.port not in (None, 80, 443) or parsed.username:
            raise OperationError("http01_redirect_outside_authorized_domain")
        request = urllib.request.Request(url, headers={"Cache-Control": "no-cache", "User-Agent": "ParallelLinesToolsHTTP01/1"})
        try:
            with opener.open(request, timeout=5) as response:
                body = response.read(1025)
                status = response.status
        except urllib.error.HTTPError as error:
            if error.code in (301, 302, 303, 307, 308) and redirects < 3:
                url = urllib.parse.urljoin(url, error.headers.get("Location", ""))
                continue
            raise OperationError("http01_public_status_" + str(error.code)) from None
        except OSError as error:
            raise OperationError("http01_public:" + type(error).__name__) from None
        if status != 200 or body != expected:
            raise OperationError("http01_public_body_mismatch")
        return {"public_reachable": True, "body_matched": True, "redirects": redirects}
    raise OperationError("http01_redirect_limit")


def certificate_status():
    """只解析工具专属的公共证书；不打开、复制或打印任何账户或证书私钥。"""
    if not PUBLIC_CERTIFICATE.is_file():
        return {"exists": False}
    if not re.fullmatch(r"(?:fullchain|cert)\d*\.pem", PUBLIC_CERTIFICATE.resolve().name):
        raise OperationError("unexpected_public_certificate_link")
    data = command("tools_public_certificate", ["openssl", "x509", "-in", str(PUBLIC_CERTIFICATE), "-noout", "-ext", "subjectAltName", "-enddate"], timeout=5).stdout
    names = re.findall(r"DNS:([A-Za-z0-9*_.-]+)", data)
    if set(names) != {DOMAIN}:
        raise OperationError("tools_certificate_domain_scope_conflict")
    valid = command("tools_certificate_expiry", ["openssl", "x509", "-in", str(PUBLIC_CERTIFICATE), "-noout", "-checkend", "2592000"], timeout=5, accepted=(0, 1)).returncode == 0
    return {"exists": True, "domains": names, "valid_more_than_30_days": valid,
            "expires": next((line.partition("=")[2] for line in data.splitlines() if line.startswith("notAfter=")), None)}


def certbot_arguments(verb):
    """将账户、工作文件、日志和 hooks 全部隔离到专属正常 Certbot config-dir。"""
    common = ["--config", "/dev/null", "--config-dir", CONTAINER_STORE,
              "--work-dir", CONTAINER_STORE + "/work", "--logs-dir", CONTAINER_STORE + "/logs",
              "--max-log-backups", "2", "--non-interactive", "--no-directory-hooks",
              "--pre-hook", "", "--post-hook", "", "--deploy-hook", "",
              "--cert-name", DOMAIN, "--webroot", "--webroot-path", "/var/www/certbot"]
    if verb == "certonly":
        common += ["--agree-tos", "--register-unsafely-without-email", "--keep-until-expiring", "-d", DOMAIN]
    elif verb == "renew":
        common.append("--no-random-sleep-on-renew")
    else:
        raise OperationError("unsupported_certbot_verb")
    return ["docker", "exec", CERTBOT, "python3", "-B", "-c", CERTBOT_GUARD, "certbot", verb] + common


def request_certificate(verb, dry_run=False):
    """使用官方容器申请/续期，容器内硬限 300 秒；只返回稳定分类，不透出旧配置或日志。"""
    arguments = certbot_arguments(verb)
    if dry_run:
        arguments.append("--dry-run")
    result = command("tools_certbot", arguments, timeout=330, accepted=(0, 1, 124))
    if result.returncode:
        category = "request_failed"
        detail = (result.stdout + result.stderr).lower()
        for keyword, code in (("rate limit", "rate_limited"), ("too many", "rate_limited"),
                              ("unauthorized", "http01_unauthorized"), ("connection", "connection_failed"),
                              ("timeout", "request_timeout")):
            if keyword in detail:
                category = code
                break
        if result.returncode == 124:
            category = "process_deadline_reached"
        raise OperationError("tools_certbot:" + category)


def certificate_identity():
    """同步身份使用公共叶证书 DER 的 SHA256，不读取或输出私钥/完整证书。"""
    certificate_status()
    data = command("public_leaf_identity", ["openssl", "x509", "-in", str(PUBLIC_CERTIFICATE), "-outform", "DER"], timeout=5, binary=True).stdout
    return hashlib.sha256(data).hexdigest()


def certificate_record(name):
    """仅读取本任务的 pending/loaded 记录，非法或跨域记录直接失败。"""
    path = APPLICATION / "ops" / ("certificate-" + name + ".json")
    if not path.exists():
        return None
    if path.is_symlink() or path.stat().st_size > 4096:
        raise OperationError("invalid_certificate_state")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("domain") != DOMAIN or not re.fullmatch(r"[0-9a-f]{64}", data.get("identity", "")):
        raise OperationError("invalid_certificate_state")
    return data


def save_certificate_record(name, identity):
    """受限地持久保存待加载/已加载公共身份，失败时不能把新文件当已生效。"""
    private_directory(APPLICATION / "ops")
    path = APPLICATION / "ops" / ("certificate-" + name + ".json")
    if path.is_symlink():
        raise OperationError("certificate_state_symlink")
    temporary = path.with_name(path.name + ".new-" + secrets.token_hex(4))
    data = {"domain": DOMAIN, "identity": identity, "recorded_at": datetime.now(timezone.utc).isoformat()}
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(data, handle)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def confirm_loaded_certificate():
    """reload 后以真实源站 SNI/CA 验证叶证书身份，确认后才清 pending，不能仅看文件变更。"""
    identity = certificate_identity()
    context = ssl.create_default_context()
    for attempt in range(5):
        try:
            with socket.create_connection(("127.0.0.1", 443), timeout=5) as raw:
                with context.wrap_socket(raw, server_hostname=DOMAIN) as connection:
                    observed = hashlib.sha256(connection.getpeercert(binary_form=True)).hexdigest()
        except ssl.SSLCertVerificationError:
            raise OperationError("origin_certificate_validation_failed") from None
        except OSError as error:
            if attempt == 4:
                raise OperationError("origin_certificate_probe:" + type(error).__name__) from None
            time.sleep(0.3)
            continue
        if observed == identity:
            if certificate_identity() != identity:
                raise OperationError("public_certificate_changed_during_confirmation")
            save_certificate_record("loaded", identity)
            pending = APPLICATION / "ops/certificate-pending.json"
            if pending.exists():
                if certificate_record("pending")["identity"] != identity:
                    raise OperationError("pending_certificate_changed_during_confirmation")
                pending.unlink()
            return True
        if attempt < 4:
            time.sleep(0.3)
    raise OperationError("origin_still_serves_previous_certificate")


def prepare_tls(expected, report):
    """前像、现场和公网探针均通过后才创建独立证书；不安装 vhost、不 reload gateway。"""
    matches, source = expected_preimage(expected)
    report["expectedPreimage"] = matches
    if not matches or not clean_main_configuration():
        raise OperationError("main_configuration_preimage_or_clean_state_changed")
    report["context"] = context_preflight()
    report["renewal_environment"] = renewal_environment()
    if not report["renewal_environment"]["cron_active"] or not report["renewal_environment"]["cron_directory_available"]:
        raise OperationError("dedicated_renewal_scheduler_not_available")
    existing = certificate_status()
    report["certificate_before"] = existing
    report["backup"] = backup_preimage(source)
    with tls_lock():
        with owned_probe() as (url, body):
            with probe_deadline():
                report["http01_probe"] = verify_public_probe(url, body)
        report["http01_probe"]["owned_probe_cleaned"] = True
        if not expected_preimage(expected)[0]:
            raise OperationError("main_configuration_changed_during_http01_probe")
        if not existing.get("valid_more_than_30_days", False):
            request_certificate("certonly")
        report["certificate_after"] = certificate_status()
        if not report["certificate_after"].get("valid_more_than_30_days"):
            raise OperationError("certificate_not_ready_after_request")
    report["certificate_store"] = str(CERTIFICATE_STORE)
    report["registration_email_provided"] = False
    report["gateway_reloaded"] = False
    report["renewal_acceptance"] = "pending_consumer_installation_and_dry_run_after_deploy"


def renew_tools(report, dry_run=False):
    """供部署后专属定时器调用；只续工具证书，内容变化且 nginx-t 通过才 reload。"""
    report["context"] = context_preflight()
    with tls_lock():
        if not configuration_may_reload():
            raise OperationError("main_configuration_not_owned_stop_before_renewal")
        before = certificate_status()
        if not before["exists"]:
            raise OperationError("tools_certificate_not_prepared")
        previous = certificate_identity()
        request_error = None
        try:
            request_certificate("renew", dry_run=dry_run)
        except OperationError as error:
            # 失败前也可能已经写入证书；仍需记录公共文件新身份，不能丢掉下一轮重载消费者。
            request_error = error
        report["certificate_after"] = certificate_status()
        latest = certificate_identity()
        changed = previous != latest
        if changed and not dry_run:
            save_certificate_record("pending", latest)
        if request_error is not None:
            raise request_error
        pending, loaded = certificate_record("pending"), certificate_record("loaded")
        report["certificate_changed"] = changed
        needs_reload = changed or pending is not None or (loaded is not None and loaded["identity"] != latest)
        report["certificate_reload_pending"] = needs_reload
        report["gateway_reloaded"] = False
        if needs_reload and not dry_run:
            save_certificate_record("pending", latest)
            if not configuration_may_reload():
                raise OperationError("main_configuration_not_owned_stop_before_reload")
            command("nginx_test", ["docker", "exec", GATEWAY, "nginx", "-t"])
            command("nginx_reload", ["docker", "exec", GATEWAY, "nginx", "-s", "reload"])
            confirm_loaded_certificate()
            report["gateway_reloaded"] = True
            report["certificate_reload_pending"] = False


def save_scheduled_result(report):
    """仅保留最新一份有界消费者记录；不能把未完成或失败运行写成成功。"""
    private_directory(APPLICATION / "ops")
    data = (json.dumps(report, ensure_ascii=True, indent=2) + "\n").encode("utf-8")
    if len(data) > 32768:
        raise OperationError("scheduled_result_size_limit")
    target = APPLICATION / "ops/last-renewal.json"
    if target.is_symlink():
        raise OperationError("scheduled_result_symlink")
    temporary = target.with_name(target.name + ".new-" + secrets.token_hex(4))
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, target)


def main(arguments):
    """prepare-tls 必须传已知前像；renew/renew-check 仅由部署后专属消费者显式调用。"""
    if not arguments or arguments[0] not in ("prepare-tls", "renew", "renew-check", "scheduled-renew"):
        print(json.dumps({"operation": "rejected", "error": "unsupported_tls_operation"}))
        return 2
    operation = arguments[0]
    if (operation == "prepare-tls" and len(arguments) != 2) or (operation != "prepare-tls" and len(arguments) != 1):
        print(json.dumps({"operation": "rejected", "error": "invalid_tls_arguments"}))
        return 2
    report = {"operation": operation, "domain": DOMAIN, "errors": [],
              "started_at": datetime.now(timezone.utc).isoformat()}
    try:
        if operation == "scheduled-renew":
            save_scheduled_result({**report, "complete": False, "stage": "running"})
        if operation == "prepare-tls":
            prepare_tls(arguments[1], report)
        else:
            renew_tools(report, dry_run=operation == "renew-check")
    except OperationError as error:
        report["errors"].append(str(error))
    except (OSError, ValueError, KeyError, TypeError, http.client.HTTPException) as error:
        report["errors"].append("tools_tls:" + type(error).__name__)
    report["complete"] = not report["errors"]
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    if operation == "scheduled-renew":
        try:
            save_scheduled_result(report)
        except (OSError, OperationError) as error:
            report["errors"].append("scheduled_result:" + type(error).__name__)
            report["complete"] = False
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report["complete"] else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
