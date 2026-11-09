"""公开工具站 release 合同与安全解包；不连接网络、不调用 Docker、不执行归档内程序。"""

import json
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tarfile
import urllib.parse


SOURCE_REPOSITORY = "https://github.com/ixiaoyy/parallel-lines-tools"
MAX_BUNDLE = 1024 * 1024 * 1024
MAX_EXPANDED = 4 * MAX_BUNDLE
MAX_MEMBERS = 10000
DEPLOY_FILES = {"deploy/Dockerfile.prebuilt", "deploy/Dockerfile.prebuilt.dockerignore",
                "deploy/nginx/default.conf", "deploy/compose.yaml"}
REQUIRED_FILES = DEPLOY_FILES | {"dist/index.html", "dist/THIRD_PARTY_NOTICES.txt",
                                "dist/release-components.json", "dist/toolbox-source-local-20261109.zip"}
# schema 1 已审核的封装/运行能力边界；变化必须连同 ops 合同评审，不能执行任意包内描述符。
DESCRIPTOR_SHA256 = {
    "deploy/Dockerfile.prebuilt": "7c1b90a2bb2c2700e21f9359d63207bf2a4e71291037383a0e90e8fb5c7b33ac",
    "deploy/Dockerfile.prebuilt.dockerignore": "b1548871ac919120f29ea30c3e8fd9302d5f8a95af31285545f4fb3f8a2031d4",
    "deploy/compose.yaml": "456f211219422fd599a7d33834073188e8f5c6147f33ee27e6757ce62c649a5f",
    "deploy/nginx/default.conf": "5d1fdd28385aae04d6a0af32a625c889452d6bcbf9feebc248679ca92645bf2b",
}


class ContractError(Exception):
    """只返回稳定合同错误码，不将未知响应正文或归档字段作为日志。"""


def validate_receipt(data, release_tag):
    """验证已校验 SHA256 的 receipt；返回原有字段副本，严格保持版本、URL、单位和类型。"""
    if not re.fullmatch(r"site-[0-9a-f]{40}", release_tag):
        raise ContractError("invalid_release_tag")
    if not isinstance(data, dict) or type(data.get("schema")) is not int or data["schema"] != 1:
        raise ContractError("unsupported_receipt_schema")
    if data.get("applicationRevision") != release_tag[5:]:
        raise ContractError("receipt_revision_mismatch")
    if data.get("expectedTitle") != "平行线工具箱":
        raise ContractError("receipt_title_mismatch")
    nginx = data.get("nginxImage")
    if not isinstance(nginx, str) or not re.fullmatch(r"(?:docker\.io/library/)?nginx(?::[A-Za-z0-9_.-]+)?@sha256:[0-9a-f]{64}", nginx):
        raise ContractError("receipt_base_image_not_pinned_official_nginx")
    version = data.get("coreVersion")
    if not isinstance(version, str) or not 1 <= len(version) <= 128 or "\n" in version:
        raise ContractError("receipt_core_version_invalid")
    source = data.get("coreSourceURL")
    if not isinstance(source, str):
        raise ContractError("receipt_core_source_invalid")
    parsed = urllib.parse.urlsplit(source)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username is not None or parsed.password is not None:
        raise ContractError("receipt_core_source_invalid")
    bundle = data.get("bundle")
    if not isinstance(bundle, dict) or bundle.get("file") != "toolbox-dist.tar.gz":
        raise ContractError("receipt_bundle_name_invalid")
    expected_url = SOURCE_REPOSITORY + "/releases/download/" + release_tag + "/toolbox-dist.tar.gz"
    if bundle.get("url") != expected_url:
        raise ContractError("receipt_bundle_url_outside_release")
    if not isinstance(bundle.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", bundle["sha256"]):
        raise ContractError("receipt_bundle_digest_invalid")
    if type(bundle.get("bytes")) is not int or not 0 < bundle["bytes"] <= MAX_BUNDLE:
        raise ContractError("receipt_bundle_size_invalid")
    return {**data, "bundle": dict(bundle)}


def member_name(member):
    """只接受固定 dist/deploy 相对路径，拒绝链接、特殊文件与路径穿越。"""
    name = member.name.rstrip("/")
    if not name or len(name) > 1024 or "\\" in name or "\x00" in name:
        raise ContractError("bundle_member_name_invalid")
    parts = name.split("/")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in ("", ".", "..") for part in parts):
        raise ContractError("bundle_path_traversal")
    if member.isdir():
        allowed = name in ("dist", "deploy", "deploy/nginx") or name.startswith("dist/")
    elif member.type in (tarfile.REGTYPE, tarfile.AREGTYPE) and not member.sparse:
        allowed = name.startswith("dist/") or name in DEPLOY_FILES
    else:
        raise ContractError("bundle_links_or_special_files_forbidden")
    if not allowed:
        raise ContractError("bundle_member_outside_contract")
    if type(member.size) is not int or member.size < 0 or member.size > MAX_BUNDLE:
        raise ContractError("bundle_member_size_invalid")
    return name


def inspect_bundle(tar_path):
    """流式核 metadata 后才允许写入，限制条目和展开量，并提前拒绝父目录文件冲突。"""
    seen = {}
    expanded = 0
    with tarfile.open(tar_path, "r:gz") as archive:
        for member in archive:
            name = member_name(member)
            if name in seen:
                raise ContractError("bundle_duplicate_target")
            seen[name] = member.isdir()
            expanded += member.size if not member.isdir() else 0
            if len(seen) > MAX_MEMBERS or expanded > MAX_EXPANDED:
                raise ContractError("bundle_expansion_limit")
    for name in seen:
        for parent in PurePosixPath(name).parents:
            if str(parent) in seen and not seen[str(parent)]:
                raise ContractError("bundle_file_directory_conflict")
    if any(name not in seen or seen[name] for name in REQUIRED_FILES):
        raise ContractError("bundle_required_file_missing")
    return {"members": len(seen), "expanded_bytes": expanded}


def safe_extract_bundle(tar_path, destination):
    """完整预检后解包到全新目录；逐文件复制，忽略归档权限/owner，不使用 extractall。"""
    summary = inspect_bundle(tar_path)
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise ContractError("bundle_destination_must_be_new")
    destination.mkdir(mode=0o750)
    with tarfile.open(tar_path, "r:gz") as archive:
        for member in archive:
            name = member_name(member)
            output = destination.joinpath(*PurePosixPath(name).parts)
            if member.isdir():
                output.mkdir(mode=0o755, parents=True, exist_ok=True)
                continue
            output.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                raise ContractError("bundle_file_unreadable")
            descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
            with source, os.fdopen(descriptor, "wb") as target:
                shutil.copyfileobj(source, target, length=128 * 1024)
                if target.tell() != member.size:
                    raise ContractError("bundle_file_length_mismatch")
    return summary


def validate_descriptors(directory):
    """对齐已审核的 COPY-only 和独立 Compose 描述符，拒绝未知 RUN、env_file 或服务能力。"""
    for name, expected in DESCRIPTOR_SHA256.items():
        data = (Path(directory) / name).read_bytes()
        if len(data) > 65536 or hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest() != expected:
            raise ContractError("release_descriptor_requires_review")
    return True
