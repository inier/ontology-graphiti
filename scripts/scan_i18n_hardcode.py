#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
i18n 硬编码中文字符串扫描器

扫描 frontend/src/modules/* 下的 .ts/.tsx 文件，提取所有硬编码的中文字符串，
生成扫描报告，便于后续接入 i18next。

输出：
- 控制台表格（按模块汇总）
- JSON 报告（i18n_scan_report.json）
- 翻译模板（可选，--emit-template）
- 与现有 locale JSON 的差异对比（可选，--diff-existing）

用法：
    python scripts/scan_i18n_hardcode.py                      # 默认扫描 + 控制台报告
    python scripts/scan_i18n_hardcode.py --output report.json # 输出到指定文件
    python scripts/scan_i18n_hardcode.py --module ontology    # 只扫描指定模块
    python scripts/scan_i18n_hardcode.py --emit-template      # 额外生成 i18n 模板
    python scripts/scan_i18n_hardcode.py --diff-existing      # 对比现有 locale
    python scripts/scan_i18n_hardcode.py --include-tests      # 包含 .test.tsx 文件
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Windows 控制台 UTF-8 输出
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

# 仓库根目录：scripts/ 上一级
REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_MODULES = REPO_ROOT / "frontend" / "src" / "modules"

# 匹配中文字符（含全角标点）
CHINESE_PATTERN = re.compile(
    r"[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]+"
)

# 常见 JSX/TS 中的"字符串字面量"上下文
STRING_LITERAL_PATTERNS = [
    # 双引号 / 单引号 / 反引号字符串
    re.compile(r'"([^"\n]*?[\u4e00-\u9fff][^"\n]*?)"'),
    re.compile(r"'([^'\n]*?[\u4e00-\u9fff][^'\n]*?)'"),
    re.compile(r"`([^`\n]*?[\u4e00-\u9fff][^`\n]*?)`"),
]

# 排除规则：包含这些上下文的字符串不视为硬编码（已 i18n 化）
EXCLUDE_CONTEXT_KEYWORDS = [
    "useTranslation",
    "i18n.t(",
    "i18next.t(",
]

# 排除目录
EXCLUDE_DIRS = {
    "node_modules",
    "dist",
    "build",
    ".git",
    "locales",  # 跳过 i18n JSON 所在目录
}

# 排除文件后缀
EXCLUDE_EXTS = {".d.ts"}

# 测试文件后缀
TEST_EXTS = {".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx"}


@dataclass
class HardcodedString:
    """单条硬编码字符串记录"""
    module: str  # 所属模块（如 ontology / workspace）
    file: str  # 源文件相对路径
    line: int  # 行号
    text: str  # 原始字符串
    snippet: str = ""  # 上下文片段
    used_translation: bool = False  # 文件是否已使用 useTranslation


@dataclass
class ScanReport:
    """扫描报告"""
    total_files: int = 0
    files_with_chinese: int = 0
    files_using_i18n: int = 0
    total_strings: int = 0
    by_module: Dict[str, int] = field(default_factory=dict)
    by_file: Dict[str, int] = field(default_factory=dict)
    strings: List[HardcodedString] = field(default_factory=list)


def should_skip_file(path: Path, include_tests: bool) -> bool:
    """判断是否跳过该文件"""
    # 跳过非源码目录
    if any(part in EXCLUDE_DIRS for part in path.parts):
        return True
    # 跳过测试文件（除非显式包含）
    if not include_tests and path.name.endswith(tuple(TEST_EXTS)):
        return True
    # 跳过 .d.ts
    if path.suffix in EXCLUDE_EXTS:
        return True
    # 只处理 .ts / .tsx
    if path.suffix not in {".ts", ".tsx"}:
        return True
    return False


def get_module_name(path: Path) -> str:
    """从文件路径提取模块名（frontend/src/modules/{module}/...）"""
    try:
        rel = path.relative_to(FRONTEND_MODULES)
        return rel.parts[0] if rel.parts else "shared"
    except ValueError:
        return "unknown"


def file_uses_translation(content: str) -> bool:
    """判断文件是否已使用 useTranslation / i18n.t"""
    return any(kw in content for kw in EXCLUDE_CONTEXT_KEYWORDS)


def extract_chinese_strings(content: str, line_offset: int = 0) -> List[Tuple[int, str]]:
    """从文本中提取所有中文字符串及其行号"""
    results: List[Tuple[int, str]] = []
    seen_in_line: Set[str] = set()
    for i, line in enumerate(content.splitlines(), start=1):
        for pattern in STRING_LITERAL_PATTERNS:
            for match in pattern.finditer(line):
                text = match.group(1).strip()
                if not text or not CHINESE_PATTERN.search(text):
                    continue
                # 去重：同一行同一字符串只记录一次
                if text in seen_in_line:
                    continue
                seen_in_line.add(text)
                results.append((i + line_offset, text))
    return results


def scan_file(path: Path) -> Tuple[bool, bool, List[Tuple[int, str]]]:
    """扫描单个文件。返回 (file_uses_i18n, has_chinese, [(line, text), ...])"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except (UnicodeDecodeError, OSError) as e:
        print(f"  [WARN] 无法读取 {path}: {e}", file=sys.stderr)
        return False, False, []

    uses_i18n = file_uses_translation(content)
    strings = extract_chinese_strings(content)
    return uses_i18n, bool(strings), strings


def scan_modules(
    target_module: str = None, include_tests: bool = False
) -> ScanReport:
    """扫描所有模块（或指定模块）"""
    report = ScanReport()

    if not FRONTEND_MODULES.exists():
        print(f"[ERROR] 模块目录不存在: {FRONTEND_MODULES}", file=sys.stderr)
        return report

    # 收集目标模块
    if target_module:
        target_dirs = [FRONTEND_MODULES / target_module]
    else:
        target_dirs = [d for d in FRONTEND_MODULES.iterdir() if d.is_dir()]

    for module_dir in target_dirs:
        if not module_dir.exists():
            print(f"[WARN] 模块不存在: {module_dir}", file=sys.stderr)
            continue

        module_name = module_dir.name
        for root, dirs, files in os.walk(module_dir):
            # 过滤目录
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for fname in files:
                fpath = Path(root) / fname
                if should_skip_file(fpath, include_tests):
                    continue
                report.total_files += 1
                uses_i18n, has_chinese, strings = scan_file(fpath)
                if uses_i18n:
                    report.files_using_i18n += 1
                if not has_chinese:
                    continue
                report.files_with_chinese += 1
                rel = str(fpath.relative_to(REPO_ROOT))
                report.by_file[rel] = len(strings)
                report.by_module[module_name] = (
                    report.by_module.get(module_name, 0) + len(strings)
                )
                # 取上下文片段
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        content = f.read()
                    lines = content.splitlines()
                except Exception:
                    lines = []
                for line_no, text in strings:
                    snippet = ""
                    if 0 < line_no <= len(lines):
                        snippet = lines[line_no - 1].strip()[:120]
                    report.strings.append(
                        HardcodedString(
                            module=module_name,
                            file=rel,
                            line=line_no,
                            text=text,
                            snippet=snippet,
                            used_translation=uses_i18n,
                        )
                    )
                    report.total_strings += 1

    return report


def print_console_report(report: ScanReport, show_list: bool = False) -> None:
    """打印控制台报告"""
    print("=" * 78)
    print(" i18n 硬编码中文字符串扫描报告")
    print("=" * 78)
    print(f"  扫描文件总数       : {report.total_files}")
    print(f"  含中文文件数       : {report.files_with_chinese}")
    print(f"  已使用 i18n 文件数 : {report.files_using_i18n}")
    print(f"  硬编码字符串总数   : {report.total_strings}")
    print()
    if report.by_module:
        print("  按模块统计:")
        print(f"  {'模块':<20} {'硬编码数':>10} {'已 i18n 文件数':>15}")
        print(f"  {'-'*20} {'-'*10} {'-'*15}")
        for module, count in sorted(
            report.by_module.items(), key=lambda x: -x[1]
        ):
            i18n_count = sum(
                1
                for s in report.strings
                if s.module == module and s.used_translation
            )
            print(f"  {module:<20} {count:>10} {i18n_count:>15}")
    print()
    if report.by_file:
        print("  Top 10 含硬编码最多的文件:")
        top = sorted(report.by_file.items(), key=lambda x: -x[1])[:10]
        for fpath, count in top:
            print(f"    {count:>4}  {fpath}")
    if show_list:
        print()
        print("  所有硬编码字符串（按文件分组）:")
        current_file = None
        for s in report.strings:
            if s.file != current_file:
                current_file = s.file
                print(f"\n  === {s.file} ===")
            marker = "  [i18n]" if s.used_translation else ""
            print(f"    L{s.line:<4} {s.text!r}{marker}")
    print("=" * 78)


def write_json_report(report: ScanReport, output_path: Path) -> None:
    """写出 JSON 报告"""
    payload = {
        "summary": {
            "total_files": report.total_files,
            "files_with_chinese": report.files_with_chinese,
            "files_using_i18n": report.files_using_i18n,
            "total_strings": report.total_strings,
        },
        "by_module": report.by_module,
        "by_file": report.by_file,
        "strings": [asdict(s) for s in report.strings],
    }
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  [INFO] JSON 报告已写入: {output_path}")


def emit_translation_template(
    report: ScanReport, target_locale: str = "en-US"
) -> Dict[str, Dict[str, str]]:
    """
    生成翻译模板：
    - zh-CN: 把所有硬编码字符串原样放入（生成 zh-CN 模板）
    - 目标语言: 占位 [TODO: translate] 等待 LLM 翻译

    返回 {locale: {module: {key: value}}}
    """
    template: Dict[str, Dict[str, str]] = {
        "zh-CN": defaultdict(dict),
        target_locale: defaultdict(dict),
    }

    for s in report.strings:
        key = _slugify(s.text, used_in_i18n_file=s.used_translation)
        if not key:
            continue
        # 若 key 已存在则附加行号后缀
        original_key = key
        suffix = 0
        while key in template["zh-CN"][s.module]:
            suffix += 1
            key = f"{original_key}_{suffix}"
        template["zh-CN"][s.module][key] = s.text
        template[target_locale][s.module][key] = f"[TODO: translate] {s.text}"

    return template


def _slugify(text: str, used_in_i18n_file: bool = False, max_len: int = 50) -> str:
    """把中文字符串转换为伪 key。仅用于占位，不用于实际翻译键。"""
    # 取前 max_len 字符
    snippet = text[:max_len].strip()
    # 用下划线连接，移除特殊字符
    snippet = re.sub(r"[\s\u3000]+", "_", snippet)
    snippet = re.sub(r"[^\w\u4e00-\u9fff]", "", snippet)
    if not snippet:
        return ""
    return f"hardcoded_{abs(hash(text)) % 100000}_{snippet[:20]}"


def diff_with_existing_locales(
    report: ScanReport, source_locale: str = "zh-CN"
) -> Dict[str, List[str]]:
    """
    对比硬编码字符串与现有 locale JSON 中的 value，返回未收录的字符串。

    返回 {module: [unmapped_strings]}
    """
    unmapped: Dict[str, List[str]] = defaultdict(list)
    # 收集所有已存在 locale 中的 value 集合
    existing_values: Set[str] = set()
    for module_dir in FRONTEND_MODULES.iterdir():
        if not module_dir.is_dir():
            continue
        locale_dir = module_dir / "locales" / source_locale
        if not locale_dir.exists():
            continue
        for fpath in locale_dir.glob("*.json"):
            try:
                data = json.loads(fpath.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            for v in _walk_values(data):
                existing_values.add(v)

    for s in report.strings:
        if s.text not in existing_values:
            unmapped[s.module].append(s.text)

    return unmapped


def _walk_values(obj) -> List[str]:
    """递归提取 dict 中所有 string value"""
    result: List[str] = []
    if isinstance(obj, dict):
        for v in obj.values():
            result.extend(_walk_values(v))
    elif isinstance(obj, list):
        for v in obj:
            result.extend(_walk_values(v))
    elif isinstance(obj, str):
        result.append(obj)
    return result


def print_diff_report(unmapped: Dict[str, List[str]]) -> None:
    """打印与现有 locale 的差异"""
    print()
    print("=" * 78)
    print(" 与现有 locale (zh-CN) 的差异")
    print("=" * 78)
    total = sum(len(v) for v in unmapped.values())
    print(f"  未收录的硬编码字符串总数: {total}")
    if not unmapped:
        print("  [OK] 所有硬编码字符串都已在 locale 中。")
        return
    for module, strings in sorted(unmapped.items(), key=lambda x: -len(x[1])):
        unique = sorted(set(strings))
        print(f"\n  [{module}] 未收录 {len(unique)} 个:")
        for s in unique[:10]:
            print(f"    - {s}")
        if len(unique) > 10:
            print(f"    ... 共 {len(unique)} 个，仅显示前 10 个")
    print("=" * 78)


def write_template_files(
    template: Dict[str, Dict[str, str]], target_dir: Path
) -> None:
    """把翻译模板写入 JSON 文件"""
    for locale, modules in template.items():
        for module, kv in modules.items():
            file_dir = target_dir / locale
            file_dir.mkdir(parents=True, exist_ok=True)
            file_path = file_dir / f"{module.replace('/', '_')}.json"
            # 合并写入（如果已存在则只追加新 key）
            existing: Dict[str, str] = {}
            if file_path.exists():
                try:
                    existing = json.loads(file_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    existing = {}
            existing.update(kv)
            file_path.write_text(
                json.dumps(existing, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"  [INFO] 模板已写入: {file_path.relative_to(REPO_ROOT)}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="扫描前端模块中的硬编码中文字符串",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--module", help="只扫描指定模块（如 ontology / workspace）", default=None
    )
    parser.add_argument(
        "--output", help="JSON 报告输出路径", default="i18n_scan_report.json"
    )
    parser.add_argument(
        "--emit-template", action="store_true", help="额外生成 i18n 翻译模板"
    )
    parser.add_argument(
        "--include-tests", action="store_true", help="包含 .test.tsx 文件"
    )
    parser.add_argument(
        "--target-locale",
        default="en-US",
        help="翻译模板的目标语言（默认 en-US）",
    )
    parser.add_argument(
        "--diff-existing",
        action="store_true",
        help="对比扫描结果与现有 locale JSON（zh-CN），输出未收录的硬编码",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="列出所有硬编码字符串（详细）",
    )
    args = parser.parse_args()

    print(f"[INFO] 仓库根: {REPO_ROOT}")
    print(f"[INFO] 扫描目录: {FRONTEND_MODULES}")
    if args.module:
        print(f"[INFO] 仅扫描模块: {args.module}")
    print()

    report = scan_modules(
        target_module=args.module, include_tests=args.include_tests
    )

    print_console_report(report, show_list=args.list)

    output_path = Path(args.output)
    if not output_path.is_absolute():
        # Windows 兼容：若 cwd 下写不进则降级到 repo 根
        try:
            output_path = (Path.cwd() / output_path).resolve()
        except OSError:
            output_path = REPO_ROOT / output_path.name
    try:
        write_json_report(report, output_path)
    except OSError as e:
        # 降级：写到 repo 根
        fallback = REPO_ROOT / output_path.name
        print(f"  [WARN] 无法写入 {output_path}: {e}, 降级到 {fallback}")
        write_json_report(report, fallback)

    if args.diff_existing:
        unmapped = diff_with_existing_locales(report, source_locale="zh-CN")
        print_diff_report(unmapped)
        # 把 diff 结果也写入 JSON
        diff_path = output_path.with_name(
            output_path.stem + "_unmapped" + output_path.suffix
        )
        try:
            diff_path.write_text(
                json.dumps(
                    {m: sorted(set(s)) for m, s in unmapped.items()},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            print(f"  [INFO] 未收录字符串已写入: {diff_path}")
        except OSError as e:
            print(f"  [WARN] 无法写入 diff: {e}", file=sys.stderr)

    if args.emit_template:
        print()
        print("=" * 78)
        print(" 生成 i18n 翻译模板")
        print("=" * 78)
        template = emit_translation_template(
            report, target_locale=args.target_locale
        )
        template_dir = (
            FRONTEND_MODULES
            / (args.module or "_generated")
            / "locales"
        )
        # 写入到 frontend/src/modules/{module}/locales/{locale}/{ns}.json
        for locale, modules in template.items():
            for module, kv in modules.items():
                ns = module.split("/")[-1]
                actual_module = module.split("/")[0] if "/" in module else module
                # 若指定了 --module 则使用它
                if args.module:
                    actual_module = args.module
                target = (
                    FRONTEND_MODULES
                    / actual_module
                    / "locales"
                    / locale
                    / f"{ns}.json"
                )
                target.parent.mkdir(parents=True, exist_ok=True)
                existing: Dict[str, str] = {}
                if target.exists():
                    try:
                        existing = json.loads(target.read_text(encoding="utf-8"))
                    except json.JSONDecodeError:
                        existing = {}
                # 只添加新 key
                added = 0
                for k, v in kv.items():
                    if k not in existing:
                        existing[k] = v
                        added += 1
                if added > 0:
                    target.write_text(
                        json.dumps(existing, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    print(
                        f"  [INFO] {target.relative_to(REPO_ROOT)} (+{added} keys)"
                    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
