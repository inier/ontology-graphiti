"""L2 Construction — 图谱侧 span 级溯源 Schema（FROZEN v1）。

冻结依据
--------
ODAP 圆桌讨论结论（代码实证版）**决策一**：span 级溯源 schema 立即冻结。

代码事实（结论文档"断链清单/质量有点无链"）：
  - 图谱边/节点上此前**零溯源字段**（裸边）；
  - 字符级 ``char_span`` 全库为零；
  - ``chunk_id`` 在 normalization merge 阶段丢失（实际写入空串）；
  - ``confidence`` 从不落图。
这些属于"抽取当时没记就永远没有"的**不可回填**类别——重跑抽取 ≠ 历史结果。
schema 冻结错过窗口即永久丢数据，故本模块把图谱侧统一溯源属性键**一次定死**，
作为所有写图路径（GraphWriteStep 及后续 writer）的唯一契约来源。

⚠️ FROZEN —— 字段名/语义一经冻结不得随意增删改。
   如确需变更，必须走 ADR 评审并递增 ``SCHEMA_VERSION``，
   且**不得重命名已落图数据的键**（只能新增，旧键保留兼容）。

实现分期（见结论文档"MVP 功能范围"）
------------------------------------
本模块只负责**冻结契约 + 归一化写入**；字段是否被上游真正填充随分期推进：
  - P1（可回填、撑 Demo）：``source_doc_ids`` / ``chunk_id`` / ``confidence``
  - P2（span 级字符抽取，PoC 验付费后投）：``char_span`` / ``evidence_text``

写入语义（与 Neo4j 存储层 ``_sanitize_neo4j_properties`` 对齐）
------------------------------------------------------------
Neo4j 无法保存 ``None``、空 list、空占位；``_sanitize_neo4j_properties`` 会丢弃
``None`` 与空 list，dict 会被扁平化为 ``key_subk``。因此本模块遵循
**"有真值才写、绝不写空占位/猜测默认值"**（呼应 AGENTS.md 规则 14：禁止未经确认的
兜底/猜测性反推）。所谓"字段占位/预留"由两点保证：
  1. 键名与语义在本模块冻结（契约层预留，写图路径统一引用）；
  2. 每个写入的节点/边都盖上 ``prov_schema_version`` 版本戳，
     用以区分"冻结 schema 时代"的数据与历史裸边，便于后续回填与审计。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# ── 冻结版本戳 ────────────────────────────────────────────────────────
SCHEMA_VERSION = "prov-span-v1"

# 落在每个节点/边上的版本戳属性键（标识该数据由哪一代溯源 schema 写入）
FIELD_SCHEMA_VERSION = "prov_schema_version"

# ── 冻结字段键（全部 snake_case ASCII，满足 Neo4j property key 校验） ──
FIELD_SOURCE_DOC_IDS = "source_doc_ids"   # List[str]：来源文档 ID 集合（边级可事后 join 回填）
FIELD_CHUNK_ID = "chunk_id"               # str：抽取所在 chunk 标识（merge 前须保留）
FIELD_CHAR_SPAN = "char_span"             # str："start:end" 字符级偏移（P2 填充）
FIELD_CONFIDENCE = "confidence"           # float：0-1 抽取置信度（禁硬编码，无真值则不写）
FIELD_EVIDENCE_TEXT = "evidence_text"     # str：证据原文片段（P2 填充）

# 冻结字段的规范顺序（供测试/文档/迁移脚本引用）
PROVENANCE_FIELDS: Tuple[str, ...] = (
    FIELD_SOURCE_DOC_IDS,
    FIELD_CHUNK_ID,
    FIELD_CHAR_SPAN,
    FIELD_CONFIDENCE,
    FIELD_EVIDENCE_TEXT,
)

# ── 上游 record 里可能承载溯源信息的别名键（仅做"归一化读取"，不做猜测补全） ──
# 说明：这些别名来自现存 5+ 条提取路径的键名漂移（结论文档"提取路径碎片化"），
# 归一化的目的是把"已经存在的真值"收敛到冻结键，而非凭空反推缺失值。
_SOURCE_DOC_ID_ALIASES: Tuple[str, ...] = (
    "source_doc_ids", "source_doc_id", "source_document_id",
    "source_document_ids", "doc_id", "doc_ids", "document_id",
)
_CHUNK_ID_ALIASES: Tuple[str, ...] = ("chunk_id", "chunk", "segment_id", "chunk_uuid")
_CHAR_SPAN_ALIASES: Tuple[str, ...] = ("char_span", "char_offsets", "span", "offsets", "text_span")
_CONFIDENCE_ALIASES: Tuple[str, ...] = ("confidence", "score", "extraction_confidence", "extract_confidence")
_EVIDENCE_TEXT_ALIASES: Tuple[str, ...] = ("evidence_text", "evidence", "source_text", "text_snippet", "snippet")


def _first_present(record: Dict[str, Any], aliases: Tuple[str, ...]) -> Optional[Any]:
    """按别名顺序返回 record 中第一个"存在且非空"的真值；无则 None。

    仅读取显式存在的键，绝不根据命名约定反推或补造缺失值（规则 14）。
    """
    for key in aliases:
        if key in record:
            val = record.get(key)
            if val is None:
                continue
            if isinstance(val, (str, list, tuple, dict)) and len(val) == 0:
                continue
            return val
    return None


def _as_doc_id_list(value: Any) -> List[str]:
    """把单值/列表统一归一为去重后的 str 列表（保序）。"""
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        items = list(value)
    else:
        items = [value]
    out: List[str] = []
    seen = set()
    for it in items:
        if it is None:
            continue
        s = it if isinstance(it, str) else str(it)
        s = s.strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def _as_confidence(value: Any) -> Optional[float]:
    """把置信度归一为 0-1 float；非法/越界返回 None（不写，绝不硬编码默认）。"""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN
        return None
    if f < 0.0 or f > 1.0:
        return None
    return f


def _as_char_span(value: Any) -> Optional[str]:
    """把字符偏移归一为 "start:end" 字符串；无法解析返回 None（不写占位）。"""
    if value is None:
        return None
    if isinstance(value, str):
        s = value.strip()
        return s or None
    if isinstance(value, (list, tuple)) and len(value) == 2:
        try:
            return f"{int(value[0])}:{int(value[1])}"
        except (TypeError, ValueError):
            return None
    if isinstance(value, dict):
        start = value.get("start", value.get("begin"))
        end = value.get("end", value.get("stop"))
        if start is not None and end is not None:
            try:
                return f"{int(start)}:{int(end)}"
            except (TypeError, ValueError):
                return None
    return None


def _candidate_sources(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    """收集所有可能承载溯源信息的 dict：record 顶层 + record['properties']。

    上游 5+ 提取路径把溯源信息放在不同层级，这里统一扫描（顶层优先）。
    """
    sources: List[Dict[str, Any]] = []
    if isinstance(record, dict):
        sources.append(record)
        props = record.get("properties")
        if isinstance(props, dict):
            sources.append(props)
    return sources


def build_provenance_props(record: Dict[str, Any]) -> Dict[str, Any]:
    """从一个 entity/relation dict 归一化出**冻结键**的溯源属性块。

    返回的 dict 只包含"有真值"的冻结字段（空值/None/空 list 一律不写，
    与 Neo4j sanitize 语义一致，且遵守规则 14 不猜测补全）。

    始终包含版本戳 ``prov_schema_version=SCHEMA_VERSION``——这是本 schema
    冻结时代数据的可观测标记，用于区分历史裸边。

    Args:
        record: 上游 entity/relation dict（可能带 properties 子字典）

    Returns:
        Neo4j 安全的溯源属性字典（可直接 merge 进 add_entity/add_relationship 的 properties）
    """
    result: Dict[str, Any] = {FIELD_SCHEMA_VERSION: SCHEMA_VERSION}
    if not isinstance(record, dict):
        return result

    sources = _candidate_sources(record)
    if not sources:
        return result

    # source_doc_ids：跨来源合并去重（顶层 + properties 里出现的都算）
    doc_ids: List[str] = []
    for src in sources:
        doc_ids.extend(_as_doc_id_list(_first_present(src, _SOURCE_DOC_ID_ALIASES)))
    doc_ids = _as_doc_id_list(doc_ids)  # 再去重一次
    if doc_ids:
        result[FIELD_SOURCE_DOC_IDS] = doc_ids

    # 其余标量字段：顶层优先，取第一个真值
    chunk_id = None
    char_span = None
    confidence = None
    evidence_text = None
    for src in sources:
        if chunk_id is None:
            v = _first_present(src, _CHUNK_ID_ALIASES)
            chunk_id = v.strip() if isinstance(v, str) else (str(v) if v is not None else None)
        if char_span is None:
            char_span = _as_char_span(_first_present(src, _CHAR_SPAN_ALIASES))
        if confidence is None:
            confidence = _as_confidence(_first_present(src, _CONFIDENCE_ALIASES))
        if evidence_text is None:
            v = _first_present(src, _EVIDENCE_TEXT_ALIASES)
            evidence_text = v.strip() if isinstance(v, str) else (str(v) if v is not None else None)

    if chunk_id:
        result[FIELD_CHUNK_ID] = chunk_id
    if char_span:
        result[FIELD_CHAR_SPAN] = char_span
    if confidence is not None:
        result[FIELD_CONFIDENCE] = confidence
    if evidence_text:
        result[FIELD_EVIDENCE_TEXT] = evidence_text

    return result


def merge_provenance(primary: Dict[str, Any], other: Dict[str, Any]) -> Dict[str, Any]:
    """合并两个 record 的溯源信息（用于 normalization merge，防止 chunk_id 丢失）。

    结论文档指出 chunk_id 在同名实体 merge 阶段丢失。本函数在合并同名实体时
    保留溯源真值：source_doc_ids 求并集，其余标量取 primary 优先、缺失回退 other。

    返回一个可直接写回 primary['properties'] 的溯源属性块（含版本戳）。
    """
    merged_doc_ids: List[str] = []
    for rec in (primary, other):
        for src in _candidate_sources(rec if isinstance(rec, dict) else {}):
            merged_doc_ids.extend(_as_doc_id_list(_first_present(src, _SOURCE_DOC_ID_ALIASES)))
    merged_doc_ids = _as_doc_id_list(merged_doc_ids)

    base = build_provenance_props(primary if isinstance(primary, dict) else {})
    fill = build_provenance_props(other if isinstance(other, dict) else {})

    out: Dict[str, Any] = {FIELD_SCHEMA_VERSION: SCHEMA_VERSION}
    if merged_doc_ids:
        out[FIELD_SOURCE_DOC_IDS] = merged_doc_ids
    for key in (FIELD_CHUNK_ID, FIELD_CHAR_SPAN, FIELD_CONFIDENCE, FIELD_EVIDENCE_TEXT):
        val = base.get(key, fill.get(key))
        if val is not None and val != [] and val != "":
            out[key] = val
    return out
