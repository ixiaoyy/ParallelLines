"""Read-only production catalog release preflight for the existing ops runner."""

import json
import re
import stat
import subprocess
import sys
from pathlib import Path

STATE = Path("/opt/parallellines/.deployment/ci-release-state.json")
SERVICES = {"api": "parallellines-api-1", "worker": "parallellines-worker-1"}
ID = re.compile(r"[0-9a-f]{64}")
REVISION = re.compile(r"[0-9a-f]{40}")
API_COMMAND = "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"


def query(label, args, timeout=10):
    """运行固定的只读命令；不回显容器命令的原始输出或错误。"""
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0 or len(result.stdout) > 16384:
        raise ValueError(label + "_failed")
    return result.stdout


def running_backend():
    """复用主站发布门禁的 Compose 标签条件，拒绝同服务的重复实例。"""
    lines = query("running_backend", [
        "docker", "ps", "--no-trunc",
        "--filter", "label=com.docker.compose.project=parallellines",
        "--filter", "label=com.docker.compose.oneoff=False",
        "--format", '{{.Label "com.docker.compose.service"}} {{.ID}} {{.Names}}',
    ]).splitlines()
    found = {}
    for line in lines:
        fields = line.split()
        if not fields or fields[0] not in SERVICES:
            continue
        service = fields[0]
        if (len(fields) != 3 or service in found or not ID.fullmatch(fields[1])
                or fields[2] != SERVICES[service]):
            raise ValueError("unexpected_backend_container_identity")
        found[service] = fields[1]
    if found.keys() != SERVICES.keys():
        raise ValueError("backend_container_missing")
    return found


def backend_receipt():
    """只读取既有私有回执的后端版本及两个容器 ID，不更改回执。"""
    parent, file = STATE.parent.lstat(), STATE.lstat()
    if not stat.S_ISDIR(parent.st_mode) or not stat.S_ISREG(file.st_mode):
        raise ValueError("release_receipt_invalid_path")
    with STATE.open("rb") as source:
        payload = source.read(16385)
    if len(payload) > 16384:
        raise ValueError("release_receipt_too_large")
    value = json.loads(payload)
    entry = value["components"]["backend"]
    ids = entry["containers"]
    revision = entry["revision"]
    if (value["schema"] != 1 or ids.keys() != SERVICES.keys() or not REVISION.fullmatch(revision)
            or not all(ID.fullmatch(container_id) for container_id in ids.values())):
        raise ValueError("backend_receipt_invalid")
    return revision, ids


def inventory(report):
    """核对常驻后端与只读数据库版本，任何中途容器或回执变化均失败。"""
    live = running_backend()
    revision, recorded = backend_receipt()
    report["backend_revision"] = revision
    report["containers"] = {
        service: {"live": live[service], "recorded": recorded[service],
                  "matches": live[service] == recorded[service]}
        for service in SERVICES
    }
    spec = json.loads(query("api_startup", [
        "docker", "inspect", "--format",
        '{"command":{{json .Config.Cmd}},"health":{{if .State.Health}}{{json .State.Health.Status}}{{else}}null{{end}}}',
        live["api"],
    ]))
    command = spec["command"]
    if len(command) != 3 or command[:2] != ["sh", "-c"] or " ".join(command[2].split()) != API_COMMAND:
        raise ValueError("api_command_requires_review")
    report["api_startup_matches"] = True
    if spec["health"] != "healthy":
        raise ValueError("api_not_healthy")
    # Alembic current 是当前生产 API 自带的只读命令，不运行 upgrade。
    output = query("alembic_current", ["docker", "exec", live["api"], "alembic", "current"], timeout=20)
    versions = re.findall(r"^([A-Za-z0-9_]{1,32})(?: \(head\))?\s*$", output, flags=re.MULTILINE)
    if len(versions) != 1:
        raise ValueError("database_revision_not_unique")
    if running_backend() != live or backend_receipt() != (revision, recorded):
        raise ValueError("backend_state_changed_during_inventory")
    report["alembic_current"] = versions[0]
    report["complete"] = True


def main(arguments):
    """入口仅接受固定只读操作，错误不包含生产输出。"""
    report = {"operation": "catalog-release-inventory", "read_only": True, "complete": False}
    if arguments == ["catalog-release-inventory"]:
        try:
            inventory(report)
        except (KeyError, OSError, TypeError, ValueError, subprocess.TimeoutExpired) as error:
            code = str(error) if type(error) is ValueError else ""
            report["error"] = code if re.fullmatch(r"[a-z_]+", code) else type(error).__name__
    else:
        report["error"] = "unsupported_operation"
    print(json.dumps(report))
    return 0 if report["complete"] else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
