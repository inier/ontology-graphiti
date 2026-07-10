#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_dangling_doc_links.py — 死链修复器（磁盘校验，零误伤）

与 check_dangling_doc_links.py 配套。对检测出的每条死链，尝试一组候选重定向，
仅当候选目标在真实文件系统中【存在】时才重写；否则标记为 "待人工" 不改。

安全铁律：
  - 不重写任何目标无法验证存在的链接（绝不盲改）
  - 默认 dry-run（只打印方案），需 --apply 才落盘
  - 每条修复都打印 “源:行 旧 -> 新 (已验证存在)”

Tier 1（机械可重定向，本脚本自动处理）：
  adr/ -> 07-adr/ , modules/ -> 03-modules/ , ui/ -> 04-ui/
  permission_checker -> opa_policy , web/ -> web_frontend/
  mock_engine -> simulator|event_simulator , 00-00-requirements -> 00-requirements
  ../../docs/ -> ../ , ./docs/ -> ../ , ../../specs/ -> ../../../specs/
  ../ARCHITECTURE.md(07-adr 内) -> ../02-architecture/ARCHITECTURE.md
  ../ODAP综合优化设计文档.md -> ../01-product-design/ODAP综合优化设计文档.md

Tier 2（目标根本不存在或歧义，本脚本标记 "待人工"，不处理）：
  ADR 改名失效（ADR-006_agent_链路追踪系统 等）
  根目录级缺失文件（TASK_BREAKDOWN/ARCHITECTURE_PLAN/RESTRUCTURE_PLAN/ARCHITECTURE_VALIDATION_REPORT）
  contracts/README.md 列出的从未创建的契约文件
"""

import argparse
import os
import re
import sys
from pathlib import Path

# 已知“安全”的 ADR 改名映射：编号相同、主题一致，可直接重定向到真实文件名。
# 注意：不做泛化“按编号匹配”，避免 ADR-006(旧名链路追踪)误映射到 ADR-006(复用策略) 这类主题不符。
ADR_RENAME = {
    "ADR-003_opa_policy_governance.md": "ADR-003_opa_策略治理引擎mvp_生产化.md",
    "ADR-028_permission_checker_system.md": "ADR-028_permission_checker_opa_integration.md",
}

# 复用检测脚本的判定逻辑
KNOWN_DEAD = [
    "specs/002-copilotkit-eval", "specs/004-microservice-split",
    "specs/006-llm-config-management", "specs/ui-ux-pro-max",
    "ARCHITECTURE_FULL_CHAIN_DEEP.md",
]
PROSE_SUPPRESS_FILES = (
    "ADR-049_规格与架构文档瘦身.md",
    "SLIMMING_REPORT_2026-07-08.md",
    "REVIEW_REPORT_2026-07-08.md",
)
EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "ftp://", "file://")
CODE_SAMPLE_RE = re.compile(r"[\[\]()*+?^$|\\]")


def is_external(target: str) -> bool:
    return target.startswith(EXTERNAL_PREFIXES) or target.startswith("#")


def target_exists(target: str, base_dir: Path, repo_root: Path) -> bool:
    path_part = target.split("#", 1)[0].strip()
    if not path_part or path_part == "/":
        return True
    candidates = []
    if path_part.startswith("/"):
        candidates.append((repo_root / path_part.lstrip("/")).resolve())
    else:
        candidates.append((base_dir / path_part).resolve())
        candidates.append((repo_root / path_part).resolve())
        candidates.append((repo_root / "docs" / path_part).resolve())
        candidates.append((repo_root / "specs" / path_part).resolve())
    return any(c.exists() for c in candidates)


def gen_candidates(target: str) -> list:
    """为一处死链生成所有候选重定向（字符串列表，未经校验）。"""
    cands: list = []
    ups = ["", "../", "../../", "../../../", "../../../../"]

    def variants(s: str):
        """对字符串 s 应用多种前缀/替换，产出候选。"""
        out = set()
        # 原始
        out.add(s)
        # 各种 ../ 前缀
        for u in ups:
            out.add(u + s)
        # adr/ -> 07-adr/
        m = re.match(r"^(?:\./|\.\./)*adr/(.*)$", s)
        if m:
            rest = m.group(1)
            for u in ups:
                out.add(u + "07-adr/" + rest)
        # modules/ -> 03-modules/
        m = re.match(r"^(?:\./|\.\./)*modules/(.*)$", s)
        if m:
            rest = m.group(1)
            for u in ups:
                out.add(u + "03-modules/" + rest)
        # ui/ -> 04-ui/
        m = re.match(r"^(?:\./|\.\./)*ui/(.*)$", s)
        if m:
            rest = m.group(1)
            for u in ups:
                out.add(u + "04-ui/" + rest)
        # permission_checker -> opa_policy
        if "permission_checker" in s:
            out.add(s.replace("permission_checker", "opa_policy"))
            for u in ups:
                out.add((u + s).replace("permission_checker", "opa_policy"))
        # web/ (非 web_frontend) -> web_frontend
        if re.search(r"(?<!frontend_)web/", s):
            fixed = re.sub(r"(?<!frontend_)web/", "web_frontend/", s)
            out.add(fixed)
            for u in ups:
                out.add(u + fixed)
        # 注意：mock_engine 不自动重定向（simulator 与 event_simulator 二义，留人工）
        # 00-00-requirements -> 00-requirements
        if "00-00-requirements" in s:
            out.add(s.replace("00-00-requirements", "00-requirements"))
            for u in ups:
                out.add((u + s).replace("00-00-requirements", "00-requirements"))
        # ../../docs/ -> ../ ; ./docs/ -> ../
        if "docs/" in s:
            stripped = re.sub(r"(\.\./|\./)*docs/", "", s)
            out.add("../" + stripped)
            out.add(stripped)
            for u in ups:
                out.add(u + stripped)
            # 剥离 docs/ 后，对结果重新套用前缀映射（关键：否则 modules/ 等不生效）
            if stripped.startswith("modules/"):
                out.add("../03-modules/" + stripped[len("modules/"):])
            if stripped.startswith("adr/"):
                out.add("../07-adr/" + stripped[len("adr/"):])
            if stripped.startswith("ui/"):
                out.add("../04-ui/" + stripped[len("ui/"):])
        # ../../specs/ -> ../../../specs/ (补一级 ..)
        if "specs/" in s and s.startswith("../"):
            extra = "../" + s
            out.add(extra)
            out.add("../" + extra)
        # ../ARCHITECTURE.md (07-adr 内) -> ../02-architecture/ARCHITECTURE.md
        if s.endswith("ARCHITECTURE.md") and not s.startswith(".." + "/02-architecture"):
            out.add("../02-architecture/ARCHITECTURE.md")
            out.add("../../02-architecture/ARCHITECTURE.md")
        # ../ODAP综合优化设计文档.md -> ../01-product-design/ODAP综合优化设计文档.md
        if "ODAP综合优化设计文档.md" in s:
            out.add("../01-product-design/ODAP综合优化设计文档.md")
            out.add("01-product-design/ODAP综合优化设计文档.md")
        return out

    cands.extend(variants(target))
    # 去重
    seen = set()
    result = []
    for c in cands:
        if c not in seen:
            seen.add(c)
            result.append(c)
    return result


def resolve(target: str, base_dir: Path, repo_root: Path):
    """返回 (corrected_target, True) 或 (None, False)。"""
    for cand in gen_candidates(target):
        if cand == target:
            continue
        if target_exists(cand, base_dir, repo_root):
            return cand, True
    # 07-adr/ 前缀（处理 ../../07-adr/X 多一级 .. 的情况）
    if "07-adr/" in target:
        idx = target.index("07-adr/")
        rest = target[idx + len("07-adr/"):]
        for u in ("", "../", "../../", "../../../"):
            cand = u + "07-adr/" + rest
            if cand != target and target_exists(cand, base_dir, repo_root):
                return cand, True
    # 已知安全 ADR 改名（编号相同、主题一致）
    b = os.path.basename(target.rstrip("/"))
    if b in ADR_RENAME:
        real = repo_root / "docs/07-adr" / ADR_RENAME[b]
        if real.exists():
            rel = os.path.relpath(real, base_dir).replace("\\", "/")
            return rel, True
    return None, False


LINK_RE = re.compile(r"\[(?P<text>[^\]]*)\]\((?P<target>[^)\s]+)(?:\s+\"[^\"]*\")?\)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--roots", nargs="*", default=["docs", "specs"])
    ap.add_argument("--apply", action="store_true", help="落盘重写（默认 dry-run）")
    args = ap.parse_args()
    repo_root = Path.cwd()
    roots = [Path(r) for r in args.roots if Path(r).exists()]

    resolved = 0
    unresolved = 0
    plan = []
    for root in roots:
        for md in sorted(root.rglob("*.md")):
            base_dir = md.parent
            lines = md.read_text(encoding="utf-8", errors="ignore").splitlines()
            new_lines = list(lines)
            changed = False
            for i, line in enumerate(lines, 1):
                for m in LINK_RE.finditer(line):
                    target = m.group("target").strip()
                    if is_external(target):
                        continue
                    if CODE_SAMPLE_RE.search(target):
                        continue
                    if target_exists(target, base_dir, repo_root):
                        continue  # 本就不是死链
                    corrected, ok = resolve(target, base_dir, repo_root)
                    if ok:
                        resolved += 1
                        new_line = line[:m.start("target")] + corrected + line[m.end("target"):]
                        # 重新扫描该行可能还有别的链接，简单整体替换
                        new_lines[i - 1] = new_lines[i - 1].replace(
                            "](%s)" % target, "](%s)" % corrected, 1)
                        changed = True
                        plan.append((str(md), i, target, corrected))
                    else:
                        unresolved += 1
                        plan.append((str(md), i, target, "【待人工】"))
            if changed and args.apply:
                md.write_text("\n".join(new_lines), encoding="utf-8")

    print("=" * 70)
    print("死链修复方案" + ("（DRY-RUN，未落盘）" if not args.apply else "（已落盘）"))
    print("=" * 70)
    for src, ln, old, new in plan:
        tag = "  OK  " if new != "【待人工】" else " HUMAN"
        print(f"[{tag}] {src}:{ln}\n        {old}\n     -> {new}")
    print("-" * 70)
    print(f"可自动修复(已验证): {resolved}    待人工: {unresolved}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
