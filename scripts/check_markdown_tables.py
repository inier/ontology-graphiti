#!/usr/bin/env python
"""Markdown 表格结构核对器。

存在理由（三次真实事故，全部靠人眼漏过、靠自报假绿）：
1. `prd.md` §4.2：表头 3 列，6 行只写 2 格 → 超出表头的第三列被 GFM **静默截断**，
   那些解释文字在渲染结果里**根本不存在**，但源文件里还在，所以搜索能找到、人眼也不会注意。
2. `uiux.md` §10.2.3：单元格内用裸换行写多段 → 表格在首行之后就结束了，后续内容实际在表外。
3. `prd.md` §2.1：整张表一致地少一列 → 每行内容左移一格。

关键判据：**以表头列数为基准，逐行比对**。
不要用「行与行之间是否一致」做判据——当整张表一致地少一列或多一列时，
行间永远互相一致，检查必然通过。拿实例跟实例比，在所有实例一致地错时永远通过。

用法：
    python scripts/check_markdown_tables.py docs/superpowers/specs/**/*.md
    python scripts/check_markdown_tables.py --all docs/

退出码：0 = 全部合规；1 = 存在列数不一致（可用作 CI 门禁）。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterable, List, Tuple

# 分隔行：| --- | :---: | ---: |
_SEPARATOR = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")


def split_cells(line: str) -> List[str]:
    """按未转义的 `|` 切分单元格，首尾竖线不计。支持 `\\|` 转义。"""
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|") and not text.endswith("\\|"):
        text = text[:-1]

    cells: List[str] = []
    buffer: List[str] = []
    escaped = False
    for char in text:
        if escaped:
            buffer.append(char)
            escaped = False
        elif char == "\\":
            buffer.append(char)
            escaped = True
        elif char == "|":
            cells.append("".join(buffer))
            buffer = []
        else:
            buffer.append(char)
    cells.append("".join(buffer))
    return cells


def iter_table_rows(lines: List[str]) -> Iterable[Tuple[int, int, List[str]]]:
    """产出 (行号, 表头列数, 单元格列表)，仅针对表格数据行。代码围栏内跳过。"""
    in_fence = False
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            index += 1
            continue

        is_table_start = (
            not in_fence
            and stripped.startswith("|")
            and index + 1 < len(lines)
            and _SEPARATOR.match(lines[index + 1])
        )
        if not is_table_start:
            index += 1
            continue

        header_count = len(split_cells(line))
        cursor = index + 2
        while cursor < len(lines) and lines[cursor].strip().startswith("|"):
            yield cursor + 1, header_count, split_cells(lines[cursor])
            cursor += 1
        index = cursor


def check_file(path: Path) -> List[str]:
    lines = path.read_text(encoding="utf-8").split("\n")
    problems: List[str] = []

    table_count = 0
    in_fence = False
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if (
            not in_fence
            and stripped.startswith("|")
            and index + 1 < len(lines)
            and _SEPARATOR.match(lines[index + 1])
        ):
            table_count += 1

    for lineno, header_count, cells in iter_table_rows(lines):
        if len(cells) != header_count:
            delta = len(cells) - header_count
            kind = f"多 {delta} 格（GFM 会静默截断）" if delta > 0 else f"少 {-delta} 格（整行左移或末列为空）"
            problems.append(
                f"{path}:{lineno}  表头 {header_count} 列 / 本行 {len(cells)} 格 → {kind}\n"
                f"    {lines[lineno - 1].strip()[:100]}"
            )

    if problems:
        problems.insert(0, f"== {path}  表格数 {table_count}  问题行 {len(problems)}")
    else:
        problems.append(f"== {path}  表格数 {table_count}  问题行 0")
    return problems


def collect(targets: List[str]) -> List[Path]:
    found: List[Path] = []
    for target in targets:
        path = Path(target)
        if path.is_dir():
            found.extend(sorted(path.rglob("*.md")))
        elif path.exists():
            found.append(path)
    return found


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="核对 Markdown 表格列数是否与表头一致")
    parser.add_argument("paths", nargs="+", help="Markdown 文件或目录")
    parser.add_argument("--quiet", action="store_true", help="只输出有问题的文件")
    args = parser.parse_args(argv)

    files = [p for p in collect(args.paths) if ".workbuddy" not in str(p)]
    if not files:
        print("未找到任何 Markdown 文件", file=sys.stderr)
        return 1

    total_problems = 0
    for path in files:
        report = check_file(path)
        if args.quiet and "问题行 0" in report[0]:
            continue
        for line in report:
            print(line)
        if "问题行 0" not in report[0]:
            total_problems += 1

    if total_problems:
        print(f"\n失败：{total_problems} 个文件存在表格列数不一致", file=sys.stderr)
        return 1
    print(f"\n通过：已核对 {len(files)} 个文件，表格列数全部与表头一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
