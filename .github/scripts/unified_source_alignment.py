"""固定统一登录版本逐路径对齐；保留其他 untracked，Nginx 由其独立事务唯一写入。"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import time


MAIN = Path("/opt/parallellines")
BEFORE = "93ca819f20f760b142cab9a320110879ff8179df"
APP = "a2cfeddeec01ca0d5def4b3308103f3d85cc3861"
ROOT = Path("/data/deployment/parallellines-unified") / APP
STATE = ROOT / "source-alignment/record.json"
REMOTE = "https://github.com/ixiaoyy/ParallelLines.git"
NGINX = frozenset({"deploy/nginx/default.conf", "deploy/nginx/forum.conf"})
FILE_LIMIT = 4 * 1024 * 1024
TOTAL_LIMIT = 32 * 1024 * 1024
PATH_LIMIT = 128
GIT = [
    "git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-c", "credential.helper=",
    "-c", "core.askPass=/bin/false", "-c", "http.extraHeader=",
    "-c", "http.https://github.com/.extraHeader=", "-c", "http.followRedirects=false",
    "-C", str(MAIN),
]


class OperationError(Exception):
    """只携带稳定代码和已审核公开路径，不输出凭据、blob 正文或命令 stderr。"""


def owned_root(value: Path) -> Path:
    """只接受固定产物根，拒绝任何已有父级符号链接。"""
    path = Path(value)
    if path != ROOT:
        raise OperationError("source_alignment_root_denied")
    for part in (path, *path.parents):
        if part.is_symlink():
            raise OperationError("source_alignment_root_symlink")
    return path


def public_name(value: str) -> str:
    """限制已授权 Git 差异为普通公开文件，明确排除迁移、运行数据及真实凭据文件。"""
    path = Path(value)
    if not re.fullmatch(r"[A-Za-z0-9_./-]+", value) or value.startswith("/") or any(part in {"", ".", ".."} for part in value.split("/")):
        raise OperationError("source_alignment_path_invalid")
    if value.startswith((".git/", ".deployment/", ".tmp/", ".build/", "data/", "var/", "secrets/", "private/", "apps/api/alembic/")):
        raise OperationError("source_alignment_private_or_migration_path")
    if (path.name.startswith(".env") and path.name != ".env.example") or path.suffix.lower() in {".key", ".pem", ".p12", ".pfx"} or path.name in {"id_rsa", "id_ed25519", "authorized_keys"}:
        raise OperationError("source_alignment_private_file")
    return value


def project_path(name: str) -> Path:
    """只定位 MAIN 下已审核路径，不跟随叶子或任意父目录链接。"""
    path = MAIN / public_name(name)
    for part in (path, *path.parents):
        if part == MAIN or MAIN in part.parents:
            if part.is_symlink():
                raise OperationError("source_alignment_project_symlink:" + name)
            if part != path and part.exists() and not part.is_dir():
                raise OperationError("source_alignment_parent_not_directory:" + name)
    return path


def attributes(path: Path) -> dict:
    """保存源文件原属主/权限；inode 仅用于证明本次创建的新文件所有权。"""
    value = path.lstat()
    if not stat.S_ISREG(value.st_mode):
        raise OperationError("source_alignment_target_not_regular")
    return {"uid": value.st_uid, "gid": value.st_gid, "mode": stat.S_IMODE(value.st_mode),
            "device": value.st_dev, "inode": value.st_ino}


def read_bytes(path: Path) -> bytes:
    """仅从已限定公开路径或私有恢复记录读普通文件，单文件最多四 MiB。"""
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as stream:
        value = os.fstat(stream.fileno())
        if not stat.S_ISREG(value.st_mode) or value.st_size > FILE_LIMIT:
            raise OperationError("source_alignment_file_limit")
        data = stream.read(FILE_LIMIT + 1)
    if len(data) > FILE_LIMIT:
        raise OperationError("source_alignment_file_grew")
    return data


def digest(value: bytes) -> str:
    """返回公开文件快照的内部完整性摘要，不用于隐藏或搬运敏感数据。"""
    return hashlib.sha256(value).hexdigest()


def private_file(path: Path) -> Path:
    """私有快照只能位于本任务 source-alignment 子目录。"""
    directory = ROOT / "source-alignment"
    if directory not in path.parents:
        raise OperationError("source_alignment_snapshot_path_denied")
    for part in (path, *path.parents):
        if part == directory or directory in part.parents:
            if part.is_symlink():
                raise OperationError("source_alignment_snapshot_symlink")
    return path


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic_private(path: Path, content: bytes) -> None:
    """仅原子保存 0600 的任务记录；不覆盖应用或 Git 文件。"""
    private_file(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(path.name + ".new-" + secrets.token_hex(8))
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    fsync_directory(path.parent)


def save(record: dict) -> None:
    """原子保存本次固定版本的私有恢复状态，不向共享日志展开逐路径记录。"""
    atomic_private(STATE, (json.dumps(record, sort_keys=True, indent=2) + "\n").encode())


def load(root: Path) -> dict:
    """读取本次固定版本记录；其他事务或损坏的 schema 明确拒绝。"""
    owned_root(root)
    record = json.loads(read_bytes(private_file(STATE)))
    if record.get("schema") != 1 or record.get("before") != BEFORE or record.get("app") != APP:
        raise OperationError("source_alignment_record_not_owned")
    return record


def git(runner, *arguments: str, timeout: int = 15) -> str:
    """经调用方总预算执行固定 Git 参数；二进制 blob 单独读取以保留真实字节。"""
    previous = os.environ.get("GIT_NO_LAZY_FETCH")
    os.environ["GIT_NO_LAZY_FETCH"] = "1"
    try:
        return runner.run([*GIT, *arguments], timeout=timeout)
    finally:
        if previous is None:
            os.environ.pop("GIT_NO_LAZY_FETCH", None)
        else:
            os.environ["GIT_NO_LAZY_FETCH"] = previous


@contextlib.contextmanager
def public_transport():
    """仅此公开 fetch 使用无交互/无系统或用户凭据配置的进程环境，结束后逐项恢复。"""
    replacements = {
        "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "/bin/false", "SSH_ASKPASS": "/bin/false",
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_NO_LAZY_FETCH": "1", "HTTP_PROXY": None, "HTTPS_PROXY": None, "ALL_PROXY": None,
        "http_proxy": None, "https_proxy": None, "all_proxy": None,
    }
    previous = {key: os.environ.get(key) for key in replacements}
    try:
        for key, value in replacements.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def blob(runner, identifier: str) -> bytes:
    """使用二进制 cat-file 保留原始换行/编码；复用调用方总预算，不允许隐式网络取对象。"""
    if not re.fullmatch(r"[0-9a-f]{40}", identifier):
        raise OperationError("source_alignment_blob_id_invalid")
    size = int(git(runner, "cat-file", "-s", identifier).strip())
    if not 0 <= size <= FILE_LIMIT:
        raise OperationError("source_alignment_blob_limit")
    remaining = runner.deadline - time.monotonic()
    if remaining <= 0:
        raise OperationError("source_alignment_deadline")
    try:
        result = subprocess.run([*GIT, "cat-file", "blob", identifier], capture_output=True,
                                timeout=min(15, remaining), check=False,
                                env={**os.environ, "GIT_NO_LAZY_FETCH": "1", "GIT_TERMINAL_PROMPT": "0"})
    except (OSError, subprocess.TimeoutExpired) as error:
        raise OperationError("source_alignment_blob_" + type(error).__name__) from None
    if result.returncode or len(result.stdout) != size or len(result.stderr) > 4096:
        raise OperationError("source_alignment_blob_read_failed")
    return result.stdout


def local_object_types(runner, names: list[str]) -> dict[str, str | None]:
    """禁 lazy-fetch 批量检查固定对象元数据；仅明确 missing 才表示需要网络，不把其他错误降级。"""
    if not 1 <= len(names) <= PATH_LIMIT * 2 or any(
        not re.fullmatch(r"[0-9a-f]{40}(?:\^\{(?:commit|tree)\})?", name) for name in names
    ):
        raise OperationError("source_alignment_local_object_query_invalid")
    remaining = runner.deadline - time.monotonic()
    if remaining <= 0:
        raise OperationError("source_alignment_deadline")
    try:
        result = subprocess.run(
            [*GIT, "cat-file", "--batch-check"], input=("\n".join(names) + "\n").encode("ascii"),
            capture_output=True, timeout=min(15, remaining), check=False,
            env={**os.environ, "GIT_NO_LAZY_FETCH": "1", "GIT_TERMINAL_PROMPT": "0"},
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise OperationError("source_alignment_local_object_" + type(error).__name__) from None
    if result.returncode or len(result.stdout) > 65536 or len(result.stderr) > 4096:
        raise OperationError("source_alignment_local_object_query_failed")
    try:
        lines = result.stdout.decode("ascii").splitlines()
    except UnicodeError:
        raise OperationError("source_alignment_local_object_response_invalid") from None
    if len(lines) != len(names):
        raise OperationError("source_alignment_local_object_response_invalid")
    found = {}
    for name, line in zip(names, lines, strict=True):
        if line == name + " missing":
            found[name] = None
            continue
        match = re.fullmatch(r"([0-9a-f]{40}) (blob|tree|commit|tag) ([0-9]+)", line)
        if match is None:
            raise OperationError("source_alignment_local_object_response_invalid")
        found[name] = match.group(2)
    return found


def local_app_delta(runner) -> list[dict] | None:
    """优先复用已有 APP commit/tree 和差异 blob；全部验证均为本地对象读取，不检查传输配置。"""
    references = [APP + "^{commit}", APP + "^{tree}"]
    metadata = local_object_types(runner, references)
    if any(metadata[name] is None for name in references):
        return None
    if metadata[references[0]] != "commit" or metadata[references[1]] != "tree":
        raise OperationError("source_alignment_local_app_type_invalid")
    # diff 本身在禁 lazy 的 git() 中读取所需树；解析/权限错误直接终止，不能冒充缺对象而取凭据。
    delta = path_delta(runner)
    identifiers = sorted({item["new_blob"] for item in delta} | {
        item["old_blob"] for item in delta if item["change"] == "M"
    })
    objects = local_object_types(runner, identifiers)
    if any(value is None for value in objects.values()):
        return None
    if any(value != "blob" for value in objects.values()):
        raise OperationError("source_alignment_local_blob_type_invalid")
    return delta


def source_state(runner, record: dict | None = None) -> tuple[str, str]:
    """只接受原 main 分支及两端 HEAD/index；不认第三方提交、额外暂存或冲突 index。"""
    if git(runner, "symbolic-ref", "--quiet", "HEAD").strip() != "refs/heads/main":
        raise OperationError("source_alignment_branch_changed")
    head = git(runner, "rev-parse", "HEAD").strip()
    if head not in ({BEFORE} if record is None else {BEFORE, APP}):
        raise OperationError("source_alignment_head_changed")
    before_diff = git(runner, "diff", "--cached", "--no-ext-diff", "--no-textconv", "--name-only", "-z", BEFORE)
    after_diff = "not_checked" if record is None else git(runner, "diff", "--cached", "--no-ext-diff", "--no-textconv", "--name-only", "-z", APP)
    if before_diff and after_diff:
        raise OperationError("source_alignment_index_changed")
    return head, BEFORE if not before_diff else APP


def path_delta(runner) -> list[dict]:
    """从固定 Git 对象枚举 A/M 普通文件；拒绝删除、重命名、类型和执行位变化。"""
    raw = git(runner, "diff", "--raw", "--no-abbrev", "--no-renames", "--no-ext-diff", "-z", BEFORE, APP)
    pieces = raw.split("\0")
    if pieces[-1] != "" or (len(pieces) - 1) % 2:
        raise OperationError("source_alignment_delta_invalid")
    result = []
    for index in range(0, len(pieces) - 1, 2):
        fields = pieces[index].split()
        if len(fields) != 5 or fields[4] not in {"A", "M"}:
            raise OperationError("source_alignment_non_add_modify_delta")
        old_mode, new_mode, old_blob, new_blob, change = fields
        old_mode = old_mode.removeprefix(":")
        if new_mode not in {"100644", "100755"} or (change == "M" and old_mode != new_mode) or (change == "A" and old_mode != "000000"):
            raise OperationError("source_alignment_mode_transition_denied")
        if not all(re.fullmatch(r"[0-9a-f]{40}", value) for value in (old_blob, new_blob)):
            raise OperationError("source_alignment_delta_blob_invalid")
        name = public_name(pieces[index + 1])
        result.append({"name": name, "change": change, "old_blob": old_blob, "new_blob": new_blob,
                       "git_mode": int(new_mode, 8) & 0o777, "delegated_nginx": name in NGINX})
    if not 1 <= len(result) <= PATH_LIMIT or {item["name"] for item in result if item["delegated_nginx"]} != NGINX:
        raise OperationError("source_alignment_delta_bounds")
    return result


def git_attributes() -> dict:
    """仅记录 index/原 loose main ref 的权限，不读取 Git 配置或任何认证内容。"""
    result = {}
    for name in ("index", "refs/heads/main"):
        path = MAIN / ".git" / name
        for part in (path, *path.parents):
            if part == MAIN or MAIN in part.parents:
                if part.is_symlink():
                    raise OperationError("source_alignment_git_metadata_symlink")
        result[name] = attributes(path)
    return result


def preserve_git_attributes(record: dict) -> None:
    """Git 原生原子更新后接续旧 UID/GID/mode，不改变其对象内容或锁机制。"""
    for name, expected in record["git_attributes"].items():
        path = MAIN / ".git" / name
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            current = os.fstat(descriptor)
            if not stat.S_ISREG(current.st_mode):
                raise OperationError("source_alignment_git_metadata_not_regular")
            os.fchown(descriptor, expected["uid"], expected["gid"])
            os.fchmod(descriptor, expected["mode"])
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def snapshot(record: dict, item: dict, direction: str) -> bytes | None:
    """读取并核对本任务私有恢复端点，不从可变工作区重新取得恢复源。"""
    expected = item[direction + "_sha256"]
    if expected is None:
        return None
    value = read_bytes(private_file(ROOT / "source-alignment" / direction / item["name"]))
    if digest(value) != expected:
        raise OperationError("source_alignment_snapshot_changed:" + item["name"])
    return value


def prepare(root: Path, runner) -> dict:
    """非激活阶段：核干净原基线、公开 fetch 固定版本，仅在私有根保存逐路径恢复记录。"""
    owned_root(root)
    if STATE.exists():
        record = load(root)
        if record.get("status") != "prepared":
            raise OperationError("source_alignment_already_started")
        source_state(runner)
        preflight(record, runner, restoring=False, preparing=True)
        return record
    source_state(runner)
    if git(runner, "status", "--porcelain=v1", "--untracked-files=no"):
        raise OperationError("source_alignment_tracked_worktree_not_clean")
    # workflow 已取得固定 operator 的完整祖先时，直接复用本地 APP 对象；不为本地读取增凭据前置。
    delta = local_app_delta(runner)
    object_source = "local"
    if delta is None:
        # 只有已确认缺对象才进入网络分支；原 guard 保留，不读取键值或打印这些名字。
        transport_keys = runner.run([*GIT, "config", "--local", "--name-only", "--get-regexp",
                                     r"^(url\..*\.insteadof|http\..*extraheader|credential\..*|core\.askpass|remote\..*\.promisor)$"],
                                    accepted=(0, 1))
        if transport_keys:
            raise OperationError("source_alignment_local_transport_requires_review")
        with public_transport():
            git(runner, "fetch", "--no-tags", "--no-write-fetch-head", "--no-recurse-submodules", REMOTE, APP, timeout=120)
        delta = local_app_delta(runner)
        if delta is None:
            raise OperationError("source_alignment_objects_missing_after_fetch")
        object_source = "public_fetch"
    record = {"schema": 1, "before": BEFORE, "app": APP, "status": "prepared", "pending": None,
              "object_source": object_source,
              "before_tree": git(runner, "rev-parse", BEFORE + "^{tree}").strip(),
              "after_tree": git(runner, "rev-parse", APP + "^{tree}").strip(),
              "git_attributes": git_attributes(), "new_owner": {"uid": MAIN.stat().st_uid, "gid": MAIN.stat().st_gid},
              "paths": []}
    total = 0
    payloads = []
    for item in delta:
        path = project_path(item["name"])
        after = blob(runner, item["new_blob"])
        before = blob(runner, item["old_blob"]) if item["change"] == "M" else None
        actual = read_bytes(path) if path.exists() else None
        if item["change"] == "M" and actual != before:
            raise OperationError("source_alignment_original_blob_mismatch:" + item["name"])
        if item["change"] == "A" and actual is not None and actual != after:
            raise OperationError("source_alignment_new_path_collision:" + item["name"])
        # 新 Git 路径可能原已是同字节 untracked；它的真实前像仍需备份，恢复时保留原文件。
        if item["change"] == "A" and actual is not None:
            before = actual
        existing = attributes(path) if actual is not None else None
        if item["change"] == "A" and existing and bool(existing["mode"] & stat.S_IXUSR) != bool(item["git_mode"] & stat.S_IXUSR):
            raise OperationError("source_alignment_existing_new_mode_conflict:" + item["name"])
        item.update({"before_sha256": digest(before) if before is not None else None,
                     "after_sha256": digest(after), "original_exists": actual is not None,
                     "original_attributes": existing, "created_identity": None})
        total += len(after) + (len(before) if before is not None else 0)
        if total > TOTAL_LIMIT:
            raise OperationError("source_alignment_total_bytes_limit")
        payloads.append((item, before, after))
        record["paths"].append(item)
    # 全部前像先通过，才保存第一份快照；prepare 不写 MAIN 下任何源文件。
    for item, before, after in payloads:
        if before is not None:
            atomic_private(ROOT / "source-alignment/before" / item["name"], before)
        atomic_private(ROOT / "source-alignment/after" / item["name"], after)
    save(record)
    source_state(runner)
    preflight(record, runner, restoring=False, preparing=True)
    return record


def same_attributes(actual: dict, expected: dict) -> bool:
    """比较必须保留的属主和权限；普通 tracked 文件允许本事务原子更新 inode。"""
    return all(actual[key] == expected[key] for key in ("uid", "gid", "mode"))


def preflight(record: dict, runner, *, restoring: bool, preparing: bool = False) -> None:
    """一次核全部路径后才写第一个文件；仅认原/新完整端点，不认未知半写内容。"""
    source_state(runner, record)
    names = {item["name"] for item in record["paths"]}
    if len(names) != len(record["paths"]) or len(names) > PATH_LIMIT:
        raise OperationError("source_alignment_record_paths_invalid")
    outside = set(filter(None, git(runner, "diff", "--no-ext-diff", "--no-textconv", "--name-only", "-z", BEFORE).split("\0"))) - names
    if outside:
        raise OperationError("source_alignment_unrelated_tracked_changes")
    for item in record["paths"]:
        path = project_path(item["name"])
        before, after = snapshot(record, item, "before"), snapshot(record, item, "after")
        actual = read_bytes(path) if path.exists() else None
        if actual not in (before, after):
            raise OperationError("source_alignment_target_changed:" + item["name"])
        if preparing and actual != (before if item["original_exists"] else None):
            raise OperationError("source_alignment_prepare_preimage_changed:" + item["name"])
        if item["delegated_nginx"] and not preparing and actual != (before if restoring else after):
            raise OperationError("source_alignment_nginx_callback_order:" + item["name"])
        if actual is not None and item["original_exists"]:
            if not same_attributes(attributes(path), item["original_attributes"]):
                raise OperationError("source_alignment_original_metadata_changed:" + item["name"])
        if item["change"] == "A" and not item["original_exists"] and actual is not None:
            if item["created_identity"] is None or attributes(path) != item["created_identity"]:
                raise OperationError("source_alignment_new_path_not_created_by_attempt:" + item["name"])


def ensure_parents(path: Path, record: dict) -> None:
    """仅建立本次新增文件所需目录，保留已有目录权限；恢复不递归删目录。"""
    missing = []
    current = path.parent
    while current != MAIN and not current.exists():
        missing.append(current)
        current = current.parent
    for parent in reversed(missing):
        parent.mkdir(mode=0o755)
        os.chown(parent, record["new_owner"]["uid"], record["new_owner"]["gid"])


def write_source(record: dict, item: dict, content: bytes, *, restoring: bool) -> None:
    """同目录原子替换普通源文件；新增文件用排他硬链接发布，绝不覆盖后出现的路径。"""
    path = project_path(item["name"])
    actual = read_bytes(path) if path.exists() else None
    actual_attributes = attributes(path) if actual is not None else None
    before, after = snapshot(record, item, "before"), snapshot(record, item, "after")
    if actual not in (before, after):
        raise OperationError("source_alignment_write_preimage_changed:" + item["name"])
    if item["original_exists"] and actual_attributes is not None and not same_attributes(actual_attributes, item["original_attributes"]):
        raise OperationError("source_alignment_write_metadata_changed:" + item["name"])
    if item["change"] == "A" and not item["original_exists"] and actual is not None and actual_attributes != item["created_identity"]:
        raise OperationError("source_alignment_write_new_path_not_owned:" + item["name"])
    if actual == content:
        return
    ensure_parents(path, record)
    target_attributes = item["original_attributes"] or {**record["new_owner"], "mode": item["git_mode"]}
    temporary = path.with_name("." + path.name + ".unified-" + secrets.token_hex(8))
    record["pending"] = {"path": item["name"], "direction": "restore" if restoring else "align", "temporary": str(temporary.relative_to(MAIN))}
    save(record)
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        os.fchown(stream.fileno(), target_attributes["uid"], target_attributes["gid"])
        os.fchmod(stream.fileno(), target_attributes["mode"])
        if item["change"] == "A" and not item["original_exists"]:
            metadata = os.fstat(stream.fileno())
            item["created_identity"] = {"uid": metadata.st_uid, "gid": metadata.st_gid,
                                        "mode": stat.S_IMODE(metadata.st_mode), "device": metadata.st_dev, "inode": metadata.st_ino}
            save(record)
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    # 逐项 CAS 再核一次，避免把写意图期间的外部变化覆盖掉。
    observed = read_bytes(path) if path.exists() else None
    observed_attributes = attributes(path) if observed is not None else None
    if observed != actual or observed_attributes != actual_attributes:
        raise OperationError("source_alignment_changed_during_write:" + item["name"])
    if item["change"] == "A" and not item["original_exists"]:
        os.link(temporary, path, follow_symlinks=False)
        temporary.unlink()
    else:
        os.replace(temporary, path)
    fsync_directory(path.parent)
    if read_bytes(path) != content or not same_attributes(attributes(path), target_attributes):
        raise OperationError("source_alignment_write_postimage_mismatch:" + item["name"])
    record["pending"] = None
    save(record)


def update_git(record: dict, runner, *, restoring: bool) -> None:
    """原生 read-tree 与 CAS update-ref 只推进已审核两端；不 reset、checkout 或清理整树。"""
    head, index = source_state(runner, record)
    target = BEFORE if restoring else APP
    for lock in (MAIN / ".git/index.lock", MAIN / ".git/refs/heads/main.lock"):
        if lock.exists() or lock.is_symlink():
            raise OperationError("source_alignment_existing_git_lock_requires_owner")
    record["pending"] = {"git_target": target}
    save(record)
    if index != target:
        git(runner, "read-tree", target)
        preserve_git_attributes(record)
    if head != target:
        git(runner, "update-ref", "refs/heads/main", target, head)
        preserve_git_attributes(record)
    record["pending"] = None
    save(record)


def align(root: Path, runner) -> dict:
    """供外部 TLS 锁内回调：Nginx 两文件已由唯一所有者写好后，推进其余路径和 main/index。"""
    record = load(root)
    if record.get("status") not in {"prepared", "aligning", "aligned"}:
        raise OperationError("source_alignment_status_requires_restore")
    preflight(record, runner, restoring=False)
    record["status"] = "aligning"
    save(record)
    for item in record["paths"]:
        if item["delegated_nginx"] or item["change"] == "A" and item["original_exists"]:
            continue
        write_source(record, item, snapshot(record, item, "after"), restoring=False)
    update_git(record, runner, restoring=False)
    if git(runner, "diff", "--no-ext-diff", "--no-textconv", "--name-only", "-z", APP) or git(runner, "diff", "--cached", "--name-only", "-z", APP):
        raise OperationError("source_alignment_not_clean_at_app")
    record["status"] = "aligned"
    save(record)
    return {"complete": True, "operation": "source-align", "revision": APP, "untracked_preserved": True}


def restore(root: Path, runner) -> dict:
    """幂等恢复自有路径；不删原有 untracked，同字节且确属本次创建的新增文件才可 unlink。"""
    record = load(root)
    if record.get("status") not in {"prepared", "aligning", "aligned", "restoring", "restored"}:
        raise OperationError("source_alignment_restore_status_invalid")
    preflight(record, runner, restoring=True)
    record["status"] = "restoring"
    save(record)
    for item in reversed(record["paths"]):
        if item["delegated_nginx"] or item["change"] == "A" and item["original_exists"]:
            continue
        path = project_path(item["name"])
        if item["change"] == "A":
            if not path.exists():
                continue
            if read_bytes(path) != snapshot(record, item, "after") or attributes(path) != item["created_identity"]:
                raise OperationError("source_alignment_created_file_changed:" + item["name"])
            record["pending"] = {"path": item["name"], "direction": "remove-created"}
            save(record)
            path.unlink()
            fsync_directory(path.parent)
            record["pending"] = None
            save(record)
        else:
            write_source(record, item, snapshot(record, item, "before"), restoring=True)
    update_git(record, runner, restoring=True)
    if git(runner, "diff", "--no-ext-diff", "--no-textconv", "--name-only", "-z", BEFORE) or git(runner, "diff", "--cached", "--name-only", "-z", BEFORE):
        raise OperationError("source_alignment_not_clean_at_before")
    record["status"] = "restored"
    save(record)
    return {"complete": True, "operation": "source-restore", "revision": BEFORE, "untracked_preserved": True}
