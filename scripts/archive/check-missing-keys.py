import os
import re
import json
from pathlib import Path

src_dir = Path('apps/web/src/modules')

dot_pattern_keys = set()
chinese_keys = set()
locale_keys = {}

for root, dirs, files in os.walk(src_dir):
    for file in files:
        if file.endswith('.ts') or file.endswith('.tsx'):
            filepath = Path(root) / file
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                    matches = re.findall(r't\(\s*[\'"](.+?)[\'"]', content)
                    for match in matches:
                        if re.match(r'^[a-z][a-zA-Z0-9_]*(\.[a-z][a-zA-Z0-9_]*)+$', match):
                            dot_pattern_keys.add(match)
                        elif '\u4e00' <= match <= '\u9fff' or match == 'OK' or match == 'ID':
                            chinese_keys.add(match)
            except:
                pass
        
        if 'locales' in root and file.endswith('.json'):
            locale_path = Path(root)
            lang = locale_path.name
            
            if lang not in locale_keys:
                locale_keys[lang] = set()
            
            filepath = Path(root) / file
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    locale_keys[lang].update(data.keys())
            except:
                pass

print(f'点分隔 key 数: {len(dot_pattern_keys)}')
print(f'中文 key 数: {len(chinese_keys)}')

missing_dot = {}
for lang, keys in locale_keys.items():
    missing = dot_pattern_keys - keys
    missing_dot[lang] = sorted(missing)

print('\n=== 点分隔格式缺失的 key ===')
for lang, missing in missing_dot.items():
    print(f'\n{lang} 缺失 {len(missing)} 个点分隔 key:')
    for key in missing[:40]:
        print(f'  - {key}')
    if len(missing) > 40:
        print(f'  ... 还有 {len(missing)-40} 个')

missing_cn = {}
for lang, keys in locale_keys.items():
    missing = chinese_keys - keys
    missing_cn[lang] = sorted(missing)

print('\n=== 中文格式缺失的 key ===')
for lang, missing in missing_cn.items():
    print(f'\n{lang} 缺失 {len(missing)} 个中文 key:')
    for key in missing[:20]:
        print(f'  - {key}')
    if len(missing) > 20:
        print(f'  ... 还有 {len(missing)-20} 个')

if 'zh-CN' in missing_dot and missing_dot['zh-CN']:
    print(f'\n{"="*50}')
    print('需要添加到 zh-CN 的点分隔 key（按模块分组）:')
    
    module_keys = {}
    for key in missing_dot['zh-CN']:
        parts = key.split('.')
        module_name = parts[0] if parts else 'unknown'
        if module_name not in module_keys:
            module_keys[module_name] = []
        module_keys[module_name].append(key)
    
    for module, keys in sorted(module_keys.items()):
        print(f'\n{module}/:')
        for key in keys:
            print(f'  "{key}": "",')
