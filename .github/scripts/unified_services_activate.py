"""仅激活/恢复本轮已制 bridge、Chat、New API；不构建、不读取数据库或环境文件。"""

from __future__ import annotations

import contextlib
import copy
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import stat
import sys
import time


APP = "a2cfeddeec01ca0d5def4b3308103f3d85cc3861"
ROOT = Path("/data/deployment/parallellines-unified") / APP
ROLES = {
    "bridge": ("parallellines-chat", "chat-oidc", "/data/deployment/parallellines-identity/compose.yaml"),
    "chat": ("pl-official-candidate-20261030", "openwebui", "/opt/pl-official-candidate-20261030/compose.yaml"),
    "newapi": ("pl-official-candidate-20261030", "newapi", "/opt/pl-official-candidate-20261030/compose.yaml"),
}
LIMIT = 2 * 1024 * 1024


class OperationError(Exception):
    """只携带稳定标识，不输出 Compose、凭据、命令 stderr 或响应正文。"""


def _path(value, *, owned=False):
    """固定事务与普通绝对路径不跟随链接；owned 只用于本轮私有记录/产物。"""
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts or (owned and path != ROOT and ROOT not in path.parents):
        raise OperationError("service_path_denied")
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise OperationError("service_path_symlink")
    return path


def _root(value):
    """只接受已成功 prepare 的固定应用版本，不能指向其他部署或数据目录。"""
    if Path(value) != ROOT:
        raise OperationError("service_root_denied")
    return _path(value, owned=True)


def _read(path):
    """读取限定的小型普通记录或 Compose；不读取 env_file 指向的内容。"""
    path = _path(path)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as stream:
        meta = os.fstat(stream.fileno())
        if not stat.S_ISREG(meta.st_mode) or meta.st_size > LIMIT:
            raise OperationError("service_file_limit")
        data = stream.read(LIMIT + 1)
    if len(data) > LIMIT:
        raise OperationError("service_file_grew")
    return data


def _save(path, record):
    """原子保存 0600 私有写意图；不会整文件写入任何 live Compose。"""
    path = _path(path, owned=True)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if stat.S_IMODE(path.parent.stat().st_mode) != 0o700:
        raise OperationError("service_record_directory_not_private")
    temporary = path.with_name(path.name + ".new-" + secrets.token_hex(8))
    data = (json.dumps(record, sort_keys=True, indent=2) + "\n").encode()
    if len(data) > LIMIT:
        raise OperationError("service_record_limit")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


@contextlib.contextmanager
def _lock(role):
    """同角色串行；共享 Compose 的跨服务写入仍由原生 CAS inode 锁协调。"""
    directory = _path(ROOT / "service-activation", owned=True)
    directory.mkdir(mode=0o700, exist_ok=True)
    if stat.S_IMODE(directory.stat().st_mode) != 0o700:
        raise OperationError("service_lock_directory_not_private")
    descriptor = os.open(directory / (role + ".lock"), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "r+b") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def _run(runner, arguments, *, timeout=20, cwd=None, accepted=(0,)):
    """全部外部动作复用调用方总期限；固定 exec-chdir 保留 Compose 的原工作目录。"""
    argv = [str(value) for value in arguments]
    if cwd is not None:
        directory = _path(cwd)
        argv = ["/usr/bin/python3", "-B", "-c",
                "import os,sys;os.chdir(sys.argv[1]);os.execvp(sys.argv[2],sys.argv[2:])", str(directory), *argv]
    value = runner.run(argv, timeout=timeout, accepted=accepted)
    return value.decode() if isinstance(value, bytes) else value


def _module(path):
    """仅加载本轮已验发布包的现有服务级部署器及其 CAS，不加载外部传入脚本。"""
    path = _path(path, owned=True)
    spec = importlib.util.spec_from_file_location("unified_prebuilt_service_release", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _inputs(root, role):
    """读取 prepare 的不可变服务身份和候选，不把 Git parent 当已部署运行基线。"""
    _root(root)
    if not isinstance(role, str) or role not in ROLES:
        raise OperationError("service_role_denied")
    prepared = json.loads(_read(ROOT / "prepared.json"))
    if prepared.get("application_revision") != APP:
        raise OperationError("service_prepared_revision_changed")
    target, image = prepared["targets"][role], prepared["images"][role]
    project, service, compose_file = ROLES[role]
    if (target["compose_project"], target["compose_service"]) != (project, service):
        raise OperationError("service_prepared_identity_changed")
    if image["base_image_id"] != target["image_id"] or any(not re.fullmatch(r"sha256:[0-9a-f]{64}", value) for value in (target["image_id"], image["image_id"])):
        raise OperationError("service_prepared_image_invalid")
    context = _path(image["context"], owned=True)
    source = ROOT / "inputs/chat/source"
    module = _module(source / "deploy/deploy-unified-login.py")
    if role == "newapi":
        files = target.get("compose_config_files", "").split(",")
        if files != [compose_file]:
            raise OperationError("newapi_compose_chain_changed")
        scope = {"source": str(source), "receipts": str(ROOT / "receipts"), role: {
            "container": target["name"].removeprefix("/"), "project": project, "service": service,
            "new_image": image["tag"], "expected_image_id": target["image_id"], "expected_compose_image": target["image"],
            "target_compose": compose_file, "working_dir": target["compose_working_dir"], "compose_files": files,
            "env_files": [p for p in (target.get("compose_env_files") or "").split(",") if p],
        }}
        if target.get("ports", {}).get("3000/tcp") != [{"HostIp": "127.0.0.1", "HostPort": "13000"}]:
            raise OperationError("newapi_loopback_binding_changed")
    else:
        scope = json.loads(_read(ROOT / "chat-scope.json"))
        item = scope[role]
        if (item["project"], item["service"], item["target_compose"], item["container"], item["expected_image_id"], item["new_image"]) != (project, service, compose_file, target["name"].removeprefix("/"), target["image_id"], image["tag"]):
            raise OperationError("service_scope_changed")
        if (Path(scope["source"]) != source or Path(scope["receipts"]) != ROOT / "receipts"
                or item["expected_compose_image"] != target["image"] or item["compose_files"] != [compose_file]
                or item["working_dir"] != target["compose_working_dir"]
                or item["env_files"] != [p for p in (target.get("compose_env_files") or "").split(",") if p]
                or (role == "chat" and Path(item["frontend_context"]) != context)):
            raise OperationError("service_prepared_consumer_missing")
    _path(compose_file)
    _path(scope[role]["working_dir"])
    return module, scope, target, image, context


def _image_id(runner, reference):
    """只读明确镜像的不可变 ID，不输出环境或完整 inspect。"""
    return _run(runner, ["docker", "image", "inspect", "--format", "{{.Id}}", reference]).strip()


def _images(runner, target, image):
    """激活/恢复前均保护候选、旧 base alias 及实际旧标签，拒绝重新指向。"""
    if (_image_id(runner, image["tag"]) != image["image_id"]
            or _image_id(runner, image["tag"] + "-base") != target["image_id"]
            or _image_id(runner, target["image"]) != target["image_id"]):
        raise OperationError("service_image_reference_drift")


def _old_image(runner, target):
    """恢复只要求实际旧引用仍可用；候选标签被清理不应破坏独立旧版本恢复路线。"""
    if _image_id(runner, target["image"]) != target["image_id"]:
        raise OperationError("service_original_image_reference_drift")


def _runtime(runner, scope):
    """只定位固定项目/服务；缺实例与 Docker 不可用分开，多个实例或改名明确停止。"""
    ids = _run(runner, ["docker", "ps", "-aq", "--filter", "label=com.docker.compose.project=" + scope["project"],
                        "--filter", "label=com.docker.compose.service=" + scope["service"]]).split()
    if not ids:
        return None
    if len(ids) != 1 or not re.fullmatch(r"[a-f0-9]{12,64}", ids[0]):
        raise OperationError("service_runtime_not_unique")
    template = ('{"image_id":{{json .Image}},"name":{{json .Name}},"running":{{json .State.Running}},'
                '"restarting":{{json .State.Restarting}},"dead":{{json .State.Dead}},"oom":{{json .State.OOMKilled}},'
                '"health":{{if .State.Health}}{{json .State.Health.Status}}{{else}}"none"{{end}}}')
    result = json.loads(_run(runner, ["docker", "inspect", "--format", template, ids[0]]))
    if result["name"].removeprefix("/") != scope["container"]:
        raise OperationError("service_runtime_name_changed")
    return result


def _compose(runner, scope, *arguments):
    """按原文件链/插值文件/目录调用 Compose；只允许调用方给出的固定服务级动作。"""
    argv = ["docker", "compose", "--project-name", scope["project"], "--project-directory", scope["working_dir"]]
    for name in scope["env_files"]:
        argv += ["--env-file", str(_path(name))]
    for name in scope["compose_files"]:
        argv += ["-f", str(_path(name))]
    return _run(runner, [*argv, *arguments], timeout=180, cwd=scope["working_dir"])


def _newapi_update(service, scope, context):
    """只换已制镜像/build 与两个非敏感开关，保留原 env_files、免费模型、额度和计费配置。"""
    if service.get("image") != scope["expected_compose_image"]:
        raise OperationError("newapi_compose_image_changed")
    service["image"] = scope["new_image"]
    service["build"] = {"context": str(context), "dockerfile": "Dockerfile"}
    if "environment" not in service:
        service["environment"] = {}
    if not isinstance(service["environment"], dict):
        raise OperationError("newapi_environment_mapping_required")
    service["environment"].update({"MAIN_UNIFIED_WEB_LOGIN_ENABLED": "true", "MAIN_WEB_ROOT_RECOVERY_ENABLED": "false"})


def _startup(runner, scope, expected_image, *, seconds=120):
    """只等已制目标容器启动；有原生 Health 等其就绪，没有则不增加 HTTP 或内容验收。"""
    deadline = time.monotonic() + seconds
    while True:
        current = _runtime(runner, scope)
        if current is not None and current["image_id"] != expected_image:
            raise OperationError("service_startup_image_changed")
        if current and (current["dead"] or current["oom"] or current["health"] == "unhealthy"):
            raise OperationError("service_startup_failed")
        if current and current["running"] and not current["restarting"]:
            if current["health"] in {"healthy", "none"}:
                return
        if time.monotonic() >= deadline:
            raise OperationError("service_startup_deadline")
        time.sleep(2)


def _state_path(role):
    return ROOT / "service-activation" / (role + ".json")


def _identity(path):
    """共享 Compose 必须保持原 inode；其他服务内容可变化，不以全文件摘要阻塞合法写入。"""
    meta = _path(path).stat()
    return {"device": meta.st_dev, "inode": meta.st_ino}


def _guard(record, utils, scope, runner, target, image, *, restoring=False):
    """恢复仅识别本次前像、后像与原 CAS 的规范化恢复形态，不接管未知服务变化。"""
    if (record.get("target_compose"), record.get("before_image_id"), record.get("before_image_reference"),
            record.get("after_image_id"), record.get("after_image_reference")) != (
            scope["target_compose"], target["image_id"], target["image"], image["image_id"], image["tag"]):
        raise OperationError("service_record_candidate_changed")
    _old_image(runner, target) if restoring else _images(runner, target, image)
    if _identity(scope["target_compose"]) != record["compose_identity"]:
        raise OperationError("service_compose_inode_changed")
    text = _read(scope["target_compose"]).decode()
    digest = utils.service_hash(text, scope["service"])
    if digest not in {record["before_service_hash"], record["after_service_hash"], record["restored_service_hash"]}:
        raise OperationError("service_compose_drift")
    current = _runtime(runner, scope)
    if current is None:
        if not record.get("restart_intent") or record["status"] in {"active", "rolled_back"}:
            raise OperationError("service_runtime_missing_without_owned_restart")
    elif current["image_id"] not in {target["image_id"], image["image_id"]}:
        raise OperationError("service_runtime_drift")
    return text, digest, current


def _load_state(role):
    path = _state_path(role)
    if not path.exists():
        return None
    value = json.loads(_read(path))
    if value.get("schema") != 1 or value.get("application_revision") != APP or value.get("role") != role:
        raise OperationError("service_record_not_owned")
    return value


def activate(root, role, runner):
    """激活一个已制角色，先私有保存可恢复写意图；重复 active 只接受同候选实际 ID。"""
    module, scope, target, image, context = _inputs(root, role)
    item, utils = scope[role], module.base.utils
    with _lock(role):
        previous = _load_state(role)
        _images(runner, target, image)
        current = _runtime(runner, item)
        if previous is not None:
            _text, digest, current = _guard(previous, utils, item, runner, target, image)
            if previous["status"] == "active":
                if not current or current["image_id"] != image["image_id"] or digest != previous["after_service_hash"]:
                    raise OperationError("service_active_record_runtime_changed")
                _startup(runner, item, image["image_id"], seconds=240 if role == "chat" else 120)
                return {"complete": True, "role": role, "already_active": True, "image_id": image["image_id"]}
            if previous["status"] != "rolled_back":
                raise OperationError("service_incomplete_activation_requires_rollback")
        if not current or current["image_id"] != target["image_id"]:
            raise OperationError("service_before_runtime_changed")
        text = _read(item["target_compose"]).decode()
        old = copy.deepcopy(utils.load_yaml(text)["services"][item["service"]])
        if old.get("image") != target["image"]:
            raise OperationError("service_before_image_reference_changed")
        # 只复用原 update 的配置语义，不调用会重读源码/4810文件的旧 deploy 验收流程。
        provisional = module.UnifiedRelease(scope, role) if role != "newapi" else None
        change = (lambda service: provisional.update(service, context)) if provisional else (lambda service: _newapi_update(service, item, context))
        after = utils.patch_service(text, item["service"], change)
        def restore(service):
            service.clear()
            service.update(copy.deepcopy(old))
        restored = utils.patch_service(after, item["service"], restore)
        old_yaml = utils.yaml.dump({"services": {item["service"]: old}}, Dumper=utils.ComposeDumper, sort_keys=False, allow_unicode=True)
        record = {"schema": 1, "application_revision": APP, "role": role, "status": "intent",
                  "compose_identity": _identity(item["target_compose"]), "target_compose": item["target_compose"],
                  "before_service_hash": utils.service_hash(text, item["service"]), "after_service_hash": utils.service_hash(after, item["service"]),
                  "restored_service_hash": utils.service_hash(restored, item["service"]), "old_service_yaml": old_yaml,
                  "before_image_id": target["image_id"], "before_image_reference": target["image"], "after_image_id": image["image_id"],
                  "after_image_reference": image["tag"], "restart_intent": False}
        if previous:
            record["previous_attempt"] = {name: previous[name] for name in ("status", "before_service_hash", "after_service_hash", "restored_service_hash")}
        _save(_state_path(role), record)
        try:
            record["status"] = "activating"
            _save(_state_path(role), record)
            _startup(runner, item, target["image_id"], seconds=240 if role == "chat" else 120)
            _compose(runner, item, "config", "--quiet")
            _text, digest, _current = _guard(record, utils, item, runner, target, image)
            if digest != record["before_service_hash"]:
                raise OperationError("service_changed_before_cas")
            record["release_stage"] = "cas"
            _save(_state_path(role), record)
            utils.cas_service_update(Path(item["target_compose"]), item["service"], digest, change,
                                     ROOT / ("service-activation/" + role + "-backup"))
            _compose(runner, item, "config", "--quiet")
            _guard(record, utils, item, runner, target, image)
            record["restart_intent"], record["release_stage"] = True, "restart"
            _save(_state_path(role), record)
            _compose(runner, item, "up", "-d", "--no-deps", "--no-build", "--pull", "never", item["service"])
            _startup(runner, item, image["image_id"], seconds=240 if role == "chat" else 120)
            _text, digest, current = _guard(record, utils, item, runner, target, image)
            if digest != record["after_service_hash"] or not current or current["image_id"] != image["image_id"]:
                raise OperationError("service_activation_not_complete")
            record["status"] = "active"
            _save(_state_path(role), record)
            return {"complete": True, "role": role, "image_id": image["image_id"], "recompiled": False}
        except Exception as error:
            record["status"], record["error_type"] = "failed", type(error).__name__
            _save(_state_path(role), record)
            try:
                _restore(module, scope, role, target, image, runner, record)
            except Exception as recovery:
                record["status"], record["recovery_error_type"] = "recovery_required", type(recovery).__name__
                _save(_state_path(role), record)
                raise OperationError("service_activation_failed:" + role + ":recovery_required") from None
            raise OperationError("service_activation_failed:" + role + ":rolled_back") from None


def _restore(module, scope, role, target, image, runner, record):
    """在已有角色锁内条件恢复；从未重建容器的失败只还原配置，不额外重启旧服务。"""
    item, utils = scope[role], module.base.utils
    _text, digest, current = _guard(record, utils, item, runner, target, image, restoring=True)
    before_hashes = {record["before_service_hash"], record["restored_service_hash"]}
    if digest not in before_hashes or not current or current["image_id"] != target["image_id"]:
        old = utils.load_yaml(record["old_service_yaml"])["services"][item["service"]]
        def restore(service):
            service.clear()
            service.update(copy.deepcopy(old))
        record["status"] = "rolling_back"
        _save(_state_path(role), record)
        _old_image(runner, target)
        if digest == record["after_service_hash"]:
            utils.cas_service_update(Path(item["target_compose"]), item["service"], digest, restore,
                                     ROOT / ("service-activation/" + role + "-rollback-backup"))
        _compose(runner, item, "config", "--quiet")
        if record.get("restart_intent") or not current or current["image_id"] != target["image_id"]:
            _old_image(runner, target)
            _compose(runner, item, "up", "-d", "--no-deps", "--no-build", "--pull", "never", item["service"])
    _startup(runner, item, target["image_id"], seconds=240 if role == "chat" else 120)
    _text, digest, current = _guard(record, utils, item, runner, target, image, restoring=True)
    if digest not in before_hashes or not current or current["image_id"] != target["image_id"]:
        raise OperationError("service_rollback_not_complete")
    record["status"] = "rolled_back"
    _save(_state_path(role), record)
    return {"complete": True, "role": role, "restored_image_id": target["image_id"], "service_only": True}


def rollback(root, role, runner):
    """只恢复本服务已保存前像；未知服务/镜像漂移停止，不整文件覆盖共享 Compose。"""
    module, scope, target, image, _context = _inputs(root, role)
    with _lock(role):
        record = _load_state(role)
        if record is None:
            return {"complete": True, "role": role, "not_started": True}
        return _restore(module, scope, role, target, image, runner, record)
