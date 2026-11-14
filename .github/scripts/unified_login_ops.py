"""统一登录定向发布盘点：只输出运行身份与公开源码摘要，不读取凭据或展开 Compose。"""

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time


class OperationError(Exception):
    """稳定失败标识；不将命令原始 stderr 或环境值写入共享日志。"""


class Runner:
    """有界执行固定 argv，保留 stdout 供内部解析，不执行用户提供的命令。"""

    def __init__(self, seconds=160):
        self.deadline = time.monotonic() + seconds

    def run(self, args, timeout=15, accepted=(0,)):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise OperationError("operation_deadline")
        try:
            result = subprocess.run(args, capture_output=True, text=True,
                                    timeout=min(remaining, timeout), check=False)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise OperationError("command_" + type(error).__name__) from None
        if result.returncode not in accepted:
            raise OperationError("command_exit_" + str(result.returncode))
        if len(result.stdout) + len(result.stderr) > 2 * 1024 * 1024:
            raise OperationError("command_output_limit")
        return result.stdout


def file_metadata(path):
    """只采集明确的公开配置/事务文件身份；不递归目录、不读取环境文件或密钥。"""
    path = Path(path)
    if not path.exists():
        return {"path": str(path), "exists": False}
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 2 * 1024 * 1024:
        raise OperationError("public_metadata_file_invalid")
    stat = path.stat()
    return {"path": str(path), "exists": True, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "device": stat.st_dev, "inode": stat.st_ino, "bytes": stat.st_size}


def records(runner):
    """仅选择明确的平行线服务；模板从不包含 Config.Env 或完整 Label 集合。"""
    ids = runner.run(["docker", "ps", "-aq"]).split()
    if len(ids) > 64 or any(not re.fullmatch(r"[a-f0-9]{12,64}", value) for value in ids):
        raise OperationError("container_inventory_limit")
    if not ids:
        raise OperationError("containers_missing")
    fields = {
        "id": ".Id", "name": ".Name", "image_id": ".Image", "image": ".Config.Image",
        "running": ".State.Running", "workdir": ".Config.WorkingDir", "command": ".Config.Cmd",
        "entrypoint": ".Config.Entrypoint", "mounts": ".Mounts",
        "ports": ".HostConfig.PortBindings", "networks": ".NetworkSettings.Networks",
        "memory": ".HostConfig.Memory", "nano_cpus": ".HostConfig.NanoCpus",
    }
    template = "{" + ",".join(json.dumps(key) + ":{{json " + value + "}}" for key, value in fields.items())
    for key, label in {"project": "project", "service": "service", "working_dir": "project.working_dir",
                       "config_files": "project.config_files", "config-hash": "config-hash"}.items():
        template += "," + json.dumps("compose_" + key) + ':{{json (index .Config.Labels "com.docker.compose.' + label + '")}}'
    template += "}"
    values = [json.loads(line) for line in runner.run(["docker", "inspect", "--format", template, *ids]).splitlines()]
    selected = []
    for value in values:
        name = value["name"].lower()
        if "fable" in name:
            continue
        if (name.startswith("/parallellines-") or name.startswith("/pl-official-candidate-")
                or "chat-oidc" in name):
            # 网络只需要名称，不输出端点地址/MAC/网络内部状态。
            value["networks"] = sorted(value["networks"])
            selected.append(value)
    if not selected:
        raise OperationError("target_services_missing")
    return selected


def python_source(runner, container, paths):
    """读取容器中明确列出的公开应用文件摘要，不读取配置值或数据目录。"""
    program = ("import hashlib,json;from pathlib import Path;names=" + repr(paths) + ";"
               "out={name:hashlib.sha256(Path(name).read_bytes()).hexdigest() if Path(name).is_file() else None for name in names};"
               "print(json.dumps(out))")
    return json.loads(runner.run(["docker", "exec", container, "python", "-c", program], timeout=20))


def inventory(runner):
    """只读盘点五个发布目标和既有续载消费者，作为后续条件更新的前像。"""
    values = records(runner)
    evidence = {}
    for value in values:
        if not value["running"]:
            continue
        service = value.get("compose_service")
        name = value["name"].lower()
        if service == "api" and value.get("compose_project") == "parallellines":
            paths = ["api/v1/auth.py", "api/v1/auth_chat_sso.py", "api/v1/auth_unified.py", "api/v1/router.py",
                     "core/chat_sso.py", "core/config.py", "schemas/chat_sso.py", "schemas/unified_auth.py",
                     "services/chat_sso.py", "services/unified_auth.py"]
            evidence["main_api"] = python_source(runner, value["id"], ["/app/app/" + path for path in paths] + ["/app/uv.lock", "/app/pyproject.toml"])
        elif "openwebui" in name or "open-webui" in value["image"]:
            paths = ["main.py", "routers/auths.py", "routers/chats.py", "utils/oauth.py", "utils/auth.py",
                     "utils/main_unified_login.py", "utils/main_model_auth.py", "utils/main_model_silent_recovery.py",
                     "models/oauth_sessions.py", "socket/main.py"]
            evidence["chat_backend"] = python_source(runner, value["id"], ["/app/backend/open_webui/" + path for path in paths])
        elif "oidc" in name or service in ("identity", "chat-oidc"):
            program = ("const fs=require('fs'),c=require('crypto');const names=['server.mjs','config.mjs','identity-provider.mjs',"
                       "'main-bridge.mjs','sqlite-adapter.mjs','rp-session.mjs','package.json','package-lock.json'];"
                       "console.log(JSON.stringify(Object.fromEntries(names.map(n=>[n,fs.existsSync(n)?c.createHash('sha256').update(fs.readFileSync(n)).digest('hex'):null]))))")
            evidence["issuer_source"] = json.loads(runner.run(["docker", "exec", value["id"], "node", "-e", program], timeout=20))
        elif service in ("newapi", "new-api") or "newapi" in name:
            evidence["gateway_binary"] = runner.run(["docker", "exec", value["id"], "sha256sum", "/new-api"]).split()[0]
    main = Path("/opt/parallellines")
    community = main / ".deployment/community/93ca819f20f760b142cab9a320110879ff8179df"
    public_files = [main / "deploy/nginx/default.conf", main / "deploy/nginx/forum.conf",
                    community / "renew-community.py", community / "current.json",
                    Path("/etc/cron.d/parallellines-community-renew")]
    consumers = {"files": [file_metadata(path) for path in public_files]}
    state = community / "current.json"
    if state.is_file() and not state.is_symlink() and state.stat().st_size < 2 * 1024 * 1024:
        current = json.loads(state.read_text())
        consumers["community_renewal"] = current.get("renewal")
    tools = Path("/opt/parallellines-tools/ops")
    if tools.is_dir() and not tools.is_symlink():
        paths = sorted([*tools.glob("*.py"), *tools.glob("*.json")])
        if len(paths) > 64:
            raise OperationError("tools_consumer_limit")
        consumers["tools_files"] = [file_metadata(path) for path in paths]
    return {"complete": True, "read_only": True, "containers": values, "source_evidence": evidence,
            "consumer_metadata": consumers, "host_python": list(sys.version_info[:3])}


def main():
    """仅接受固定只读操作；发布激活须另行提供经过盘点的完整事务实现。"""
    if len(sys.argv) != 2 or sys.argv[1] != "inventory":
        raise OperationError("unsupported_operation")
    return inventory(Runner())


if __name__ == "__main__":
    try:
        print(json.dumps(main(), sort_keys=True, indent=2))
    except Exception as error:
        print(json.dumps({"complete": False, "error": str(error) if isinstance(error, OperationError) else type(error).__name__}))
        raise SystemExit(1) from None
