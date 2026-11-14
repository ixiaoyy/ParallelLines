"""固定统一登录发布目录的公开产物准备；不激活服务，不读取环境文件或数据库。"""

from __future__ import annotations

import bz2
import contextlib
import gzip
import hashlib
import http.client
import json
import lzma
import math
import os
from pathlib import Path, PurePosixPath
import re
import signal
import ssl
import stat
import tarfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib


ROOT = Path("/data/deployment/parallellines-unified/a2cfeddeec01ca0d5def4b3308103f3d85cc3861")
MAX_EXPANDED = 1024 * 1024 * 1024
MAX_ENTRIES = 20000
MAX_RECORD = 128 * 1024 * 1024
CHUNK = 1024 * 1024
NAME = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}")
DOWNLOAD_PATH = re.compile(
    r"/ixiaoyy/(?:ParallelLines|parallellines-chat|parallellines-new-api)/releases/download/"
    r"[A-Za-z0-9][A-Za-z0-9._+-]{0,127}/[A-Za-z0-9][A-Za-z0-9._+-]{0,159}"
)


class ArtifactPreparationError(RuntimeError):
    """只携带稳定错误码，不包含响应正文、临时签名跳转 URL 或环境内容。"""


def _check_time(deadline: float) -> None:
    """每段文件/网络工作检查同一个总预算，不重置累计时间。"""
    if time.monotonic() >= deadline:
        raise ArtifactPreparationError("artifact_prepare_deadline")


@contextlib.contextmanager
def _deadline(runner):
    """Linux 主线程硬限制包括 DNS/读取/解包；不超过 runner 剩余时间及 900 秒。"""
    if threading.current_thread() is not threading.main_thread() or not hasattr(signal, "setitimer"):
        raise ArtifactPreparationError("artifact_prepare_requires_linux_main_thread")
    now = time.monotonic()
    outer = getattr(runner, "deadline", None)
    if type(outer) not in (int, float) or not math.isfinite(outer) or outer <= now:
        raise ArtifactPreparationError("artifact_runner_deadline_invalid")
    previous_timer = signal.getitimer(signal.ITIMER_REAL)
    until = min(now + 900, outer)
    if previous_timer[0] > 0:
        until = min(until, now + previous_timer[0])

    def expired(_number, _frame):
        raise ArtifactPreparationError("artifact_prepare_deadline")

    previous_handler = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, max(0.001, until - now))
    try:
        yield until
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0] > 0:
            remaining = max(0.001, previous_timer[0] - (time.monotonic() - now))
            signal.setitimer(signal.ITIMER_REAL, remaining, previous_timer[1])


def _url(value: str, *, redirect: bool = False) -> str:
    """首 URL 只接受三个自有仓的公开 release 下载；跳转仍要求正常 HTTPS 和固定域名。"""
    if not isinstance(value, str) or len(value) > 16384 or any(ord(ch) < 32 for ch in value):
        raise ArtifactPreparationError("artifact_url_invalid")
    try:
        parsed = urllib.parse.urlsplit(value)
    except ValueError:
        raise ArtifactPreparationError("artifact_url_invalid") from None
    if (parsed.scheme != "https" or parsed.username or parsed.password or parsed.fragment
            or parsed.netloc not in {"github.com", "release-assets.githubusercontent.com"}):
        raise ArtifactPreparationError("artifact_url_not_allowed")
    if parsed.netloc == "github.com":
        if parsed.query or not DOWNLOAD_PATH.fullmatch(parsed.path):
            raise ArtifactPreparationError("artifact_repository_url_not_allowed")
    elif not redirect:
        raise ArtifactPreparationError("artifact_initial_cdn_url_not_allowed")
    return value


class _Redirects(urllib.request.HTTPRedirectHandler):
    """最多五次白名单跳转；不转发认证信息，也不把 CDN 的签名查询记入回执。"""

    def __init__(self, deadline: float):
        self.deadline = deadline
        self.count = 0

    def redirect_request(self, request, fp, code, message, headers, newurl):
        _check_time(self.deadline)
        self.count += 1
        if self.count > 5:
            raise ArtifactPreparationError("artifact_redirect_limit")
        _url(newurl, redirect=True)
        request.timeout = min(15, max(0.001, self.deadline - time.monotonic()))
        return super().redirect_request(request, fp, code, message, headers, newurl)


def _directory(path: Path) -> None:
    """只创建指定准备目录；任何祖先或目标链接均拒绝，不改已有目录的权限/内容。"""
    for candidate in [*reversed(path.parents), path]:
        if candidate.is_symlink():
            raise ArtifactPreparationError("artifact_directory_link")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.is_dir():
        raise ArtifactPreparationError("artifact_directory_invalid")


def _digest(path: Path, deadline: float) -> str:
    """流式读取已限定产物，不跟随链接；只用于明确的完整性/复用核对。"""
    if path.is_symlink() or not path.is_file():
        raise ArtifactPreparationError("artifact_file_invalid")
    expected_size = path.stat().st_size
    value = hashlib.sha256()
    count = 0
    with path.open("rb") as stream:
        while True:
            _check_time(deadline)
            chunk = stream.read(CHUNK)
            if not chunk:
                if count != expected_size:
                    raise ArtifactPreparationError("artifact_file_changed")
                return value.hexdigest()
            count += len(chunk)
            if count > expected_size:
                raise ArtifactPreparationError("artifact_file_changed")
            value.update(chunk)


def _record(path: Path, value: dict) -> None:
    """私有回执初次以 0600 排他创建；已有回执只接受完整相等，绝不覆盖未知记录。"""
    if path.exists() or path.is_symlink():
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_size > MAX_RECORD):
            raise ArtifactPreparationError("artifact_record_invalid")
        try:
            actual = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeError):
            raise ArtifactPreparationError("artifact_record_invalid") from None
        if actual != value:
            raise ArtifactPreparationError("artifact_record_mismatch")
        return
    data = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    if len(data) > MAX_RECORD:
        raise ArtifactPreparationError("artifact_record_limit")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(path, flags, 0o600), "wb") as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def _download(item: dict, directory: Path, deadline: float) -> Path:
    """一次下载、逐字节计数并核摘要；已存在仅精确匹配复用，失败只清理本次独占临时文件。"""
    key = item["key"]
    filename = PurePosixPath(urllib.parse.urlsplit(item["url"]).path).name
    target = directory / (key + "--" + filename)
    expected = {name: item[name] for name in ("key", "url", "sha256", "bytes", "kind")}
    if target.exists() or target.is_symlink():
        if target.is_symlink() or not target.is_file() or target.stat().st_size != item["bytes"]:
            raise ArtifactPreparationError("artifact_existing_mismatch:" + key)
        if _digest(target, deadline) != item["sha256"]:
            raise ArtifactPreparationError("artifact_existing_mismatch:" + key)
        _record(directory / ("." + key + ".json"), expected)
        return target
    temporary = directory / ("." + key + ".download")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(temporary, flags, 0o600)
    try:
        # 不采集代理/环境配置；公开下载不携带 Cookie、Basic 或任何私有请求头。
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
            urllib.request.HTTPSHandler(context=ssl.create_default_context()), _Redirects(deadline))
        request = urllib.request.Request(item["url"], headers={
            "User-Agent": "ParallelLinesUnifiedArtifact/1", "Accept": "application/octet-stream"})
        with os.fdopen(descriptor, "wb") as output:
            descriptor = None
            with opener.open(request, timeout=min(15, max(0.001, deadline - time.monotonic()))) as response:
                if response.status != 200:
                    raise ArtifactPreparationError("artifact_http_status:" + key)
                _url(response.geturl(), redirect=True)
                length = response.headers.get("Content-Length")
                if length is not None and (not length.isdecimal() or int(length) != item["bytes"]):
                    raise ArtifactPreparationError("artifact_http_size:" + key)
                total = 0
                value = hashlib.sha256()
                while True:
                    _check_time(deadline)
                    chunk = response.read(CHUNK)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > item["bytes"]:
                        raise ArtifactPreparationError("artifact_download_size:" + key)
                    output.write(chunk)
                    value.update(chunk)
                if total != item["bytes"] or value.hexdigest() != item["sha256"]:
                    raise ArtifactPreparationError("artifact_download_mismatch:" + key)
            output.flush()
            os.fsync(output.fileno())
        # 同一目录内排他安装，不用 replace 覆盖并发创建或未知的目标。
        os.link(temporary, target, follow_symlinks=False)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        temporary.unlink()
    _record(directory / ("." + key + ".json"), expected)
    return target


class _TarReader:
    """限制 tar 元数据单次读取和原始偏移，避免 PAX/长名头触发巨量分配；正常文件按块读取。"""

    def __init__(self, stream, deadline: float):
        """绑定已解压文件流与累计期限；不自行打开任何应用或运行文件。"""
        self.stream = stream
        self.deadline = deadline
        self.limit = MAX_EXPANDED + MAX_ENTRIES * 8192

    def read(self, size: int = -1):
        """只返回有上限的字节块，拒绝无界读取或超大元数据请求。"""
        _check_time(self.deadline)
        if size < 0 or size > CHUNK or self.tell() + size > self.limit:
            raise ArtifactPreparationError("artifact_tar_read_limit")
        return self.stream.read(size)

    def tell(self):
        """返回已解压 tar 的当前位置，供标准 tarfile 读取器定位。"""
        return self.stream.tell()

    def seek(self, offset, whence=0):
        """只允许预算内绝对/相对定位，不执行向文件末尾的无界扫描。"""
        _check_time(self.deadline)
        position = offset if whence == 0 else self.tell() + offset
        if whence not in (0, 1) or position < 0 or position > self.limit:
            raise ArtifactPreparationError("artifact_tar_seek_limit")
        return self.stream.seek(offset, whence)


def _consume(budget: dict, *, size: int = 0, entries: int = 0) -> None:
    """本次所有归档共同使用一份 1GiB/20000 目录项预算，复用目录也计入。"""
    budget["bytes"] += size
    budget["entries"] += entries
    if budget["bytes"] > MAX_EXPANDED or budget["entries"] > MAX_ENTRIES:
        raise ArtifactPreparationError("artifact_expanded_limit")


def _tree(directory: Path, deadline: float, budget: dict) -> dict:
    """只扫描该归档自己的已准备目录；拒绝链接/设备，复用必须逐文件内容与权限完全一致。"""
    if (directory.is_symlink() or not directory.is_dir()
            or stat.S_IMODE(directory.lstat().st_mode) != 0o755):
        raise ArtifactPreparationError("artifact_input_directory_invalid")
    result = {"files": {}, "directories": []}
    pending = [directory]
    while pending:
        with os.scandir(pending.pop()) as children:
            for entry in children:
                _check_time(deadline)
                path = Path(entry.path)
                info = entry.stat(follow_symlinks=False)
                if stat.S_ISDIR(info.st_mode):
                    if stat.S_IMODE(info.st_mode) != 0o755:
                        raise ArtifactPreparationError("artifact_input_directory_changed")
                    _consume(budget, entries=1)
                    result["directories"].append(path.relative_to(directory).as_posix())
                    pending.append(path)
                elif stat.S_ISREG(info.st_mode):
                    _consume(budget, size=info.st_size, entries=1)
                    result["files"][path.relative_to(directory).as_posix()] = {
                        "bytes": info.st_size, "sha256": _digest(path, deadline), "mode": stat.S_IMODE(info.st_mode)}
                else:
                    raise ArtifactPreparationError("artifact_input_link_or_device")
    result["directories"].sort()
    return result


def _member_path(member: tarfile.TarInfo) -> PurePosixPath:
    """归档名只按 POSIX 处理；路径穿越、绝对路径、反斜线和异常长名均拒绝。"""
    name = member.name
    path = PurePosixPath(name)
    if (len(name.encode("utf-8")) > 4096 or "\\" in name or "\x00" in name
            or path.is_absolute() or ".." in path.parts):
        raise ArtifactPreparationError("artifact_tar_path_invalid")
    return path


def _extract(item: dict, archive: Path, inputs: Path, deadline: float, budget: dict) -> Path:
    """只向排他新目录解包；失败目录保留且不得隐式重用，完成记录不混入应用构建上下文。"""
    target = inputs / item["key"]
    receipt = inputs / ("." + item["key"] + ".prepared.json")
    identity = {name: item[name] for name in ("key", "url", "sha256", "bytes", "kind")}
    if target.exists() or target.is_symlink():
        if not receipt.exists():
            raise ArtifactPreparationError("artifact_existing_input_unknown:" + item["key"])
        actual = _tree(target, deadline, budget)
        _record(receipt, {"artifact": identity, **actual})
        return target
    if receipt.exists() or receipt.is_symlink():
        raise ArtifactPreparationError("artifact_input_record_without_directory:" + item["key"])
    target.mkdir(mode=0o700, exist_ok=False)
    seen = set()
    directories = set()
    contents = {"files": {}, "directories": []}

    def parents(path: PurePosixPath):
        for index in range(1, len(path.parts) + 1):
            name = PurePosixPath(*path.parts[:index]).as_posix()
            if name in directories:
                continue
            _consume(budget, entries=1)
            destination = target / name
            destination.mkdir(mode=0o755, exist_ok=False)
            destination.chmod(0o755)
            directories.add(name)

    with contextlib.ExitStack() as stack:
        raw = stack.enter_context(archive.open("rb"))
        magic = raw.read(6)
        raw.seek(0)
        stream = raw
        if magic.startswith(b"\x1f\x8b"):
            stream = stack.enter_context(gzip.GzipFile(fileobj=raw))
        elif magic.startswith(b"BZh"):
            stream = stack.enter_context(bz2.BZ2File(raw))
        elif magic.startswith(b"\xfd7zXZ\x00"):
            stream = stack.enter_context(lzma.LZMAFile(raw))
        tar = stack.enter_context(tarfile.open(fileobj=_TarReader(stream, deadline), mode="r:"))
        for index, member in enumerate(tar, start=1):
            _check_time(deadline)
            if index > MAX_ENTRIES:
                raise ArtifactPreparationError("artifact_tar_member_limit")
            path = _member_path(member)
            if member.size < 0 or member.sparse is not None:
                raise ArtifactPreparationError("artifact_tar_sparse_or_size")
            if not path.parts:
                if member.isdir() and member.size == 0:
                    continue
                raise ArtifactPreparationError("artifact_tar_root_invalid")
            name = path.as_posix()
            if name in seen:
                raise ArtifactPreparationError("artifact_tar_duplicate_path")
            seen.add(name)
            if member.isdir() and member.size == 0:
                parents(path)
                continue
            if member.type not in (tarfile.REGTYPE, tarfile.AREGTYPE):
                raise ArtifactPreparationError("artifact_tar_link_or_device")
            _consume(budget, size=member.size, entries=1)
            parents(path.parent)
            destination = target / name
            mode = 0o755 if member.mode & 0o111 else 0o644
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
            with tar.extractfile(member) as source, os.fdopen(os.open(destination, flags, 0o600), "wb") as output:
                value = hashlib.sha256()
                count = 0
                while True:
                    _check_time(deadline)
                    chunk = source.read(CHUNK)
                    if not chunk:
                        break
                    count += len(chunk)
                    if count > member.size:
                        raise ArtifactPreparationError("artifact_tar_body_size")
                    output.write(chunk)
                    value.update(chunk)
                if count != member.size:
                    raise ArtifactPreparationError("artifact_tar_body_size")
            destination.chmod(mode)
            contents["files"][name] = {"bytes": count, "sha256": value.hexdigest(), "mode": mode}
    contents["directories"] = sorted(directories)
    target.chmod(0o755)
    _record(receipt, {"artifact": identity, **contents})
    return target


def prepare(plan: dict, root: Path, runner) -> dict:
    """按固定公开 plan 准备产物；返回 artifacts 元数据及 inputs 路径，不执行构建或激活。

    plan 必须含 artifacts 列表和完整 revisions 字典。runner 只提供单调时钟 deadline。
    tar 输入是 inputs/key 目录；file 输入直接引用 artifacts 已核文件，不额外复制。
    任何既有内容不匹配或失败残留都停止，由发布负责人处理，不自动覆盖/清理未知目录。
    """
    if not isinstance(root, Path) or root != ROOT or not root.is_absolute():
        raise ArtifactPreparationError("artifact_prepare_root_mismatch")
    if not isinstance(plan, dict) or not isinstance(plan.get("artifacts"), list):
        raise ArtifactPreparationError("artifact_plan_invalid")
    items = plan["artifacts"]
    revisions = plan.get("revisions")
    if (not items or len(items) > 32 or not isinstance(revisions, dict) or not revisions
            or len(revisions) > 16 or any(not isinstance(key, str) or not NAME.fullmatch(key)
                or not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}", value)
                for key, value in revisions.items())):
        raise ArtifactPreparationError("artifact_revisions_or_count_invalid")
    keys = set()
    normalized = []
    for item in items:
        if (not isinstance(item, dict) or not isinstance(item.get("key"), str)
                or not NAME.fullmatch(item["key"]) or item["key"] in keys
                or item.get("kind") not in ("tar", "file")
                or type(item.get("bytes")) is not int or item["bytes"] < 0
                or not isinstance(item.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"])):
            raise ArtifactPreparationError("artifact_descriptor_invalid")
        keys.add(item["key"])
        _url(item.get("url"))
        normalized.append({name: item[name] for name in ("key", "url", "sha256", "bytes", "kind")})
    try:
        with _deadline(runner) as deadline:
            _directory(root)
            artifacts, inputs = root / "artifacts", root / "inputs"
            _directory(artifacts)
            _directory(inputs)
            prepared = {"schema": 1, "complete": True, "root": str(root),
                        "revisions": dict(revisions), "artifacts": {}, "inputs": {}}
            budget = {"bytes": 0, "entries": 0}
            for item in normalized:
                path = _download(item, artifacts, deadline)
                prepared["artifacts"][item["key"]] = {**item, "path": str(path)}
                source = _extract(item, path, inputs, deadline, budget) if item["kind"] == "tar" else path
                prepared["inputs"][item["key"]] = str(source)
            _record(inputs / ".prepared.json", prepared)
            return prepared
    except ArtifactPreparationError:
        raise
    except (OSError, ValueError, KeyError, tarfile.TarError, EOFError, urllib.error.URLError,
            http.client.HTTPException, zlib.error, lzma.LZMAError):
        raise ArtifactPreparationError("artifact_prepare_io_or_archive_failed") from None
