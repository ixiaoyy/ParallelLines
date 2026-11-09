"""工具 vhost 的唯一自有字节段；不读文件、不规范化或重写主站其它字节。"""

BEGIN = b"# BEGIN parallellines-tools-managed"
END = b"# END parallellines-tools-managed"


class ManagedConfigError(Exception):
    """标记/所有权不匹配必须停止，不用宽泛正则或整文件回退。"""


def span(source):
    """返回唯一标记段的起止位置，无标记返回 None；标记须独占行且以换行结束。"""
    starts, ends = source.count(BEGIN), source.count(END)
    if starts == ends == 0:
        return None
    if starts != 1 or ends != 1:
        raise ManagedConfigError("managed_marker_not_unique")
    start, end = source.index(BEGIN), source.index(END)
    if end <= start or (start and source[start - 1:start] != b"\n"):
        raise ManagedConfigError("managed_marker_boundary_invalid")
    if source[start + len(BEGIN):start + len(BEGIN) + 1] != b"\n":
        raise ManagedConfigError("managed_marker_boundary_invalid")
    tail = end + len(END)
    if source[tail:tail + 1] != b"\n":
        raise ManagedConfigError("managed_marker_final_newline_required")
    return start, tail + 1


def split(source):
    """返回不含自有段的原始字节和该段；主站其余内容逐字节保留。"""
    location = span(source)
    if location is None:
        return source, None
    start, end = location
    return source[:start] + source[end:], source[start:end]


def validate_fragment(fragment):
    """片段只可包含一个完整自有段，不容纳额外主站指令或外围空白。"""
    outside, owned = split(fragment)
    if outside or owned != fragment:
        raise ManagedConfigError("fragment_must_only_contain_owned_block")
    return fragment


def replace(source, expected_fragment, replacement):
    """只替换已匹配的自有段；首次追加不增加外围换行，拒绝未知旧段。"""
    _, actual = split(source)
    if actual != expected_fragment:
        raise ManagedConfigError("managed_fragment_preimage_mismatch")
    if replacement is not None:
        validate_fragment(replacement)
    location = span(source)
    if location is None:
        if replacement is None:
            return source
        if source and not source.endswith(b"\n"):
            raise ManagedConfigError("base_final_newline_required")
        return source + replacement
    start, end = location
    return source[:start] + (replacement or b"") + source[end:]


def owned_delta_allowed(disk, head, recorded):
    """仅允许与 Git HEAD 外围完全一致且自有段等于已保存片段的明确自有差异。"""
    if recorded is not None:
        validate_fragment(recorded)
    disk_outside, disk_owned = split(disk)
    head_outside, _ = split(head)
    return disk_outside == head_outside and disk_owned == recorded
