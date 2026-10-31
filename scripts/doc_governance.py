#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""doc_governance.py — 文档治理三合一工具（迁移 / 审计 / 索引）

为什么存在（经验沉淀）:
  ADR-097 裁定「front-matter 为文档元数据唯一真相源 + 可机械校验」，但该 ADR 接受后
  零执行：281 份 md 中仅 1 份（第三方 vendor 文件）带 front-matter。文档治理停留在
  「口头约定 + 人肉记忆」，于是历史上反复出现：
    - 权威漂移：ARCHITECTURE.md 与 ARCHITECTURE-v2.md 同时自称架构设计文档
    - 层编号冲突：08-tasks/ 与 08-evaluation/ 共用 "08" 前缀
    - 版本漂移：DOCUMENT_BASELINE_v1.0.0.md 文件名 v1.0.0 / 正文标题 v1.1.0
    - 冗余无溯源：过程报告与现行设计平铺混放，归档无证据链
  本工具把「哪份是权威、哪份已被取代、凭什么取代」变成可进 CI 的规则 R1~R13。

单一真相源设计（关键，勿破坏）:
  - **事实**（某篇文档是什么状态）只写在文档自己的 front-matter。
  - **规则**（层怎么分、状态怎么推导）写在 docs/DOC-GOVERNANCE-POLICY.yaml。
  - **索引**（docs/DOC-INDEX.md）由本工具生成，禁止手改——它是投影不是真相。
  - docs/DOC-GOVERNANCE-SEED.yaml 是一次性迁移种子，迁移后仅作审计留痕。
  三者职责不重叠，避免出现「两处都要改、改一处就漂」的第二真相源。

子命令:
  migrate [--dry-run] [--force]   为纳管 md 补齐 front-matter（幂等）
  audit   [--ci] [--verbose]      按 R1~R13 校验，FAIL 时 --ci 退出码 1
  index                           生成 docs/DOC-INDEX.md 与 09-checklists/doc-inventory.csv

用法:
  python scripts/doc_governance.py migrate --dry-run
  python scripts/doc_governance.py migrate
  python scripts/doc_governance.py audit --ci
  python scripts/doc_governance.py index
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.stderr.write("缺少 PyYAML，请执行: uv pip install pyyaml\n")
    raise

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
POLICY_PATH = DOCS / "DOC-GOVERNANCE-POLICY.yaml"
SEED_PATH = DOCS / "DOC-GOVERNANCE-SEED.yaml"
INDEX_PATH = DOCS / "DOC-INDEX.md"
INVENTORY_PATH = DOCS / "09-checklists" / "doc-inventory.csv"

TODAY = "2026-10-17"

# 纳管范围：只有 markdown 能承载 front-matter；其余为产物文件，按 policy.artifacts 登记。
GOVERNED_SUFFIXES = {".md", ".markdown"}
ARTIFACT_SUFFIXES = {".yaml", ".yml", ".json", ".csv", ".css"}

# front-matter 必需字段（ADR-097 第 2 条 + 本工具扩展 layer/concern/lifecycle）
REQUIRED_FIELDS = [
    "id", "status", "owner", "version", "layer", "concern",
    "lifecycle", "superseded_by", "supersedes", "last_verified", "citations",
]

VER_RE = re.compile(r"版\s*本[\s*:：]*v?([0-9]+(?:\.[0-9]+)*)")


@dataclass
class Finding:
    rule: str
    level: str  # error | warn
    path: str
    message: str


@dataclass
class Doc:
    path: str            # repo-relative posix
    fm: dict[str, Any]   # 有效 front-matter（缺省补空）
    has_fm: bool
    body_version: str = ""
    inbound: int = 0
    outbound: list[str] = field(default_factory=list)

    # 便捷访问
    @property
    def status(self) -> str:
        return str(self.fm.get("status", "") or "")

    @property
    def layer(self) -> str:
        return str(self.fm.get("layer", "") or "")

    @property
    def concern(self) -> str:
        return str(self.fm.get("concern", "") or "")


# ────────────────────────── 基础工具 ──────────────────────────

def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"缺少文件: {path.relative_to(ROOT).as_posix()}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"{path.name} 根节点必须是映射")
    return data


def rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def split_front_matter(text: str) -> tuple[str | None, str]:
    """返回 (front-matter 文本 或 None, 正文)。只认开头 3 行内的 --- 围栏，且围栏间必须是 k: v 形式。"""
    stripped = text.lstrip("\ufeff")
    if not stripped.startswith("---"):
        return None, text
    lines = stripped.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return None, text
    for i in range(1, min(len(lines), 60)):
        if lines[i].strip() == "---":
            block = "".join(lines[1:i])
            if not re.search(r"^\s*[\w-]+\s*:", block, re.M):
                return None, text
            return block, "".join(lines[i + 1:])
    return None, text


def slugify(s: str) -> str:
    s = s.replace("\\", "/")
    s = re.sub(r"\.(md|markdown)$", "", s, flags=re.I)
    s = re.sub(r"[^0-9A-Za-z\u4e00-\u9fa5]+", "-", s).strip("-").lower()
    return re.sub(r"-{2,}", "-", s)


def resolve_layer(path: str, layers: list[dict[str, Any]]) -> dict[str, Any] | None:
    """最长目录前缀匹配。docs 根层兜底。"""
    best, best_len = None, -1
    for layer in layers:
        d = str(layer.get("dir", "")).rstrip("/")
        if d and (path == d or path.startswith(d + "/")) and len(d) > best_len:
            best, best_len = layer, len(d)
    return best


def doc_id(path: str, layer_id: str) -> str:
    return f"odap.{layer_id.lower()}.{slugify(path.split('/', 2)[-1] if path.count('/') >= 2 else path)}"


# ────────────────────────── 判定解析 ──────────────────────────

class Seed:
    def __init__(self, policy: dict[str, Any], seed: dict[str, Any]):
        self.policy = policy
        self.layers: list[dict[str, Any]] = policy.get("layers") or []
        self.defaults: dict[str, dict[str, Any]] = policy.get("layer_defaults") or {}
        self.overrides: dict[str, dict[str, Any]] = {
            str(o["path"]): o for o in (seed.get("overrides") or []) if o.get("path")
        }
        # 前缀分组按长度降序，保证最长前缀优先
        self.groups: list[dict[str, Any]] = sorted(
            (seed.get("groups") or []), key=lambda g: len(str(g.get("match", ""))), reverse=True
        )
        self.archive_groups: dict[str, dict[str, Any]] = {}
        for ag in (policy.get("archive_groups") or []):
            self.archive_groups[str(ag["prefix"]).rstrip("/")] = ag
        self.adr_rules: dict[str, Any] = policy.get("adr_derivation") or {}
        self.adr_files: dict[str, str] = {}
        for layer in self.layers:
            pass
        for p in sorted(self._adr_paths()):
            m = re.match(r".*ADR-(\d{3})", p)
            if m:
                self.adr_files.setdefault(m.group(1), p)

    def _adr_paths(self) -> list[str]:
        glob = str(self.adr_rules.get("glob", ""))
        if not glob:
            return []
        return [rel(p) for p in sorted(ROOT.glob(glob))]

    def _archive_meta(self, path: str) -> dict[str, Any]:
        best, best_len = None, -1
        for prefix, ag in self.archive_groups.items():
            if (path == prefix or path.startswith(prefix + "/")) and len(prefix) > best_len:
                best, best_len = ag, len(prefix)
        if not best:
            return {}
        return {"reason": best.get("reason", ""), "evidence": best.get("evidence", "")}

    def _adr_status(self, path: str) -> dict[str, Any]:
        """从 ADR 的**状态段**推导状态。

        为什么必须限定段落：ADR 正文里常出现 Deprecated / 提议 / Superseded 等字样
        用于描述**别的东西**，全文扫描会误判。实测三例：
          - ADR-067 正文提到「Deprecated 重定向 __init__.py」→ 曾被误判为 superseded，
            而其真实状态是 Accepted（决策已执行完毕）。
          - ADR-085 正文提到「原提议（2026-10-04 提交）」→ 曾被误判为 proposed，
            而其真实状态是「部分落地」（提出内容已部分实现，仍在生效）。
          - ADR-077 状态段写「Superseded in part by ADR-085（提议）」→ 属**部分**取代，
            整体决策仍生效，不得标 superseded。
        """
        if not re.match(r"docs/07-adr/ADR-", path):
            return {}
        text = (ROOT / path).read_text(encoding="utf-8", errors="ignore")
        # 去掉 front-matter，只在正文里找状态段
        _, body = split_front_matter(text)
        section = self._status_section(body)
        if not section:
            return {}

        # 状态段内的引用块（> ...）是**旁注**，不是状态声明本身。ADR-067 即典型：
        # 声明行是 Accepted，旁注里提到「Deprecated 重定向 __init__.py」，若一并扫描会误判。
        # 故先判正文部分，判不出再看旁注（旁注里也可能是有效声明，如 ADR-077 的部分取代说明）。
        plain = "\n".join(l for l in section.splitlines() if not l.lstrip().startswith(">"))
        quoted = "\n".join(l for l in section.splitlines() if l.lstrip().startswith(">"))
        for part in (plain, quoted):
            verdict = self._decide_markers(part, path)
            if verdict is not None:
                return verdict
        return {}

    def _decide_markers(self, part: str, path: str) -> dict[str, Any] | None:
        """对一段文本做状态判定。返回 None 表示「这段里没有可用信号」。"""
        low = part.replace("*", "").replace("_", "")
        if not low.strip():
            return None
        rules = self.adr_rules

        # 1) 部分取代：整体决策仍有效
        for marker in rules.get("partial_superseded_markers", ["Superseded in part", "部分取代"]):
            if marker in low:
                return {"status": "active",
                        "reason": f"状态段声明部分取代（{marker}），整体决策仍生效"}

        # 2) 整体取代
        for marker in rules.get("superseded_markers", []):
            if marker in low:
                out: dict[str, Any] = {
                    "status": "superseded",
                    "reason": f"状态段自述{marker}",
                    "evidence": f"`{path}` 状态段落自述 {marker}",
                }
                m = re.search(rules.get("superseded_by_pattern", r"ADR-(\d{3})"), low)
                if m:
                    target = self.adr_files.get(m.group(1))
                    if target:
                        out["superseded_by"] = target
                return out

        # 3) 部分落地：已实现部分仍在生效
        for marker in rules.get("partial_landed_markers", ["部分落地"]):
            if marker in low:
                return {"status": "active", "reason": f"状态段声明{marker}，已在生效"}

        # 4) 提议
        for marker in rules.get("proposed_markers", []):
            if marker in low:
                return {"status": "proposed"}

        # 5) 接受 / 已采纳：ADR 层默认即 active，返回 {} 表示「已判定为 active」
        for marker in rules.get("accepted_markers", []):
            if marker in low:
                return {}
        return None

    @staticmethod
    def _status_section(body: str) -> str:
        """取状态段：优先 `## Status` / `## 状态` 标题块，退化到首 40 行内的「状态:」行。"""
        lines = body.splitlines()
        heading_re = re.compile(r"^#{2,3}\s*(Status|状态)\s*$", re.I)
        for i, line in enumerate(lines):
            if heading_re.match(line.strip()):
                buf = []
                for nxt in lines[i + 1:]:
                    if re.match(r"^#{1,3}\s+\S", nxt):
                        break
                    buf.append(nxt)
                return "\n".join(buf).strip()
        inline_re = re.compile(r"^\s*[-*>]*\s*(?:\*\*)?\s*状态\s*(?:\*\*)?\s*[:：]")
        for line in lines[:40]:
            if inline_re.match(line):
                return line.strip()
        return ""

    def resolve(self, path: str) -> dict[str, Any]:
        layer = resolve_layer(path, self.layers)
        layer_id = str(layer.get("id")) if layer else ""
        base: dict[str, Any] = {
            "layer": layer_id,
            "owner": str((layer or {}).get("owner_role", "architect")),
            "concern": str((layer or {}).get("concern", "")),
            "status": "active",
            "lifecycle": "living",
            "version": "",
            "superseded_by": "",
            "supersedes": [],
            "reason": "",
            "evidence": "",
        }
        base.update(self.defaults.get(layer_id, {}) or {})

        # 归档层成组溯源
        if base.get("status") == "archived":
            base.update(self._archive_meta(path))

        # 最长前缀分组
        for g in self.groups:
            match = str(g.get("match", "")).rstrip("/")
            if path == match or path.startswith(match + "/"):
                base.update({k: v for k, v in g.items() if k != "match"})
                break

        # ADR 推导
        base.update(self._adr_status(path))

        # 精确覆盖优先级最高
        base.update(self.overrides.get(path, {}))
        return base


# ────────────────────────── migrate ──────────────────────────

MANAGED_KEYS = ["id", "status", "owner", "version", "layer", "concern",
                "lifecycle", "superseded_by", "supersedes", "last_verified", "citations"]

# 审计/迁移内部使用、不写入 front-matter 的键
INTERNAL_KEYS = {"path", "reason", "evidence", "note", "generated_by"}


def build_fm(path: str, meta: dict[str, Any]) -> dict[str, Any]:
    fm: dict[str, Any] = {
        "id": doc_id(path, str(meta.get("layer", "l?"))),
        "status": meta.get("status", "active"),
        "owner": meta.get("owner", "architect"),
        "version": str(meta.get("version", "") or ""),
        "layer": meta.get("layer", ""),
        "concern": meta.get("concern", ""),
        "lifecycle": meta.get("lifecycle", "living"),
        "superseded_by": meta.get("superseded_by", "") or "",
        "supersedes": meta.get("supersedes", []) or [],
        "last_verified": TODAY,
        "citations": meta.get("citations", []) or [],
    }
    # reason / evidence 属于治理溯源证据，保留在 front-matter 便于机械校验 R5
    if meta.get("reason"):
        fm["governance_reason"] = str(meta["reason"])
    if meta.get("evidence"):
        fm["governance_evidence"] = str(meta["evidence"])
    return fm


def dump_fm(fm: dict[str, Any]) -> str:
    return yaml.safe_dump(fm, allow_unicode=True, sort_keys=False,
                          default_flow_style=False, width=1000)


def cmd_migrate(args: argparse.Namespace) -> int:
    policy = load_yaml(POLICY_PATH)
    seed_data = load_yaml(SEED_PATH) if SEED_PATH.exists() else {}
    seed = Seed(policy, seed_data)

    skip_paths = artifact_path_set(policy)
    created, updated, skipped = [], [], []
    for p in sorted(DOCS.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in GOVERNED_SUFFIXES:
            continue
        path = rel(p)
        if path in skip_paths:
            skipped.append(path)
            continue
        text = p.read_text(encoding="utf-8")
        existing_block, body = split_front_matter(text)
        meta = seed.resolve(path)
        new_fm = build_fm(path, meta)

        if existing_block is None:
            content = "---\n" + dump_fm(new_fm) + "---\n\n" + text.lstrip("\ufeff").lstrip("\n")
            created.append(path)
        else:
            try:
                current = yaml.safe_load(existing_block) or {}
            except yaml.YAMLError:
                current = {}
            if not isinstance(current, dict):
                current = {}
            merged = dict(current)
            changed = False
            if args.reset:
                # 重新推导覆盖全部受管字段（用于修正错误的初始迁移），保留 citations 等人工字段
                for k in MANAGED_KEYS:
                    if k == "last_verified":
                        continue
                    if merged.get(k) != new_fm[k]:
                        merged[k] = new_fm[k]
                        changed = True
                for k in ("governance_reason", "governance_evidence"):
                    if k in new_fm:
                        if merged.get(k) != new_fm[k]:
                            merged[k] = new_fm[k]
                            changed = True
                    elif k in merged:
                        merged.pop(k)
                        changed = True
            else:
                for k in MANAGED_KEYS:
                    if k not in merged or merged.get(k) in ("", None):
                        merged[k] = new_fm[k]
                        changed = True
                for k in ("governance_reason", "governance_evidence"):
                    if k in new_fm and k not in merged:
                        merged[k] = new_fm[k]
                        changed = True
            if not changed:
                skipped.append(path)
                continue
            content = "---\n" + dump_fm(merged) + "---\n\n" + body.lstrip("\n")
            updated.append(path)

        if args.dry_run:
            continue
        p.write_text(content, encoding="utf-8", newline="\n")

    verb = "将" if args.dry_run else "已"
    print(f"新增 front-matter {verb} {len(created)} 份")
    print(f"补齐字段 {verb} {len(updated)} 份")
    print(f"跳过（已完整） {len(skipped)} 份")
    if args.dry_run:
        for p in created[:10]:
            print("  +", p)
        print("  ...（--dry-run 未落盘）")
    return 0


# ────────────────────────── audit ──────────────────────────

def artifact_path_set(policy: dict[str, Any]) -> set[str]:
    """policy.artifacts 中的路径一律不参与 front-matter 治理（含生成物 .md）。"""
    return {str(a.get("path")) for a in (policy.get("artifacts") or []) if a.get("path")}


def collect_docs(policy: dict[str, Any] | None = None) -> tuple[dict[str, Doc], list[str]]:
    skip = artifact_path_set(policy) if policy else set()
    docs: dict[str, Doc] = {}
    artifacts: list[str] = []
    for p in sorted(DOCS.rglob("*")):
        if not p.is_file():
            continue
        suffix = p.suffix.lower()
        path = rel(p)
        if suffix in ARTIFACT_SUFFIXES or path in skip:
            artifacts.append(path)
            continue
        if suffix not in GOVERNED_SUFFIXES:
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        block, body = split_front_matter(text)
        fm: dict[str, Any] = {}
        if block:
            try:
                loaded = yaml.safe_load(block)
                if isinstance(loaded, dict):
                    fm = loaded
            except yaml.YAMLError:
                fm = {}
        ver = VER_RE.search(body[:1200])
        docs[path] = Doc(path=path, fm=fm, has_fm=block is not None,
                         body_version=(ver.group(1) if ver else ""))
    return docs, artifacts


LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
# 本仓文档大量使用「反引号包裹的仓库内路径」引用（如 `docs/02-architecture/ARCHITECTURE-v2.md`），
# 不识别这种写法会把 SPEC-v2 / ARCHITECTURE-v2 这类核心文档误判为孤立文档。
CODE_PATH_RE = re.compile(r"`([^`\n]*?docs/[^`\n]+?\.(?:md|yaml|yml|json|csv))`")


def build_reference_graph(docs: dict[str, Doc]) -> None:
    """从正文的 markdown 链接与反引号路径构建引用图。

    DOC-INDEX.md 是生成物，不参与构图，否则它对全部文档的列举会让「孤立文档」永远为 0。
    """
    known = set(docs)
    for path, doc in docs.items():
        if path.endswith("DOC-INDEX.md"):
            continue
        text = (ROOT / path).read_text(encoding="utf-8", errors="ignore")
        src_dir = (ROOT / path).parent
        targets = LINK_RE.findall(text) + CODE_PATH_RE.findall(text)
        for target in targets:
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target = target.split("#")[0].strip()
            if not target:
                continue
            resolved = None
            for cand in ((src_dir / target), (ROOT / target), (DOCS / target)):
                try:
                    if cand.is_file():
                        resolved = rel(cand.resolve())
                        break
                except (OSError, ValueError):
                    continue
            if resolved and resolved in known and resolved != path:
                doc.outbound.append(resolved)
                docs[resolved].inbound += 1


def audit(policy: dict[str, Any], seed_data: dict[str, Any]) -> tuple[dict[str, Doc], list[Finding], list[str]]:
    findings: list[Finding] = []
    seed = Seed(policy, seed_data)
    docs, artifacts = collect_docs(policy)
    layers = policy.get("layers") or []
    status_values = set(policy.get("status_values") or [])
    lifecycle_values = set(policy.get("lifecycle_values") or [])
    owner_roles = set(policy.get("owner_roles") or [])
    archive_groups = policy.get("archive_groups") or []

    # ── R1 覆盖完整 ──
    for path, doc in docs.items():
        if not doc.has_fm:
            findings.append(Finding("R1", "error", path, "缺少 front-matter（未纳入治理）"))
            continue
        missing = [f for f in REQUIRED_FIELDS if f not in doc.fm]
        if missing:
            findings.append(Finding("R1", "error", path, f"front-matter 缺字段: {','.join(missing)}"))

    # ── R13 产物登记 ──
    declared = {str(a.get("path")): a for a in (policy.get("artifacts") or [])}
    for path in artifacts:
        if path not in declared:
            findings.append(Finding("R13", "error", path, "产物文件未在 policy.artifacts 登记"))
    for path in declared:
        if not (ROOT / path).exists():
            findings.append(Finding("R13", "error", path, "policy.artifacts 登记了不存在的文件"))

    # 产物参与权威唯一校验
    artifact_concerns: list[tuple[str, str, str, str]] = []  # (layer_for_concern, concern, status, path)
    for path, a in declared.items():
        layer = resolve_layer(path, layers)
        artifact_concerns.append((str((layer or {}).get("id", "")), str(a.get("concern", "")),
                                  str(a.get("status", "")), path))

    # ── R2 / R6 / R7 ──
    for path, doc in docs.items():
        if not doc.has_fm:
            continue
        if doc.status and doc.status not in status_values:
            findings.append(Finding("R6", "error", path, f"非法 status: {doc.status}"))
        life = str(doc.fm.get("lifecycle", ""))
        if life and life not in lifecycle_values:
            findings.append(Finding("R6", "error", path, f"非法 lifecycle: {life}"))
        owner = str(doc.fm.get("owner", ""))
        if owner and owner not in owner_roles:
            findings.append(Finding("R6", "error", path, f"非法 owner: {owner}"))
        layer = resolve_layer(path, layers)
        if layer is None:
            findings.append(Finding("R7", "error", path, "不属于任何已声明层"))
        elif doc.layer and doc.layer != str(layer.get("id")):
            findings.append(Finding("R7", "error", path,
                                    f"声明层 {doc.layer} 与目录归属 {layer.get('id')} 不一致"))
        sb = str(doc.fm.get("superseded_by", "") or "")
        if sb and not (ROOT / sb).exists():
            findings.append(Finding("R2", "error", path, f"superseded_by 指向不存在的文件: {sb}"))

    # ── R3 权威唯一 ──
    buckets: dict[tuple[str, str], list[str]] = {}
    for path, doc in docs.items():
        if doc.status == "authoritative":
            buckets.setdefault((doc.layer, doc.concern), []).append(path)
    for layer_id, concern, status, path in artifact_concerns:
        if status == "authoritative":
            buckets.setdefault((layer_id, concern), []).append(path)
    for (layer_id, concern), paths in sorted(buckets.items()):
        if len(paths) > 1:
            findings.append(Finding("R3", "error", ", ".join(sorted(paths)),
                                    f"层 {layer_id} 关注点 '{concern}' 有 {len(paths)} 个 authoritative，必须唯一"))

    # ── R4 取代闭环 ──
    # 不变式：取代链必须终止于一个「仍生效或至少未被取代」的文档。
    # 不要求接任者必须是 authoritative/active——历史过程报告可以由同级的更详尽报告接任
    # （例：REVIEW_REPORT_20260505 → DEEP_REVIEW_REPORT_20260505，两者都是 reference）。
    # 真正要防的是「接任者本身也已被取代/归档」造成的悬空链。
    for path, doc in docs.items():
        if not doc.has_fm:
            continue
        sb = str(doc.fm.get("superseded_by", "") or "")
        if doc.status == "superseded":
            if not sb:
                findings.append(Finding("R4", "error", path, "superseded 未声明 superseded_by"))
                continue
            target = docs.get(sb)
            if target is None:
                if not (ROOT / sb).exists():
                    findings.append(Finding("R4", "error", path, f"接任者不存在: {sb}"))
            elif target.status in {"superseded", "archived"}:
                findings.append(Finding("R4", "error", path,
                                        f"接任者 {sb} 状态为 {target.status}，取代链悬空"))
        elif sb:
            findings.append(Finding("R4", "error", path, f"状态 {doc.status} 却声明了 superseded_by"))

    # ── R14 id 唯一 ──
    id_map: dict[str, list[str]] = {}
    for path, doc in docs.items():
        if not doc.has_fm:
            continue
        did = str(doc.fm.get("id", "") or "")
        if did:
            id_map.setdefault(did, []).append(path)
    for did, paths in sorted(id_map.items()):
        if len(paths) > 1:
            findings.append(Finding("R14", "error", ", ".join(sorted(paths)),
                                    f"front-matter id 重复: {did}"))

    # ── R5 归档溯源 ──
    for path, doc in docs.items():
        if not doc.has_fm or doc.status != "archived":
            continue
        reason = str(doc.fm.get("governance_reason", "") or "")
        evidence = str(doc.fm.get("governance_evidence", "") or "")
        if not reason:
            group = next((ag for ag in archive_groups
                          if (path == str(ag.get("prefix", "")).rstrip("/")
                              or path.startswith(str(ag.get("prefix", "")).rstrip("/") + "/"))), None)
            if not group:
                findings.append(Finding("R5", "error", path, "archived 缺少 reason 且未命中归档分组"))
        if not evidence:
            findings.append(Finding("R5", "error", path, "archived 缺少 evidence（溯源证据）"))

    # ── R8 层编号唯一 ──
    seen: dict[str, str] = {}
    for layer in layers:
        d = str(layer.get("dir", "")).rstrip("/")
        m = re.match(r"^docs/(\d{2})-", d)
        if not m:
            continue
        if m.group(1) in seen:
            findings.append(Finding("R8", "error", d,
                                    f"层编号 {m.group(1)} 与 {seen[m.group(1)]} 重复"))
        else:
            seen[m.group(1)] = d

    # ── R9 版本一致 ──
    for path, doc in docs.items():
        if not doc.has_fm:
            continue
        declared = str(doc.fm.get("version", "") or "").lstrip("v")
        if declared and doc.body_version and declared != doc.body_version.lstrip("v"):
            findings.append(Finding("R9", "warn", path,
                                    f"front-matter 版本 {declared} 与正文 {doc.body_version} 不一致"))

    # ── R10 悬空引用 ──
    for path, doc in docs.items():
        if not doc.has_fm:
            continue
        cits = doc.fm.get("citations") or []
        if not isinstance(cits, list):
            continue
        for c in cits:
            ref = ""
            if isinstance(c, dict):
                ref = str(c.get("ref", "") or "")
            elif isinstance(c, str):
                ref = c
            if ref.startswith(("docs/", "../")):
                cand = (DOCS / ref.replace("docs/", "", 1)) if ref.startswith("docs/") else (ROOT / path).parent / ref
                if not cand.exists():
                    findings.append(Finding("R10", "error", path, f"citations 悬空: {ref}"))

    # ── R11 孤立文档 ──
    build_reference_graph(docs)
    for path, doc in docs.items():
        if not doc.has_fm or doc.status in {"archived", "vendor"}:
            continue
        name = path.rsplit("/", 1)[-1]
        if name in {"README.md", "DOC-INDEX.md"}:
            continue
        if doc.inbound == 0 and not doc.outbound:
            findings.append(Finding("R11", "warn", path, "孤立文档：无任何出入引用"))

    # ── R12 ADR 状态可解析 ──
    adr_glob = str(seed.adr_rules.get("glob", ""))
    for path, doc in docs.items():
        if not adr_glob or not re.match(r"docs/07-adr/ADR-", path):
            continue
        status = doc.status
        if status == "active":
            text = (ROOT / path).read_text(encoding="utf-8", errors="ignore")[:2000]
            markers = seed.adr_rules.get("accepted_markers", [])
            if not any(m in text for m in markers):
                findings.append(Finding("R12", "warn", path, "ADR 未声明可识别的状态段落"))

    return docs, findings, artifacts


def cmd_audit(args: argparse.Namespace) -> int:
    policy = load_yaml(POLICY_PATH)
    seed_data = load_yaml(SEED_PATH) if SEED_PATH.exists() else {}
    docs, findings, artifacts = audit(policy, seed_data)

    errors = [f for f in findings if f.level == "error"]
    warns = [f for f in findings if f.level == "warn"]

    counts: dict[str, int] = {}
    for d in docs.values():
        key = d.status or "(无)"
        counts[key] = counts.get(key, 0) + 1

    print(f"纳管 md: {len(docs)}  产物文件: {len(artifacts)}")
    print("状态分布: " + "  ".join(f"{k}={counts[k]}" for k in sorted(counts)))
    print(f"error: {len(errors)}  warn: {len(warns)}")

    shown = 0
    for f in errors:
        if shown >= 40:
            print(f"  ... 另有 {len(errors) - 40} 条 error")
            break
        print(f"  [ERROR][{f.rule}] {f.path} — {f.message}")
        shown += 1
    if args.verbose:
        for f in warns:
            print(f"  [WARN][{f.rule}] {f.path} — {f.message}")
    elif warns:
        agg: dict[str, int] = {}
        for f in warns:
            agg[f.rule] = agg.get(f.rule, 0) + 1
        print("warn 汇总: " + "  ".join(f"{k}={v}" for k, v in sorted(agg.items()))
              + "（--verbose 查看明细）")

    if errors:
        print("结论: 存在阻断项")
        return 1 if args.ci else 0
    print("结论: R1~R13 无阻断项")
    return 0


# ────────────────────────── index ──────────────────────────

def cmd_index(args: argparse.Namespace) -> int:
    policy = load_yaml(POLICY_PATH)
    seed_data = load_yaml(SEED_PATH) if SEED_PATH.exists() else {}
    docs, findings, artifacts = audit(policy, seed_data)
    layers = policy.get("layers") or []
    layer_order = [str(l.get("id")) for l in layers]
    layer_name = {str(l.get("id")): str(l.get("name")) for l in layers}

    lines: list[str] = []
    lines.append("# 文档索引（DOC-INDEX）")
    lines.append("")
    lines.append("> **本文件由脚本生成，请勿手改。** 重新生成：`python scripts/doc_governance.py index`")
    lines.append("> 真相源：各文档自身的 YAML front-matter（ADR-097 第 2 条）。")
    lines.append("> 规则：`docs/DOC-GOVERNANCE-POLICY.yaml`。校验：`python scripts/doc_governance.py audit --ci`。")
    lines.append("")
    lines.append(f"纳管文档 **{len(docs)}** 份，产物文件 **{len(artifacts)}** 份。")
    lines.append("")
    errors = [f for f in findings if f.level == "error"]
    warns = [f for f in findings if f.level == "warn"]
    lines.append(f"治理校验：error **{len(errors)}** / warn **{len(warns)}**")
    lines.append("")
    lines.append("## 1. 状态图例")
    lines.append("")
    lines.append("| status | 含义 |")
    lines.append("|--------|------|")
    lines.append("| authoritative | 该关注点的唯一权威，冲突时以此为准 |")
    lines.append("| active | 现行有效，但非唯一权威 |")
    lines.append("| proposed | 已提议未接受（ADR） |")
    lines.append("| reference | 参考资料，不作实施依据 |")
    lines.append("| superseded | 已被取代，保留作历史可追溯 |")
    lines.append("| archived | 已归档，不再维护 |")
    lines.append("| vendor | 第三方/导出内容，不纳入本项目治理 |")
    lines.append("")

    for lid in layer_order:
        entries = sorted((d for d in docs.values() if d.layer == lid), key=lambda d: d.path)
        if not entries:
            continue
        lines.append(f"## {lid} {layer_name.get(lid, '')}（{len(entries)}）")
        lines.append("")
        lines.append("| 文档 | 状态 | 归属 | 关注点 | 版本 | 取代/被取代 |")
        lines.append("|------|------|------|--------|------|-------------|")
        for d in entries:
            name = d.path.split("/", 2)[-1] if d.path.count("/") >= 2 else d.path
            sup = str(d.fm.get("superseded_by", "") or "")
            sup_cell = f"→ `{sup.split('/')[-1]}`" if sup else ""
            lines.append(
                f"| `{name}` | {d.status or '—'} | {d.fm.get('owner','—')} | "
                f"{d.concern or '—'} | {d.fm.get('version','') or '—'} | {sup_cell} |"
            )
        lines.append("")

    if errors:
        lines.append("## 治理阻断项")
        lines.append("")
        lines.append("| 规则 | 文档 | 说明 |")
        lines.append("|------|------|------|")
        for f in errors:
            lines.append(f"| {f.rule} | `{f.path}` | {f.message} |")
        lines.append("")

    INDEX_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    INVENTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    cols = ["path", "layer", "status", "lifecycle", "owner", "concern", "version", "superseded_by"]
    with INVENTORY_PATH.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for path in sorted(docs):
            d = docs[path]
            w.writerow([path, d.layer, d.status, d.fm.get("lifecycle", ""), d.fm.get("owner", ""),
                        d.concern, d.fm.get("version", ""), d.fm.get("superseded_by", "")])

    print(f"已生成 {rel(INDEX_PATH)}（{len(docs)} 份文档）")
    print(f"已生成 {rel(INVENTORY_PATH)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="文档治理三合一工具")
    sub = ap.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("migrate", help="补齐 front-matter")
    m.add_argument("--dry-run", action="store_true")
    m.add_argument("--force", action="store_true", help="（保留参数位）")
    m.add_argument("--reset", action="store_true",
                   help="按策略重新推导并覆盖全部受管字段（修正错误的初始迁移）")
    m.set_defaults(func=cmd_migrate)

    a = sub.add_parser("audit", help="按 R1~R13 校验")
    a.add_argument("--ci", action="store_true", help="有 error 时退出码 1")
    a.add_argument("--verbose", action="store_true")
    a.set_defaults(func=cmd_audit)

    i = sub.add_parser("index", help="生成 DOC-INDEX.md 与清单 CSV")
    i.set_defaults(func=cmd_index)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
