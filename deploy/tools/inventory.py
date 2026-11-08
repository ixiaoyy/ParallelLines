"""TOOLS-OPS inventory：仅收集授权生产主机的非敏感元数据，不部署、不写服务器文件。"""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request


REPOSITORY = Path("/opt/parallellines")
MAIN_CONFIG = REPOSITORY / "deploy/nginx/default.conf"
DOMAINS = ("pingxingxian.space", "tools.pingxingxian.space")
MAX_CONTAINERS = 64
MAX_GATEWAY_CANDIDATES = 8
MAX_CERTIFICATES = 12
OUTPUT_LIMIT = 1024 * 1024


class InventoryError(Exception):
    """只携带稳定错误码；不得把命令 stderr、环境或配置原文作为诊断输出。"""


class Reader:
    """限定命令耗时及返回量，结果只供明确的白名单解析器使用。"""

    def __init__(self):
        self.deadline = time.monotonic() + 150

    def run(self, label, arguments, timeout=12, accepted=(0,)):
        """执行固定只读 argv，返回结果；不使用 shell，不打印 stderr 或完整命令结果。"""
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise InventoryError("inventory_deadline_reached")
        try:
            result = subprocess.run(
                arguments, capture_output=True, text=True, check=False,
                timeout=min(timeout, remaining),
            )
        except subprocess.TimeoutExpired:
            raise InventoryError(label + ":timeout") from None
        except OSError as error:
            raise InventoryError(label + ":" + type(error).__name__) from None
        if result.returncode not in accepted:
            raise InventoryError(label + ":exit_" + str(result.returncode))
        if len(result.stdout) > OUTPUT_LIMIT:
            raise InventoryError(label + ":output_limit")
        return result


def summarize_nginx(text):
    """只保留 include、公开 vhost/证书路径及 ACME root；不输出 headers、私钥路径或配置正文。"""
    result = []
    source = None
    allowed = re.compile(r"^\s*(include|server_name|listen|root|ssl_certificate)\s+([^;]+);\s*(?:#.*)?$")
    for line_number, line in enumerate(text.splitlines(), 1):
        match = re.fullmatch(r"# configuration file ([^:\r\n]+):", line.strip())
        if match:
            source = match.group(1)
            continue
        match = allowed.match(line)
        if match:
            # 每种允许指令只包含路径、公开域名、IP 或 listen 选项；异常内容不下发。
            value = match.group(2).strip()
            if not re.fullmatch(r"[A-Za-z0-9_./*:\[\]$~ -]{1,1024}", value):
                continue
            directive = "document_directory" if match.group(1) == "root" else match.group(1)
            result.append({"source": source, "line": line_number,
                           "directive": directive, "value": value})
        elif re.fullmatch(r"\s*location\s+(?:\^~\s+)?/\.well-known/acme-challenge/\s*\{\s*", line):
            result.append({"source": source, "line": line_number,
                           "directive": "acme_location", "value": "/.well-known/acme-challenge/"})
        if len(result) > 256:
            raise InventoryError("nginx_summary_limit")
    return result


def container_inventory(reader):
    """只查询固定 Docker 字段；禁止完整 inspect、Config.Env、完整 label 或日志。"""
    identifiers = reader.run("docker_ps", ["docker", "ps", "--all", "--no-trunc", "--format", "{{.ID}}"])
    ids = identifiers.stdout.split()
    if not all(re.fullmatch(r"[0-9a-f]{64}", item) for item in ids):
        raise InventoryError("invalid_container_identifier")
    if len(ids) > MAX_CONTAINERS:
        raise InventoryError("container_inventory_limit")
    if not ids:
        raise InventoryError("no_containers")
    template = ('{"id":{{json .Id}},"name":{{json .Name}},"image":{{json .Config.Image}},'
                '"state":{{json .State.Status}},'
                '"service":{{json (index .Config.Labels "com.docker.compose.service")}},'
                '"project":{{json (index .Config.Labels "com.docker.compose.project")}},'
                '"networks":"{{range $name, $network := .NetworkSettings.Networks}}{{$name}} {{end}}"}')
    output = reader.run("docker_metadata", ["docker", "inspect", "--format", template] + ids)
    records = [json.loads(line) for line in output.stdout.splitlines() if line.strip()]
    for record in records:
        record["networks"] = record["networks"].split()
    return records


def gateway_inventory(reader, containers):
    """通过实际主站配置 bind mount 识别唯一 gateway；不根据默认容器名猜实例。"""
    candidates = [item for item in containers
                  if item.get("service") == "nginx" or "nginx" in item.get("name", "").lower()]
    candidates.sort(key=lambda item: item.get("project") != "parallellines")
    if len(candidates) > MAX_GATEWAY_CANDIDATES:
        raise InventoryError("gateway_candidate_limit")
    found = []
    for candidate in candidates:
        mounts = json.loads(reader.run("gateway_mounts", ["docker", "inspect", "--format", "{{json .Mounts}}", candidate["id"]]).stdout)
        if any(mount.get("Destination") == "/etc/nginx/conf.d/default.conf"
               and mount.get("Source") == str(MAIN_CONFIG) for mount in mounts):
            found.append((candidate, mounts))
    if len(found) != 1:
        raise InventoryError("gateway_not_unique:" + str(len(found)))
    gateway, mounts = found[0]
    if gateway["state"] != "running":
        raise InventoryError("gateway_not_running")
    selected_mounts = [{key: mount.get(key) for key in ("Type", "Source", "Destination", "RW")}
                       for mount in mounts if mount.get("Destination", "").startswith(
                           ("/etc/nginx", "/etc/letsencrypt", "/var/www/certbot"))]
    # nginx -T 的原文仅供本机白名单解析，不写文件、不打印 stderr 或完整配置。
    raw = reader.run("nginx_config_inventory", ["docker", "exec", gateway["id"], "nginx", "-T"], timeout=15)
    return {"name": gateway["name"], "image": gateway["image"],
            "networks": gateway["networks"], "mounts": selected_mounts,
            "nginx": summarize_nginx(raw.stdout)}


def git_inventory(reader):
    """只核当前 HEAD 和 default.conf 的 tracked/dirty/摘要，不查询其他工作树内容。"""
    base = ["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-C", str(REPOSITORY)]
    head = reader.run("main_head", base + ["rev-parse", "--verify", "HEAD"]).stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", head):
        raise InventoryError("invalid_main_head")
    name = "deploy/nginx/default.conf"
    tracked = reader.run("main_config_tracked", base + ["ls-files", "--error-unmatch", "--", name], accepted=(0, 1)).returncode == 0
    worktree = reader.run("main_config_worktree", base + ["diff", "--no-ext-diff", "--quiet", "--", name], accepted=(0, 1)).returncode
    staged = reader.run("main_config_index", base + ["diff", "--no-ext-diff", "--cached", "--quiet", "--", name], accepted=(0, 1)).returncode
    with MAIN_CONFIG.open("rb") as handle:
        source = handle.read(2 * 1024 * 1024 + 1)
    if len(source) > 2 * 1024 * 1024:
        raise InventoryError("main_config_size_limit")
    return {"head": head, "config_path": str(MAIN_CONFIG), "config_tracked": tracked,
            "config_dirty": not tracked or bool(worktree or staged),
            "config_sha256": hashlib.sha256(source).hexdigest()}


def storage_inventory():
    """只读取指定部署目录所在文件系统容量和系统负载，不枚举用户文件。"""
    disks = []
    for path in ("/", "/opt/parallellines", "/opt/parallellines-tools", "/data"):
        if not Path(path).exists():
            disks.append({"path": path, "exists": False})
            continue
        usage = shutil.disk_usage(path)
        disks.append({"path": path, "exists": True, "total": usage.total,
                      "used": usage.used, "free": usage.free})
    return {"load_average": os.getloadavg(), "cpu_count": os.cpu_count(), "disks": disks}


def certificate_inventory(reader, gateway, containers):
    """读取公共证书的 DNS SAN 与续期配置路径；不读取私钥、账户或 DNS 凭据。"""
    root = next((Path(mount["Source"]) for mount in gateway["mounts"]
                 if mount["Destination"] == "/etc/letsencrypt"), None)
    result = {"host_certbot_path": shutil.which("certbot"), "openssl_path": shutil.which("openssl"),
              "acme_mounts": [mount for mount in gateway["mounts"] if mount["Destination"] == "/var/www/certbot"],
              "certificates": [], "renewal_config_paths": [], "renewal_hook_directories": []}
    certbot = [item for item in containers if item.get("service") == "certbot"]
    result["certbot_containers"] = [{"name": item["name"], "image": item["image"], "state": item["state"]} for item in certbot]
    for item in certbot[:2]:
        if item["state"] == "running":
            version = reader.run("certbot_version", ["docker", "exec", item["id"], "certbot", "--version"], timeout=5)
            result.setdefault("certbot_versions", []).append(version.stdout.strip()[:120])
    if root is None:
        raise InventoryError("certificate_mount_not_found")
    result["certificate_store"] = str(root)
    configs = sorted((root / "renewal").glob("*.conf"))
    result["renewal_config_paths"] = [str(path) for path in configs[:MAX_CERTIFICATES]]
    result["renewal_config_truncated"] = len(configs) > MAX_CERTIFICATES
    result["renewal_hook_directories"] = [str(root / "renewal-hooks" / name)
                                          for name in ("pre", "deploy", "post")
                                          if (root / "renewal-hooks" / name).is_dir()]
    for directory in sorted((root / "live").glob("*"))[:MAX_CERTIFICATES]:
        public = directory / "fullchain.pem"
        # 仅解析公共 fullchain/cert 文件；不得跟随异常链接读取 key/env 文件。
        if not public.is_file() or not re.fullmatch(r"(?:fullchain|cert)\d*\.pem", public.resolve().name):
            continue
        output = reader.run("public_certificate", ["openssl", "x509", "-in", str(public), "-noout", "-ext", "subjectAltName", "-enddate"], timeout=5)
        result["certificates"].append({"name": directory.name,
            "dns_names": re.findall(r"DNS:([A-Za-z0-9*_.-]+)", output.stdout),
            "expires": next((line.partition("=")[2] for line in output.stdout.splitlines() if line.startswith("notAfter=")), None)})
    return result


def public_dns_inventory(reader):
    """向公共 DNS-over-HTTPS 查询固定公开域名，单次请求 4 秒、响应最多 64 KiB，不重试。"""
    rows = []
    for domain in DOMAINS:
        for kind in ("A", "AAAA"):
            if time.monotonic() >= reader.deadline:
                raise InventoryError("inventory_deadline_reached")
            query = urllib.parse.urlencode({"name": domain, "type": kind})
            request = urllib.request.Request("https://dns.google/resolve?" + query,
                                             headers={"Accept": "application/dns-json"})
            try:
                with urllib.request.urlopen(request, timeout=4) as response:
                    body = response.read(65537)
                if len(body) > 65536:
                    raise InventoryError("dns_response_limit")
                data = json.loads(body)
            except (OSError, ValueError) as error:
                raise InventoryError("public_dns:" + type(error).__name__) from None
            answers = [{"type": item.get("type"), "data": item.get("data")}
                       for item in data.get("Answer", []) if item.get("type") in (1, 5, 28)]
            rows.append({"name": domain, "type": kind, "resolver": "dns.google DoH",
                         "status": data.get("Status"), "answers": answers})
    return rows


def collect_section(report, name, callback):
    """独立只读项各自报告失败，保留其它有效结果；任一失败仍令整个 inventory 非零退出。"""
    try:
        value = callback()
        report[name] = value
        return value
    except InventoryError as error:
        report["errors"].append(name + ":" + str(error))
    except (OSError, ValueError, KeyError, TypeError) as error:
        # 不透出异常中的原始文件内容、命令输出、代理配置或凭据。
        report["errors"].append(name + ":" + type(error).__name__)
    return None


def main(arguments):
    """只接受固定 inventory 操作；任何其他参数在执行命令前失败。"""
    if arguments != ["inventory"]:
        print(json.dumps({"operation": "rejected", "error": "inventory_is_the_only_supported_operation"}))
        return 2
    reader = Reader()
    report = {"operation": "inventory", "target": str(REPOSITORY), "read_only": True, "errors": []}
    collect_section(report, "storage", storage_inventory)
    collect_section(report, "main_source", lambda: git_inventory(reader))
    containers = collect_section(report, "containers", lambda: container_inventory(reader))
    if containers is not None:
        gateway = collect_section(report, "gateway", lambda: gateway_inventory(reader, containers))
        if gateway is not None:
            collect_section(report, "tls", lambda: certificate_inventory(reader, gateway, containers))
        else:
            report["skipped"] = ["tls:gateway_unavailable"]
    else:
        report["skipped"] = ["gateway:containers_unavailable", "tls:gateway_unavailable"]
    collect_section(report, "public_dns", lambda: public_dns_inventory(reader))
    report["complete"] = not report["errors"]
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report["complete"] else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
