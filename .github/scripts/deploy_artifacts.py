"""CI/Deploy 产物交接及本机只读镜像核验；不连接远端或执行部署。"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import threading


METADATA_LIMIT = 4 * 1024 * 1024
REVISION_LABEL = "org.opencontainers.image.revision"
MANIFEST_TYPES = {"application/vnd.oci.image.manifest.v1+json",
                  "application/vnd.docker.distribution.manifest.v2+json"}
CONFIG_TYPES = {"application/vnd.oci.image.config.v1+json",
                "application/vnd.docker.container.image.v1+json"}
LAYER_TYPES = {"application/vnd.oci.image.layer.v1.tar",
               "application/vnd.oci.image.layer.v1.tar+gzip",
               "application/vnd.oci.image.layer.v1.tar+zstd",
               "application/vnd.docker.image.rootfs.diff.tar",
               "application/vnd.docker.image.rootfs.diff.tar.gzip"}


def revision(value: str) -> str:
    """校验完整提交 ID，禁止将任意输入拼入后续文件名或命令。"""
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ValueError("expected_full_commit_sha")
    return value


def flag(value: str) -> bool:
    """将动作输出的 true/false 转成布尔；其他值视为交接错误。"""
    if value not in {"true", "false"}:
        raise ValueError("expected_boolean_flag")
    return value == "true"


def write_json(path: Path, value: dict) -> None:
    """写入指定交接清单并创建其父目录，不修改其他文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def outputs(path: Path, values: dict) -> None:
    """向当前 step 输出已校验的标量，不将清单内容当脚本执行。"""
    with path.open("a", encoding="utf-8") as stream:
        for key, value in values.items():
            text = str(value).lower() if isinstance(value, bool) else str(value)
            if "\n" in text or "\r" in text:
                raise ValueError("invalid_step_output")
            stream.write(f"{key}={text}\n")


def make_plan(env: dict) -> dict:
    """保留原 push 的范围；手动发布和不可用基线明确按全范围处理。"""
    event = env["GITHUB_EVENT_NAME"]
    full = event == "workflow_dispatch" or flag(env.get("FULL_SCOPE", "false"))
    before = env.get("BEFORE_SHA", "")
    if before:
        revision(before)
    scopes = {name: full or flag(env.get(f"{name.upper()}_CHANGED", "false"))
              for name in ("backend", "frontend", "nginx", "compose")}
    checks = {name: full or flag(env.get(f"CHECK_{name.upper()}", "false"))
              for name in ("backend", "frontend", "workflow")}
    return {
        "schema": 1, "revision": revision(env["GITHUB_SHA"]),
        "repository": env["GITHUB_REPOSITORY"], "run_id": str(env["GITHUB_RUN_ID"]),
        "event": event, "ref": env["GITHUB_REF"], "before": before,
        "full_scope": full, "scopes": scopes, "checks": checks,
    }


def validate_plan(plan: dict, sha: str, repository: str, run_id: str, event: str) -> dict:
    """自动链只接受对应本仓 main push；手动入口不依赖历史 CI 产物。"""
    if (plan.get("schema") != 1 or plan.get("revision") != revision(sha)
            or plan.get("repository") != repository or plan.get("run_id") != str(run_id)):
        raise ValueError("deploy_plan_identity_mismatch")
    wanted = "push" if event == "workflow_run" else "workflow_dispatch"
    if plan.get("event") != wanted or (wanted == "push" and plan.get("ref") != "refs/heads/main"):
        raise ValueError("deploy_plan_not_trusted_main_push")
    scopes = plan.get("scopes", {})
    if set(scopes) != {"backend", "frontend", "nginx", "compose"}:
        raise ValueError("deploy_plan_scope_missing")
    if any(type(value) is not bool for value in scopes.values()):
        raise ValueError("deploy_plan_scope_not_boolean")
    if wanted == "workflow_dispatch" and not all(scopes.values()):
        raise ValueError("manual_full_stack_scope_required")
    return scopes


def prepare_context(dist: Path, nginx: Path, destination: Path) -> None:
    """只封装同次已检查的 dist 与 Nginx 配置，不重新安装或编译前端。"""
    if not (dist / "index.html").is_file() or not nginx.is_file():
        raise ValueError("checked_frontend_or_nginx_missing")
    destination.mkdir(parents=True, exist_ok=False)
    shutil.copytree(dist, destination / "dist")
    shutil.copy2(nginx, destination / "nginx.conf")


def archive_name(sha: str) -> str:
    """返回完整提交 ID 对应的归档名，不接受分支或任意路径。"""
    return f"parallellines-web-{revision(sha)}.tar.gz"


def checksum(path: Path) -> str:
    """流式核对交接文件完整性，避免大型镜像归档全部驻留内存。"""
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def content_digest(value: str) -> str:
    """校验 SHA-256 内容地址；不把标签或 native ID 暗中当作 config 摘要。"""
    if not isinstance(value, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
        raise ValueError("invalid_content_digest")
    return value


def config_identity(config: dict, sha: str) -> dict:
    """提取当前单平台 config 的公开身份；不返回 Env 或其他运行配置。"""
    if (config.get("os") != "linux" or config.get("architecture") != "amd64"
            or config.get("variant", "") not in ("", None)):
        raise ValueError("web_image_platform_not_linux_amd64")
    if config.get("config", {}).get("Labels", {}).get(REVISION_LABEL) != sha:
        raise ValueError("web_image_revision_mismatch")
    rootfs = config.get("rootfs", {})
    layers = rootfs.get("diff_ids")
    if (rootfs.get("type") != "layers" or not isinstance(layers, list) or not layers
            or any(content_digest(value) != value for value in layers)):
        raise ValueError("web_image_rootfs_invalid")
    return {"platform": {"os": "linux", "architecture": "amd64", "variant": ""},
            "rootfs_diff_ids": layers, "image_revision": sha}


def archive_identity(archive: Path, sha: str) -> dict:
    """从 docker-save 归档原始 config bytes 取摘要，不解包、不重序列化 config。"""
    revision(sha)
    with tarfile.open(archive, "r:gz") as bundle:
        members = bundle.getmembers()
        names = [member.name for member in members]
        if len(names) != len(set(names)):
            raise ValueError("web_archive_duplicate_member")

        def read_member(name: str) -> bytes:
            member = bundle.getmember(name)
            if not member.isfile() or member.size > METADATA_LIMIT:
                raise ValueError("web_archive_metadata_invalid")
            return bundle.extractfile(member).read(METADATA_LIMIT + 1)

        manifest = json.loads(read_member("manifest.json"))
        # 当前只发布一个 linux/amd64 镜像；两个别名必须属于同一条 config。
        if (not isinstance(manifest, list) or len(manifest) != 1
                or len(manifest[0].get("RepoTags", [])) != 2
                or set(manifest[0].get("RepoTags", [])) != {
                    f"parallellines-web:{sha}", "parallellines-web:latest"}):
            raise ValueError("web_archive_alias_or_platform_ambiguous")
        entry = manifest[0]
        name = entry.get("Config", "")
        if not re.fullmatch(r"(?:[0-9a-f]{64}\.json|blobs/sha256/[0-9a-f]{64})", name):
            raise ValueError("web_archive_config_path_invalid")
        raw = read_member(name)
        digest = "sha256:" + hashlib.sha256(raw).hexdigest()
        if name.removesuffix(".json").split("/")[-1] != digest.removeprefix("sha256:"):
            raise ValueError("web_archive_config_digest_mismatch")
        identity = config_identity(json.loads(raw), sha)
        layers = entry.get("Layers", [])
        if (not isinstance(layers, list) or len(layers) != len(identity["rootfs_diff_ids"])
                or any(not bundle.getmember(layer).isfile() for layer in layers)):
            raise ValueError("web_archive_layers_missing")
        return {"image_config_digest": digest, **identity}


def receipt_identity(receipt: dict, sha: str, run_id: str) -> dict:
    """正常自动链只接受显式 schema 2；旧清单须另走人工确认入口。"""
    if (receipt.get("schema") != 2 or receipt.get("revision") != revision(sha)
            or receipt.get("run_id") != str(run_id)
            or receipt.get("image") != f"parallellines-web:{sha}"
            or receipt.get("archive") != archive_name(sha)):
        raise ValueError("web_artifact_identity_mismatch_schema_2_required")
    content_digest(receipt.get("image_id"))
    content_digest(receipt.get("image_config_digest"))
    # 复用 config 约束，拒绝错误平台、无序/缺失 RootFS 和错误 revision。
    identity = config_identity({**receipt.get("platform", {}),
                                "config": {"Labels": {REVISION_LABEL: receipt.get("image_revision")}},
                                "rootfs": {"type": "layers", "diff_ids": receipt.get("rootfs_diff_ids")}}, sha)
    return {"image_config_digest": receipt["image_config_digest"], **identity}


def write_receipt(directory: Path, sha: str, image_id: str, image_revision: str, run_id: str) -> None:
    """绑定原 native ID 审计值和独立 config 摘要；两者含义不得混用。"""
    revision(sha)
    if image_revision != sha:
        raise ValueError("built_image_revision_mismatch")
    content_digest(image_id)
    archive = directory / archive_name(sha)
    identity = archive_identity(archive, sha)
    digest = checksum(archive)
    write_json(directory / "web-image.json", {
        "schema": 2, "revision": sha, "run_id": str(run_id),
        "image": f"parallellines-web:{sha}", "image_id": image_id,
        "archive": archive.name, "archive_sha256": digest, **identity,
    })
    (directory / f"{archive.name}.sha256").write_text(f"{digest}  {archive.name}\n", encoding="ascii")
    (directory / f"parallellines-web-{sha}.image-id").write_text(image_id + "\n", encoding="ascii")
    (directory / f"parallellines-web-{sha}.image-config-digest").write_text(
        identity["image_config_digest"] + "\n", encoding="ascii")


def verify_web(directory: Path, sha: str, run_id: str) -> None:
    """拒绝错提交、错来源或损坏产物，不自动换 SHA 或重新构建兜底。"""
    archive = directory / archive_name(sha)
    receipt = json.loads((directory / "web-image.json").read_text(encoding="utf-8"))
    identity = receipt_identity(receipt, sha, run_id)
    digest = checksum(archive)
    if receipt.get("archive_sha256") != digest:
        raise ValueError("web_artifact_archive_changed")
    expected = f"{digest}  {archive.name}\n"
    if (directory / f"{archive.name}.sha256").read_text(encoding="ascii") != expected:
        raise ValueError("web_artifact_checksum_sidecar_changed")
    if (directory / f"parallellines-web-{sha}.image-id").read_text(encoding="ascii") != receipt["image_id"] + "\n":
        raise ValueError("web_artifact_image_sidecar_changed")
    if ((directory / f"parallellines-web-{sha}.image-config-digest").read_text(encoding="ascii")
            != identity["image_config_digest"] + "\n"):
        raise ValueError("web_artifact_config_sidecar_changed")
    if archive_identity(archive, sha) != identity:
        raise ValueError("web_artifact_config_identity_changed")


def read_metadata(command: list[str]) -> bytes:
    """执行有限时本机只读命令；错误不回显可能含运行配置的 stdout/stderr。"""
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        raise ValueError("metadata_tool_missing:" + command[0]) from None
    except PermissionError:
        raise ValueError("metadata_command_failed_check_local_permissions:" + command[0]) from None
    expired = threading.Event()

    def deadline() -> None:
        expired.set()
        process.kill()

    # 限制实际读取量；只检查 communicate 完成后的长度不能限制内存占用。
    timer = threading.Timer(30, deadline)
    with process:
        timer.start()
        try:
            raw = process.stdout.read(METADATA_LIMIT + 1)
            if len(raw) > METADATA_LIMIT:
                process.kill()
            process.wait()
        finally:
            timer.cancel()
    if expired.is_set():
        raise ValueError("metadata_command_timeout:" + command[0])
    if len(raw) > METADATA_LIMIT:
        raise ValueError("metadata_output_too_large")
    if process.returncode:
        raise ValueError("metadata_command_failed_check_local_permissions:" + command[0])
    return raw


def verify_loaded(sha: str, expected_digest: str, expected_identity: dict | None = None,
                  run=read_metadata) -> dict:
    """只读核验本机两个标签；classic 比 config ID，containerd 校验小 blob 内容链。"""
    revision(sha)
    content_digest(expected_digest)
    # 只读取公开身份字段，禁止将完整 inspect Config/Env 打入日志或交接清单。
    template = ('{"id":{{json .Id}},"descriptor":{{json (index . "Descriptor")}},'
                '"os":{{json .Os}},"architecture":{{json .Architecture}},'
                '"variant":{{json (index . "Variant")}},"rootfs":{{json .RootFS}},'
                '"revision":{{json (index .Config.Labels "' + REVISION_LABEL + '")}}}')
    records = [json.loads(line) for line in run([
        "docker", "image", "inspect", "--format", template,
        f"parallellines-web:{sha}", "parallellines-web:latest"]).splitlines()]
    if len(records) != 2 or records[0]["id"] != records[1]["id"]:
        raise ValueError("loaded_image_alias_mismatch")
    native_id = content_digest(records[0]["id"])
    identities = [config_identity({"os": item.get("os"), "architecture": item.get("architecture"),
                                   "variant": item.get("variant"),
                                   "config": {"Labels": {REVISION_LABEL: item.get("revision")}},
                                   "rootfs": {"type": item.get("rootfs", {}).get("Type"),
                                              "diff_ids": item.get("rootfs", {}).get("Layers")}}, sha)
                  for item in records]
    if identities[0] != identities[1]:
        raise ValueError("loaded_image_alias_metadata_mismatch")
    identity = {"image_config_digest": expected_digest, **identities[0]}
    if expected_identity is not None and identity != expected_identity:
        raise ValueError("loaded_image_receipt_metadata_mismatch")
    descriptors = [item.get("descriptor") for item in records]
    if descriptors == [None, None]:
        if native_id != expected_digest:
            raise ValueError("classic_image_config_digest_mismatch")
        store = "classic"
    else:
        # native ID 在 containerd store 表示 manifest，不跨存储类型直接比较 .Id。
        for descriptor in descriptors:
            if (not isinstance(descriptor, dict) or descriptor.get("digest") != native_id
                    or descriptor.get("mediaType") not in MANIFEST_TYPES
                    or type(descriptor.get("size")) is not int
                    or not 0 < descriptor["size"] <= METADATA_LIMIT):
                raise ValueError("loaded_descriptor_not_single_manifest")
        if (descriptors[0]["size"] != descriptors[1]["size"]
                or descriptors[0]["mediaType"] != descriptors[1]["mediaType"]):
            raise ValueError("loaded_descriptor_alias_mismatch")
        info = json.loads(run(["docker", "info", "--format", "{{json .Containerd}}"]))
        address = info.get("Address") if isinstance(info, dict) else None
        namespace = info.get("Namespaces", {}).get("Containers") if isinstance(info, dict) else None
        if (not isinstance(address, str) or not address.startswith("/")
                or not isinstance(namespace, str) or not re.fullmatch(r"[a-zA-Z0-9_.-]+", namespace)):
            raise ValueError("local_containerd_address_or_namespace_unavailable")
        ctr = shutil.which("ctr")
        if not ctr:
            raise ValueError("containerd_ctr_missing_no_install_or_fallback")

        def blob(digest: str, size: int) -> bytes:
            raw = run([ctr, "--address", address, "--namespace", namespace, "content", "get", digest])
            if len(raw) != size or "sha256:" + hashlib.sha256(raw).hexdigest() != digest:
                raise ValueError("containerd_blob_digest_or_size_mismatch")
            return raw

        manifest = json.loads(blob(native_id, descriptors[0]["size"]))
        config = manifest.get("config", {})
        if (manifest.get("schemaVersion") != 2
                or manifest.get("mediaType") != descriptors[0]["mediaType"]
                or config.get("mediaType") not in CONFIG_TYPES
                or config.get("digest") != expected_digest or type(config.get("size")) is not int
                or not 0 < config["size"] <= METADATA_LIMIT):
            raise ValueError("loaded_manifest_config_mismatch")
        raw_identity = config_identity(json.loads(blob(expected_digest, config["size"])), sha)
        layers = manifest.get("layers")
        if (raw_identity != identities[0] or not isinstance(layers, list)
                or len(layers) != len(raw_identity["rootfs_diff_ids"])):
            raise ValueError("loaded_config_rootfs_mismatch")
        for layer in layers:
            if (not isinstance(layer, dict) or layer.get("mediaType") not in LAYER_TYPES
                    or type(layer.get("size")) is not int or layer["size"] < 0):
                raise ValueError("loaded_manifest_layer_descriptor_invalid")
            content_digest(layer.get("digest"))
        store = "containerd"
    return {"store": store, "native_image_id": native_id, **identity}


def main() -> None:
    """执行计划、封装或核验子命令；失败直接退出，不自动构建或部署。"""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan")
    plan.add_argument("--output", type=Path, required=True)
    plan.add_argument("--github-output", type=Path, required=True)
    read = commands.add_parser("read-plan")
    read.add_argument("--source", type=Path, required=True)
    read.add_argument("--github-output", type=Path, required=True)
    context = commands.add_parser("context")
    context.add_argument("--dist", type=Path, required=True)
    context.add_argument("--nginx", type=Path, required=True)
    context.add_argument("--output", type=Path, required=True)
    archive = commands.add_parser("archive-identity")
    archive.add_argument("--archive", type=Path, required=True)
    archive.add_argument("--sha", required=True)
    loaded = commands.add_parser("verify-loaded")
    loaded.add_argument("--sha", required=True)
    loaded.add_argument("--receipt", type=Path)
    loaded.add_argument("--run-id")
    loaded.add_argument("--expected-config-digest")
    for name in ("receipt", "verify-web"):
        command = commands.add_parser(name)
        command.add_argument("--directory", type=Path, required=True)
        command.add_argument("--sha", required=True)
        command.add_argument("--run-id", required=True)
        if name == "receipt":
            command.add_argument("--image-id", required=True)
            command.add_argument("--image-revision", required=True)
    args = parser.parse_args()
    if args.command == "plan":
        value = make_plan(os.environ)
        write_json(args.output, value)
        outputs(args.github_output, {**value["scopes"], **{
            f"check_{key}": enabled for key, enabled in value["checks"].items()
        }})
    elif args.command == "read-plan":
        value = json.loads(args.source.read_text(encoding="utf-8"))
        scopes = validate_plan(value, os.environ["DEPLOY_SHA"], os.environ["GITHUB_REPOSITORY"],
                               os.environ["SOURCE_RUN_ID"], os.environ["GITHUB_EVENT_NAME"])
        outputs(args.github_output, {**scopes, "sha": value["revision"], "source_run_id": value["run_id"],
                                     "web_required": scopes["frontend"] or scopes["compose"]})
    elif args.command == "context":
        prepare_context(args.dist, args.nginx, args.output)
    elif args.command == "receipt":
        write_receipt(args.directory, args.sha, args.image_id, args.image_revision, args.run_id)
    elif args.command == "verify-web":
        verify_web(args.directory, args.sha, args.run_id)
    elif args.command == "archive-identity":
        print(json.dumps(archive_identity(args.archive, args.sha), sort_keys=True))
    elif args.command == "verify-loaded":
        identity = None
        if args.receipt:
            if not args.run_id:
                parser.error("verify-loaded --receipt requires --run-id")
            identity = receipt_identity(json.loads(args.receipt.read_text(encoding="utf-8")),
                                        args.sha, args.run_id)
            digest = identity["image_config_digest"]
            if args.expected_config_digest and args.expected_config_digest != digest:
                raise ValueError("loaded_config_sidecar_mismatch")
            mode = "schema_2_receipt"
        else:
            # 旧 schema 1 只供操作员先核原归档/收据后显式恢复；自动链没有降级。
            if not args.expected_config_digest or args.run_id:
                parser.error("operator mode requires --expected-config-digest and no --run-id")
            digest = args.expected_config_digest
            mode = "explicit_operator_config_digest"
        print(json.dumps({"mode": mode, **verify_loaded(args.sha, digest, identity)}, sort_keys=True))


if __name__ == "__main__":
    main()
