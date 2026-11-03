"""CI 与 Deploy 的提交、范围和 Web 产物交接；不连接服务器或执行部署。"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil


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


def write_receipt(directory: Path, sha: str, image_id: str, image_revision: str, run_id: str) -> None:
    """绑定构建提交、镜像身份与归档；旁文件供已有服务器基础命令校验。"""
    revision(sha)
    if image_revision != sha or not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
        raise ValueError("built_image_revision_mismatch")
    archive = directory / archive_name(sha)
    digest = checksum(archive)
    write_json(directory / "web-image.json", {
        "schema": 1, "revision": sha, "run_id": str(run_id),
        "image": f"parallellines-web:{sha}", "image_id": image_id,
        "archive": archive.name, "archive_sha256": digest,
    })
    (directory / f"{archive.name}.sha256").write_text(f"{digest}  {archive.name}\n", encoding="ascii")
    (directory / f"parallellines-web-{sha}.image-id").write_text(image_id + "\n", encoding="ascii")


def verify_web(directory: Path, sha: str, run_id: str) -> None:
    """拒绝错提交、错来源或损坏产物，不自动换 SHA 或重新构建兜底。"""
    archive = directory / archive_name(sha)
    receipt = json.loads((directory / "web-image.json").read_text(encoding="utf-8"))
    if (receipt.get("schema") != 1 or receipt.get("revision") != sha
            or receipt.get("run_id") != str(run_id)
            or receipt.get("image") != f"parallellines-web:{sha}"
            or receipt.get("archive") != archive.name):
        raise ValueError("web_artifact_identity_mismatch")
    image_id = receipt.get("image_id", "")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
        raise ValueError("web_artifact_image_id_invalid")
    digest = checksum(archive)
    if receipt.get("archive_sha256") != digest:
        raise ValueError("web_artifact_archive_changed")
    expected = f"{digest}  {archive.name}\n"
    if (directory / f"{archive.name}.sha256").read_text(encoding="ascii") != expected:
        raise ValueError("web_artifact_checksum_sidecar_changed")
    if (directory / f"parallellines-web-{sha}.image-id").read_text(encoding="ascii") != image_id + "\n":
        raise ValueError("web_artifact_image_sidecar_changed")


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
    else:
        verify_web(args.directory, args.sha, args.run_id)


if __name__ == "__main__":
    main()
