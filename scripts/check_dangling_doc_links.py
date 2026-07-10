#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_dangling_doc_links.py — Markdown 文档死链检测器

为什么存在（经验沉淀）:
  ODAP 在 2026-07-08 一轮文档瘦身中删除了 ARCHITECTURE_FULL_CHAIN_DEEP.md 等文件，
  但遗漏了约 21 处指向它们的 markdown 链接，造成系统性"删文件留尾巴"死链。
  本脚本将"删文件 → 必须 grep 查引用"这一铁律工具化，可在删除前后运行，
  也可接入 pre-commit / CI 防止复发。

检测内容:
  1. 死链（FAIL）: markdown 链接 [text](path) 指向的本地文件/目录不存在。
     依次尝试多种解析基准，减少误报:
       - 相对于当前文件所在目录
       - 相对于仓库根目录
       - 相对于 docs/ 根（项目约定：链接常以 docs/ 为隐式根，如 02-architecture/...）
       - 相对于 specs/ 根
  2. 已知删除提及（WARN）: 散文/正文中出现已知已删路径（如 specs/002-copilotkit-eval），
     多半是未清理的引用尾巴。删除记录类文档（ADR-049 / *_REPORT）除外。

跳过（非死链）:
  - 外部链接 http/https/mailto/ftp/file://
  - 纯锚点 #anchor
  - 看起来像代码/正则样本的 target（含 [ ] ( ) * + ? ^ $ { } | \\ 等元字符）

用法:
  python scripts/check_dangling_doc_links.py                 # 扫描 docs/ specs/
  python scripts/check_dangling_doc_links.py --roots docs specs odap
  python scripts/check_dangling_doc_links.py --ci           # 发现死链则退出码 1
  python scripts/check_dangling_doc_links.py --strict       # 已知删除提及也判失败

退出码:
  0 = 无死链
  1 = 发现死链（或 --strict 下发现已知删除提及）
"""

import argparse
import re
import sys
from pathlib import Path

# 匹配 markdown 链接: [text](target) 或 [text](target "title")
LINK_RE = re.compile(r"\[(?P<text>[^\]]*)\]\((?P<target>[^)\s]+)(?:\s+\"[^\"]*\")?\)")

# 已知已删除的路径（散文提及告警用）。删除记录文档中的提及不告警。
KNOWN_DEAD = [
    "specs/002-copilotkit-eval",
    "specs/004-microservice-split",
    "specs/006-llm-config-management",
    "specs/ui-ux-pro-max",
    "ARCHITECTURE_FULL_CHAIN_DEEP.md",
]

# 这些文件名内的已知删除提及属合法"删除记录"，不告警
PROSE_SUPPRESS_FILES = (
    "ADR-049_规格与架构文档瘦身.md",
    "SLIMMING_REPORT_2026-07-08.md",
    "REVIEW_REPORT_2026-07-08.md",
)

EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "ftp://", "file://")
# 看起来像代码/正则样本的 target（非真实路径）
CODE_SAMPLE_RE = re.compile(r"[\[\]()*+?^$|\\]")


def is_external(target: str) -> bool:
    return target.startswith(EXTERNAL_PREFIXES) or target.startswith("#")


def target_exists(target: str, base_dir: Path, repo_root: Path) -> bool:
    """判断链接目标是否存在，兼容多种项目链接约定。"""
    path_part = target.split("#", 1)[0].strip()
    if not path_part or path_part == "/":
        return True  # 纯锚点或根，跳过
    candidates = []
    if path_part.startswith("/"):
        candidates.append((repo_root / path_part.lstrip("/")).resolve())
    else:
        candidates.append((base_dir / path_part).resolve())
        candidates.append((repo_root / path_part).resolve())
        # 项目约定：docs/ 为隐式链接根
        candidates.append((repo_root / "docs" / path_part).resolve())
        candidates.append((repo_root / "specs" / path_part).resolve())
    return any(c.exists() for c in candidates)


def scan_file(md: Path, repo_root: Path):
    dangling = []  # (line_no, target)
    prose = []     # (line_no, matched)
    try:
        lines = md.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return dangling, prose

    base_dir = md.parent
    for i, line in enumerate(lines, 1):
        for m in LINK_RE.finditer(line):
            target = m.group("target").strip()
            if is_external(target):
                continue
            if CODE_SAMPLE_RE.search(target):
                continue  # 代码/正则样本，非真实路径
            if not target_exists(target, base_dir, repo_root):
                dangling.append((i, target))
        # 散文提及（仅非删除记录文件）
        if md.name not in PROSE_SUPPRESS_FILES:
            for dead in KNOWN_DEAD:
                if dead in line:
                    prose.append((i, dead))
                    break
    return dangling, prose


def main():
    parser = argparse.ArgumentParser(description="Markdown 文档死链检测器")
    parser.add_argument("--roots", nargs="*", default=["docs", "specs"],
                        help="要扫描的根目录（默认 docs specs）")
    parser.add_argument("--known-dead", nargs="*", default=KNOWN_DEAD,
                        help="散文提及告警的已知已删路径")
    parser.add_argument("--ci", action="store_true", help="发现死链则退出码 1")
    parser.add_argument("--strict", action="store_true", help="已知删除提及也判失败")
    args = parser.parse_args()

    repo_root = Path.cwd()
    roots = [Path(r) for r in args.roots if Path(r).exists()]
    if not roots:
        print(f"[WARN] 未找到任何扫描根目录: {args.roots}", file=sys.stderr)
        return 0

    total_dangling = 0
    total_prose = 0
    for root in roots:
        for md in sorted(root.rglob("*.md")):
            dangling, prose = scan_file(md, repo_root)
            for ln, tgt in dangling:
                total_dangling += 1
                print(f"[FAIL] 死链 {md}:{ln} -> {tgt}")
            for ln, dead in prose:
                total_prose += 1
                print(f"[WARN] 已知删除提及 {md}:{ln} -> {dead}")

    print("-" * 60)
    print(f"扫描根: {', '.join(str(r) for r in roots)}")
    print(f"死链(FAIL): {total_dangling}   已知删除提及(WARN): {total_prose}")
    if total_dangling == 0:
        print("✅ 无死链")
    else:
        print("❌ 存在死链，请修复后复查（或确认是合法的外部/锚点链接）")

    if total_dangling > 0 or (args.strict and total_prose > 0):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
