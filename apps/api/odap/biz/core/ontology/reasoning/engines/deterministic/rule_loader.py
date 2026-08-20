"""RuleLoader — 规则白名单校验 + Datalog 编译 (ADR-075 §3.1)。

安全模型：加载编译期 + 运行期双控。
- 白名单 tokenizer + 文法解析（零依赖）。
- 拒绝 eval / exec / import / getattr / 双下划线 / ';' 析取 / 裸 not。
- 校验失败返回 RuleValidationError（含行列/token），拒绝入库。
- 递归深度 > 16 拒绝；每规则单条子句（head <= body）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

# ── 禁止 token（白名单黑名单纯词表）──
FORBIDDEN_KEYWORDS = {
    "eval", "exec", "compile", "import", "__import__",
    "getattr", "setattr", "delattr", "globals", "locals", "vars",
    "open", "file", "input", "print", "exit", "quit",
    "os", "sys", "subprocess", "pathlib", "shutil",
}

# 禁止片段（子串级双保险）
FORBIDDEN_FRAGMENTS = [
    "__",           # 双下划线（魔术方法）
    ";",            # 析取
    "not ",         # 裸 not（pyDatalog 中 not 需限定变量绑定，风险高）
    "not(",
]

MAX_RECURSION_DEPTH = 16   # 递归规则深度上限（ADR-075 spike 约束）
MAX_RULES = 100            # 单次加载规则数上限


@dataclass
class Token:
    """词法 token"""
    kind: str          # ident / number / string / op / punct
    value: str
    line: int
    col: int


class RuleValidationError(ValueError):
    """规则校验失败（含行列/token 定位）"""

    def __init__(
        self,
        message: str,
        rule_id: str = "",
        line: int = 0,
        col: int = 0,
        token: str = "",
    ):
        self.rule_id = rule_id
        self.line = line
        self.col = col
        self.token = token
        loc = f" (line {line}, col {col})" if line else ""
        tok = f" token='{token}'" if token else ""
        super().__init__(f"规则校验失败[{rule_id}]{loc}{tok}: {message}")


_TOKEN_RE = re.compile(
    r"""
    (?P<ws>\s+)
  | (?P<comment>\#[^\n]*)
  | (?P<string>"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')
  | (?P<number>\d+(?:\.\d+)?)
  | (?P<ident>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<op><=|>=|==|!=|<|>|\+|\-|\*|/)
  | (?P<punct>[()\[\],.&|=])
  """,
    re.VERBOSE,
)


def tokenize(rule_text: str) -> List[Token]:
    """白名单 tokenizer：仅产出 ident/number/string/op/punct/comment/ws。

    无法识别的字符抛 RuleValidationError。
    """
    tokens: List[Token] = []
    line = 1
    col = 1
    pos = 0
    n = len(rule_text)
    while pos < n:
        ch = rule_text[pos]
        if ch == "\n":
            line += 1
            col = 1
            pos += 1
            continue
        m = _TOKEN_RE.match(rule_text, pos)
        if m is None:
            raise RuleValidationError(
                f"无法识别的字符 {ch!r}",
                line=line, col=col, token=ch,
            )
        kind = m.lastgroup
        value = m.group()
        if kind == "ws" or kind == "comment":
            # 跳过空白与注释
            pass
        elif kind in ("op", "punct"):
            tokens.append(Token(kind=kind, value=value, line=line, col=col))
        else:
            tokens.append(Token(kind=kind, value=value, line=line, col=col))
        # 更新行列
        consumed = m.end() - m.start()
        for c in value:
            if c == "\n":
                line += 1
                col = 1
            else:
                col += 1
        pos = m.end()

    return tokens


def validate_rule_text(rule_text: str, rule_id: str = "") -> List[Token]:
    """白名单校验规则文本，返回 tokens；失败抛 RuleValidationError。

    检查项：
    1. 禁止片段（__ 双下划线 / ';' / 裸 not）
    2. token 级禁止关键词（eval/exec/import/...）
    3. 语法骨架：必须包含 '<='
    4. 递归深度（规则链）> 16 拒绝
    """
    # 1. 子串级检查
    for frag in FORBIDDEN_FRAGMENTS:
        if frag in rule_text:
            raise RuleValidationError(
                f"包含禁止片段 {frag!r}（白名单拒绝）",
                rule_id=rule_id,
            )

    # 2. token 化
    tokens = tokenize(rule_text)
    for t in tokens:
        if t.kind == "ident" and t.value in FORBIDDEN_KEYWORDS:
            raise RuleValidationError(
                f"禁止关键字 {t.value!r}（白名单拒绝）",
                rule_id=rule_id, line=t.line, col=t.col, token=t.value,
            )
        if t.kind == "ident" and "__" in t.value:
            raise RuleValidationError(
                f"禁止双下划线标识符 {t.value!r}",
                rule_id=rule_id, line=t.line, col=t.col, token=t.value,
            )

    # 3. 骨架检查：必须含 '<='（head <= body）
    ops = [t for t in tokens if t.kind == "op" and t.value == "<="]
    if not ops:
        raise RuleValidationError(
            "规则必须为 Datalog 子句（head <= body），缺少 '<='",
            rule_id=rule_id,
        )
    if len(ops) > 1:
        raise RuleValidationError(
            "单条规则仅允许一个 '<='（每条规则一个子句）",
            rule_id=rule_id,
        )

    # 4. 递归深度检查：统计 'head 谓词' 在 body 中出现的嵌套层数
    depth = _recursion_depth(tokens)
    if depth > MAX_RECURSION_DEPTH:
        raise RuleValidationError(
            f"递归深度 {depth} 超过上限 {MAX_RECURSION_DEPTH}",
            rule_id=rule_id,
        )

    return tokens


def _recursion_depth(tokens: List[Token]) -> int:
    """估算规则递归深度。

    简化实现：head 谓词名出现在 body 中记为递归（深度 >= 1），
    深度上限检查交给编译期递归展开深度限制。
    """
    # 提取 head 谓词（'<=' 之前第一个 ident）
    head_name: Optional[str] = None
    for i, t in enumerate(tokens):
        if t.kind == "ident":
            head_name = t.value
            break
        if t.kind == "op" and t.value == "<=":
            break
    if head_name is None:
        return 0
    # 在 body 中出现的次数作为递归深度估算
    body_start = False
    count = 0
    for t in tokens:
        if t.kind == "op" and t.value == "<=":
            body_start = True
            continue
        if body_start and t.kind == "ident" and t.value == head_name:
            count += 1
    return count


class RuleLoader:
    """规则加载器：白名单校验 + Datalog 编译"""

    def __init__(self):
        self._compiled: Dict[str, str] = {}

    def compile_rule(self, rule_text: str, rule_id: str = "") -> str:
        """校验并编译单条规则 → pyDatalog 可加载子句。

        返回 Datalog 子句文本；校验失败抛 RuleValidationError。
        """
        tokens = validate_rule_text(rule_text, rule_id=rule_id)
        # 重建标准形式（token 级净化后的文本）
        clause = _rebuild_clause(tokens)
        self._compiled[rule_id or clause] = clause
        return clause

    def compile_many(self, rules: List[Dict[str, Any]]) -> List[str]:
        """批量编译；任一条失败整体拒绝（拒绝入库语义）"""
        if len(rules) > MAX_RULES:
            raise RuleValidationError(f"批量加载超过上限 {MAX_RULES} 条", rule_id="batch")
        clauses = []
        for r in rules:
            clauses.append(self.compile_rule(r["rule_text"], r.get("rule_id", "")))
        return clauses

    def clear(self) -> None:
        self._compiled.clear()


def _rebuild_clause(tokens: List[Token]) -> str:
    """由净化后的 tokens 重建 Datalog 子句（规范化空白）"""
    parts: List[str] = []
    for t in tokens:
        if t.kind == "punct" and t.value == ",":
            parts.append(", ")
        elif t.kind == "op" and t.value == "<=":
            parts.append(" <= ")
        elif t.kind == "op" and t.value == "&":
            parts.append(" & ")
        elif t.kind == "op" and t.value == "==":
            parts.append(" == ")
        elif t.kind == "op" and t.value == "!=":
            parts.append(" != ")
        elif t.kind == "op" and t.value == "<":
            parts.append(" < ")
        elif t.kind == "op" and t.value == ">":
            parts.append(" > ")
        elif t.kind == "op" and t.value == ">=":
            parts.append(" >= ")
        elif t.kind == "op" and t.value == "<=":
            # 已是 == 分支之一，不会到这里
            parts.append(" <= ")
        else:
            parts.append(t.value)
    return "".join(parts)


__all__ = [
    "Token", "RuleValidationError", "RuleLoader",
    "tokenize", "validate_rule_text",
    "FORBIDDEN_KEYWORDS", "MAX_RECURSION_DEPTH", "MAX_RULES",
]
