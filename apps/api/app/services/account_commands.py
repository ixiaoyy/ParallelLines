"""账号域受控写入用例（阶段 1 · 同进程收口）。

所有非账号业务服务（如上传、后台管理、审核、反垃圾、徽章与系统建号）修改账号核心字段
或构造新 User 记录时，必须通过本模块显式命令执行，禁止直接赋值 user.<field> 或直接
实例化 User(...)，以便后续统一审计、会话联动及按需独立部署。
"""

from __future__ import annotations

from typing import Any

from app.models.user import User


def set_user_avatar_url(user: User, avatar_url: str | None) -> None:
    """更新用户头像地址；调用方保持原有本地事务提交语义。"""
    user.avatar_url = avatar_url


def set_user_role(user: User, role: str) -> None:
    """更新用户平台角色；调用方负责权限校验、审计记录与事务提交。"""
    user.role = role


def set_user_status(user: User, status: str) -> None:
    """更新用户账号状态（如 active / silenced / suspended）；保持原事务边界。"""
    user.status = status


def set_user_trust_level(user: User, trust_level: int) -> None:
    """更新用户社区信任等级字段；保持原事务边界。"""
    user.trust_level = trust_level


def build_provisioned_user(**fields: Any) -> User:
    """为系统人物、内置 Bot 或历史数据导入构造 User 实例，统一收口账号实体创建点。"""
    return User(**fields)
