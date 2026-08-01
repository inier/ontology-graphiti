#!/usr/bin/env python3
"""
同步 locale 文件脚本
比较各语言 locale 文件，找出缺失的 key
支持多模块同步
"""

import os
import json
import argparse
from pathlib import Path


def sync_module_locales(module_dir, fix=False):
    locales_dir = module_dir / 'locales'
    
    if not locales_dir.exists():
        return 0, 0, 0
    
    lang_dirs = []
    for item in locales_dir.iterdir():
        if item.is_dir():
            lang_dirs.append(item)
    
    if not lang_dirs:
        return 0, 0, 0
    
    json_files = []
    for item in (locales_dir / 'zh-CN').iterdir():
        if item.is_file() and item.suffix == '.json':
            json_files.append(item.name)
    
    if not json_files:
        return 0, 0, 0
    
    module_name = module_dir.name
    total_missing = 0
    total_fixed = 0
    total_keys = 0
    
    for json_file in json_files:
        all_keys = set()
        locale_data = {}
        
        for lang_dir in lang_dirs:
            lang_file = lang_dir / json_file
            if lang_file.exists():
                with open(lang_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    locale_data[lang_dir.name] = data
                    all_keys.update(data.keys())
            else:
                locale_data[lang_dir.name] = {}
        
        total_keys += len(all_keys)
        
        for lang, data in locale_data.items():
            missing = all_keys - set(data.keys())
            if missing:
                total_missing += len(missing)
                print(f'  {lang}/{json_file}: 缺失 {len(missing)} 个 key')
                
                if fix:
                    lang_file = locales_dir / lang / json_file
                    lang_dir = locales_dir / lang
                    lang_dir.mkdir(parents=True, exist_ok=True)
                    
                    zh_file = locales_dir / 'zh-CN' / json_file
                    with open(zh_file, 'r', encoding='utf-8') as f:
                        zh_data = json.load(f)
                    
                    for key in sorted(missing):
                        data[key] = zh_data.get(key, key)
                    
                    with open(lang_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    
                    total_fixed += len(missing)
    
    return total_keys, total_missing, total_fixed


def main():
    parser = argparse.ArgumentParser(description='同步 locale 文件')
    parser.add_argument('--modules', default='apps/web/src/modules', help='modules 目录路径')
    parser.add_argument('--fix', action='store_true', help='自动补充缺失的 key（使用中文作为默认值）')
    args = parser.parse_args()
    
    modules_dir = Path(args.modules)
    
    if not modules_dir.exists():
        print(f'错误: modules 目录不存在: {modules_dir}')
        return
    
    total_keys = 0
    total_missing = 0
    total_fixed = 0
    
    print('开始同步所有模块的 locale 文件...')
    
    for module_dir in modules_dir.iterdir():
        if module_dir.is_dir():
            keys, missing, fixed = sync_module_locales(module_dir, args.fix)
            if keys > 0:
                print(f'\n模块: {module_dir.name}')
                print(f'  总 key 数: {keys}')
                if missing > 0:
                    print(f'  缺失 key 数: {missing}')
                    if fixed > 0:
                        print(f'  已修复: {fixed}')
                else:
                    print(f'  ✅ 无缺失')
                total_keys += keys
                total_missing += missing
                total_fixed += fixed
    
    print(f'\n{"="*50}')
    print(f'总计: {total_keys} 个 key')
    if total_missing > 0:
        print(f'缺失: {total_missing} 个 key')
        if total_fixed > 0:
            print(f'已修复: {total_fixed} 个 key')
    else:
        print('✅ 所有 locale 文件已同步，无缺失 key')


if __name__ == '__main__':
    main()
