"""契约对账的扫描器（前端 / OpenAPI 契约 / 后端实际路由）—— `check_api_contract.py` 的实现层。

拆分成独立模块的原因：三套扫描器（正则/AST/Pydantic 路由表）与「对账口径 + 报告输出」
变化原因不同；同文件超过单文件行数上限。

所有扫描只读不写，不做任何代码改动。
"""

from __future__ import annotations

import ast
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB_SRC = ROOT / "apps" / "web" / "src"
API_DIR = ROOT / "apps" / "api"
SPEC = ROOT / "docs" / "02-architecture" / "openapi-v2.yaml"

_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}
_TEMPLATE_EXPR = re.compile(r"\$\{[^}]*\}")


def _template_sub(match: re.Match[str]) -> str:
    """`${encodeURIComponent(entryId)}` → `{entryId}`：保留变量名，便于跨端比对。"""
    identifiers = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", match.group(0)[2:-1])
    return "{%s}" % (identifiers[-1] if identifiers else "param")


def _subst(text: str) -> str:
    return _TEMPLATE_EXPR.sub(_template_sub, text)


def _param_token(name: str) -> str:
    """参数名归一：entryId / entry_id / ENTRY_ID 视为同一语义槽位。"""
    return re.sub(r"[^a-z0-9]", "", name.lower())


@dataclass
class Endpoint:
    """一条对账记录（按 normalized path 聚合三方信息）。"""

    path: str  # 规范形态，如 /api/v1/wiki/entries/{param}
    raw: dict[str, str] = field(default_factory=dict)  # 来源 -> 原始写法
    params: dict[str, tuple[str, ...]] = field(default_factory=dict)  # 来源 -> 路径参数名
    methods: dict[str, set[str]] = field(default_factory=dict)  # 来源 -> 方法集合


def normalize(raw: str) -> tuple[str, tuple[str, ...]]:
    """把任意写法的路径归一为 (占位符折叠形态, 参数名元组)。"""
    path = raw.strip().split("?", 1)[0].split("#", 1)[0]
    names: list[str] = []

    def _braced(match: re.Match[str]) -> str:
        names.append(match.group(1).strip())
        return "{}"

    path = re.sub(r"\{([^{}]*)\}", _braced, path)
    path = re.sub(r":([A-Za-z_][A-Za-z0-9_]*)", _braced, path)
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return path, tuple(names)


def _record(table: dict[str, Endpoint], source: str, raw: str, method: str | None,
            params: tuple[str, ...]) -> None:
    path, names = normalize(raw)
    if not path.startswith("/"):
        return
    entry = table.setdefault(path, Endpoint(path=path))
    entry.raw.setdefault(source, raw.strip())
    entry.params[source] = names or params
    if method:
        entry.methods.setdefault(source, set()).add(method.lower())


# --------------------------------------------------------------------------- 前端

def _frontend_base(text: str) -> str | None:
    """推断该文件的 API 前缀：本地声明优先，其次从 config 导入（config 里是 env || ''）。"""
    declared = re.search(r"const\s+API_BASE\s*=\s*['\"]([^'\"]*)['\"]", text)
    if declared:
        return declared.group(1)
    if re.search(r"import\s*\{[^}]*\bAPI_BASE\b[^}]*\}\s*from", text):
        return ""
    return None


def scan_frontend(src: Path) -> dict[str, Endpoint]:
    table: dict[str, Endpoint] = {}
    files = sorted(list(src.rglob("*.ts")) + list(src.rglob("*.tsx")))
    for file in files:
        if ".test." in file.name or ".spec." in file.name:
            continue
        text = file.read_text(encoding="utf-8", errors="replace")
        base = _frontend_base(text)

        # 模式 A：`${API_BASE}/xxx/${id}` 模板串（历史 shared/services/api.ts）
        for match in re.finditer(r"`([^`]*)`", text, re.S):
            body = match.group(1)
            if "${API_BASE}" in body and base is not None:
                _record(table, "frontend", _subst(body.replace("${API_BASE}", base)),
                        None, ())

        # 模式 B：文件自带完整 base（如 /api/v1）时，文件内以 / 开头的相对端点常量
        if base and base.startswith("/api"):
            for match in re.finditer(r"['\"`](/[^'\"`\s]*)['\"`]", text):
                literal = match.group(1)
                if literal == base or literal.startswith(base + "/"):
                    continue
                _record(table, "frontend", base + _subst(literal), None, ())

        # 模式 C：任意字符串里出现的 /api/vN/... 绝对写法（含 mock 文案披露的端点）
        for match in re.finditer(r"/api/v[0-9]+/[A-Za-z0-9_\-./{}]*", text):
            _record(table, "frontend", _subst(match.group(0)), None, ())
    return table


# --------------------------------------------------------------------------- 契约

def scan_spec(spec_path: Path) -> dict[str, Endpoint]:
    import yaml

    document = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    servers = document.get("servers") or [{"url": ""}]
    prefix = servers[0].get("url", "").rstrip("/")
    table: dict[str, Endpoint] = {}
    for raw_path, item in (document.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        methods = [k for k in item if k.lower() in _METHODS]
        for method in methods:
            _record(table, "spec", prefix + raw_path, method, ())
            entry = table.get(normalize(prefix + raw_path)[0])
            if entry is not None:
                entry.raw["spec"] = prefix + raw_path
    return table


# --------------------------------------------------------------------------- 后端

def scan_backend_live() -> dict[str, Endpoint]:
    """读真实 FastAPI 路由表。JWT_SECRET 缺失时注入仅在本次进程内生效的审计占位值。

    该占位值不参与任何鉴权（本脚本不发请求、不起服务），仅用于让配置校验通过以导出路由表。
    """
    for path in (str(API_DIR), str(ROOT)):
        if path not in sys.path:
            sys.path.insert(0, path)
    os.environ.setdefault("JWT_SECRET", "contract-audit-placeholder-not-used-for-auth")
    from odap.web.app import app  # noqa: PLC0415 - 延迟导入，避免 --help 时拉起整个应用

    table: dict[str, Endpoint] = {}
    for raw_path, item in app.openapi().get("paths", {}).items():
        for method in item:
            if method.lower() in _METHODS:
                _record(table, "backend", raw_path, method, ())
    return table


def scan_backend_ast() -> dict[str, Endpoint]:
    """兜底：AST 扫描 APIRouter(prefix=...) + @router.<method>('path')。"""
    table: dict[str, Endpoint] = {}
    for file in sorted(API_DIR.rglob("*.py")):
        try:
            tree = ast.parse(file.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError as exc:
            print(f"[WARN] 跳过无法解析的文件 {file.relative_to(ROOT)}: {exc}")
            continue
        prefixes: dict[str, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                func = node.value.func
                name = getattr(func, "id", getattr(func, "attr", ""))
                if name != "APIRouter":
                    continue
                prefix = ""
                for kw in node.value.keywords:
                    if kw.arg == "prefix" and isinstance(kw.value, ast.Constant):
                        prefix = str(kw.value.value)
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        prefixes[target.id] = prefix
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call) or not decorator.args:
                    continue
                func = decorator.func
                router = getattr(func, "value", None)
                method = getattr(func, "attr", "")
                if not isinstance(router, ast.Name) or method.lower() not in _METHODS:
                    continue
                route_path = decorator.args[0]
                if not isinstance(route_path, ast.Constant):
                    continue
                prefix = prefixes.get(router.id, "")
                _record(table, "backend", prefix + str(route_path.value), method, ())
    return table


def scan_backend() -> tuple[dict[str, Endpoint], str]:
    try:
        return scan_backend_live(), "live"
    except Exception as exc:  # noqa: BLE001 - 导入失败必须降级并说清原因
        print(f"[WARN] 应用导入失败，退回 AST 路由扫描：{type(exc).__name__}: {exc}")
        table = scan_backend_ast()
        if not table:
            raise RuntimeError("AST 兜底也未扫到任何路由，对账中止") from exc
        return table, "ast"


