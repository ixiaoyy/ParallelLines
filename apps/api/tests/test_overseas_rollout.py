"""海外版本发布协议的纯内存 Docker mock；不连接服务器、Docker 或数据库。"""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "deploy/community-content/releases/rollout.py"
RELEASES = ("20261117-overseas", "20261117-overseas-render")


@pytest.fixture(params=RELEASES, ids=("initial", "render"))
def ops(request, tmp_path, monkeypatch):
    """加载同一发布脚本后选固定版本；Windows 只替换不实际调用的文件锁 API。"""

    if sys.platform == "win32":
        monkeypatch.setitem(sys.modules, "fcntl", SimpleNamespace())
    spec = importlib.util.spec_from_file_location("overseas_rollout_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.select_release(module.RELEASE_BASE / request.param)
    assert module.RELEASE == request.param
    monkeypatch.setattr(module, "RECORD", tmp_path / "rollout.json")
    return module


def test_release_profile_preserves_fixed_directory_overlays_and_recovery_image(ops):
    assert ops.ROOT == Path("/opt/parallellines/.deployment/community-content") / ops.RELEASE
    assert ops.RECOVERY_IMAGE == f"parallellines-community-content:{ops.RELEASE}-recovery"
    scheduled = "app/services/scheduled_content.py"
    if ops.RELEASE == RELEASES[0]:
        assert ops.FILES == ("app/services/community_schedule.py", scheduled,
                             "app/services/overseas_content.py")
    else:
        assert ops.FILES == (scheduled,)


def test_cli_rejects_the_same_release_under_a_different_parent(ops, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(ops, "__file__", str(tmp_path / ops.RELEASE / "rollout.py"))
    monkeypatch.setattr(sys, "argv", ["rollout.py", "apply"])
    monkeypatch.setattr(ops, "mutation_lock", lambda: pytest.fail("错误目录不能取切换锁"))
    assert ops.main() == 1
    assert json.loads(capsys.readouterr().out) == {
        "complete": False,
        "error": "wrong_fixed_release_directory",
    }


def test_fixed_release_directory_rejects_unknown_name(ops):
    with pytest.raises(ops.RolloutError, match="^wrong_fixed_release_directory$"):
        ops.select_release(ops.RELEASE_BASE / "20261117-overseas-unknown")


def container(ops, identity, image, name, *, running=False):
    """只构造校验所需的非敏感容器配置。"""

    return {
        "Id": identity,
        "Image": image,
        "Name": "/" + name,
        "Config": {
            "Image": image,
            "Hostname": identity,
            "Env": ["LIVING_FORUM_PUBLISH_MODE=off"],
            "Cmd": ["python", "-m", "app.workers.community_content"],
            "Labels": {
                ops.PREFIX + "release": ops.RELEASE,
                ops.PREFIX + "root": str(ops.ROOT),
                ops.PREFIX + "transaction": "transaction",
            },
        },
        "HostConfig": {
            "Memory": 512 * 1024 * 1024,
            "NetworkMode": "existing-network",
            "OomKillDisable": None,
        },
        "State": {
            "Running": running,
            "StartedAt": "2026-11-17T09:00:00Z",
            "Health": {"Status": "healthy"},
        },
    }


def record(ops):
    """生成不含凭据的完整切换前像。"""

    value = {
        "phase": "installed",
        "transaction": "transaction",
        "old_id": "old",
        "old_image": "old-image",
        "new_id": "new",
        "new_image": "new-image",
        "recovery_id": "recovery",
        "recovery_image": "recovery-image",
        "others": {},
    }
    ops.RECORD.write_text(json.dumps(value), encoding="utf-8")
    return value


def test_config_check_preserves_environment_resources_network_and_command(ops):
    old = container(ops, "old", "old-image", ops.NAME, running=True)
    new = container(ops, "new", "new-image", ops.CANDIDATE)
    new["HostConfig"]["OomKillDisable"] = False
    ops.validate_config(old, new)
    for section, field, changed in (
        ("Config", "Env", ["LIVING_FORUM_PUBLISH_MODE=auto"]),
        ("Config", "Cmd", ["wrong-worker"]),
        ("HostConfig", "Memory", 0),
        ("HostConfig", "NetworkMode", "wrong-network"),
    ):
        candidate = copy.deepcopy(new)
        candidate[section][field] = changed
        with pytest.raises(ops.RolloutError, match="configuration_mismatch"):
            ops.validate_config(old, candidate)


@pytest.mark.parametrize("field,changed", [("Id", "unrelated"), ("Image", "wrong-image")])
def test_owned_check_rejects_container_or_image_drift(ops, field, changed):
    value = record(ops)
    current = container(ops, "new", "new-image", ops.NAME)
    current[field] = changed
    with pytest.raises(ops.RolloutError, match="drift"):
        ops.require_owned(current, value, "new")


@pytest.mark.parametrize(
    "heartbeat,expected",
    [("2026-11-17T08:59:59+00:00", False), ("2026-11-17T09:00:15+00:00", True)],
)
def test_status_requires_a_new_heartbeat_after_start_not_shared_old_file(
    ops, monkeypatch, heartbeat, expected
):
    record(ops)
    current = container(ops, "new", "new-image", ops.NAME, running=True)
    monkeypatch.setattr(ops, "inspect", lambda name: current)
    monkeypatch.setattr(ops, "others", lambda excluded: {})
    monkeypatch.setattr(ops, "run", lambda *args: json.dumps({"recent": True, "value": heartbeat}))
    assert ops.status()["complete"] is expected


def test_prepared_release_status_can_report_healthy_unchanged_original(ops, monkeypatch):
    value = record(ops)
    value["phase"] = "prepared"
    ops.RECORD.write_text(json.dumps(value), encoding="utf-8")
    old = container(ops, "old", "old-image", ops.NAME, running=True)
    monkeypatch.setattr(ops, "inspect", lambda name: old)
    monkeypatch.setattr(ops, "others", lambda excluded: {})
    monkeypatch.setattr(
        ops, "run", lambda *args: json.dumps({"recent": True, "value": "2026-11-17T09:00:15Z"})
    )
    result = ops.status()
    assert result["complete"] and result["active_version"] == "previous"
    assert result["phase"] == "prepared"


def test_apply_rechecks_config_after_build_and_never_stops_a_drifted_original(
    ops, monkeypatch, tmp_path
):
    root = tmp_path / "release"
    root.mkdir()
    monkeypatch.setattr(ops, "ROOT", root)
    monkeypatch.setattr(ops, "RECORD", root / "rollout.json")
    for name in ops.FILES:
        for folder in ("context", "before"):
            path = root / folder / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("pass", encoding="utf-8")
    old = container(ops, "old", "old-image", ops.NAME, running=True)
    (root / "production-before.json").write_text(
        json.dumps({"id": "old", "image": "old-image", "other_containers": {}}), encoding="utf-8"
    )
    original_reads = 0
    state, calls = {}, []

    def inspect(name):
        nonlocal original_reads
        if name == ops.NAME:
            original_reads += 1
            value = copy.deepcopy(old)
            if original_reads > 1:
                value["HostConfig"]["Memory"] = 256 * 1024 * 1024
            return value
        return state.get(name)

    def create(original, image, name, data):
        value = copy.deepcopy(original)
        value["Id"], value["Image"] = name, image
        value["Config"]["Image"] = image
        value["State"]["Running"] = False
        value["Config"]["Labels"][ops.PREFIX + "transaction"] = data["transaction"]
        state[name] = value
        return name

    def run(step, argv, **kwargs):
        calls.append(step)
        if step == "check_runtime_baseline":
            return json.dumps({name: "pass" for name in ops.FILES[:2]})
        if step == "read_image":
            return json.dumps(argv[-1] + "-image")
        return ""

    monkeypatch.setattr(ops, "inspect", inspect)
    monkeypatch.setattr(ops, "create", create)
    monkeypatch.setattr(ops, "others", lambda excluded: {})
    monkeypatch.setattr(ops, "run", run)
    with pytest.raises(ops.RolloutError, match="configuration_mismatch"):
        ops.apply()
    assert original_reads == 2
    assert "disable_old_restart" not in calls and "stop_old_worker" not in calls
    assert old["State"]["Running"]


@pytest.mark.parametrize("already_renamed", (False, True))
def test_recovery_is_serial_and_resumes_if_rename_receipt_was_lost(
    ops, monkeypatch, already_renamed
):
    record(ops)
    old = container(ops, "old", "old-image", ops.BACKUP)
    new = container(ops, "new", "new-image", ops.NAME, running=not already_renamed)
    recovery = container(ops, "recovery", "recovery-image", ops.RECOVERY)
    state = {ops.BACKUP: old}
    if already_renamed:
        state[ops.FAILED] = new
        state[ops.NAME] = recovery
    else:
        state[ops.NAME], state[ops.RECOVERY] = new, recovery
    calls = []

    def run(step, argv, **kwargs):
        calls.append(argv)
        by_id = {value["Id"]: value for value in state.values()}
        if argv[1] == "stop":
            by_id[argv[-1]]["State"]["Running"] = False
        elif argv[1] == "rename":
            old_name = next(name for name, value in state.items() if value["Id"] == argv[2])
            state[argv[3]] = state.pop(old_name)
        elif argv[1] == "start":
            assert not old["State"]["Running"] and not new["State"]["Running"]
            by_id[argv[2]]["State"]["Running"] = True
        return ""

    monkeypatch.setattr(ops, "inspect", lambda name: state.get(name))
    monkeypatch.setattr(ops, "run", run)
    result = ops.recover()
    expected = {"complete": True, "phase": "recovered", "id": "recovery", "health_pending": True}
    if not already_renamed:
        release_flag = ("overseas_pending_tasks_skip_safely" if ops.RELEASE == RELEASES[0]
                        else "previous_release_restored")
        expected.update({release_flag: True, "business_data_not_reverted": True})
    assert result == expected
    assert state[ops.NAME]["Id"] == "recovery" and recovery["State"]["Running"]
    assert not old["State"]["Running"] and not new["State"]["Running"]
    assert json.loads(ops.RECORD.read_text())["phase"] == "recovered"
    assert [argv[-1] for argv in calls if argv[1] == "start"] == ["recovery"]
