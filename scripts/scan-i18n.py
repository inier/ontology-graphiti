#!/usr/bin/env python3
import os
import re
import json
from pathlib import Path

CHINESE_PATTERN = re.compile(r"['\"]([\u4e00-\u9fff]+)['\"]")
TSX_FILE_PATTERN = re.compile(r'\.tsx?$')

def scan_file(filepath: Path) -> list:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        matches = CHINESE_PATTERN.findall(content)
        results = []
        for match in matches:
            text = match.strip()
            if len(text) >= 1 and not text.startswith('t(') and not text.startswith('i18n'):
                results.append(text)
        return results
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return []

def generate_key(text: str) -> str:
    key = re.sub(r'[\u4e00-\u9fff\s，。、；：！？（）《》【】\-]+', '_', text.strip())
    key = re.sub(r'_+', '_', key).strip('_')
    if len(key) > 50:
        key = key[:50]
    return key

def main():
    base_dir = Path('apps/web/src/modules/ontology')
    print(f"Base dir: {base_dir}")
    print(f"Exists: {base_dir.exists()}")
    
    all_files = list(base_dir.rglob('*'))
    print(f"Total files found: {len(all_files)}")
    
    tsx_files = []
    for f in all_files:
        if f.is_file() and (f.suffix == '.tsx' or f.suffix == '.ts'):
            tsx_files.append(f)
    print(f"TSX files found: {len(tsx_files)}")
    for f in tsx_files[:5]:
        print(f"  {f.relative_to(base_dir)}")
    
    all_chinese = {}
    
    for filepath in tsx_files:
        chinese_texts = scan_file(filepath)
        if chinese_texts:
            rel_path = filepath.relative_to(base_dir)
            print(f"Found {len(chinese_texts)} Chinese strings in {rel_path}")
            for text in chinese_texts:
                if text not in all_chinese:
                    all_chinese[text] = {
                        'files': [],
                        'suggested_key': generate_key(text)
                    }
                if str(rel_path) not in all_chinese[text]['files']:
                    all_chinese[text]['files'].append(str(rel_path))
    
    print(f"\nTotal Chinese strings found: {len(all_chinese)}")
    print("\n" + "="*80)
    
    report = {
        'total_strings': len(all_chinese),
        'strings': []
    }
    
    for text, info in sorted(all_chinese.items(), key=lambda x: len(x[0])):
        print(f"\nText: '{text}'")
        print(f"  Files: {', '.join(info['files'])}")
        print(f"  Suggested key: {info['suggested_key']}")
        
        report['strings'].append({
            'text': text,
            'files': info['files'],
            'suggested_key': info['suggested_key']
        })
    
    output_file = Path('scripts/i18n-scan-report.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"\nReport saved to {output_file}")
    
    zh_template = {}
    en_template = {}
    
    for text, info in sorted(all_chinese.items(), key=lambda x: x[1]['suggested_key']):
        zh_template[info['suggested_key']] = text
        en_template[info['suggested_key']] = text
    
    zh_output = Path('scripts/i18n-zh-template.json')
    en_output = Path('scripts/i18n-en-template.json')
    
    with open(zh_output, 'w', encoding='utf-8') as f:
        json.dump({'untranslated': zh_template}, f, ensure_ascii=False, indent=2)
    
    with open(en_output, 'w', encoding='utf-8') as f:
        json.dump({'untranslated': en_template}, f, ensure_ascii=False, indent=2)
    
    print(f"Chinese template saved to {zh_output}")
    print(f"English template saved to {en_output}")

if __name__ == '__main__':
    main()