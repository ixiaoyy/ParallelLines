"""Catalog release diagnostics and a guarded backend-receipt repair."""

import hashlib
import io
import json
import os
import re
import stat
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

REPO = Path("/opt/parallellines")
STATE = Path("/opt/parallellines/.deployment/ci-release-state.json")
APP_PATHS = ("app", "alembic", "alembic.ini", "pyproject.toml", "uv.lock")
EXPECTED_RELEASE = "25fb43e0c6a7015acdcc063e5fc5ec5f20ed7e35"
EXPECTED_API = "77be24efc3f9770820b49763020b5cfe3919749ab798d90bf6b8038673288d85"
MYSQL_IMAGE = "mysql:8.4@sha256:563602a18ffd5be220968e8508d84c9dcd80fbffe69e28af51572db29e3285b2"
MYSQL_DATA = "/opt/parallellines/var/mysql"
MYSQL_COMMAND = [
    "--character-set-server=utf8mb4", "--collation-server=utf8mb4_unicode_ci",
    "--max-connections=30", "--innodb-buffer-pool-size=256M", "--event-scheduler=OFF",
]
SERVICES = {"api": "parallellines-api-1", "worker": "parallellines-worker-1"}
ID = re.compile(r"[0-9a-f]{64}")
REVISION = re.compile(r"[0-9a-f]{40}")
API_COMMAND = "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"


def query(label, args, timeout=10, max_output=16384):
    """运行固定的只读命令；不回显容器命令的原始输出或错误。"""
    result = subprocess.run(args, capture_output=True, encoding="utf-8", timeout=timeout)
    if result.returncode != 0 or len(result.stdout) > max_output:
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


def canonical_source():
    """只读取已批准 Git 版本中 Dockerfile 复制的公开应用文件，不读工作树。"""
    result = subprocess.run(
        ["git", "-c", f"safe.directory={REPO}", "-C", str(REPO),
         "archive", "--format=tar", EXPECTED_RELEASE, *(f"apps/api/{name}" for name in APP_PATHS)],
        capture_output=True, timeout=25,
    )
    if result.returncode != 0 or len(result.stdout) > 32 * 1024 * 1024:
        raise ValueError("trusted_release_archive_failed")
    files = {}
    with tarfile.open(fileobj=io.BytesIO(result.stdout), mode="r:") as archive:
        for obj in archive:
            if obj.isdir():
                continue
            if not obj.isfile() or not obj.name.startswith("apps/api/") or obj.size > 8 * 1024 * 1024:
                raise ValueError("trusted_release_archive_member_invalid")
            stream = archive.extractfile(obj)
            files[obj.name.removeprefix("apps/api/")] = hashlib.sha256(stream.read()).hexdigest()
    if not files or len(files) > 800:
        raise ValueError("trusted_release_archive_file_count")
    return files


# 比较范围对应当前 Dockerfile 的三个 COPY，排除运行时生成的字节码。
# 不输出文件内容、配置、环境或依赖安装目录。
COMPARE = """
import hashlib,json,sys
from pathlib import Path
root=Path('/app')
expected=json.load(sys.stdin)
files=[]
for name in ('app','alembic','alembic.ini','pyproject.toml','uv.lock'):
    base=root/name
    if base.is_symlink():
        raise ValueError('invalid source root')
    for item in (base.rglob('*') if base.is_dir() else (base,)):
        if '__pycache__' in item.parts:
            continue
        if item.is_symlink() or (item.is_file() and item.stat().st_size > 8388608):
            raise ValueError('invalid source file')
        if item.is_file():
            files.append(item)
            if len(files) > 800:
                raise ValueError('source count exceeded')
actual={item.relative_to(root).as_posix():hashlib.sha256(item.read_bytes()).hexdigest() for item in files}
missing=sorted(expected.keys()-actual.keys())
extra=sorted(actual.keys()-expected.keys())
changed=sorted(k for k in expected.keys() & actual.keys() if expected[k]!=actual[k])
print(json.dumps({'matches':not(missing or extra or changed),'files':len(files),
                  'missing_count':len(missing),'extra_count':len(extra),'changed_count':len(changed),
                  'known_differences':(missing+changed)[:20]}))
"""


def runtime_source(container, expected):
    """只在已定位的常驻容器内比较应用、迁移与依赖锁文件。"""
    result = subprocess.run(
        ["docker", "exec", "-i", container, "python", "-I", "-B", "-c", COMPARE],
        input=json.dumps(expected), text=True, capture_output=True, timeout=25,
    )
    if result.returncode != 0 or len(result.stdout) > 8192:
        raise ValueError("read_runtime_source_failed")
    return json.loads(result.stdout)


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
    report["alembic_current"] = versions[0]
    if revision != EXPECTED_RELEASE:
        raise ValueError("backend_reference_revision_changed")
    source = canonical_source()
    report["source_verification"] = {
        service: runtime_source(container, source) for service, container in live.items()
    }
    if running_backend() != live or backend_receipt() != (revision, recorded):
        raise ValueError("backend_state_changed_during_inventory")
    report["complete"] = True


def trusted_helper(path, alias):
    """从固定提交加载现有发布锁和登记逻辑，不执行可变工作树中的版本。"""
    source = query("trusted_release_helper", [
        "git", "-c", f"safe.directory={REPO}", "-C", str(REPO),
        "show", f"{EXPECTED_RELEASE}:{path}",
    ], max_output=65536)
    namespace = {"__name__": alias}
    exec(compile(source, path, "exec"), namespace)
    return namespace


def inspect_release_components(report):
    """只输出有差异的组件和服务名，不回显回执和其他容器资料。"""
    native = trusted_helper(".github/scripts/deploy_artifacts.py", "catalog_native_release")
    entries = native["read_release_state"](REPO)
    live = native["running_release_containers"]()
    forum = (REPO / ".deployment/forum-enabled").exists()
    report["component_drift"] = {}
    for component, entry in entries.items():
        names = native["services_for"](component, forum)
        changes = [name for name in names if entry is None or entry["containers"].get(name) != live.get(name)]
        if changes:
            report["component_drift"][component] = changes


def describe(report):
    """同一次只读盘点连同发布门禁的组件范围一起报告。"""
    inventory(report)
    report["complete"] = False
    inspect_release_components(report)
    report["complete"] = True


def verify_database(container, report):
    """用固定 Compose 前像核对 MySQL 元数据；不接触数据目录或环境变量。"""
    if not container or not ID.fullmatch(container):
        raise ValueError("database_container_missing")
    spec = json.loads(query("database_runtime", [
        "docker", "inspect", "--format",
        '{"name":{{json .Name}},"image":{{json .Config.Image}},"image_id":{{json .Image}},'
        '"command":{{json .Config.Cmd}},"ports":{{json .HostConfig.PortBindings}},'
        '"health":{{if .State.Health}}{{json .State.Health.Status}}{{else}}null{{end}},'
        '"mounts":[{{range $i,$m := .Mounts}}{{if $i}},{{end}}'
        '{"source":{{json $m.Source}},"target":{{json $m.Destination}},'
        '"type":{{json $m.Type}},"rw":{{json $m.RW}}}{{end}}]}',
        container,
    ]))
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", spec["image_id"]):
        raise ValueError("database_image_identity_invalid")
    digests = json.loads(query("database_image_digest", [
        "docker", "image", "inspect", "--format", "{{json .RepoDigests}}", spec["image_id"],
    ]))
    expected_digest = MYSQL_IMAGE.split("@", 1)[1]
    report["database_spec"] = {
        "container": spec["name"] == "/parallellines-db-1",
        "healthy": spec["health"] == "healthy",
        "image": spec["image"] == MYSQL_IMAGE and any(
            digest in (f"mysql@{expected_digest}", f"docker.io/library/mysql@{expected_digest}")
            for digest in digests or []
        ),
        "data_mount": spec["mounts"] == [
            {"source": MYSQL_DATA, "target": "/var/lib/mysql", "type": "bind", "rw": True}
        ],
        "command": spec["command"] == MYSQL_COMMAND,
        "ports": not spec["ports"],
    }
    if not all(report["database_spec"].values()):
        raise ValueError("database_configuration_differs_from_release")


def repair(report):
    """持已有发布锁，备份后只同步已复核的 API 和 MySQL 身份。"""
    native = trusted_helper(".github/scripts/deploy_artifacts.py", "catalog_native_release")
    tls = trusted_helper("deploy/nginx/run-deploy-with-tls-lock.py", "catalog_native_lock")
    with tls["existing_tls_lock"](tls["LOCK_FILE"]):
        observed = {}
        inventory(observed)
        if (observed["alembic_current"] != "0114_add_four_browser_games"
                or observed["containers"]["api"]["live"] != EXPECTED_API
                or not observed["containers"]["worker"]["matches"]
                or not all(item["matches"] for item in observed["source_verification"].values())):
            raise ValueError("backend_repair_preimage_changed")
        entries = native["read_release_state"](REPO)
        before = STATE.read_bytes()
        live = native["running_release_containers"]()
        forum = (REPO / ".deployment/forum-enabled").exists()
        if entries["compose"] is None or entries["compose"]["revision"] != EXPECTED_RELEASE:
            raise ValueError("compose_reference_revision_changed")
        verify_database(live.get("db"), report)
        changes = []
        admitted = {"backend": {"api"}, "compose": {"db"}}
        effective = {}
        # 只允许本批的 API/DB 变化；Redis、certbot、Web、圈子和网关仍受原门禁保护。
        for component, entry in entries.items():
            if entry is None:
                raise ValueError("release_component_receipt_missing")
            expected = {name: live.get(name) for name in native["services_for"](component, forum)}
            effective[component] = expected
            old = entry["containers"]
            differences = {name for name in old.keys() | expected.keys() if old.get(name) != expected.get(name)}
            if differences - admitted.get(component, set()):
                raise ValueError("another_release_component_drift")
            if differences:
                changes.append(component)
        if not changes:
            native["release_snapshot"](REPO)
            report.update({"complete": True, "repaired_components": []})
            return
        expected_live = {name: observed["containers"][name]["live"] for name in SERVICES}
        expected_recorded = {name: observed["containers"][name]["recorded"] for name in SERVICES}
        if (running_backend() != expected_live
                or backend_receipt() != (EXPECTED_RELEASE, expected_recorded)):
            raise ValueError("backend_repair_preimage_changed")
        # 使用新的 0600 备份，不覆盖原有恢复记录。
        with tempfile.NamedTemporaryFile("wb", dir=STATE.parent, prefix="ci-release-state.catalog-before-",
                                         suffix=".json", delete=False) as backup:
            backup.write(before)
            backup.flush()
            os.fsync(backup.fileno())
            report["receipt_backup"] = Path(backup.name).name
        if STATE.read_bytes() != before or native["running_release_containers"]() != live:
            raise ValueError("backend_repair_preimage_changed")
        native["record_release"](REPO, changes, EXPECTED_RELEASE)
        after = native["read_release_state"](REPO)
        expected_after = {
            key: ({"revision": EXPECTED_RELEASE, "containers": effective[key]} if key in changes else entry)
            for key, entry in entries.items()
        }
        if after != expected_after:
            raise ValueError("backend_repair_verification_failed")
        native["release_snapshot"](REPO)
        report.update({"complete": True, "repaired_components": changes, "release_revision": EXPECTED_RELEASE})


def main(arguments):
    """入口只允许固定操作，错误不回显现场配置或命令输出。"""
    operations = {"catalog-release-inventory": describe, "catalog-record-backend": repair}
    operation = arguments[0] if len(arguments) == 1 else ""
    report = {"operation": operation, "read_only": operation != "catalog-record-backend", "complete": False}
    if operation in operations:
        try:
            operations[operation](report)
        except Exception as error:
            code = str(error) if type(error) is ValueError else ""
            report["error"] = code if re.fullmatch(r"[a-z_]+", code) else type(error).__name__
    else:
        report["error"] = "unsupported_operation"
    print(json.dumps(report))
    return 0 if report["complete"] else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
