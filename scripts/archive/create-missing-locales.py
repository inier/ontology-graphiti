import os
import json
from pathlib import Path

src_dir = Path('apps/web/src/modules')

for module_dir in src_dir.iterdir():
    if module_dir.is_dir():
        zh_locale = module_dir / 'locales' / 'zh-CN'
        ja_locale = module_dir / 'locales' / 'ja-JP'
        
        if zh_locale.is_dir():
            ja_locale.mkdir(parents=True, exist_ok=True)
            
            for json_file in zh_locale.glob('*.json'):
                ja_file = ja_locale / json_file.name
                if not ja_file.exists():
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    with open(ja_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    
                    print(f'创建: {ja_file.relative_to(src_dir.parent.parent)}')
                else:
                    print(f'已存在: {ja_file.relative_to(src_dir.parent.parent)}')

print('\n所有缺失文件已创建完成！')
