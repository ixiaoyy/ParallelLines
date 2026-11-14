"""统一登录 Nginx 发布边界：先只读确认现场消费者接口，不执行未知 ownership 写入。"""

from __future__ import annotations

import ast
import json
from pathlib import Path
import re
import sys


TOOLS = Path("/opt/parallellines-tools/ops")
MODULES = (
    "tls.py", "managed_config.py", "release_contract.py", "main_web.py",
    "deploy.py", "rollback.py", "health.py",
)
SOURCE_LIMIT = 256 * 1024
FUNCTION_LIMIT = 128
SOURCE_CONTRACTS = {
    "tls.py": (
        "clean_main_configuration", "main_web_redirect_record", "configuration_may_reload",
        "context_preflight", "tls_lock",
    ),
    "managed_config.py": ("span", "split", "replace", "replace_tool_entries", "owned_delta_allowed"),
    "main_web.py": ("modules", "anchor", "guard", "install_sources", "restore", "deploy"),
    "deploy.py": (
        "gateway_binding", "gateway_guard", "known_configuration", "inplace_configuration",
        "assert_attempt_owner", "restore_state",
    ),
}
DIGEST_LITERAL = re.compile(r"(?<![A-Za-z0-9])[0-9a-fA-F]{32,128}(?![A-Za-z0-9])")
SENSITIVE_NAME = re.compile(
    r"secret|password|(?:access|refresh|id)[_-]?token|authorization|credential|private[_-]?key",
    re.IGNORECASE,
)


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


class SourceRedactor(ast.NodeTransformer):
    """仅为语义审阅生成脱敏 AST 文本；不执行源码，也不用源码恢复此前遮蔽摘要。"""

    def visit_Constant(self, node: ast.Constant):
        if not isinstance(node.value, str):
            return node
        value = node.value
        if "\n" in value or len(value) > 1024:
            value = "<multiline-or-long-literal-omitted>"
        elif "-----BEGIN" in value or "Bearer " in value:
            value = "<sensitive-literal-omitted>"
        else:
            value = DIGEST_LITERAL.sub("<digest-redacted>", value)
        return ast.copy_location(ast.Constant(value=value), node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.generic_visit(node)
        # 默认参数可能含凭据或配置内容；签名已由 describe 给出，仅保留有无默认值。
        node.args.defaults = [ast.Constant(value="<default>") for _ in node.args.defaults]
        node.args.kw_defaults = [
            ast.Constant(value="<default>") if value is not None else None
            for value in node.args.kw_defaults
        ]
        for argument in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]:
            argument.annotation = None
        node.returns = None
        return node

    def visit_Assign(self, node: ast.Assign):
        self.generic_visit(node)
        names = [part.id for target in node.targets for part in ast.walk(target) if isinstance(part, ast.Name)]
        if any(SENSITIVE_NAME.search(name) for name in names) and isinstance(node.value, ast.Constant):
            node.value = ast.Constant(value="<sensitive-assignment-omitted>")
        return node

    def visit_Dict(self, node: ast.Dict):
        self.generic_visit(node)
        for index, key in enumerate(node.keys):
            if isinstance(key, ast.Constant) and isinstance(key.value, str) and SENSITIVE_NAME.search(key.value):
                node.values[index] = ast.Constant(value="<sensitive-dict-value-omitted>")
        return node


def public_constant(value: object) -> object:
    """只公开确切函数引用的固定部署路径、工具路径与 marker；不输出摘要或任意配置字面量。"""
    if isinstance(value, str):
        if "\n" not in value and len(value) <= 512 and not DIGEST_LITERAL.search(value):
            if value.startswith(("/opt/parallellines", "/etc/nginx", "/etc/cron.d/parallellines", "/tools")):
                return value
            if value.startswith(("# BEGIN parallellines-tools", "# END parallellines-tools")):
                return value
            if re.fullmatch(r"https://(?:tools\.)?pingxingxian[.]space/?", value):
                return value
        return "<nonpublic-literal-omitted>"
    if isinstance(value, (tuple, list)) and len(value) <= 16:
        return [public_constant(item) for item in value]
    return "<nonpublic-literal-omitted>"


def describe_source() -> dict:
    """仅读固定模块的固定公开函数 AST 段；所有输出仅供审阅，禁止作为运行源码复用。"""
    modules = {}
    for module, requested in SOURCE_CONTRACTS.items():
        path = owned_source(module)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=module)
        except (UnicodeError, SyntaxError):
            raise OperationError("consumer_module_not_parseable:" + module) from None
        available = {
            node.name: node for node in tree.body
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
        }
        if any(name not in available for name in requested):
            raise OperationError("consumer_public_contract_changed:" + module)
        referenced = {
            node.id for name in requested for node in ast.walk(available[name])
            if isinstance(node, ast.Name) and node.id.isupper()
        }
        constants = {}
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in referenced:
                    try:
                        literal = ast.literal_eval(node.value)
                    except (ValueError, TypeError):
                        constants[target.id] = "<nonliteral-value-omitted>"
                    else:
                        constants[target.id] = public_constant(literal)
        sources = {}
        for name in requested:
            redacted = SourceRedactor().visit(available[name])
            ast.fix_missing_locations(redacted)
            sources[name] = ast.unparse(redacted)
        modules[module] = {
            "path": str(path), "referenced_public_constants": constants, "public_functions": sources,
        }
    result = {
        "complete": True, "operation": "describe-source", "read_only": True,
        "transaction_ready": False, "redacted_source_not_executable": True, "modules": modules,
        "unknown_values": "默认值、摘要及敏感字面量不输出；此前遮蔽内容保持未知",
    }
    if len(json.dumps(result, ensure_ascii=True).encode()) > 192 * 1024:
        raise OperationError("consumer_source_output_limit")
    return result


def main(arguments: list[str]) -> dict:
    """仅开放两项固定只读审阅；未审核的写阶段明确拒绝，不提供通用执行入口。"""
    if arguments == ["describe"]:
        return describe()
    if arguments == ["describe-source"]:
        return describe_source()
    raise OperationError("ownership_contract_not_reviewed:describe_required")


if __name__ == "__main__":
    try:
        print(json.dumps(main(sys.argv[1:]), ensure_ascii=True, sort_keys=True, indent=2))
    except Exception as error:
        print(json.dumps({
            "complete": False,
            "error": str(error) if isinstance(error, OperationError) else type(error).__name__,
        }))
        raise SystemExit(1) from None
