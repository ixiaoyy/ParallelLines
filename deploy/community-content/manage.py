"""本次独立内容 worker 的受限交付入口；只允许固定版本的四项操作。"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path("/opt/parallellines/.deployment/community-content/20261115-h1")
CONTEXT = ROOT / "context"
STATE = ROOT / "state.json"
BUILD = ROOT / "build.json"
NAME = "parallellines-community-content"
IMAGE = "parallellines-community-content:20261115-h1"
BASE_TAG = "parallellines-community-content-base:20261115-h1"
BASE_IMAGE = "sha256:4f2e43c0ee4a95c93734b075be7860cf2e4ce1407c1603f8f8689a309e4e00ea"
API = "parallellines-api-1"
NETWORK = "parallellines_default"
ENV_FILE = Path("/opt/parallellines/apps/api/.env")
RELEASE = "20261115-h1"
RELEASE_LABEL = "io.parallellines.community-content.release"
ROOT_LABEL = "io.parallellines.community-content.root"
TRANSACTION_LABEL = "io.parallellines.community-content.transaction"
SOURCE_FILES = {
    "app/core/community_content.py",
    "app/services/community_schedule.py",
    "app/services/scheduled_content.py",
    "app/services/overseas_content.py",
    "app/services/living_forum.py",
    "app/services/daily_reading.py",
    "app/services/daily_reading_provider.py",
    "app/workers/community_content.py",
    "app/workers/community_content_health.py",
    "scripts/collect_weibo_hot_search.py",
    "scripts/plan_living_forum_day.py",
    "scripts/publish_daily_reading.py",
}


class OperationError(RuntimeError):
    """保存可公开的稳定错误码，禁止转储可能含运行环境的原始子进程输出。"""


def run(step: str, arguments: list[str], *, timeout: int = 30) -> str:
    """有界执行固定参数命令并返回标准输出；失败仅报告步骤/退出码。"""

    try:
        result = subprocess.run(
            arguments, text=True, capture_output=True, check=False, timeout=timeout
        )
    except subprocess.TimeoutExpired as exc:
        raise OperationError(f"{step}:timeout") from exc
    except OSError as exc:
        raise OperationError(f"{step}:unavailable") from exc
    if result.returncode:
        raise OperationError(f"{step}:exit_{result.returncode}")
    if len(result.stdout) > 262144:
        raise OperationError(f"{step}:output_limit")
    return result.stdout.strip()


def read_record(path: Path) -> dict | None:
    """读取本版本非敏感状态；错误或外部替换的记录不会被当作空状态覆盖。"""

    if path.is_symlink():
        raise OperationError(f"linked_record:{path.name}")
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise OperationError(f"invalid_record:{path.name}") from exc
    if not isinstance(value, dict) or value.get("release") != RELEASE:
        raise OperationError(f"foreign_record:{path.name}")
    return value


def save_record(path: Path, value: dict) -> None:
    """原子保存本事务公开标识；不写入任何真实环境变量值或凭据。"""

    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


@contextmanager
def mutation_lock():
    """同一交付目录一次只允许一个写操作，防止两个 install 相互覆盖前像。"""

    with (ROOT / ".manage.lock").open("a", encoding="ascii") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise OperationError("another_content_operation_is_running") from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def inspect_container(name: str) -> dict | None:
    """仅取固定容器的必要身份/健康字段，不读取或输出整个 inspect 环境。"""

    found = run("find_container", [
        "docker", "ps", "-aq", "--no-trunc", "--filter", f"name=^/{name}$"
    ]).splitlines()
    if not found:
        return None
    if len(found) != 1:
        raise OperationError("container_name_not_unique")
    fields = (
        '{"id":{{json .Id}},"image":{{json .Image}},"name":{{json .Name}},'
        '"running":{{json .State.Running}},"status":{{json .State.Status}},'
        '"health":{{if .State.Health}}{{json .State.Health.Status}}{{else}}null{{end}},'
        '"restart":{{json .HostConfig.RestartPolicy.Name}},'
        f'"release":{{{{json (index .Config.Labels "{RELEASE_LABEL}")}}}},'
        f'"root":{{{{json (index .Config.Labels "{ROOT_LABEL}")}}}},'
        f'"transaction":{{{{json (index .Config.Labels "{TRANSACTION_LABEL}")}}}}'
        "}"
    )
    return json.loads(run("inspect_container", [
        "docker", "inspect", "--type", "container", "--format", fields, found[0]
    ]))


def image_id(reference: str) -> str:
    """只读取本地镜像 ID，不触发远程拉取。"""

    return json.loads(run("inspect_image", [
        "docker", "image", "inspect", "--format", "{{json .Id}}", reference
    ]))


def unrelated_ids() -> list[str]:
    """保存其他所有容器的完整 ID；不要求也不改变它们的状态或配置。"""

    all_ids = run("list_container_ids", ["docker", "ps", "-aq", "--no-trunc"]).splitlines()
    owned = inspect_container(NAME)
    return sorted(value for value in all_ids if not owned or value != owned["id"])


def require_base() -> None:
    """只允许在已核现用 API 镜像的服务器构建，不换基底也不影响其服务。"""

    api = inspect_container(API)
    if not api or not api["running"] or api["image"] != BASE_IMAGE:
        raise OperationError("production_api_image_changed")
    if image_id(BASE_IMAGE) != BASE_IMAGE:
        raise OperationError("production_base_image_missing")


def require_owned(container: dict, state: dict, build: dict) -> None:
    """操作前精确核对本版本、事务、容器与镜像；漂移时不重建或停止外部资源。"""

    expected = {
        "name": "/" + NAME,
        "release": RELEASE,
        "root": str(ROOT),
        "transaction": state.get("transaction"),
        "image": build.get("image_id"),
    }
    if any(container.get(key) != value or value is None for key, value in expected.items()):
        raise OperationError("content_container_ownership_or_image_changed")
    if state.get("container_id") and state["container_id"] != container["id"]:
        raise OperationError("content_container_identity_changed")
    if state.get("image_id") != build.get("image_id"):
        raise OperationError("content_build_record_changed")


def build_image() -> dict:
    """只构建已审运行文件的离线 overlay；保留现用镜像和其他服务。"""

    if inspect_container(NAME):
        raise OperationError("content_container_exists_do_not_rebuild_this_release")
    if read_record(STATE):
        raise OperationError("content_install_state_exists_do_not_rebuild")
    if read_record(BUILD):
        raise OperationError("content_build_already_recorded_do_not_rebuild")
    require_base()
    if (CONTEXT.is_symlink() or (ROOT / "Dockerfile").is_symlink()
            or not CONTEXT.is_dir() or not (ROOT / "Dockerfile").is_file()):
        raise OperationError("curated_context_or_dockerfile_missing")
    actual = set()
    for path in CONTEXT.rglob("*"):
        if path.is_symlink() or not path.resolve().is_relative_to(CONTEXT.resolve()):
            raise OperationError("source_context_contains_external_path")
        if path.is_file():
            actual.add(path.relative_to(CONTEXT).as_posix())
    if actual != SOURCE_FILES:
        raise OperationError("source_context_inventory_mismatch")
    before = unrelated_ids()
    existing_base_tag = run("find_existing_base_tag", [
        "docker", "image", "ls", "--quiet", "--no-trunc", BASE_TAG
    ])
    if existing_base_tag and existing_base_tag != BASE_IMAGE:
        raise OperationError("base_tag_owned_by_another_image")
    run("tag_existing_base", ["docker", "image", "tag", BASE_IMAGE, BASE_TAG])
    run("build_content_overlay", [
        "docker", "build", "--network=none", "--pull=false",
        "--file", str(ROOT / "Dockerfile"),
        "--build-arg", f"BASE_IMAGE={BASE_TAG}",
        "--label", f"{RELEASE_LABEL}={RELEASE}",
        "--label", f"{ROOT_LABEL}={ROOT}",
        "--tag", IMAGE, str(CONTEXT),
    ], timeout=180)
    record = {"release": RELEASE, "base_image": BASE_IMAGE, "image_id": image_id(IMAGE)}
    save_record(BUILD, record)
    if unrelated_ids() != before:
        raise OperationError("unrelated_container_identity_changed_during_build")
    return {"complete": True, "image_id": record["image_id"], "offline_build": True}


def install() -> dict:
    """安装唯一独立内容容器；已有精确同事务运行容器保持不变，不覆盖其他实例。"""

    build = read_record(BUILD)
    if not build or build.get("base_image") != BASE_IMAGE or image_id(IMAGE) != build.get("image_id"):
        raise OperationError("content_image_not_the_recorded_build")
    current = inspect_container(NAME)
    state = read_record(STATE)
    if current:
        if not state:
            raise OperationError("existing_content_container_has_no_owned_state")
        require_owned(current, state, build)
        if state.get("status") not in ("installing", "running_pending_validation", "installed"):
            raise OperationError("owned_content_state_requires_review")
        if not current["running"] or current["restart"] != "unless-stopped":
            raise OperationError("owned_content_container_stopped_no_implicit_restart")
        if state.get("status") != "installed":
            if unrelated_ids() != state.get("unrelated_container_ids"):
                raise OperationError("unrelated_container_identity_changed_during_install")
            state.update(container_id=current["id"], status="installed")
            save_record(STATE, state)
        return {"complete": True, "unchanged": True, "container_id": current["id"],
                "start_at": state["start_at"]}
    if state and (state.get("status") != "installing" or state.get("container_id")
                  or state.get("image_id") != build["image_id"]):
        raise OperationError("recorded_content_container_missing_do_not_replace")
    require_base()
    if not ENV_FILE.is_file():
        raise OperationError("existing_api_env_file_missing")
    run("require_existing_network", ["docker", "network", "inspect", "--format", "{{.Name}}", NETWORK])
    before = unrelated_ids()
    if state and before != state.get("unrelated_container_ids"):
        raise OperationError("unrelated_container_identity_changed_since_install_attempt")
    persistent = ROOT / "var"
    if persistent.is_symlink():
        raise OperationError("content_snapshot_path_is_symlink")
    persistent.mkdir(exist_ok=True)
    if not state:
        state = {
            "release": RELEASE, "transaction": uuid.uuid4().hex, "status": "installing",
            "image_id": build["image_id"], "container_id": None,
            "start_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "unrelated_container_ids": before,
        }
    # 先保存非敏感前像；即使 docker run 回执丢失，也不能重新创建另一事务。
    save_record(STATE, state)
    run("start_owned_content_container", [
        "docker", "run", "--detach", "--name", NAME,
        "--restart", "unless-stopped", "--network", NETWORK,
        "--memory=512m", "--cpus=0.5", "--pids-limit=128",
        "--log-driver=json-file", "--log-opt=max-size=10m", "--log-opt=max-file=3",
        "--label", f"{RELEASE_LABEL}={RELEASE}",
        "--label", f"{ROOT_LABEL}={ROOT}",
        "--label", f"{TRANSACTION_LABEL}={state['transaction']}",
        "--env-file", str(ENV_FILE),
        "--env", "COMMUNITY_CONTENT_ENABLED=true",
        "--env", f"COMMUNITY_CONTENT_START_AT={state['start_at']}",
        "--env", "LIVING_FORUM_PUBLISH_MODE=off",
        "--env", "DAILY_READING_PUBLISH_MODE=auto",
        "--env", "DAILY_READING_AI_PROVIDER=local",
        "--mount", f"type=bind,src={persistent},dst=/app/var",
        IMAGE,
    ], timeout=90)
    current = inspect_container(NAME)
    if not current:
        raise OperationError("started_content_container_not_found")
    require_owned(current, state, build)
    state.update(container_id=current["id"], status="running_pending_validation")
    save_record(STATE, state)
    if unrelated_ids() != before:
        raise OperationError("unrelated_container_identity_changed_during_install")
    if not current["running"]:
        raise OperationError("content_container_not_running")
    state["status"] = "installed"
    save_record(STATE, state)
    return {"complete": True, "container_id": current["id"], "image_id": current["image"],
            "start_at": state["start_at"], "other_container_ids_unchanged": True,
            "health_pending": current["health"] != "healthy"}


def status() -> dict:
    """独立只读健康入口；只检查本容器与心跳，不运行任务或改变任何状态。"""

    current, state, build = inspect_container(NAME), read_record(STATE), read_record(BUILD)
    if not current or not state or not build:
        return {"complete": False, "read_only": True, "reason": "not_installed"}
    require_owned(current, state, build)
    heartbeat = False
    if current["running"]:
        try:
            run("read_content_heartbeat", [
                "docker", "exec", current["id"], "python", "-m",
                "app.workers.community_content_health",
            ], timeout=15)
            heartbeat = True
        except OperationError:
            heartbeat = False
    return {
        "complete": (state.get("status") == "installed" and current["running"]
                     and current["health"] == "healthy" and heartbeat),
        "read_only": True, "container_id": current["id"], "image_id": current["image"],
        "running": current["running"], "health": current["health"],
        "deployment_status": state.get("status"),
        "heartbeat_recent": heartbeat, "restart": current["restart"], "start_at": state["start_at"],
    }


def stop() -> dict:
    """恢复到未启用内容发布：只关闭本版本事务容器及其自动重启，不删数据或镜像。"""

    current, state, build = inspect_container(NAME), read_record(STATE), read_record(BUILD)
    if not current or not state or not build:
        raise OperationError("no_owned_content_container_to_stop")
    require_owned(current, state, build)
    before = unrelated_ids()
    run("disable_owned_content_restart", ["docker", "update", "--restart=no", current["id"]])
    if current["running"]:
        run("stop_owned_content_container", ["docker", "stop", "--time", "30", current["id"]], timeout=45)
    after = inspect_container(NAME)
    if not after:
        raise OperationError("owned_container_disappeared_during_stop")
    require_owned(after, state, build)
    if after["running"] or after["restart"] != "no":
        raise OperationError("owned_content_stop_not_confirmed")
    state.update(container_id=after["id"], status="stopped")
    save_record(STATE, state)
    if unrelated_ids() != before:
        raise OperationError("unrelated_container_identity_changed_during_stop")
    return {"complete": True, "stopped": True, "container_id": after["id"],
            "data_and_images_preserved": True, "other_container_ids_unchanged": True}


def main() -> int:
    """仅在固定服务器交付目录派发白名单操作；失败统一返回非零及稳定原因。"""

    parser = argparse.ArgumentParser(description="20261115 独立圈子内容 worker 交付")
    parser.add_argument("operation", choices=("build", "install", "status", "stop"))
    operation = parser.parse_args().operation
    try:
        if os.name != "posix" or Path(__file__).resolve().parent != ROOT.resolve():
            raise OperationError("run_only_from_the_fixed_server_artifact_directory")
        if operation == "status":
            report = status()
        else:
            with mutation_lock():
                report = {"build": build_image, "install": install, "stop": stop}[operation]()
        report["operation"] = operation
    except OperationError as exc:
        report = {"operation": operation, "complete": False, "error": str(exc)}
    except Exception as exc:
        report = {"operation": operation, "complete": False,
                  "error": f"unexpected_{type(exc).__name__}"}
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
