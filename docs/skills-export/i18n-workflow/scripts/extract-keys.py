#!/usr/bin/env python3
"""
国际化 key 提取脚本
从 TypeScript/TSX 文件中提取所有 t('中文') 调用的 key
"""

import os
import re
import json
import argparse
from pathlib import Path


def extract_translation_keys(root_dir: str) -> list:
    """从代码中提取所有 t('中文') 调用的 key"""
    keys = set()
    
    # 匹配 t('中文') 和 t("中文") 模式
    patterns = [
        re.compile(r"t\('([^']+)'\)"),
        re.compile(r't\("([^"]+)"\)'),
    ]
    
    # 匹配 t('中文', { ... }) 模式
    patterns_with_options = [
        re.compile(r"t\('([^']+)',\s*\{"),
        re.compile(r't\("([^"]+)",\s*\{'),
    ]
    
    for path in Path(root_dir).rglob('*.tsx'):
        if 'node_modules' in str(path):
            continue
        
        try:
            content = path.read_text(encoding='utf-8')
        except Exception:
            continue
        
        for pattern in patterns:
            for match in pattern.finditer(content):
                key = match.group(1).strip()
                if key and key != '':
                    keys.add(key)
        
        for pattern in patterns_with_options:
            for match in pattern.finditer(content):
                key = match.group(1).strip()
                if key and key != '':
                    keys.add(key)
    
    return sorted(list(keys))


def load_existing_keys(locale_file: str) -> set:
    """加载已有的翻译 key"""
    if not os.path.exists(locale_file):
        return set()
    
    with open(locale_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return set(data.keys())


def main():
    parser = argparse.ArgumentParser(description='提取国际化翻译 key')
    parser.add_argument('--src', default='apps/web/src', help='源代码目录')
    parser.add_argument('--locale', default='apps/web/src/modules/shared/locales/zh-CN/common.json', help='现有 locale 文件路径')
    parser.add_argument('--output', default=None, help='输出文件路径')
    parser.add_argument('--missing', action='store_true', help='只输出缺失的 key')
    args = parser.parse_args()
    
    print(f'正在从 {args.src} 提取翻译 key...')
    code_keys = extract_translation_keys(args.src)
    print(f'从代码中提取到 {len(code_keys)} 个唯一 key')
    
    existing_keys = load_existing_keys(args.locale)
    print(f'现有 locale 文件中有 {len(existing_keys)} 个 key')
    
    if args.missing:
        missing = sorted(set(code_keys) - existing_keys)
        print(f'\n缺失的 key ({len(missing)} 个):')
        for key in missing:
            print(f'  "{key}": "{key}",')
        
        if args.output:
            missing_dict = {key: key for key in missing}
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(missing_dict, f, ensure_ascii=False, indent=2)
            print(f'\n已保存到 {args.output}')
    else:
        print(f'\n所有提取的 key ({len(code_keys)} 个):')
        for key in code_keys:
            print(f'  "{key}"')
        
        if args.output:
            all_dict = {key: key for key in code_keys}
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(all_dict, f, ensure_ascii=False, indent=2)
            print(f'\n已保存到 {args.output}')


if __name__ == '__main__':
    main()
