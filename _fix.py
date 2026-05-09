src = r'e:\DEMO\AI\ontology-graphiti\odap\biz\ontology\storage\sqlite_ingest_storage.py'
dst = src + '.fixed'

with open(src, 'rb') as f:
    raw = f.read()

try:
    content = raw.decode('utf-8')
    ok = True
except:
    try:
        content = raw.decode('utf-16')
        ok = True
    except:
        content = raw.decode('latin-1')
        ok = False

replaced = content.count('conn = sqlite3.connect(self.db_path)')
if replaced > 0:
    content = content.replace('conn = sqlite3.connect(self.db_path)', 'conn = self._get_conn()')

with open(dst, 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)

import os
os.replace(dst, src)
print(f"Fixed. Encoding={'ok' if ok else 'latin-1'}, Replaced={replaced}")

import py_compile
py_compile.compile(src, doraise=True)
print("Compile OK")