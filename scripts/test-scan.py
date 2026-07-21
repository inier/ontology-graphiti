#!/usr/bin/env python3
import re
from pathlib import Path

filepath = Path('apps/web/src/modules/ontology/components/BranchList.tsx')
content = filepath.read_text(encoding='utf-8')

pattern = re.compile(r"['\"]([\u4e00-\u9fff]+)['\"]")
matches = pattern.findall(content)
print(f"File: {filepath}")
print(f"Matches found: {len(matches)}")
if matches:
    print(f"First 10 matches: {matches[:10]}")
else:
    print("No matches found")
    
sample = content[:500]
print(f"\nSample content: {sample}")