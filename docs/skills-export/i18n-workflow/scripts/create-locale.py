#!/usr/bin/env python3
"""
创建新语言 locale 文件脚本
基于 zh-CN 创建新语言的 locale 文件
支持多模块创建
"""

import os
import json
import argparse
from pathlib import Path


def create_module_locale(module_dir, lang):
    locales_dir = module_dir / 'locales'
    zh_dir = locales_dir / 'zh-CN'
    
    if not zh_dir.exists():
        return 0
    
    new_lang_dir = locales_dir / lang
    new_lang_dir.mkdir(parents=True, exist_ok=True)
    
    created_files = []
    
    for zh_file in zh_dir.iterdir():
        if zh_file.is_file() and zh_file.suffix == '.json':
            with open(zh_file, 'r', encoding='utf-8') as f:
                zh_data = json.load(f)
            
            new_data = {}
            for key, value in zh_data.items():
                new_data[key] = value
            
            new_file = new_lang_dir / zh_file.name
            with open(new_file, 'w', encoding='utf-8') as f:
                json.dump(new_data, f, ensure_ascii=False, indent=2)
            
            created_files.append(new_file)
    
    return len(created_files)


def main():
    parser = argparse.ArgumentParser(description='创建新语言 locale 文件')
    parser.add_argument('--lang', required=True, help='语言代码（如 ja-JP, ko-KR）')
    parser.add_argument('--name', required=True, help='语言名称（如 日本語, 한국어）')
    parser.add_argument('--modules', default='apps/web/src/modules', help='modules 目录路径')
    args = parser.parse_args()
    
    modules_dir = Path(args.modules)
    
    if not modules_dir.exists():
        print(f'错误: modules 目录不存在: {modules_dir}')
        return
    
    total_files = 0
    processed_modules = 0
    
    print(f'开始为 {args.lang} 创建 locale 文件...')
    
    for module_dir in modules_dir.iterdir():
        if module_dir.is_dir():
            locales_dir = module_dir / 'locales'
            zh_dir = locales_dir / 'zh-CN'
            
            if zh_dir.exists():
                count = create_module_locale(module_dir, args.lang)
                if count > 0:
                    print(f'  ✅ {module_dir.name}: 创建 {count} 个文件')
                    total_files += count
                    processed_modules += 1
    
    print(f'\n{"="*50}')
    print(f'✅ 已为 {args.lang} 创建 locale 文件:')
    print(f'   处理模块数: {processed_modules}')
    print(f'   创建文件数: {total_files}')
    print(f'\n📋 下一步操作:')
    print(f'1. 在 i18nStore.ts 中添加 {args.lang} 到 Locale 类型')
    print(f'2. 在 LanguageSwitcher 组件中添加 "{args.name}" 选项')
    print(f'3. 运行 python .trae/skills/i18n-workflow/scripts/sync-locales.py --fix 验证完整性')
    print(f'4. 使用 translate-locale-from-cn.py 批量翻译中文内容')


if __name__ == '__main__':
    main()
