"""统一登录 Nginx 发布边界：先只读确认现场消费者接口，不执行未知 ownership 写入。"""

from __future__ import annotations

import ast
import json
from pathlib import Path
import sys


TOOLS = Path("/opt/parallellines-tools/ops")
MODULES = (
    "tls.py", "managed_config.py", "release_contract.py", "main_web.py",
    "deploy.py", "rollback.py", "health.py",
)
SOURCE_LIMIT = 256 * 1024
FUNCTION_LIMIT = 128


class OperationError(Exception):
    """仅携带稳定错误标识；不输出配置、源码正文、默认参数值或异常上下文。"""


def owned_source(name: str) -> Path:
    """限定已经盘点的 tools 公开模块；拒绝符号链接、特殊文件和任意路径输入。"""
    if name not in MODULES:
        raise OperationError("module_not_allowed")
    path = TOOLS / name
    for part in (TOOLS, TOOLS.parent, path):
        if part.is_symlink():
            raise OperationError("consumer_module_symlink")
    if not path.is_file() or path.stat().st_size > SOURCE_LIMIT:
        raise OperationError("consumer_module_missing_or_large:" + name)
    return path


def reference(node: ast.AST) -> str | None:
    """只提取调用目标的标识符，不求值属性、参数或默认值。"""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = reference(node.value)
        return prefix + "." + node.attr if prefix else None
    return None


def signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """展示参数名和参数种类；所有默认值统一隐藏，注解也不回显字符串内容。"""
    args = node.args
    positional = [*args.posonlyargs, *args.args]
    required = len(positional) - len(args.defaults)
    parts = []
    for index, argument in enumerate(positional):
        parts.append(argument.arg + ("=<default>" if index >= required else ""))
        if args.posonlyargs and index + 1 == len(args.posonlyargs):
            parts.append("/")
    if args.vararg:
        parts.append("*" + args.vararg.arg)
    elif args.kwonlyargs:
        parts.append("*")
    for argument, default in zip(args.kwonlyargs, args.kw_defaults, strict=True):
        parts.append(argument.arg + ("=<default>" if default is not None else ""))
    if args.kwarg:
        parts.append("**" + args.kwarg.arg)
    return "(" + ", ".join(parts) + ")"


def function_interface(node: ast.FunctionDef | ast.AsyncFunctionDef, *, owner: str = "") -> dict:
    """返回公开函数的签名、位置和调用名；不给出函数正文、实参或状态文件内容。"""
    calls = sorted({
        name for item in ast.walk(node) if isinstance(item, ast.Call)
        if (name := reference(item.func)) is not None
    })
    if len(calls) > FUNCTION_LIMIT:
        raise OperationError("consumer_call_inventory_limit")
    return {
        "name": owner + node.name,
        "signature": signature(node),
        "async": isinstance(node, ast.AsyncFunctionDef),
        "line": node.lineno,
        "end_line": node.end_lineno,
        "calls": calls,
    }


def module_interface(name: str) -> dict:
    """AST 解析现场文件而不 import；模块顶层写入、动态导入和默认值表达式均不会运行。"""
    path = owned_source(name)
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=name)
    except (UnicodeError, SyntaxError):
        raise OperationError("consumer_module_not_parseable:" + name) from None
    functions = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
            functions.append(function_interface(node))
        elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            for member in node.body:
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)) and not member.name.startswith("_"):
                    functions.append(function_interface(member, owner=node.name + "."))
    if len(functions) > FUNCTION_LIMIT:
        raise OperationError("consumer_interface_inventory_limit")
    return {"path": str(path), "public_functions": functions}


def describe() -> dict:
    """只读列出真实 tools 接口，供集成人员核对接续和恢复合同；不申请锁或读取凭据。"""
    return {
        "complete": True,
        "operation": "describe",
        "read_only": True,
        "transaction_ready": False,
        "modules": {name: module_interface(name) for name in MODULES},
        "known_required_interfaces": {
            "tls.py": ["tls_lock", "configuration_may_reload"],
        },
        "next_evidence": [
            "确认现有 managed_config/release 接口如何接续主配置前后像及消费者 ownership，和严格逆向恢复方法",
            "对选中的公开函数再做有范围的源码审阅；仅凭签名不得调用未知写接口",
            "随后补齐 prepare/activate/rollback；describe 不代表发布事务已可执行",
        ],
        "unknown_values": "既有回执中遮蔽的摘要保持未知，不从其他通道猜补或恢复",
    }


def main(arguments: list[str]) -> dict:
    """当前仅开放无副作用 describe；未审核的写阶段明确拒绝，不提供通用执行入口。"""
    if arguments != ["describe"]:
        raise OperationError("ownership_contract_not_reviewed:describe_required")
    return describe()


if __name__ == "__main__":
    try:
        print(json.dumps(main(sys.argv[1:]), ensure_ascii=True, sort_keys=True, indent=2))
    except Exception as error:
        print(json.dumps({
            "complete": False,
            "error": str(error) if isinstance(error, OperationError) else type(error).__name__,
        }))
        raise SystemExit(1) from None
