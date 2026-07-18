#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
remove_dead_links.py — 将"无有效重定向目标"的死链转为纯文本（保留文字、去掉链接）。

适用场景（经人工确认的 Tier 2 清理）：
  - A 组：目标文件确认已删/从未存在 → 死链无意义，转纯文本
  - B 组：contracts/README.md 索引的 21 个从未创建的契约文件 → 保留文件名、去死链
  - C 组（mock_engine）：歧义，跳过，留待人工

安全：仅改写 [text](dead_target) 为 text；对每个死链先经 target_exists 复核。
"""

import argparse
import re
import sys
from pathlib import Path

EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "ftp://", "file://")
CODE_SAMPLE_RE = re.compile(r"[\[\]()*+?^$|\\]")
LINK_RE = re.compile(r"\[(?P<text>[^\]]*)\]\((?P<target>[^)\s]+)(?:\s+\"[^\"]*\")?\)")

# 跳过（留待人工）的死链：mock_engine 歧义
SKIP_SUBSTR = ("mock_engine",)


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--roots", nargs="*", default=["docs", "specs"])
    ap.add_argument("--apply", action="store_true", help="落盘（默认 dry-run）")
    args = ap.parse_args()
    repo_root = Path.cwd()
    roots = [Path(r) for r in args.roots if Path(r).exists()]

    converted = 0
    skipped = 0
    for root in roots:
        for md in sorted(root.rglob("*.md")):
            base_dir = md.parent
            lines = md.read_text(encoding="utf-8", errors="ignore").splitlines()
            new_lines = list(lines)
            changed = False
            for i, line in enumerate(lines, 1):
                for m in LINK_RE.finditer(line):
                    target = m.group("target").strip()
                    text = m.group("text")
                    if is_external(target) or CODE_SAMPLE_RE.search(target):
                        continue
                    if target_exists(target, base_dir, repo_root):
                        continue  # 非死链
                    if any(s in target for s in SKIP_SUBSTR):
                        skipped += 1
                        print(f"[SKIP] {md}:{i} -> {target}")
                        continue
                    # 死链且不在跳过列表 → 转纯文本
                    converted += 1
                    new_line = line[:m.start()] + text + line[m.end():]
                    new_lines[i - 1] = new_line
                    changed = True
                    print(f"[{'APPLY' if args.apply else 'DRY'}] {md}:{i} "
                          f"[{text}]({target}) -> {text}")
            if changed and args.apply:
                md.write_text("\n".join(new_lines), encoding="utf-8")

    print("-" * 50)
    print(f"转为纯文本: {converted}    跳过(mock_engine): {skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
