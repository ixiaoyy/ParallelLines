"""独立工具站的只读健康检查；不依赖部署进程、外部 Python 包或可写服务器状态。"""

import contextlib
import html
import http.client
import json
import re
import signal
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request


GATEWAY = "parallellines-nginx-1"
TOOLS_CONTAINER = "parallellines-tools-static"
NETWORK = "parallellines_default"
TOOLS_DOMAIN = "tools.pingxingxian.space"
TOOLS_SOURCE = "https://github.com/ixiaoyy/parallel-lines-tools"
EXPECTED_TITLE = "平行线工具箱"
TOTAL_SECONDS = 70
ITEM_SECONDS = 6
BODY_LIMIT = 1024 * 1024


class HealthError(Exception):
    """仅携带稳定错误码，不包含响应正文、stderr、环境或凭据。"""


class Budget:
    """限定当前整次检查和每一项操作的资源时限。"""

    def __init__(self):
        self.deadline = time.monotonic() + TOTAL_SECONDS

    def remaining(self):
        """返回当前项可用秒数；总预算用尽时立即失败，不继续建立连接。"""
        value = self.deadline - time.monotonic()
        if value <= 0:
            raise HealthError("health_budget_exhausted")
        return min(ITEM_SECONDS, value)


def _alarm_expired(_signal, _frame):
    """中断本检查进程中的超时操作，不给服务或容器发送信号。"""
    raise HealthError("check_timeout")


@contextlib.contextmanager
def check_deadline(seconds):
    """在已确认的 Linux 主机上限制 DNS、连接和整个读取阶段，退出后恢复信号状态。"""
    if not hasattr(signal, "setitimer") or not hasattr(signal, "ITIMER_REAL"):
        raise HealthError("linux_deadline_support_required")
    started = time.monotonic()
    previous_handler = signal.signal(signal.SIGALRM, _alarm_expired)
    previous_delay, previous_interval = signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_delay > 0:
            remaining = max(0.001, previous_delay - (time.monotonic() - started))
            signal.setitimer(signal.ITIMER_REAL, remaining, previous_interval)


def command(arguments, budget):
    """执行固定的只读 argv，限时返回 stdout；不打印 stderr，也不使用 shell。"""
    try:
        result = subprocess.run(arguments, capture_output=True, timeout=budget.remaining(), check=False)
    except subprocess.TimeoutExpired:
        raise HealthError("command_timeout") from None
    except OSError as error:
        raise HealthError("command_" + type(error).__name__) from None
    if result.returncode != 0:
        raise HealthError("command_exit_" + str(result.returncode))
    if len(result.stdout) > BODY_LIMIT:
        raise HealthError("command_output_limit")
    return result.stdout


def container_metadata(name, budget, require_tools_source=False):
    """只读镜像身份、公开来源/版本、运行状态与网络；不读取 Env、完整 labels 或日志。"""
    template = ('{"image_id":{{json .Image}},"running":{{json .State.Running}},'
                '"source":{{json (index .Config.Labels "org.opencontainers.image.source")}},'
                '"revision":{{json (index .Config.Labels "org.opencontainers.image.revision")}},'
                '"networks":"{{range $name, $network := .NetworkSettings.Networks}}{{$name}} {{end}}"}')
    try:
        record = json.loads(command(["docker", "inspect", "--format", template, name], budget))
    except (ValueError, UnicodeError):
        raise HealthError("invalid_container_metadata") from None
    networks = record.get("networks")
    if not isinstance(networks, str):
        raise HealthError("invalid_container_networks")
    networks = networks.split()
    if record.get("running") is not True:
        raise HealthError("container_not_running")
    if NETWORK not in networks:
        raise HealthError("gateway_network_missing")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", record.get("image_id") or ""):
        raise HealthError("invalid_image_identity")
    if require_tools_source:
        if record.get("source") != TOOLS_SOURCE:
            raise HealthError("tools_source_label_mismatch")
        if not re.fullmatch(r"[0-9a-f]{40}", record.get("revision") or ""):
            raise HealthError("invalid_tools_revision")
    return {"container": name, "image_id": record["image_id"],
            "source": record.get("source"), "revision": record.get("revision"),
            "networks": networks, "running": True}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """健康入口必须直接返回目标内容，不跟随重定向掩盖错误 vhost 或外部落点。"""

    def redirect_request(self, _request, _fp, _code, _message, _headers, _new_url):
        return None


def public_get(url, budget, read_body=False):
    """固定公开 GET；默认不读取正文，不使用身份、Cookie 或重试。"""
    request = urllib.request.Request(url, method="GET", headers={"User-Agent": "ParallelLinesToolsHealth/1"})
    opener = urllib.request.build_opener(NoRedirect())
    try:
        with opener.open(request, timeout=budget.remaining()) as response:
            status = response.status
            body = response.read(BODY_LIMIT + 1) if read_body else b""
    except urllib.error.HTTPError as error:
        raise HealthError("http_status_" + str(error.code)) from None
    except urllib.error.URLError as error:
        raise HealthError("http_" + type(error.reason).__name__) from None
    if status != 200:
        raise HealthError("http_status_" + str(status))
    if len(body) > BODY_LIMIT:
        raise HealthError("http_body_limit")
    return body


class OriginHTTPSConnection(http.client.HTTPSConnection):
    """直接连接宿主机 443，但按工具域名发送 SNI 并执行标准 CA/主机名验证。"""

    def connect(self):
        raw = socket.create_connection(("127.0.0.1", 443), timeout=self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=TOOLS_DOMAIN)
        except Exception:
            raw.close()
            raise


def gateway_http(budget):
    """独立验证现有 gateway 的本机 HTTP 健康入口，预期保留原来的 204。"""
    connection = http.client.HTTPConnection("127.0.0.1", 80, timeout=budget.remaining())
    try:
        connection.request("GET", "/nginx-health", headers={"Host": "pingxingxian.space"})
        response = connection.getresponse()
        status = response.status
        response.read(1)
    finally:
        connection.close()
    if status != 204:
        raise HealthError("gateway_http_status_" + str(status))
    return {"status": status}


def tools_container_http(budget):
    """只在本次已确认来源的工具容器内读取固定 healthz，不修改其状态。"""
    body = command(["docker", "exec", TOOLS_CONTAINER, "wget", "-q", "-O", "-", "http://127.0.0.1/healthz"], budget)
    if body.strip() != b"ok":
        raise HealthError("tools_container_health_body_mismatch")
    return {"body_matches": True}


def tools_origin_tls(budget):
    """从源站环回验证独立工具 vhost 与实际 TLS 证书，不能只依赖 CDN 表面可达。"""
    connection = OriginHTTPSConnection(TOOLS_DOMAIN, timeout=budget.remaining(), context=ssl.create_default_context())
    try:
        connection.request("GET", "/healthz", headers={"Host": TOOLS_DOMAIN})
        response = connection.getresponse()
        status = response.status
        body = response.read(33)
    finally:
        connection.close()
    if status != 200:
        raise HealthError("origin_http_status_" + str(status))
    if body.strip() != b"ok":
        raise HealthError("origin_health_body_mismatch")
    return {"status": status, "body_matches": True, "ca_verified": True,
            "sni": TOOLS_DOMAIN, "connect_address": "127.0.0.1:443"}


def tools_public_health(budget):
    """验证公网工具入口的固定正文，正文只参与比较、不写日志。"""
    body = public_get("https://" + TOOLS_DOMAIN + "/healthz", budget, read_body=True)
    if body.strip() != b"ok":
        raise HealthError("public_health_body_mismatch")
    return {"status": 200, "body_matches": True}


def tools_public_title(budget):
    """验证工具首页的已约定标题，避免将错误站点的通用 200 当作成功。"""
    body = public_get("https://" + TOOLS_DOMAIN + "/", budget, read_body=True)
    match = re.search(rb"<title\b[^>]*>([^<]{0,4096})</title\s*>", body, re.IGNORECASE)
    if match is None:
        raise HealthError("public_title_missing")
    try:
        actual = html.unescape(match.group(1).decode("utf-8")).strip()
    except UnicodeError:
        raise HealthError("public_title_encoding") from None
    if actual != EXPECTED_TITLE:
        raise HealthError("public_title_mismatch")
    return {"status": 200, "title_matches": True}


def collect_check(report, name, budget, callback):
    """每项失败明确保留，其它独立只读检查继续；不打印失败对象的原始内容。"""
    try:
        with check_deadline(budget.remaining()):
            details = callback()
        report["checks"].append({"name": name, "ok": True, **(details or {})})
        return True
    except HealthError as error:
        code = str(error)
    except (OSError, ValueError, KeyError, TypeError, http.client.HTTPException) as error:
        code = type(error).__name__
    report["checks"].append({"name": name, "ok": False, "error": code})
    report["errors"].append(name + ":" + code)
    return False


def run_health():
    """执行固定、有限的检查矩阵，返回结构化报告；不做恢复、reload 或任何写操作。"""
    budget = Budget()
    report = {"operation": "health", "read_only": True, "healthy": False, "checks": [], "errors": []}
    gateway_ok = collect_check(report, "gateway_container", budget, lambda: container_metadata(GATEWAY, budget))
    if gateway_ok:
        collect_check(report, "gateway_configuration", budget,
                      lambda: {"valid": command(["docker", "exec", GATEWAY, "nginx", "-t"], budget) is not None})
    else:
        report["checks"].append({"name": "gateway_configuration", "ok": False, "skipped": "gateway_container_failed"})
    collect_check(report, "gateway_http", budget, lambda: gateway_http(budget))
    tools_ok = collect_check(report, "tools_container", budget,
                             lambda: container_metadata(TOOLS_CONTAINER, budget, require_tools_source=True))
    if tools_ok:
        collect_check(report, "tools_container_http", budget, lambda: tools_container_http(budget))
    else:
        report["checks"].append({"name": "tools_container_http", "ok": False, "skipped": "tools_container_failed"})
    collect_check(report, "tools_origin_tls", budget, lambda: tools_origin_tls(budget))
    collect_check(report, "tools_public_health", budget, lambda: tools_public_health(budget))
    collect_check(report, "tools_public_title", budget, lambda: tools_public_title(budget))
    public_routes = (
        ("main_health", "https://pingxingxian.space/healthz"),
        ("chat_health", "https://chat.pingxingxian.space/health"),
        ("oidc_discovery", "https://pingxingxian.space/auth/oidc/.well-known/openid-configuration"),
        ("api_status", "https://api.pingxingxian.space/api/status"),
    )
    for name, url in public_routes:
        collect_check(report, name, budget, lambda endpoint=url: {"status": 200, "checked": public_get(endpoint, budget) == b""})
    report["healthy"] = not report["errors"] and all(item["ok"] for item in report["checks"])
    return report


def main(arguments):
    """只接受 health 操作，向 stdout 输出 JSON；未部署或检查失败时返回非零。"""
    if arguments != ["health"]:
        print(json.dumps({"operation": "rejected", "healthy": False, "checks": [],
                          "errors": ["health_is_the_only_supported_operation"]}))
        return 2
    report = run_health()
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report["healthy"] else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
