"""统一登录定向发布盘点：只输出运行身份与公开源码摘要，不读取凭据或展开 Compose。"""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

APP = "a2cfeddeec01ca0d5def4b3308103f3d85cc3861"
ROOT = Path("/data/deployment/parallellines-unified") / APP


def save(path, value):
    """只保存本轮私有事务记录；不向日志展开 Compose 或会话资料。"""
    path = Path(path)
    if ROOT not in path.parents or path.is_symlink():
        raise OperationError("transaction_path_denied")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(path.name + ".new")
    if temporary.exists():
        raise OperationError("transaction_temporary_exists")
    with temporary.open("x", encoding="utf-8") as stream:
        os.chmod(temporary, 0o600)
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def load_module(name, path):
    """加载本次已提交运维模块或公开发布包中的现有部署能力，不执行外部传入源码。"""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class OperationError(Exception):
    """稳定失败标识；不将命令原始 stderr 或环境值写入共享日志。"""


def error_code(error):
    """仅下发自有受控模块的稳定码；库异常只记类型，不展开潜在凭据或配置。"""
    if isinstance(error, OperationError) or type(error).__module__ in {"unified_nginx_release", "unified_source_alignment", "unified_services_activate"}:
        value = str(error)
        if re.fullmatch(r"[A-Za-z0-9_:/.-]{1,250}", value):
            return value
    return type(error).__name__


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
                       "config_files": "project.config_files", "env_files": "project.environment_file",
                       "config-hash": "config-hash"}.items():
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


def selected(values, project, service):
    """只选择实际 Compose 文件链管理的唯一运行服务，不接管继承镜像标签的独立容器。"""
    matches = [item for item in values if item.get("compose_project") == project
               and item.get("compose_service") == service and item.get("compose_config_files")]
    if len(matches) != 1 or not matches[0]["running"]:
        raise OperationError("target_not_unique_or_running:" + service)
    return matches[0]


def build_image(runner, role, base_id, context, dockerfile, tag):
    """仅离线封装已验产物，旧镜像保留；已有候选必须属于本轮记录，不覆盖标签。"""
    alias = tag + "-base"
    record_path = ROOT / ("image-" + role + ".json")
    if runner.run(["docker", "image", "ls", "-q", tag]).strip():
        if record_path.is_file() and not record_path.is_symlink():
            previous = json.loads(record_path.read_text())
            observed = runner.run(["docker", "image", "inspect", "--format", "{{.Id}}", tag]).strip()
            if previous.get("tag") == tag and previous.get("base_image_id") == base_id and previous.get("image_id") == observed:
                return previous
        raise OperationError("candidate_tag_already_exists:" + role)
    existing = runner.run(["docker", "image", "ls", "-q", alias]).strip()
    if existing:
        if runner.run(["docker", "image", "inspect", "--format", "{{.Id}}", alias]).strip() != base_id:
            raise OperationError("candidate_base_changed:" + role)
    else:
        runner.run(["docker", "image", "tag", base_id, alias])
    (context / "Dockerfile").write_text(dockerfile.replace("__BASE__", alias), encoding="utf-8")
    print(json.dumps({"stage": "build", "component": role}), flush=True)
    runner.run(["docker", "build", "--pull=false", "--network=none", "-t", tag, context], timeout=300)
    image = runner.run(["docker", "image", "inspect", "--format", "{{.Id}}", tag]).strip()
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
        raise OperationError("candidate_image_invalid:" + role)
    result = {"tag": tag, "image_id": image, "context": str(context), "base_image_id": base_id}
    save(record_path, result)
    return result


def make_chat_scope(chat_root, targets, runner):
    """从固定发布包预期与当前 Compose 标签生成非敏感范围，原生部署器再核实际源与服务。"""
    manifest = json.loads((chat_root / "release-input-manifest.json").read_text())
    plan = json.loads(Path(__file__).with_name("unified-login-release-plan.json").read_text())
    if manifest["git_commit"] != plan["revisions"]["chat"]:
        raise OperationError("chat_source_revision_changed")
    scope = {"source": str(chat_root / "source"), "receipts": str(ROOT / "receipts")}
    for role in ("bridge", "chat"):
        target = targets[role]
        compose_files = (target.get("compose_config_files") or "").split(",")
        if len(compose_files) != 1 or not Path(compose_files[0]).is_absolute():
            raise OperationError("chat_compose_chain_requires_review")
        scope[role] = {
            "container": target["name"].removeprefix("/"), "project": target["compose_project"],
            "service": target["compose_service"], "new_image": "parallellines-" + ("identity" if role == "bridge" else "chat") + ":unified-" + manifest["git_commit"][:8],
            "expected_image_id": target["image_id"], "expected_compose_image": target["image"],
            "target_compose": compose_files[0], "working_dir": target["compose_working_dir"],
            "env_files": [path for path in (target.get("compose_env_files") or "").split(",") if path],
            "compose_files": compose_files, "source_root": "/app", "interpreter": "node" if role == "bridge" else "python",
            "expected_source": manifest["expected_bridge_before" if role == "bridge" else "expected_backend_before"],
        }
        if role == "chat":
            scope[role].update({"frontend_context": str(chat_root / "contexts/chat"),
                               "frontend_manifest_sha256": manifest["frontend_manifest_sha256"]})
    (ROOT / "receipts").mkdir(mode=0o700, exist_ok=True)
    release_module = load_module("chat_scope_release", chat_root / "source/deploy/deploy-unified-login.py")
    for role in ("bridge", "chat"):
        release = release_module.UnifiedRelease(scope, role)
        observed = release.source_hashes(list(scope[role]["expected_source"]), "/app", scope[role]["interpreter"])
        if observed != scope[role]["expected_source"]:
            raise OperationError("chat_component_source_changed:" + role)
        release.compose("config", "--quiet")
    return scope


def prepare():
    """下载固定提交产物并构建五个候选镜像；不切换服务、不读取真实环境文件或数据库。"""
    os.umask(0o077)
    if ROOT.is_symlink() or any(path.is_symlink() for path in ROOT.parents):
        raise OperationError("deployment_root_symlink")
    ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    if (ROOT / "prepared.json").exists():
        raise OperationError("already_prepared_use_recorded_candidate")
    runner = Runner(2400)
    if runner.run(["findmnt", "-n", "-o", "TARGET", "/data"]).strip() != "/data" or shutil.disk_usage(ROOT).free < 2 * 1024 ** 3:
        raise OperationError("deployment_data_disk_not_ready")
    before = inventory(runner)
    targets = {
        "api": selected(before["containers"], "parallellines", "api"),
        "web": selected(before["containers"], "parallellines", "web"),
        "circle": selected(before["containers"], "parallellines", "forum-web"),
        "bridge": selected(before["containers"], "parallellines-chat", "chat-oidc"),
        "chat": selected(before["containers"], "pl-official-candidate-20261030", "openwebui"),
        "newapi": selected(before["containers"], "pl-official-candidate-20261030", "newapi"),
    }
    expected = {"api": "sha256:4f2e43c0ee4a95c93734b075be7860cf2e4ce1407c1603f8f8689a309e4e00ea",
                "web": "sha256:db4c12e1ce357f6ec3b63eff368fe0ff46697835c2f4975e1d0b12f66528ffc6",
                "circle": "sha256:581718a121c5bfd02e63b18da570142b3f358528fbb6b4e0313691f297a30f46",
                "bridge": "sha256:6837ffcfbef78fe4316155807d17148bd53848c78979743ac08f3970994c7b35",
                "chat": "sha256:e672d829c3a9a1306f55727c7cf624fade235e4ec65fb00ecdfdf5ae6a0fc42b"}
    if any(targets[role]["image_id"] != value for role, value in expected.items()):
        raise OperationError("production_baseline_changed")
    if targets["newapi"]["image"] != "parallellines-newapi:v0.13.2-pkce.9" or before["source_evidence"].get("gateway_binary") != "26d44a3a75ac9b1c67b3830445378d92415f91ed2bdb8afabe9e6e95f5d62546":
        raise OperationError("gateway_baseline_changed")
    save(ROOT / "before.json", before)
    plan = json.loads(Path(__file__).with_name("unified-login-release-plan.json").read_text())
    if plan["application_revision"] != APP:
        raise OperationError("application_revision_changed")
    downloader = load_module("unified_artifact_prepare", Path(__file__).with_name("unified_artifact_prepare.py"))
    try:
        payload = downloader.prepare(plan, ROOT, runner)
    except downloader.ArtifactPreparationError as error:
        raise OperationError("artifact:" + str(error)) from None
    save(ROOT / "payload.json", payload)
    # 每个下载产物的位置由固定key决定；模块返回记录只作交付证据，不接受任意来源路径。
    inputs = ROOT / "inputs"
    app = inputs / "main-app"
    source = json.loads((app / "main-source-manifest.json").read_text())
    if source["application_revision"] != APP:
        raise OperationError("main_source_revision_changed")
    actual = before["source_evidence"]["main_api"]
    for name, record in source["files"].items():
        if hashlib.sha256((app / name).read_bytes()).hexdigest() != record["sha256"]:
            raise OperationError("main_payload_changed")
        if name.startswith("apps/api/app/") and actual.get("/app/app/" + name.removeprefix("apps/api/app/")) != record["before_sha256"]:
            raise OperationError("main_source_before_changed")
    prepared = {"application_revision": APP, "targets": targets, "images": {}, "payload": payload}
    builds = ROOT / "builds"
    builds.mkdir(mode=0o700, exist_ok=True)
    api_context = builds / "api"
    api_context.mkdir(mode=0o700, exist_ok=True)
    for name in source["files"]:
        if name.startswith("apps/api/app/"):
            path = api_context / "app" / name.removeprefix("apps/api/app/")
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(app / name, path)
    prepared["images"]["api"] = build_image(runner, "api", targets["api"]["image_id"], api_context,
        "FROM __BASE__\nCOPY app/ /app/app/\nLABEL org.opencontainers.image.revision=" + APP + "\n", "parallellines-unified-api:a2cfedde")
    for role, key in (("web", "main-web"), ("circle", "circle-web")):
        context = builds / role
        context.mkdir(mode=0o700, exist_ok=True)
        # 公开静态文件与运维上下文分开，Dockerfile和检查记录不能被复制到可访问目录。
        shutil.copytree(inputs / key, context / "html", dirs_exist_ok=True)
        shutil.copyfile(app / "apps/web/nginx.conf", context / "nginx.conf")
        dockerfile = ("FROM __BASE__\nRUN rm -rf /usr/share/nginx/html && mkdir -p /usr/share/nginx/html\n"
                      "COPY html/ /usr/share/nginx/html/\nCOPY nginx.conf /etc/nginx/conf.d/default.conf\n"
                      "LABEL org.opencontainers.image.revision=" + APP + "\n")
        prepared["images"][role] = build_image(runner, role, targets[role]["image_id"], context, dockerfile,
            "parallellines-" + ("web" if role == "web" else "forum-web") + ":unified-a2cfedde")
        runner.run(["docker", "run", "--rm", "--network", "none", "--entrypoint", "nginx", prepared["images"][role]["tag"], "-t"], timeout=30)
    # Chat/issuer 使用原有服务级部署器制作候选，不调用其包含激活的deploy入口。
    chat_root = inputs / "chat"
    module = load_module("chat_unified_release", chat_root / "source/deploy/deploy-unified-login.py")
    scope = make_chat_scope(chat_root, targets, runner)
    for role in ("bridge", "chat"):
        record_path = ROOT / ("image-" + role + ".json")
        scope_path = ROOT / ("scope-" + role + ".json")
        if record_path.is_file() and scope_path.is_file():
            record = json.loads(record_path.read_text())
            observed = runner.run(["docker", "image", "inspect", "--format", "{{.Id}}", record["tag"]]).strip()
            if record.get("tag") != scope[role]["new_image"] or record.get("base_image_id") != targets[role]["image_id"] or record["image_id"] != observed:
                raise OperationError("owned_candidate_changed:" + role)
            scope[role] = json.loads(scope_path.read_text())
            prepared["images"][role] = record
            continue
        release = module.UnifiedRelease(scope, role)
        release.run_dir = builds / role
        release.run_dir.mkdir(mode=0o700, exist_ok=True)
        context, image = release.build()
        scope[role] = release.s
        prepared["images"][role] = {"tag": scope[role]["new_image"], "image_id": image, "context": str(context), "base_image_id": targets[role]["image_id"]}
        save(record_path, prepared["images"][role])
        save(scope_path, scope[role])
    save(ROOT / "chat-scope.json", scope)
    newapi_context = builds / "newapi"
    newapi_context.mkdir(mode=0o700, exist_ok=True)
    shutil.copyfile(payload["inputs"]["newapi-binary"], newapi_context / "new-api")
    os.chmod(newapi_context / "new-api", 0o755)
    prepared["images"]["newapi"] = build_image(runner, "newapi", targets["newapi"]["image_id"], newapi_context,
        "FROM __BASE__\nCOPY --chmod=0755 new-api /new-api\nLABEL org.opencontainers.image.version=v0.13.2-pkce.10\n"
        "LABEL org.opencontainers.image.revision=" + plan["revisions"]["newapi"] + "\n", "parallellines-newapi:v0.13.2-pkce.10")
    save(ROOT / "prepared.json", prepared)
    return {"complete": True, "stage": "prepared", "application_revision": APP, "services_activated": False,
            "images": {key: value["tag"] for key, value in prepared["images"].items()}}


def transaction():
    """只消费本次已完成的候选记录，不从未知运行镜像推断发布成功。"""
    path = ROOT / "prepared.json"
    if path.is_symlink() or not path.is_file():
        raise OperationError("prepared_transaction_required")
    value = json.loads(path.read_text())
    if value.get("application_revision") != APP:
        raise OperationError("prepared_revision_changed")
    return value


def compose(runner, files, services, env_files=()):
    """沿现有项目和真实文件链运行明确服务，不启动默认栈、不构建其他服务。"""
    command = ["docker", "compose", "--project-name", "parallellines", "--project-directory", "/opt/parallellines"]
    for path in env_files:
        command += ["--env-file", path]
    for path in files:
        command += ["-f", path]
    return runner.run(command + services, timeout=240)


def wait_main(runner, prepared, expected_roles):
    """必要服务就绪有总时限；仅检查本轮指定镜像，不用页面200冒充已替换。"""
    deadline = time.monotonic() + 150
    while True:
        current = records(runner)
        matches = []
        for role in expected_roles:
            target = prepared["targets"][role]
            observed = selected(current, target["compose_project"], target["compose_service"])
            if observed["image_id"] != prepared["images"][role]["image_id"]:
                raise OperationError("running_candidate_image_mismatch:" + role)
            state = json.loads(runner.run(["docker", "inspect", "--format", '{"running":{{.State.Running}},"oom":{{.State.OOMKilled}},"health":{{json .State.Health.Status}}}', observed["id"]]))
            if state["oom"] or not state["running"]:
                raise OperationError("main_candidate_failed:" + role)
            matches.append(state["health"] == "healthy")
        if all(matches):
            return
        if time.monotonic() >= deadline:
            raise OperationError("main_candidate_health_deadline")
        time.sleep(2)


def rollback_main(runner):
    """只恢复本轮写意图中的三个应用服务和Nginx/源码；不回灌数据或重建网关。"""
    prepared = transaction()
    intent_path = ROOT / "main-intent.json"
    if not intent_path.is_file():
        return {"complete": True, "stage": "main_not_started"}
    intent = json.loads(intent_path.read_text())
    current = records(runner)
    for role in ("api", "web", "circle"):
        target = prepared["targets"][role]
        item = selected(current, target["compose_project"], target["compose_service"])
        if item["image_id"] not in (target["image_id"], prepared["images"][role]["image_id"]):
            raise OperationError("rollback_runtime_drift:" + role)
    # 原文件链保留原image；先复原应用运行版本，再由Nginx事务恢复原配置和Git索引。
    for role in ("circle", "web", "api"):
        target = prepared["targets"][role]
        observed = selected(records(runner), target["compose_project"], target["compose_service"])
        if observed["image_id"] == target["image_id"]:
            continue
        tag_id = runner.run(["docker", "image", "inspect", "--format", "{{.Id}}", target["image"]]).strip()
        if tag_id != target["image_id"]:
            raise OperationError("rollback_original_image_tag_changed:" + role)
        compose(runner, target["compose_config_files"].split(","),
                ["up", "-d", "--no-deps", "--no-build", "--pull", "never", target["compose_service"]],
                [p for p in (target.get("compose_env_files") or "").split(",") if p])
    alignment = load_module("unified_source_alignment", Path(__file__).with_name("unified_source_alignment.py"))
    nginx = load_module("unified_nginx_release", Path(__file__).with_name("unified_nginx_release.py"))
    nginx.rollback(intent["nginx_transaction"], source_restore=lambda: alignment.restore(ROOT, runner))
    for name, old in intent["markers"].items():
        path = Path("/opt/parallellines/.deployment") / name
        expected = "unified-a2cfedde\n"
        if path.exists() and path.read_text() not in (expected, old):
            raise OperationError("rollback_marker_drift")
        if old is None:
            if path.exists():
                path.unlink()
        else:
            path.write_text(old)
    restored = {**prepared, "images": {role: {"image_id": prepared["targets"][role]["image_id"]} for role in ("api", "web", "circle")}}
    wait_main(runner, restored, ("api", "web", "circle"))
    save(ROOT / "main-rolled-back.json", {"complete": True, "restored_images": True, "data_restored": False})
    save(ROOT / "main-active.json", {"complete": False, "application_revision": APP, "state": "rolled_back"})
    return {"complete": True, "stage": "main_rolled_back"}


def activate_main():
    """接续Nginx/源后仅切换三个主站服务；保留手动恢复，不因就绪等待自动回退。"""
    os.umask(0o077)
    runner = Runner(1000)
    prepared = transaction()
    if (ROOT / "main-active.json").is_file() and json.loads((ROOT / "main-active.json").read_text()).get("state") in {"active", "switched"}:
        return {"complete": True, "stage": "main_already_active"}
    current = records(runner)
    for role in ("api", "web", "circle"):
        target = prepared["targets"][role]
        if selected(current, target["compose_project"], target["compose_service"])["image_id"] != target["image_id"]:
            raise OperationError("main_baseline_changed:" + role)
    alignment = load_module("unified_source_alignment", Path(__file__).with_name("unified_source_alignment.py"))
    nginx = load_module("unified_nginx_release", Path(__file__).with_name("unified_nginx_release.py"))
    alignment.prepare(ROOT, runner)
    tx = Path("/opt/parallellines/.deployment/unified-login") / APP / "nginx"
    source = ROOT / "inputs/main-app"
    nginx.prepare(tx, source / "deploy/nginx/default.conf", source / "deploy/nginx/forum.conf")
    files = []
    env_files = []
    for role in ("api", "web", "circle"):
        for path in prepared["targets"][role]["compose_config_files"].split(","):
            if path not in files:
                files.append(path)
        for path in (prepared["targets"][role].get("compose_env_files") or "").split(","):
            if path and path not in env_files:
                env_files.append(path)
    override = ROOT / "runtime-main.override.json"
    service_names = {"api": "api", "web": "web", "circle": "forum-web"}
    services = {service_names[role]: {"image": prepared["images"][role]["tag"],
                "build": {"context": prepared["images"][role]["context"], "dockerfile": "Dockerfile"}}
                for role in service_names}
    services["api"]["environment"] = {"UNIFIED_AUTH_ENABLED": "true", "UNIFIED_AUTH_ALLOW_LOOPBACK_HTTP": "false"}
    save(override, {"services": services})
    markers = {}
    for name in ("forum-enabled", "unified-auth-enabled"):
        path = Path("/opt/parallellines/.deployment") / name
        if path.is_symlink() or (path.exists() and (not path.is_file() or path.stat().st_size > 256)):
            raise OperationError("main_marker_invalid")
        markers[name] = path.read_text() if path.exists() else None
    save(ROOT / "main-intent.json", {"nginx_transaction": str(tx), "files": files, "env_files": env_files, "markers": markers})
    try:
        nginx.activate(tx, source_align=lambda: alignment.align(ROOT, runner))
        compose(runner, files + [str(override)], ["config", "--quiet"], env_files)
        compose(runner, files + [str(override)], ["up", "-d", "--no-deps", "--no-build", "--pull", "never", "api", "web", "forum-web"], env_files)
        for name in markers:
            (Path("/opt/parallellines/.deployment") / name).write_text("unified-a2cfedde\n")
        save(ROOT / "main-active.json", {"complete": True, "application_revision": APP, "state": "switched", "readiness_waited": False})
    except Exception as error:
        save(ROOT / "main-failure.json", {"error_type": type(error).__name__, "error_code": error_code(error), "automatic_rollback": False})
        raise OperationError("main_activation_command_failed:" + error_code(error)) from None
    return {"complete": True, "stage": "main_switched", "application_revision": APP, "gateway_recreated": False,
            "readiness_waited": False, "automatic_rollback": False}


def activate_services():
    """直接切换三个已制下游版本；保留意图与旧版，不执行额外验收或自动回退。"""
    active = ROOT / "main-active.json"
    if not active.is_file() or json.loads(active.read_text()).get("state") not in {"active", "switched"}:
        raise OperationError("main_activation_required")
    transaction()
    runner = Runner(900)
    module = load_module("unified_services_activate", Path(__file__).with_name("unified_services_activate.py"))
    results = []
    try:
        for role in ("bridge", "chat", "newapi"):
            print(json.dumps({"stage": "activate", "component": role}), flush=True)
            results.append(module.activate(ROOT, role, runner))
        save(ROOT / "all-active.json", {"complete": True, "application_revision": APP, "components": results,
                                        "additional_validation": False, "automatic_rollback": False})
    except Exception as error:
        save(ROOT / "services-failure.json", {"error": error_code(error), "completed": results,
                                              "automatic_rollback": False})
        raise OperationError("services_activation_command_failed:" + error_code(error)) from None
    return {"complete": True, "stage": "all_services_switched", "application_revision": APP,
            "components": ["main-api", "main-web", "circle", "bridge", "chat", "newapi"],
            "additional_validation": False, "recompiled": False, "automatic_rollback": False}


def remove_source_archive():
    """按用户纠正仅撤本轮闲置源码专包和下载依赖，不改变镜像、运行材料或业务数据。"""
    key = "newapi-source"
    expected_hash = "067c78864b90f6bfaa1f6840728cd86d3150cd204512ad46b521bad64d73118f"
    expected_size = 14643572
    target = ROOT / "artifacts/newapi-source--new-api-v0.13.2-pkce.10-corresponding-source.tar.gz"
    receipt = ROOT / "artifacts/.newapi-source.json"
    for path in (ROOT, target.parent, ROOT / "inputs"):
        if path.is_symlink() or not path.is_dir():
            raise OperationError("archive_cleanup_root_invalid")
    records_to_update = []
    for path in (ROOT / "payload.json", ROOT / "prepared.json", ROOT / "inputs/.prepared.json"):
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 2 * 1024 * 1024:
            raise OperationError("archive_cleanup_record_invalid")
        value = json.loads(path.read_text())
        payload = value["payload"] if path.name == "prepared.json" else value
        old = payload.get("artifacts", {}).get(key)
        if old is not None and (old.get("path") != str(target) or old.get("kind") != "file"
                or old.get("sha256") != expected_hash or old.get("bytes") != expected_size):
            raise OperationError("archive_cleanup_ownership_changed")
        payload.get("artifacts", {}).pop(key, None)
        payload.get("inputs", {}).pop(key, None)
        records_to_update.append((path, value))
    exists = target.exists()
    if target.is_symlink() or (exists and (not target.is_file() or target.stat().st_size != expected_size or target.stat().st_nlink != 1)):
        raise OperationError("archive_cleanup_file_changed")
    if exists:
        digest = hashlib.sha256()
        with target.open("rb") as stream:
            for chunk in iter(lambda: stream.read(65536), b""):
                digest.update(chunk)
        if digest.hexdigest() != expected_hash:
            raise OperationError("archive_cleanup_content_changed")
    if receipt.exists():
        if receipt.is_symlink() or not receipt.is_file() or receipt.stat().st_size > 4096:
            raise OperationError("archive_cleanup_receipt_changed")
        old = json.loads(receipt.read_text())
        if old.get("key") != key or old.get("sha256") != expected_hash or old.get("bytes") != expected_size:
            raise OperationError("archive_cleanup_receipt_changed")
    save(ROOT / "source-archive-removal.json", {"state": "removing", "reason": "user_removed_extra_source_archive", "archive_was_present": exists})
    if exists:
        target.unlink()
    if receipt.exists():
        receipt.unlink()
    for path, value in records_to_update:
        save(path, value)
    save(ROOT / "source-archive-removal.json", {"state": "removed", "reason": "user_removed_extra_source_archive", "archive_was_present": exists})
    return {"complete": True, "stage": "extra_source_archive_removed", "archive_deleted": exists,
            "download_dependency_removed": True, "running_services_changed": False, "application_data_changed": False}


def diagnose_chat_startup():
    """仅取得候选启动错误：无网络、独立tmpfs、清空继承环境，结束后移除本次临时容器。"""
    runner = Runner(150)
    prepared = transaction()
    image = prepared["images"]["chat"]
    observed = runner.run(["docker", "image", "inspect", "--format", "{{.Id}}", image["tag"]]).strip()
    if observed != image["image_id"]:
        raise OperationError("diagnostic_candidate_changed")
    name = "pl-unified-chat-startup-a2cfedde"
    if runner.run(["docker", "ps", "-aq", "--filter", "name=^/" + name + "$"]).strip():
        raise OperationError("diagnostic_container_already_exists")
    settings = {"HOME": "/tmp", "DATABASE_URL": "sqlite:////app/backend/data/webui.db",
                "DATA_DIR": "/app/backend/data", "OFFLINE_MODE": "true", "MAIN_UNIFIED_LOGIN_ENABLED": "true",
                "WEBUI_SECRET_KEY": "isolated-startup-diagnostic-not-a-production-key",
                "OAUTH_SESSION_TOKEN_ENCRYPTION_KEY": "isolated-oauth-diagnostic-not-a-production-key",
                "ENABLE_OAUTH": "false", "OPENID_PROVIDER_URL": "", "ENABLE_OPENAI_API": "false",
                "ENABLE_OLLAMA_API": "false", "RAG_EMBEDDING_MODEL": "", "PYTHONUNBUFFERED": "1"}
    program = "import os,sys,runpy,functools,inspect\npath=os.environ.get('PATH','/usr/local/bin:/usr/bin:/bin')\nos.environ.clear()\nos.environ.update(" + repr(settings) + ")\nos.environ['PATH']=path\n"
    program += """
import uvicorn.config as uc
def watch(obj,name):
    f=getattr(obj,name,None)
    if not inspect.iscoroutinefunction(f):
        return
    @functools.wraps(f)
    async def observed(*args,**kwargs):
        print('PL_START '+name,flush=True)
        try:
            return await f(*args,**kwargs)
        finally:
            print('PL_END '+name,flush=True)
    setattr(obj,name,observed)
original=uc.Config.load
def load(self):
    print('PL_START config_load',flush=True)
    result=original(self)
    main=sys.modules.get('open_webui.main')
    if main:
        for name in ('import_legacy_config_json','seed_registered_defaults','initialize_runtime_config','migrate_legacy_webhook_config','install_tool_and_function_dependencies','get_all_models','set_tool_servers','set_terminal_servers','publish_event'):
            watch(main,name)
    mfa=sys.modules.get('open_webui.utils.mfa')
    if mfa:
        watch(mfa,'validate_mfa_configuration')
    apps=sys.modules.get('open_webui.socket.apps')
    if apps:
        watch(apps.connections,'start')
    print('PL_END config_load',flush=True)
    return result
uc.Config.load=load
sys.argv=['uvicorn','open_webui.main:app','--host','0.0.0.0','--port','8080','--no-proxy-headers','--workers','1','--ws-per-message-deflate','true']
runpy.run_module('uvicorn',run_name='__main__')
"""
    cid = runner.run(["docker", "run", "-d", "--name", name, "--network", "none", "--memory", "1536m", "--cpus", "1",
                      "--pids-limit", "256", "--tmpfs", "/app/backend/data:rw,size=128m", "--label", "pl.unified.diagnostic=" + APP,
                      "--label", "com.docker.compose.project=pl-unified-diagnostic", "--label", "com.docker.compose.service=diagnostic",
                      "--entrypoint", "python", image["tag"], "-c", program], timeout=20).strip()
    if not re.fullmatch(r"[a-f0-9]{64}", cid):
        raise OperationError("diagnostic_container_id_invalid")
    log = ""
    state = {}
    try:
        until = time.monotonic() + 35
        while True:
            state = json.loads(runner.run(["docker", "inspect", "--format", '{"running":{{.State.Running}},"exit_code":{{.State.ExitCode}},"oom":{{.State.OOMKilled}}}', cid]))
            if not state["running"] or time.monotonic() >= until:
                break
            time.sleep(2)
        # docker logs的Python traceback通常在stderr；不公开完整日志，只留下本地私有记录。
        result = subprocess.run(["docker", "logs", "--tail", "100", cid], capture_output=True, text=True, timeout=10)
        log = result.stdout + result.stderr
        local_status = runner.run(["docker", "exec", cid, "python", "-c",
            "import http.client\nc=http.client.HTTPConnection('127.0.0.1',8080,timeout=2)\n"
            "try:\n c.request('GET','/health');print(c.getresponse().status)\n"
            "except Exception as e:\n print(type(e).__name__)\n"
            "finally:\n c.close()"], accepted=(0, 1), timeout=5).strip()
        path = ROOT / "chat-startup-diagnostic.log"
        with path.open("w", encoding="utf-8") as stream:
            os.chmod(path, 0o600)
            stream.write(log[:131072])
    finally:
        identity = runner.run(["docker", "inspect", "--format", '{{.Name}} {{index .Config.Labels "pl.unified.diagnostic"}}', cid]).strip()
        if identity != "/" + name + " " + APP:
            raise OperationError("diagnostic_cleanup_identity_changed")
        runner.run(["docker", "rm", "-f", cid], timeout=15)
    symbols = []
    for line in log.splitlines():
        if line.startswith(("PL_START ", "PL_END ")) or re.search(r"(?:ImportError:|ModuleNotFoundError:|NameError:|AttributeError:|TypeError:|SyntaxError:|ValueError:|RuntimeError:|FastAPIError:|Error: No such option|invalid option name|option requires an argument)", line):
            symbols.append(line[:400])
        elif re.fullmatch(r'\s*File "/(?:app/backend|usr/local/lib)/[A-Za-z0-9_./-]+", line [0-9]+, in [A-Za-z0-9_<>]+', line):
            symbols.append(line.strip())
    return {"complete": True, "stage": "isolated_startup_diagnosis", "production_data_mounted": False,
            "network_enabled": False, "temporary_container_removed": True, "state": state,
            "error_symbols": symbols[-35:], "local_health_status": local_status,
            "startup_completed": "Application startup complete" in log}


def startup_output():
    """只读取刚才无网络/空数据启动的既有输出，不再次启动容器或读取生产日志。"""
    path = ROOT / "chat-startup-diagnostic.log"
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 131072:
        raise OperationError("startup_output_not_owned")
    lines = []
    text = path.read_text(errors="replace")
    has_stack = "Timeout (" in text
    if has_stack:
        text = text.rsplit("Timeout (", 1)[-1]
    for line in text.splitlines():
        if re.search(r"secret|password|authorization|token|(?:api|private)[_-]?key", line, re.IGNORECASE):
            continue
        line = re.sub(r"\x1b\[[0-9;]*m", "", line)
        lines.append(line[:600])
    details = {}
    for role in ("bridge", "chat", "newapi"):
        record_path = ROOT / "service-activation" / (role + ".json")
        if record_path.is_file() and not record_path.is_symlink() and record_path.stat().st_size < 2 * 1024 * 1024:
            record = json.loads(record_path.read_text())
            details[role] = {key: record.get(key) for key in ("status", "release_stage", "error_type", "recovery_error_type", "restart_intent")}
    return {"complete": True, "source": "existing_startup_records", "lines": lines[:45] if has_stack else lines[-12:], "service_stages": details}


def main():
    """固定盘点/候选准备入口；没有任意 shell、路径或真实环境内容输入。"""
    if len(sys.argv) != 2 or sys.argv[1] not in ("inventory", "prepare", "activate-main", "activate-services", "remove-source-archive", "diagnose-chat-startup", "startup-output"):
        raise OperationError("unsupported_operation")
    return {"inventory": lambda: inventory(Runner()), "prepare": prepare, "activate-main": activate_main, "activate-services": activate_services,
            "remove-source-archive": remove_source_archive, "diagnose-chat-startup": diagnose_chat_startup,
            "startup-output": startup_output}[sys.argv[1]]()


if __name__ == "__main__":
    try:
        print(json.dumps(main(), sort_keys=True, indent=2))
    except Exception as error:
        print(json.dumps({"complete": False, "error": error_code(error)}))
        raise SystemExit(1) from None
