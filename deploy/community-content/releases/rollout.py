"""圈子海外版本的固定覆盖、单实例切换及独立恢复。"""

from __future__ import annotations

import copy
import fcntl
import http.client
import json
import socket
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

RELEASE_BASE = Path("/opt/parallellines/.deployment/community-content")
NAME = "parallellines-community-content"
PREFIX = "io.parallellines.community-content."
RELEASES = {
    "20261117-overseas": (
        ("app/services/community_schedule.py", "app/services/scheduled_content.py",
         "app/services/overseas_content.py"),
        "overseas_pending_tasks_skip_safely",
    ),
    "20261117-overseas-render": (
        ("app/services/scheduled_content.py",),
        "previous_release_restored",
    ),
}


class RolloutError(RuntimeError):
    """只保存稳定错误码，不输出 Docker 配置、环境值或原始错误内容。"""


def select_release(directory: Path) -> None:
    """从已批准的绝对版本目录选定覆盖清单和恢复目标，不接收自定义路径。"""

    if directory.parent != RELEASE_BASE or directory.name not in RELEASES:
        raise RolloutError("wrong_fixed_release_directory")
    global ROOT, RELEASE, FILES, RECOVERY_RESULT, RECORD
    global IMAGE, BASE_TAG, RECOVERY_IMAGE, CANDIDATE, RECOVERY, BACKUP, FAILED
    ROOT, RELEASE = directory, directory.name
    FILES, RECOVERY_RESULT = RELEASES[RELEASE]
    IMAGE = f"{NAME}:{RELEASE}"
    BASE_TAG = f"{NAME}-base:{RELEASE}"
    RECOVERY_IMAGE = f"{NAME}:{RELEASE}-recovery"
    CANDIDATE = f"{NAME}-candidate-{RELEASE}"
    RECOVERY = f"{NAME}-recovery-{RELEASE}"
    BACKUP = f"{NAME}-before-{RELEASE}"
    FAILED = f"{NAME}-failed-{RELEASE}"
    RECORD = ROOT / "rollout.json"


def run(step: str, argv: list[str], *, timeout: int = 30) -> str:
    """有界执行固定命令；敏感 inspect 输出只在内存消费，不转储日志或文件。"""

    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RolloutError(f"{step}:{type(exc).__name__}") from exc
    if result.returncode:
        raise RolloutError(f"{step}:exit_{result.returncode}")
    return result.stdout


def inspect(name: str) -> dict | None:
    """按精确名称/ID读取单个本地容器；不读取真实环境文件。"""

    ids = run(
        "find_container",
        ["docker", "ps", "-aq", "--no-trunc", "--filter", f"name=^/{name}$"],
    ).splitlines()
    if not ids:
        return None
    if len(ids) != 1:
        raise RolloutError("container_name_not_unique")
    return json.loads(run("inspect_container", ["docker", "inspect", ids[0]]))[0]


def others(excluded: set[str]) -> dict:
    """只比较本次所有权集合之外的容器 ID、启动时间和状态，不改变它们。"""

    ids = run("list_containers", ["docker", "ps", "-aq", "--no-trunc"]).splitlines()
    values = (
        json.loads(run("inspect_other_containers", ["docker", "inspect", *ids]))
        if ids
        else []
    )
    return {
        value["Id"]: {
            "name": value["Name"],
            "started_at": value["State"]["StartedAt"],
            "running": value["State"]["Running"],
        }
        for value in values
        if value["Id"] not in excluded
    }


def save(record: dict) -> None:
    """原子保存非敏感阶段和精确 ID，回执丢失后由 status/recover 接续，不另建事务。"""

    temporary = RECORD.with_suffix(".tmp")
    temporary.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    temporary.replace(RECORD)


def require_owned(container: dict | None, record: dict, kind: str) -> dict:
    """只接受本次记录的候选/恢复容器及事务标签，漂移时停止。"""

    if (
        not container
        or container["Id"] != record.get(kind + "_id")
        or container["Image"] != record.get(kind + "_image")
        or container["Config"]["Labels"].get(PREFIX + "release") != RELEASE
        or container["Config"]["Labels"].get(PREFIX + "root") != str(ROOT)
        or container["Config"]["Labels"].get(PREFIX + "transaction")
        != record["transaction"]
    ):
        raise RolloutError("owned_container_or_image_drift:" + kind)
    return container


class DockerSocket(http.client.HTTPConnection):
    """复用本机 Docker API；环境配置仅内存复制，不经 shell、参数或文件传递。"""

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(30)
        self.sock.connect("/var/run/docker.sock")


def create(old: dict, image: str, name: str, record: dict) -> str:
    """复制现用容器配置创建停止态候选，仅替换镜像、主机名及本版本所有权标签。"""

    config = copy.deepcopy(old["Config"])
    config["Image"], config["Hostname"] = image, ""
    config["Labels"].update(
        {
            PREFIX + "release": RELEASE,
            PREFIX + "root": str(ROOT),
            PREFIX + "transaction": record["transaction"],
        }
    )
    config["HostConfig"] = copy.deepcopy(old["HostConfig"])
    connection = DockerSocket("localhost", timeout=30)
    try:
        connection.request(
            "POST",
            "/containers/create?name=" + name,
            json.dumps(config).encode(),
            {"Content-Type": "application/json"},
        )
        response = connection.getresponse()
        body = response.read(262144)
        if response.status != 201:
            raise RolloutError(f"create_candidate:http_{response.status}")
        return json.loads(body)["Id"]
    finally:
        connection.close()


def validate_config(old: dict, candidate: dict) -> None:
    """核环境、挂载、资源、网络、启动命令与健康检查不变；只允许已声明差异。"""

    old_config, new_config = (
        copy.deepcopy(old["Config"]),
        copy.deepcopy(candidate["Config"]),
    )
    for config in (old_config, new_config):
        for field in ("Image", "Hostname", "Labels"):
            config.pop(field, None)
    old_host, new_host = (
        copy.deepcopy(old["HostConfig"]),
        copy.deepcopy(candidate["HostConfig"]),
    )
    for host in (old_host, new_host):
        if host.get("OomKillDisable") is None:
            host["OomKillDisable"] = False
    if (
        old_config != new_config
        or old_host != new_host
        or candidate["State"]["Running"]
    ):
        raise RolloutError("candidate_runtime_configuration_mismatch")


def require_idle(old_id: str) -> None:
    """切换前只读检查内容队列无运行中任务，避免中断正在提交的帖子。"""

    code = (
        "import asyncio;from sqlalchemy import select;"
        "from app.db.session import AsyncSessionLocal,engine;"
        "from app.models.background_job import BackgroundJob\n"
        "async def main():\n"
        " async with AsyncSessionLocal() as s:\n"
        "  x=await s.scalar(select(BackgroundJob.id).where(BackgroundJob.queue=='community_content',"
        "BackgroundJob.status=='running').limit(1));await s.rollback();print('idle' if x is None else 'busy')\n"
        " await engine.dispose()\nasyncio.run(main())"
    )
    if (
        run(
            "require_idle_queue", ["docker", "exec", old_id, "python", "-c", code]
        ).strip()
        != "idle"
    ):
        raise RolloutError("content_queue_busy_wait_before_switch")


def apply() -> dict:
    """在原 worker 仍运行时构建新版本和恢复候选，预检通过后串行切换，不更新旧目录。"""

    import uuid

    if RECORD.exists():
        raise RolloutError("release_record_exists_use_status_or_recover")
    expected = json.loads((ROOT / "production-before.json").read_text())
    old = inspect(NAME)
    if (
        not old
        or old["Id"] != expected["id"]
        or old["Image"] != expected["image"]
        or not old["State"]["Running"]
    ):
        raise RolloutError("production_baseline_drift")
    if any(inspect(name) for name in (CANDIDATE, RECOVERY, BACKUP, FAILED)):
        raise RolloutError("release_container_name_exists")
    for name in FILES:
        source = ROOT / "context" / name
        if source.is_symlink() or not source.is_file():
            raise RolloutError("missing_or_linked_source:" + name)
        compile(source.read_text(), name, "exec")
    paths = FILES[:2]
    code = (
        'import json;from pathlib import Path;print(json.dumps({p:Path("/app",p).read_text() for p in '
        + repr(paths)
        + "}))"
    )
    actual = json.loads(
        run(
            "check_runtime_baseline",
            ["docker", "exec", old["Id"], "python", "-c", code],
        )
    )
    for name in paths:
        if actual[name] != (ROOT / "before" / name).read_text():
            raise RolloutError("runtime_source_drift:" + name)
    for tag in (IMAGE, RECOVERY_IMAGE, BASE_TAG):
        if run(
            "require_unused_image_tag",
            ["docker", "image", "ls", "-q", "--no-trunc", tag],
        ).strip():
            raise RolloutError("release_image_tag_exists")
    if others({old["Id"]}) != expected["other_containers"]:
        raise RolloutError("other_container_state_changed_before_release")
    record = {
        "phase": "prepared",
        "transaction": uuid.uuid4().hex,
        "old_id": old["Id"],
        "old_image": old["Image"],
        "others": expected["other_containers"],
    }
    save(record)
    run("preserve_base_image", ["docker", "tag", old["Image"], BASE_TAG])
    for kind, dockerfile, context, tag, name in (
        ("new", "Dockerfile", "context", IMAGE, CANDIDATE),
        ("recovery", "Dockerfile.recovery", "recovery", RECOVERY_IMAGE, RECOVERY),
    ):
        run(
            "build_" + kind,
            [
                "docker",
                "build",
                "--network=none",
                "--pull=false",
                "--build-arg",
                "BASE_IMAGE=" + BASE_TAG,
                "-t",
                tag,
                "-f",
                str(ROOT / dockerfile),
                str(ROOT / context),
            ],
            timeout=180,
        )
        record[kind + "_image"] = json.loads(
            run(
                "read_image",
                ["docker", "image", "inspect", "--format", "{{json .Id}}", tag],
            )
        )
        save(record)
        record[kind + "_id"] = create(old, record[kind + "_image"], name, record)
        save(record)
        validate_config(old, require_owned(inspect(name), record, kind))
    # 构建期间可能有其他运维更新旧实例；按最新现场重验，不用开头的配置快照覆盖新决定。
    fresh = inspect(NAME)
    if (
        not fresh
        or fresh["Id"] != old["Id"]
        or fresh["Image"] != old["Image"]
        or not fresh["State"]["Running"]
        or fresh["State"]["StartedAt"] != old["State"]["StartedAt"]
        or fresh["Config"]["Labels"] != old["Config"]["Labels"]
    ):
        raise RolloutError("original_container_changed_during_build")
    for kind, name in (("new", CANDIDATE), ("recovery", RECOVERY)):
        validate_config(fresh, require_owned(inspect(name), record, kind))
    actual = json.loads(
        run(
            "recheck_runtime_baseline",
            ["docker", "exec", fresh["Id"], "python", "-c", code],
        )
    )
    if any(actual[name] != (ROOT / "before" / name).read_text() for name in paths):
        raise RolloutError("runtime_source_changed_during_build")
    old = fresh
    require_idle(old["Id"])
    owned = {record[key] for key in ("old_id", "new_id", "recovery_id")}
    if others(owned) != record["others"]:
        raise RolloutError("other_container_state_changed_before_switch")
    # 先停稳旧实例并保留，再启动新版；从不并行运行两个队列 worker。
    record["phase"] = "ready_to_switch"
    save(record)
    run("disable_old_restart", ["docker", "update", "--restart=no", old["Id"]])
    run("stop_old_worker", ["docker", "stop", "--time", "30", old["Id"]], timeout=45)
    if inspect(NAME)["State"]["Running"]:
        raise RolloutError("old_worker_did_not_stop")
    record["phase"] = "old_stopped"
    save(record)
    run("preserve_old_container", ["docker", "rename", old["Id"], BACKUP])
    run("name_new_worker", ["docker", "rename", record["new_id"], NAME])
    run("start_new_worker", ["docker", "start", record["new_id"]], timeout=45)
    record["phase"] = "installed"
    save(record)
    return {
        "complete": True,
        "phase": record["phase"],
        "new_id": record["new_id"],
        "image": record["new_image"],
        "old_preserved": True,
        "health_pending": True,
        "other_containers_unchanged": others(owned) == record["others"],
    }


def status() -> dict:
    """独立只读检查精确实例、Docker 健康及新实例启动后的有效心跳，不入队或发帖。"""

    if not RECORD.exists():
        return {"complete": False, "read_only": True, "phase": "not_started"}
    record = json.loads(RECORD.read_text())
    current = inspect(NAME)
    if (
        current
        and current["Id"] == record["old_id"]
        and current["Image"] == record["old_image"]
    ):
        kind = "previous"
    else:
        kind = (
            "recovery"
            if current and current["Id"] == record.get("recovery_id")
            else "new"
        )
        current = require_owned(current, record, kind)
    heartbeat = False
    if current["State"]["Running"]:
        code = (
            "import json;from app.workers.community_content_health import HEARTBEAT,worker_is_healthy;"
            "print(json.dumps({'recent':worker_is_healthy(),'value':HEARTBEAT.read_text() if HEARTBEAT.exists() else None}))"
        )
        value = json.loads(
            run(
                "read_heartbeat",
                ["docker", "exec", current["Id"], "python", "-c", code],
            )
        )
        heartbeat = bool(
            value["recent"]
            and value["value"]
            and datetime.fromisoformat(value["value"])
            > datetime.fromisoformat(current["State"]["StartedAt"])
        )
    owned = {
        record[key] for key in ("old_id", "new_id", "recovery_id") if key in record
    }
    unchanged = others(owned) == record["others"]
    return {
        "complete": current["State"].get("Health", {}).get("Status") == "healthy"
        and heartbeat
        and unchanged,
        "phase": record["phase"],
        "active_version": kind,
        "read_only": True,
        "id": current["Id"],
        "image": current["Image"],
        "running": current["State"]["Running"],
        "health": current["State"].get("Health", {}).get("Status"),
        "fresh_heartbeat_after_start": heartbeat,
        "other_containers_unchanged": unchanged,
    }


def recover() -> dict:
    """停止并保留失败新版，再启动当前发布记录内已准备好的固定恢复实例。"""

    record = json.loads(RECORD.read_text())
    current = inspect(NAME)
    if current and current["Id"] == record["old_id"] and current["State"]["Running"]:
        run(
            "restore_old_restart",
            ["docker", "update", "--restart=unless-stopped", current["Id"]],
        )
        return {"complete": True, "phase": "old_worker_unchanged"}
    if record.get("phase") == "recovered":
        return status()
    # 恢复实例已改名但回执未写完时，仅接续原精确实例，不另建或启动第二个 worker。
    if current and current["Id"] == record.get("recovery_id"):
        require_owned(current, record, "recovery")
        old = inspect(BACKUP)
        if not old or old["Id"] != record["old_id"] or old["State"]["Running"]:
            raise RolloutError("recovery_original_not_stopped")
        if not current["State"]["Running"]:
            run("resume_recovery_start", ["docker", "start", current["Id"]], timeout=45)
        record["phase"] = "recovered"
        save(record)
        return {
            "complete": True,
            "phase": "recovered",
            "id": current["Id"],
            "health_pending": True,
        }
    recovery = require_owned(inspect(RECOVERY), record, "recovery")
    if recovery["State"]["Running"]:
        raise RolloutError("recovery_already_running_under_unexpected_name")
    old = inspect(BACKUP) or current
    if not old or old["Id"] != record["old_id"] or old["State"]["Running"]:
        raise RolloutError("original_container_missing_or_still_running")
    if current and current["Id"] != old["Id"]:
        require_owned(current, record, "new")
        if inspect(FAILED):
            raise RolloutError("failed_container_name_exists")
        run("disable_new_restart", ["docker", "update", "--restart=no", current["Id"]])
        run(
            "stop_new_worker",
            ["docker", "stop", "--time", "30", current["Id"]],
            timeout=45,
        )
        run("preserve_failed_new_worker", ["docker", "rename", current["Id"], FAILED])
    elif current:
        run("preserve_stopped_original", ["docker", "rename", old["Id"], BACKUP])
    run("name_recovery_worker", ["docker", "rename", recovery["Id"], NAME])
    run("start_recovery_worker", ["docker", "start", recovery["Id"]], timeout=45)
    record["phase"] = "recovered"
    save(record)
    return {
        "complete": True,
        "phase": "recovered",
        "id": recovery["Id"],
        "health_pending": True,
        RECOVERY_RESULT: True,
        "business_data_not_reverted": True,
    }


@contextmanager
def mutation_lock():
    """沿用旧内容管理锁协调切换；只锁操作，不覆盖任何旧版本记录。"""

    path = Path(
        "/opt/parallellines/.deployment/community-content/20261115-h1/.manage.lock"
    )
    with path.open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RolloutError("another_content_operation_is_running") from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def main() -> int:
    """只允许固定目录的 apply/status/recover，错误只输出稳定代码。"""

    try:
        script = Path(__file__).absolute()
        if script.parent != script.resolve().parent:
            raise RolloutError("wrong_fixed_release_directory")
        select_release(script.parent)
        action = sys.argv[1]
        if action == "status":
            result = status()
        elif action in ("apply", "recover"):
            with mutation_lock():
                result = {"apply": apply, "recover": recover}[action]()
        else:
            raise RolloutError("unsupported_operation")
    except RolloutError as exc:
        result = {"complete": False, "error": str(exc)}
    except Exception as exc:
        result = {"complete": False, "error": type(exc).__name__}
    print(json.dumps(result))
    return 0 if result["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
