"""在既有 Tools TLS 锁下，以原部署账号执行固定发布脚本。"""

from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import pwd
import re
import stat
import sys


LOCK_FILE = Path("/opt/parallellines-tools/ops/tls.lock")
LOCK_BUSY = 75
SCRIPT_LIMIT = 64 * 1024


class TLSLockBusy(Exception):
    """现有锁被其他发布或续载进程持有。"""


@contextmanager
def existing_tls_lock(path: Path):
    """只打开当前锁 inode，不创建、替换或删除；争用时调用方可重新派发。"""
    if path.parent.resolve(strict=True) != path.parent:
        raise ValueError("tls_lock_directory_changed")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != 0 or metadata.st_mode & 0o022:
            raise ValueError("tls_lock_not_owned")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise TLSLockBusy from None
        current = path.lstat()
        if (metadata.st_dev, metadata.st_ino) != (current.st_dev, current.st_ino):
            raise ValueError("tls_lock_inode_changed")
        yield fd
    finally:
        os.close(fd)


def main(args: list[str]) -> int:
    """锁 FD 随发布 shell 继承，直到命令结束；sudo 只用于打开受限的锁文件。"""
    if len(args) != 1 or not re.fullmatch(r"[0-9a-f]{40}", args[0]):
        print("gateway_tls_lock_invalid_revision", file=sys.stderr)
        return 1
    script = sys.stdin.buffer.read(SCRIPT_LIMIT + 1)
    if not script or len(script) > SCRIPT_LIMIT or b"\0" in script:
        print("gateway_tls_lock_invalid_script", file=sys.stderr)
        return 1
    try:
        uid = int(os.environ["SUDO_UID"])
        gid = int(os.environ["SUDO_GID"])
        account = pwd.getpwuid(uid)
        with existing_tls_lock(LOCK_FILE) as fd:
            # shell 保留 FD 9，后续单个 sudo 子命令关闭其副本不会提前解除父 shell 的锁。
            if fd != 9:
                os.dup2(fd, 9, inheritable=True)
            else:
                os.set_inheritable(fd, True)
            os.initgroups(account.pw_name, gid)
            os.setgid(gid)
            os.setuid(uid)
            env = {**os.environ, "HOME": account.pw_dir, "USER": account.pw_name,
                   "LOGNAME": account.pw_name}
            for name in ("SUDO_UID", "SUDO_GID", "SUDO_USER", "SUDO_COMMAND"):
                env.pop(name, None)
            # 先读完固定脚本，再用 argv 交给 shell；Docker 等子命令不能从 stdin 吃掉后续脚本。
            os.execve("/bin/sh", [b"/bin/sh", b"-ec", script, b"main-deploy", args[0].encode()], env)
    except TLSLockBusy:
        print("gateway_tls_lock_busy: retry the Deploy after the current TLS operation", file=sys.stderr)
        return LOCK_BUSY
    except (KeyError, OSError, ValueError):
        print("gateway_tls_lock_unavailable: verify the existing Tools lock and deploy identity", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
