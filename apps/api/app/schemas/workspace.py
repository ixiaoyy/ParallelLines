import json
import re
from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.exceptions import AppError, ValidationError

WORKSPACE_SCHEMA_VERSION = 1
MAX_WORKSPACE_CONFIG_BYTES = 128 * 1024
MAX_WORKSPACE_JSON_DEPTH = 32
MAX_REVISION = (1 << 63) - 1


class WorkspaceConfigUpdate(BaseModel):
    """完整的云配置快照。基准版本 0 仅用于首次创建。"""

    model_config = ConfigDict(extra="forbid", strict=True)

    expected_revision: Annotated[str, Field(pattern=r"^(0|[1-9][0-9]{0,18})$")]
    schema_version: Annotated[int, Field(ge=WORKSPACE_SCHEMA_VERSION, le=WORKSPACE_SCHEMA_VERSION)]
    config: dict[str, Any]

    @field_validator("expected_revision")
    @classmethod
    def check_incrementable_revision(cls, value: str) -> str:
        """只接受能够绑定到有符号 BIGINT 且可再递增一次的版本。"""
        if int(value) >= MAX_REVISION:
            raise ValueError("Revision cannot be incremented")
        return value


class WorkspaceConfigSnapshot(BaseModel):
    """读写共用的快照结构；没有云配置时版本为 0，配置和时间为 null。"""

    revision: str
    schema_version: int
    config: dict[str, Any] | None
    updated_at: datetime | None


def _style(value: object) -> bool:
    """仅允许颜色、渐变、阴影、滤镜等值，不允许 URL、转义或声明分隔符。"""
    return (
        isinstance(value, str)
        and re.fullmatch(r"[a-zA-Z0-9 #(),.+%\-]*", value) is not None
        and all(
            fn.lower() in _PAINT_FUNCTIONS
            for fn in re.findall(r"([a-zA-Z][a-zA-Z0-9-]*) *\(", value)
        )
    )


_PAINT_FUNCTIONS = frozenset(
    {
        "rgb",
        "rgba",
        "hsl",
        "hsla",
        "linear-gradient",
        "radial-gradient",
        "conic-gradient",
        "repeating-linear-gradient",
        "repeating-radial-gradient",
        "repeating-conic-gradient",
        "blur",
        "brightness",
        "contrast",
        "drop-shadow",
        "grayscale",
        "hue-rotate",
        "invert",
        "opacity",
        "saturate",
        "sepia",
    }
)


def _manual_link(value: object) -> bool:
    """只接收手动点击的 HTTP(S) 或同源路径，排除凭据、控制字符和协议相对地址。"""
    if not isinstance(value, str) or re.search(r"[\s\\\x00-\x1f\x7f]", value):
        return False
    if not value:
        return True
    if value.startswith("/"):
        return not value.startswith("//")
    try:
        url = urlsplit(value)
        return (
            url.scheme in {"http", "https"}
            and bool(url.hostname)
            and url.username is None
            and url.password is None
        )
    except ValueError:
        return False


type _Check = Callable[[Any], bool]


def _matches_fields(value: object, fields: dict[str, _Check]) -> bool:
    """校验对象形状，不补默认值，也不静默删除不支持的字段。"""
    return isinstance(value, dict) and all(
        key in fields and fields[key](item) for key, item in value.items()
    )


def _text(value: object) -> bool:
    return isinstance(value, str)


def _id(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _number(value: object) -> bool:
    return type(value) is float or (type(value) is int and abs(value) < 2**53)


def _flag(value: object) -> bool:
    return type(value) is bool


def _empty_text(value: object) -> bool:
    return value == ""


def _font(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[\w ,'\x22-]*", value) is not None


def _check_list(value: object, check: _Check) -> bool:
    return isinstance(value, list) and all(check(item) for item in value)


_GLOBAL_FIELDS: dict[str, _Check] = {
    "background": _style,
    "backgroundFilter": _style,
    "gutter": _number,
    "lang": _text,
    "globalFontFamily": _font,
    "siteTitle": _text,
    "disabledDialogAnimation": _flag,
    "showMenuBtn": _flag,
    # 兼容原型的空占位；实际代码、远端字体和图片仍仅留本地。
    "css": _empty_text,
    "js": _empty_text,
    "siteIcon": _empty_text,
    "loadHarmonyOSFont": lambda value: value is False,
}
_SHORTCUT_FIELDS: dict[str, _Check] = {
    "id": _id,
    "name": _text,
    "icon": _text,
    "color": _style,
    "prompt": _text,
    "autoSend": _flag,
}


def _shortcut(value: object) -> bool:
    """只同步已保存的指令结构，不在配置读写时发送或展开指令。"""
    return (
        isinstance(value, dict)
        and {"id", "name", "prompt"} <= value.keys()
        and _matches_fields(value, _SHORTCUT_FIELDS)
    )


def _bookmark(value: object) -> bool:
    """支持文件夹和手动链接；图标仅用文本颜色，防止渲染时外联。"""
    return (
        isinstance(value, dict)
        and "id" in value
        and _matches_fields(
            value,
            {
                "id": _id,
                "title": _text,
                "url": _manual_link,
                "iconType": lambda item: item == "text",
                "bgColor": _style,
                "iconPath": _style,
                "type": lambda item: item in ("icon", "folder"),
                "children": lambda item: _check_list(item, _bookmark),
            },
        )
    )


_TEXT_APPEARANCE: dict[str, _Check] = {
    "fontFamily": _font,
    "padding": _number,
    "textColor": _style,
    "textFontSize": _number,
}
_POSITIONED_TEXT = {**_TEXT_APPEARANCE, "position": _number, "textShadow": _style}
_MATERIAL_FIELDS: dict[str, dict[str, _Check]] = {
    "Empty": {**_POSITIONED_TEXT, "customText": _text},
    "Clock": {
        **_POSITIONED_TEXT,
        "duration": _number,
        "textHollow": _flag,
        "textHollowBg": _style,
        "textHollowBorder": _number,
    },
    "Day": {
        **_POSITIONED_TEXT,
        "duration": _number,
        "formatter": _text,
        "custom": _text,
        "timeZone": _text,
        "chineseWeekDay": _flag,
        "showTTS1": _flag,
        "showTTS2": _flag,
        "ttsFontSize": _number,
    },
    "Search": {
        **_POSITIONED_TEXT,
        "backdropBlur": _number,
        "boxBackground": _style,
        "boxRadius": _number,
        "boxShadow": _style,
        "maxWidth": _number,
        "showTabTips": _flag,
        "focusBgAnimation": _flag,
        "autoFocus": _flag,
        "rememberHistory": _flag,
        "linkBookMark": _flag,
    },
    "AiSearch": {
        **_TEXT_APPEARANCE,
        "maxWidth": _number,
        "autoSaveSearchToShortcut": _flag,
        "defaultMode": _text,
        "shortcuts": lambda value: _check_list(value, _shortcut),
    },
    "Bookmark": {
        **_TEXT_APPEARANCE,
        **dict.fromkeys(
            ("boxSize", "boxRadius", "iconSize", "tileTitleLines", "maxWidth"), _number
        ),
        **dict.fromkeys(("closeClickOutside", "disabledDrag", "hiddenAddBtn"), _flag),
        "folderBg": _style,
        "boxShadow": _style,
        "jumpType": lambda value: type(value) is int and value in (1, 2),
        "bookmark": lambda value: _check_list(value, _bookmark),
    },
    "Collection": {
        **_POSITIONED_TEXT,
        "keyboardMaxWidth": _number,
        "keyBackground": _style,
        "keyBorderRadius": _number,
        "keyGutter": _number,
    },
    # 笔记、待办、历史、搜索引擎配置与城市位置不随布局上传。
    "TodoList": {
        "baseFontSize": _number,
        "padding": _number,
        "themeColor": _style,
        "todo": lambda value: value == {},
    },
    "Editor": {
        **_TEXT_APPEARANCE,
        **dict.fromkeys(("enablePrism", "enableSlash", "enableTooltip", "showTitle"), _flag),
        "markdown": _empty_text,
    },
    "CountDown": {**_POSITIONED_TEXT, "eventName": _text, "eventTime": _text, "unit": _text},
    "SlackCountdown": {
        **_TEXT_APPEARANCE,
        "workStart": _text,
        "workEnd": _text,
        "restMode": _text,
        "paydayDay": _number,
        "advanceOnRest": _flag,
    },
    "WeatherCard": {},
    "AlarmTimer": {"fontFamily": _font, "textColor": _style},
}
_ELEMENT_FIELDS: dict[str, _Check] = {
    **dict.fromkeys(("position", "w", "h", "x", "y", "zIndex", "borderRadius"), _number),
    **dict.fromkeys(("background", "backgroundFilter", "backdropFilter", "boxShadow"), _style),
    "i": _id,
    "material": _text,
    "componentSetting": lambda value: isinstance(value, dict),
    "affixInfo": lambda value: _matches_fields(value, dict.fromkeys(("mode", "x", "y"), _number)),
}


def _element(value: object) -> bool:
    """校验物料键及其专属设置，拒绝任意动作嵌套、脚本和未注册字段。"""
    if not isinstance(value, dict) or not {"i", "material"} <= value.keys():
        return False
    if not _matches_fields(value, _ELEMENT_FIELDS):
        return False
    fields = _MATERIAL_FIELDS.get(value["material"])
    return fields is not None and _matches_fields(value.get("componentSetting", {}), fields)


_LAYOUT_FIELDS: dict[str, _Check] = {
    "list": lambda value: _check_list(value, _element),
    "affix": lambda value: _check_list(value, _element),
    "global": lambda value: _matches_fields(value, _GLOBAL_FIELDS),
    "showBackgroundEffect": _flag,
    "showRefreshBtn": _flag,
    "backgroundEffectActive": _number,
}


def _tab(value: object) -> bool:
    """选中标签页可省略 data 或使用 null；其他标签页使用相同布局规则。"""
    return (
        isinstance(value, dict)
        and "id" in value
        and _matches_fields(
            value,
            {
                "id": _id,
                "name": _text,
                "selected": _flag,
                "data": lambda item: item is None or _matches_fields(item, _LAYOUT_FIELDS),
            },
        )
    )


_CONFIG_FIELDS: dict[str, _Check] = {
    **_LAYOUT_FIELDS,
    "tabList": lambda value: _check_list(value, _tab),
    "showTabSwitchBtn": lambda value: _flag(value) or _number(value),
    "enableKeydownSwitchTab": _flag,
}


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """拒绝重复键，避免同一份 JSON 在多个消费者之间产生两种含义。"""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def parse_workspace_update(body: bytearray) -> WorkspaceConfigUpdate:
    """从已经限长的 UTF-8 请求解析 v1 快照；错误不回显私有配置或字段内容。"""
    try:
        raw = json.loads(body.decode("utf-8"), object_pairs_hook=_unique_object)
        payload = WorkspaceConfigUpdate.model_validate(raw)
        # 先验证固定的深度和字节口径，避免深度递归及非标准 JSON 落库。
        pending = [(payload.config, 1)]
        while pending:
            current, depth = pending.pop()
            if depth > MAX_WORKSPACE_JSON_DEPTH:
                raise ValueError("Workspace nesting is too deep")
            children = current.values() if isinstance(current, dict) else current
            pending.extend((item, depth + 1) for item in children if isinstance(item, (dict, list)))
        config_bytes = len(
            json.dumps(
                payload.config, ensure_ascii=False, separators=(",", ":"), allow_nan=False
            ).encode("utf-8")
        )
    except (ValueError, RecursionError):
        raise ValidationError("workspace_config_invalid", "工作台配置格式无效") from None
    if config_bytes > MAX_WORKSPACE_CONFIG_BYTES:
        raise AppError(
            "workspace_config_too_large", "云配置最多 128 KiB，原配置可保留在本地", status_code=413
        )
    if not _matches_fields(payload.config, _CONFIG_FIELDS):
        raise ValidationError("workspace_config_invalid", "配置含有不支持的字段或值")
    return payload
