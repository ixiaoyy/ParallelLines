from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

from app.core.exceptions import ValidationError

PersonaKind = Literal["editorial", "automation", "fictional"]
PERSONA_KIND_COMMENT = (
    "运营身份细分：editorial 栏目、automation 自动账号、fictional 创作角色；"
    "NULL 为未细分，仅 is_persona=true 生效。"
)


@dataclass(frozen=True)
class PersonaIdentity:
    """Hold the public kind, label, and explanation for an operator account."""

    kind: PersonaKind | None
    label: str
    description: str


@dataclass(frozen=True)
class SeededPersonaClassification:
    """Bind one project-owned seed identity to its approved public subtype."""

    username: str
    email: str
    kind: PersonaKind


PERSONA_IDENTITIES: dict[PersonaKind, PersonaIdentity] = {
    "editorial": PersonaIdentity(
        "editorial", "官方栏目", "该账号由平行线运营维护，用于栏目内容发布。"
    ),
    "automation": PersonaIdentity(
        "automation", "自动账号", "该账号由平行线运营维护，用于自动化发布或辅助互动。"
    ),
    "fictional": PersonaIdentity(
        "fictional", "创作角色", "该账号是平行线运营的创作角色，不代表独立社区成员。"
    ),
}
GENERIC_PERSONA_IDENTITY = PersonaIdentity(None, "运营角色", "该账号由平行线运营维护。")

SEEDED_PERSONA_CLASSIFICATIONS: tuple[SeededPersonaClassification, ...] = (
    SeededPersonaClassification(
        "不吃香菜的猫", "no-coriander-cat@pingxingxian.space", "fictional"
    ),
    SeededPersonaClassification(
        "一杯冰美式续命", "iced-americano@pingxingxian.space", "fictional"
    ),
    SeededPersonaClassification("外卖备注写错了", "waimai-note@pingxingxian.space", "fictional"),
    SeededPersonaClassification(
        "冰箱里还有半瓶可乐", "half-cola@pingxingxian.space", "fictional"
    ),
    SeededPersonaClassification("刚下班别催", "offwork-no-push@pingxingxian.space", "fictional"),
    SeededPersonaClassification("雾里看山", "fog-mountain@pingxingxian.space", "fictional"),
    SeededPersonaClassification("远山便利店", "yuanshan-shop@pingxingxian.space", "fictional"),
    SeededPersonaClassification("老槐", "old-huai-tree@pingxingxian.space", "fictional"),
    SeededPersonaClassification("oldhuai", "oldhuai@pingxingxian.space", "fictional"),
    SeededPersonaClassification("huai_07", "huai-07@pingxingxian.space", "fictional"),
    SeededPersonaClassification("Aki_慢慢来", "aki-slow@pingxingxian.space", "fictional"),
    SeededPersonaClassification("momo-离线", "momo-offline@pingxingxian.space", "fictional"),
    SeededPersonaClassification("kk不在线", "kk-offline@pingxingxian.space", "fictional"),
    SeededPersonaClassification("Nate_路过", "nate-passby@pingxingxian.space", "fictional"),
    SeededPersonaClassification("小K_再看看", "xiaok-look@pingxingxian.space", "fictional"),
    SeededPersonaClassification("rain_404", "rain404@pingxingxian.space", "fictional"),
    SeededPersonaClassification("zzZ_醒了", "zzz-awake@pingxingxian.space", "fictional"),
    SeededPersonaClassification("beta路人", "beta-passer@pingxingxian.space", "fictional"),
    SeededPersonaClassification("loop_一下", "loop-once@pingxingxian.space", "fictional"),
    SeededPersonaClassification("穿猫的靴子", "cat-boots@pingxingxian.space", "fictional"),
    SeededPersonaClassification("小漫家", "xiaomanjia@pingxingxian.space", "fictional"),
    SeededPersonaClassification(
        "小小资讯", "xiaoxiao-zixun@pingxingxian.space", "automation"
    ),
    SeededPersonaClassification(
        "小小鸡仔", "xiaoxiao-jizai@pingxingxian.space", "editorial"
    ),
    SeededPersonaClassification("小瓜同学", "xiaogua@pingxingxian.space", "editorial"),
    SeededPersonaClassification(
        "页边有光", "page-margin-light@pingxingxian.space", "editorial"
    ),
    SeededPersonaClassification(
        "今天也想早睡", "sleepy_today@parallellines.local", "fictional"
    ),
)

_SEEDED_PERSONA_CLASSIFICATION_BY_IDENTITY = {
    (classification.username, classification.email): classification.kind
    for classification in SEEDED_PERSONA_CLASSIFICATIONS
}


def seeded_persona_kind(username: str, email: str) -> PersonaKind | None:
    """Return the approved subtype for one exact seeded username/email pair.

    Parameters are the canonical public username and email. The return value is
    the configured kind or None; matching is exact and this helper has no side effects.
    """

    return _SEEDED_PERSONA_CLASSIFICATION_BY_IDENTITY.get((username, email))


def normalize_persona_kind(is_persona: bool, kind: object) -> PersonaKind | None:
    """Return a known subtype only for an explicitly managed account.

    Parameters are the existing operator flag and possibly legacy subtype.
    False/unknown flags or invalid subtypes return None without repairing data.
    """

    if is_persona is not True or not isinstance(kind, str) or kind not in PERSONA_IDENTITIES:
        return None
    return cast(PersonaKind, kind)


def persona_identity(is_persona: bool, kind: object = None) -> PersonaIdentity | None:
    """Return public identity copy, a managed fallback, or no operator identity.

    The flag remains authoritative; missing/invalid kinds on a managed account
    use generic copy. This lookup does not infer content origin or mutate data.
    """

    if is_persona is not True:
        return None
    normalized = normalize_persona_kind(is_persona, kind)
    return PERSONA_IDENTITIES[normalized] if normalized else GENERIC_PERSONA_IDENTITY


def resolve_persona_update(
    current_is_persona: bool,
    current_kind: str | None,
    *,
    requested_is_persona: bool | None,
    requested_kind: object = None,
    kind_provided: bool = False,
) -> tuple[bool, str | None]:
    """Validate an administrator's requested identity before any ORM mutation.

    Current values supply omitted fields; kind_provided distinguishes omission
    from an explicit null. Returns the next flag/kind, or raises a typed error
    for an invalid/conflicting kind. Closing or newly opening the operator flag
    clears stale subtypes; unrelated edits preserve stored values.
    """

    next_is_persona = current_is_persona if requested_is_persona is None else requested_is_persona
    if kind_provided:
        kind = normalize_persona_kind(True, requested_kind)
        if requested_kind is not None and kind is None:
            raise ValidationError("persona_kind_invalid", "请选择有效的公开身份。")
        if kind is not None and next_is_persona is not True:
            raise ValidationError(
                "persona_kind_requires_persona", "请先将账号归类为运营/测试账号，再选择公开身份。"
            )
        return next_is_persona, kind
    if requested_is_persona is False or (
        requested_is_persona is True and current_is_persona is not True
    ):
        return next_is_persona, None
    return next_is_persona, current_kind
