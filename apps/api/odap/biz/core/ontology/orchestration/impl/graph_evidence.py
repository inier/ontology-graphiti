"""graph_edge 证据校验器（AC-37 补齐）。

支持的 ref 形态（`retrieval_executor` 与编排层真实产出）：

    edge:<src>-><dst>               边存在性（任意关系类型）
    edge:<src>-[<REL_TYPE>]-><dst>  指定关系类型的边存在性
    <node_id>                       裸节点标识（检索行只给 entity_id / id 时按节点校验）

判定一律查 Neo4j，schema 以 `infra/graph` 的真实写入为准：
节点为 `(:Entity {id})`，关系类型写入前 `upper().replace(' ', '_')`。

不可用语义（绝不假通过）：驱动未安装 / 密码未配置 / 连接失败 / 查询异常，
一律返回 `(False, <可读原因>)`，原因前缀 `GRAPH_UNAVAILABLE` 或 `GRAPH_QUERY_FAILED`。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

_EDGE_REF = re.compile(r"^edge:(?P<src>[^>\[]+?)(?:-\[(?P<rel>[^\]]+)\])?->(?P<dst>.+)$")
_NODE_PREFIXES = ("node:", "entity:", "graph:")
_NODE_CYPHER = "MATCH (n:Entity {id: $id}) RETURN 1 LIMIT 1"
_EDGE_CYPHER = (
    "MATCH (:Entity {id: $sid})-[r]->(:Entity {id: $tid}) "
    "WHERE ($rel IS NULL OR type(r) = $rel) RETURN 1 LIMIT 1"
)


class GraphUnavailableError(RuntimeError):
    """图后端不可用（驱动缺失 / 凭据缺失 / 连接失败）。"""


@dataclass(frozen=True)
class GraphRef:
    """解析后的图证据引用。"""

    kind: str  # "edge" | "node"
    source: str = ""
    relation: Optional[str] = None
    target: str = ""


def parse_graph_ref(ref: str) -> Optional[GraphRef]:
    """解析证据 ref；形态非法返回 None（调用方负责给出违约原因）。"""
    value = (ref or "").strip()
    if not value:
        return None
    matched = _EDGE_REF.match(value)
    if matched:
        source = matched.group("src").strip()
        target = matched.group("dst").strip()
        raw_relation = (matched.group("rel") or "").strip().upper().replace(" ", "_")
        relation = raw_relation or None
        if not source or not target:
            return None
        return GraphRef(kind="edge", source=source, relation=relation, target=target)
    if value.startswith("edge:"):
        return None  # 声明是边但缺端点，属拼写错误而非节点
    node_id = value
    for prefix in _NODE_PREFIXES:
        if node_id.lower().startswith(prefix):
            node_id = node_id[len(prefix):]
            break
    node_id = node_id.strip()
    return GraphRef(kind="node", source=node_id) if node_id else None


class Neo4jGraphReader:
    """Neo4j 存在性读取器（惰性连接，一次会话内复用驱动）。"""

    def __init__(self, uri: str = "", user: str = "", password: str = "",
                 driver=None) -> None:
        self._uri = uri
        self._user = user
        self._password = password
        self._driver = driver

    def _session(self):
        if self._driver is None:
            self._driver = self._build_driver()
        return self._driver.session()

    def _build_driver(self):
        if not self._password:
            raise GraphUnavailableError("NEO4J_PASSWORD 未配置，无法校验图证据")
        try:
            from neo4j import GraphDatabase
        except ImportError as exc:  # pragma: no cover - 依赖已在 pyproject 声明
            raise GraphUnavailableError(f"neo4j 驱动不可用: {exc}") from exc
        from odap.infra.security import security_config

        uri = self._uri or getattr(security_config, "NEO4J_URI", "")
        user = self._user or getattr(security_config, "NEO4J_USER", "neo4j")
        if not uri:
            raise GraphUnavailableError("NEO4J_URI 未配置，无法校验图证据")
        try:
            driver = GraphDatabase.driver(
                uri, auth=(user, self._password), connection_timeout=5,
            )
            driver.verify_connectivity()
        except Exception as exc:  # noqa: BLE001 - 连接失败必须转成显式不可用
            raise GraphUnavailableError(f"Neo4j 连接失败: {type(exc).__name__}: {exc}") from exc
        return driver

    def node_exists(self, node_id: str) -> bool:
        return self._probe(_NODE_CYPHER, {"id": node_id})

    def edge_exists(self, source: str, target: str, relation: Optional[str]) -> bool:
        return self._probe(_EDGE_CYPHER, {"sid": source, "tid": target, "rel": relation})

    def _probe(self, cypher: str, params: dict) -> bool:
        try:
            with self._session() as session:
                return session.run(cypher, **params).single() is not None
        except GraphUnavailableError:
            raise
        except Exception as exc:  # noqa: BLE001 - 查询异常不吞成「不存在」
            raise GraphUnavailableError(f"图查询失败: {type(exc).__name__}: {exc}") from exc

    def close(self) -> None:
        if self._driver is not None:
            try:
                self._driver.close()
            except Exception as exc:  # noqa: BLE001 - 关闭失败不影响校验结论
                logger.warning("Neo4j 驱动关闭失败: %s", exc)
            self._driver = None


_DEFAULT_READER: Optional[Neo4jGraphReader] = None


def default_graph_reader() -> Neo4jGraphReader:
    """进程级默认读取器（避免每次校验重连）。"""
    global _DEFAULT_READER
    if _DEFAULT_READER is None:
        from odap.infra.security import security_config

        _DEFAULT_READER = Neo4jGraphReader(
            uri=getattr(security_config, "NEO4J_URI", ""),
            user=getattr(security_config, "NEO4J_USER", "neo4j"),
            password=security_config.get_neo4j_password() or "",
        )
    return _DEFAULT_READER


def reset_default_graph_reader() -> None:
    """测试与热重载用：丢弃缓存的默认读取器。"""
    global _DEFAULT_READER
    if _DEFAULT_READER is not None:
        _DEFAULT_READER.close()
    _DEFAULT_READER = None


def verify_graph_ref(ref: str, reader=None) -> Tuple[bool, str]:
    """校验图证据 ref 是否在图中真实存在。"""
    spec = parse_graph_ref(ref)
    if spec is None:
        return False, f"graph_edge ref 形态非法：{ref!r}（应形如 edge:<src>-><dst>）"
    try:
        backend = reader or default_graph_reader()
    except Exception as exc:  # noqa: BLE001 - 取不到读取器即「图后端不可用」
        return False, f"GRAPH_UNAVAILABLE: {type(exc).__name__}: {exc}"
    try:
        if spec.kind == "node":
            if backend.node_exists(spec.source):
                return True, ""
            return False, f"图中不存在节点：{spec.source}"
        if backend.edge_exists(spec.source, spec.target, spec.relation):
            return True, ""
        label = f"（关系类型 {spec.relation}）" if spec.relation else ""
        return False, f"图中不存在边{label}：{spec.source} -> {spec.target}"
    except GraphUnavailableError as exc:
        return False, f"GRAPH_UNAVAILABLE: {exc}"
    except Exception as exc:  # noqa: BLE001 - 任何异常都不得变成假通过
        logger.warning("graph evidence verify error: ref=%s error=%s", ref, exc)
        return False, f"GRAPH_QUERY_FAILED: {type(exc).__name__}: {exc}"


__all__ = [
    "GraphRef",
    "GraphUnavailableError",
    "Neo4jGraphReader",
    "default_graph_reader",
    "parse_graph_ref",
    "reset_default_graph_reader",
    "verify_graph_ref",
]
