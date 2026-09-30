"""核对：确认只有 llm.model 被修改，其余配置项（尤其敏感项）未被误动。"""
import sqlite3

DB = "/app/data/config.db"
c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row

print("=" * 78)
print("全部 config_items（按 updated_at 倒序）")
print("=" * 78)
for r in c.execute(
    "SELECT key, value, is_sensitive, updated_at, updated_by FROM config_items "
    "ORDER BY updated_at DESC"
).fetchall():
    d = dict(r)
    v = d["value"]
    if d["is_sensitive"] and v:
        v = f"<encrypted len={len(v)}>"
    elif v and len(str(v)) > 46:
        v = str(v)[:46] + "..."
    print(f"  {d['key']:26s} sens={d['is_sensitive']} {str(v):52s} {d['updated_at']} by={d['updated_by']}")

print()
print("=" * 78)
print("今日(2026-09-28)被修改的项")
print("=" * 78)
rows = c.execute(
    "SELECT key, value, updated_by FROM config_items WHERE updated_at LIKE '2026-09-28%'"
).fetchall()
for r in rows:
    print(f"  {r['key']} = {r['value']!r} by={r['updated_by']}")
if not rows:
    print("  (无)")

print()
print("=" * 78)
print("敏感项行数校验（应为 3：llm.api_key / graph_db.password / jwt.secret 等）")
print("=" * 78)
for r in c.execute(
    "SELECT key, length(value) AS n, updated_at FROM config_items WHERE is_sensitive=1"
).fetchall():
    print(f"  {r['key']:26s} len={r['n']:4d}  {r['updated_at']}")
